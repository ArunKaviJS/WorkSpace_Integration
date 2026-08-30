# CORE — WorkSpace_Integration: Complete Backend Architecture

> Authoritative reference covering the **end-to-end backend architecture** of the
> "AI Command Center". Written from the actual source so that an engineer or a
> diagram tool (draw.io) can reconstruct **every** flow without reading the code.
>
> The backend is a set of two independent LLM-driven **agents** (ClickUp and
> Bitbucket) that share one cloud LLM brain, one web server, and talk to two
> external SaaS REST APIs when their agents decide to call a tool.

---

## 1. System Overview

### 1.1 What this system does

The system is a single web application ("AI Command Center") that lets a team
lead manage two separate engineering workflows through one React UI plus two
natural-language AI agents:

- **ClickUp path** — orchestrate project-management tasks: navigate the
  workspace hierarchy, create/update/classify/delete tasks, post comments,
  set tags/dependencies, time tracking, docs, chat, and render team dashboards.
- **Bitbucket path** — orchestrate source control: manage repositories,
  branches, pull requests (review/approve/decline/merge), pipelines
  (run/inspect/analyze failures), deployments/environments, webhooks and
  application properties.

A user either clicks dashboards/forms (which hit **direct REST endpoints**) or
types a natural-language message (which hits an **agent chat endpoint**). The
agent interprets the message, and — using one shared LLM — repeatedly decides
which **tool** to invoke until it can produce a plain-text answer. Every tool
is deterministic Python that makes a single REST call to ClickUp or Bitbucket.

### 1.2 Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18, ReactDOM, Vite 6 (`@vitejs/plugin-react`) — dev proxy on port 5173 |
| Backend framework | FastAPI + Uvicorn, on port 8000 |
| HTTP client | `requests` (both external APIs, 30s timeout) |
| Config / secrets | `python-dotenv` loading a local `.env` |
| LLM | AWS **Amazon Bedrock** → `bedrock-runtime.invoke_model` (Anthropic Messages format) |
| AWS SDK | `boto3`, `botocore` |
| Model | `global.anthropic.claude-sonnet-4-6` (Claude Sonnet 4.6) |
| Cloud API 1 | **ClickUp REST API** — `https://api.clickup.com/api/v2` (v3 sub-URL for Chat & Docs) |
| Cloud API 2 | **Bitbucket Cloud REST API** — `https://api.bitbucket.org/2.0` |
| Persistence | None (in-memory only) — no database, no vector store |

---

## 2. Entry Points

There are **two entry surfaces** into the backend:

### 2.1 Web (primary) — FastAPI

`backend/server.py` builds a single `FastAPI` app that mounts two route groups:

```python
app = FastAPI(title="ClickUp AI Agent API")
app.add_middleware(CORSMiddleware, allow_origins=[...], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(bitbucket_router)   # /bitbucket/*
# ClickUp routes are defined directly on `app` under /api/*
```

The frontend calls the backend **only** through the Vite dev proxy
(`frontend/vite.config.js`): `/api/*` and `/bitbucket/*` are forwarded to
`http://localhost:8000`.

**Request schemas & auth flow:**

- Auth is **API-token based per external service**, provided through the
  backend's own `.env`; the frontend does **not** authenticate. Credentials are
  read once at import time by `config/settings.py`.
  - ClickUp: header `Authorization: <CLICKUP_API_TOKEN>`
  - Bitbucket: HTTP Basic auth with the credential pair `(BITBUCKET_EMAIL, BITBUCKET_API_TOKEN)`
  - LLM: AWS credentials from `AWS_ACCESS_KEY` / `AWS_SECRET_KEY` / `REGION`
- There is **no session/auth middleware**, no per-user login. All state is
  in-memory server-side (see §8).

**Web routes (ClickUp)** — defined directly on `app`:

| Method | Route | Handler purpose |
|---|---|---|
| GET | `/api/health` | liveness — returns `{"status": "ok"}` |
| GET | `/api/dashboard` | walk the whole ClickUp workspace → classified tasks → `build_dashboard` → adds `report_text` |
| POST | `/api/chat` | body `{"message": str}` → `orch.run(message)` → returns `{"reply", "tool_calls"}` |
| POST | `/api/chat/reset` | `orch.reset()` → `{"status": "reset"}` |

**Web routes (Bitbucket)** — mounted `APIRouter(prefix="/bitbucket")`, ~49
endpoints. Grouped (full list in §6 / §10): chat, dashboard, commits,
pending-prs, human-gated PR actions (approve/decline/merge), repo
create/delete, branch create/permission, collaborator invite, and the
`bitbucket_*` REST-tool routes (workspaces, repos, files, commits, branches,
PRs, pipelines + analyze, deployments, environments). See
`backend/bitbucket/bitbucket_routes.py`.

### 2.2 CLI (secondary) — ClickUp only

`backend/main.py` is an interactive REPL for the ClickUp agent only:

```
python main.py
```
- Prompts `You:` in a loop; `exit` quits, `reset` calls `agent.reset()`.
- Each non-command line is sent to `Orchestrator().run(...)` (shared singleton).

Session/context: the CLI creates **one** `Orchestrator` for the process; the Web
`server.py` also creates **one** global `Orchestrator()`. Both keep call
history in memory (see §8).

---

## 3. Agent Architecture

### 3.1 Agent inventory

| Agent | Class | File path | External system | Tool registry | Enabled via |
|---|---|---|---|---|---|
| **ClickUp Orchestrator** | `Orchestrator` | `backend/agent/orchestrator.py` | ClickUp | `TOOL_REGISTRY` / `TOOL_MAP` (`backend/tools/__init__.py`) | `/api/chat`, CLI `main.py` |
| **Bitbucket Agent** | `BitbucketAgent` | `backend/bitbucket/bitbucket_agent.py` | Bitbucket | `BITBUCKET_TOOL_REGISTRY` / `BITBUCKET_TOOL_MAP` (`backend/bitbucket/bitbucket_tools.py`) | `/bitbucket/chat` |

There is **no multi-agent planner** and **no router/classifier agent**. The two
agents are independent, and they are selected **not by any LLM routing logic**
but by **which HTTP endpoint the user called**:

- A message posted to `/api/chat` → dispatched to the ClickUp `Orchestrator`.
- A message posted to `/bitbucket/chat` → dispatched to the `BitbucketAgent`.

Neither agent can hand off to the other. Inside a single agent, the **same** LLM
both decides which tool to call and produces the final reply; there is no
separate sub-agent dispatch.

### 3.2 The shared LLM brain

Both agents use **one and only one** `BedrockLLM` client, created lazily by
`get_llm()` in `backend/agent/llm.py`:

```python
def get_llm() -> BedrockLLM: ...   # module-level singleton `_llm`
```

`BedrockLLM`:
- `__init__(self) -> None` — builds `boto3.client("bedrock-runtime", region_name=AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_KEY)` and stores `self.model_id`.
- `chat(self, messages, system="", max_tokens=4096, temperature=0.0) -> str`
  — posts an Anthropic Messages request (`anthropic_version=bedrock-2023-05-31`)
  to `invoke_model(modelId=self.model_id, body=json, contentType="application/json", accept="application/json")`, returning `result["content"][0]["text"]`.
- `complete(self, prompt, system="", **kwargs) -> str`
  — convenience: single user turn.

Signatures shown for each agent's role:

| Agent | Role | When invoked | What triggers it | What it returns |
|---|---|---|---|---|
| `Orchestrator` | Turn a natural-language ClickUp request into a chain of tool calls, then a final answer. | HTTPS POST `/api/chat` or CLI input. | User message body arrives on the route. | `str` final reply; also populates `self.tool_calls_log` (list of dicts) and `self.history`. |
| `BitbucketAgent` | Turn a natural-language Bitbucket request into a chain of tool calls, then a final answer. | HTTPS POST `/bitbucket/chat`. | User message body arrives on the route. | `str` final reply; also populates `self.tool_calls_log` and `self.history`. |

---

## 4. The Observe → Think → Act Loop

Both agents run the **same** bounded loop, capped at `MAX_ITERATIONS = 12`
(`agent/orchestrator.py:37`, `bitbucket/bitbucket_agent.py:25`). The loop lives
inside `run()`.

### 4.1 Shared step definitions

- **Observe** — reads:
  - the incoming `user_message`,
  - the agent's own accumulated `self.history` (a `list[{"role": "user"|"assistant", "content": str}]`),
  - the agent's `system` prompt (which embeds the full tool catalogue),
  - the resolved date context injected by `resolve_relative_dates()` / `ist_now()`.
- **Think** — `self.llm.chat(messages=self.history, system=self.system)` with
  `temperature=0`, `max_tokens=4096`. The model returns either a tool-call JSON
  block or a plain-text final answer. There is **no explicit chain-of-thought**
  prompt; reasoning is implicit in a single completion per iteration.
- **Act** —
  - If the text contains a tool-call block: parse it, look it up in the tool
    map, `_dispatch` it (see §4.3), and feed the result back as a new turn
    (loop continues).
  - Otherwise: treat the text as the **final answer**, return it (loop ends).

### 4.2 The exact per-iteration sequence (both agents)

```
1.  user_message = resolve_relative_dates(user_message)     # deterministic date rewrite
2.  self.history.append({"role":"user", "content": user_message})
3.  for iteration in range(MAX_ITERATIONS=12):
4.      assistant_text = self.llm.chat(messages=self.history, system=self.system)
5.      tool_call = _extract_tool_call(assistant_text)
6.      if tool_call is None:                                # final answer
7.          self.history.append({"role":"assistant","content":assistant_text})
8.          return assistant_text
9.      tool_name  = tool_call["tool"]
10.     tool_args  = tool_call.get("args", {})
11.     result     = _dispatch(tool_name, tool_args)
12.     result_text= json.dumps(result, default=str, indent=2)
13.     self._tool_calls_log.append({"iteration","tool","args","result_preview":result_text[:300]})
14.     self.history.append({"role":"assistant","content":assistant_text})
15.     self.history.append({"role":"user","content":f"[TOOL RESULT: {tool_name}]\n{result_text}"})
16.     # repeat → back to step 4
17. # (if the for-loop exhausts) → append & return the fallback message (§9)
```

### 4.3 Tool-call extraction and dispatch

`_extract_tool_call(text) -> dict | None` tries, in order, two regexes
(auto-generated in a module constant):
1. `<code>```json {...}```</code>` — `re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)`
2. a bare object — `re.compile(r"^\s*(\{.*?\})\s*$", re.DOTALL)`

It `json.loads` the captured group; if the object has a `"tool"` key it is
returned, else it keeps scanning. `None` means "final answer".

`_dispatch(tool_name, args)`:
- ClickUp (`agent/orchestrator.py:96`): `TOOL_MAP.get(tool_name)`; if missing
  returns `{"error": f"Unknown tool: {tool_name}"}`; otherwise
  `entry["fn"](**args)`; any exception returns `{"error": str(exc)}`.
- Bitbucket (`bitbucket/bitbucket_agent.py:33`): same, but catches
  `BitbucketError` explicitly and returns a structured error
  `{"error": True, "message": str(exc), "status_code": exc.status_code}`; other
  exceptions return `{"error": True, "message": str(exc), "status_code": 0}`.

### 4.4 Termination conditions

- **Happy path**: the LLM emits plain text with no parseable tool call → taken
  as the final answer.
- **Exhaustion**: after 12 iterations the fallback string is appended and
  returned: *"I reached the maximum number of steps without completing your
  request. Please try rephrasing."*
- Note: because `run()` **starts a new assistant turn with a fresh look** at the
  conversation each call, the loop naturally keeps multi-step work going until
  the model answers in prose.

---

## 5. Tools — Complete Catalog

Tool registry format (both agents): each entry is
`{"name", "fn", "description", "params": [{"name","type","required","default"}]}`.
The registry is rendered into the system prompt as `### name` + description +
`Parameters: <json>`.

> The two ClickUp HTTP helpers: `tools/http.py` centralises
> `request/get/post/put/patch/delete`; the earliest modules
> (`task_tools.py`, `workspace_tools.py`, `comment_tools.py`) define their own
> private `_get/_post/_put/_delete` with identical behaviour
> (base `https://api.clickup.com/api/v2`, `Auth` header, 30s timeout). All
> URLs below are relative to the stated base unless another base is given.
> `V3_URL = https://api.clickup.com/api/v3` is used only by Chat/Docs tools.

### 5.A ClickUp tools (`backend/tools/`)

#### workspace_tools.py — hierarchy navigation

| Tool | Signature | REST call | Returns / notes |
|---|---|---|---|
| `get_authorized_user` | `() -> dict` | `GET /user` | id, username, email, color, profilePicture |
| `get_workspaces` | `() -> list[dict]` | `GET /team` | id, name, color, avatar, member usernames |
| `get_spaces` | `(team_id: str) -> list[dict]` | `GET /team/{team_id}/space?archived=false` | id, name, private, statuses |
| `get_folders` | `(space_id: str) -> list[dict]` | `GET /space/{space_id}/folder?archived=false` | id, name, task_count |
| `get_lists` | `(folder_id: str) -> list[dict]` | `GET /folder/{folder_id}/list?archived=false` | id, name, task_count, status |
| `get_folderless_lists` | `(space_id: str) -> list[dict]` | `GET /space/{space_id}/list?archived=false` | id, name, task_count |
| `get_workspace_members` | `(team_id: str) -> list[dict]` | `GET /team/{team_id}` | id, username, email, role per member |

#### task_tools.py — task CRUD + classification

Shared helper `_fmt_task(t: dict) -> dict` normalises a raw ClickUp task and
**computes intelligence flags in code**: `is_complete` (status in
`{"complete","closed","done","finished"}`), `overdue` (due < now & not complete),
`due_soon_5min` (0 < due-now ≤ 300s). Fields: id, name, status, is_complete,
overdue, due_soon_5min, due_date_epoch (seconds), priority, assignees (usernames),
url, description, tags.

| Tool | Signature | REST call | Returns / notes |
|---|---|---|---|
| `get_tasks` | `(list_id: str, include_closed: bool = True) -> list[dict]` | `GET /list/{list_id}/task?include_closed=…&subtasks=true&page=N` (paginated, 100/page) | formatted task list |
| `get_task` | `(task_id: str) -> dict` | `GET /task/{task_id}` | one formatted task |
| `get_team_tasks` | `(team_id: str, assignee_ids: list[int] | None = None) -> list[dict]` | `GET /team/{team_id}/task?…&assignees[]=<list>` (paginated) | formatted tasks across a workspace |
| `classify_tasks` | `(tasks: list[dict]) -> dict` | none (pure) | `{"completed","pending","overdue","due_soon_5min","total"}` |
| `create_task` | `(list_id: str, name: str, description="", assignee_ids=None, status=None, priority=None, due_date_epoch_ms=None, tags=None, notify_all=False) -> dict` | `POST /list/{list_id}/task` body includes name, description, assignees, status, priority, due_date(+due_date_time), tags, notify_all | formatted created task |
| `update_task_status` | `(task_id: str, new_status: str) -> dict` | `PUT /task/{task_id}` `{"status": new_status}` | formatted updated task |
| `update_task` | `(task_id: str, fields: dict) -> dict` | `PUT /task/{task_id}` body=`fields` | formatted updated task |
| `delete_task` | `(task_id: str) -> dict` | `DELETE /task/{task_id}` | `{"deleted": True, "task_id"}` (prompt-gated only, see §9) |
| `get_list_custom_fields` | `(list_id: str) -> list[dict]` | `GET /list/{list_id}/field` | field id/name/type/option ids |
| `set_custom_field` | `(task_id: str, field_id: str, value: Any) -> dict` | `POST /task/{task_id}/field/{field_id}` `{"value": value}` | raw response |

#### comment_tools.py

| Tool | Signature | REST call | Returns |
|---|---|---|---|
| `get_task_comments` | `(task_id: str) -> list[dict]` | `GET /task/{task_id}/comment` | id, text, author, date per comment |
| `post_task_comment` | `(task_id: str, comment_text: str, notify_all: bool = False) -> dict` | `POST /task/{task_id}/comment` | raw response |

#### dashboard_tools.py — pure aggregation (no API)

| Tool | Signature | Returns |
|---|---|---|
| `build_dashboard` | `(classified: dict, member_map: dict[str,str] | None = None) -> dict` | `{"generated_at","summary","per_developer","upcoming_24h","overdue_tasks","due_soon_5min"}`; computes `due_in_minutes`,`minutes_overdue`,`seconds_remaining` |
| `render_dashboard_text` | `(dashboard: dict) -> str` | human-readable text report |

#### search_tools.py (uses shared `tools/http.get`)

| Tool | Signature | REST calls | Returns |
|---|---|---|---|
| `search_workspace` | `(team_id: str, query: str) -> dict` | `GET /team/{team_id}/task` (client filter), `GET /team/{team_id}/space`, per-space `GET /space/{id}/folder`, `GET /space/{id}/list`, `GET /folder/{id}/list` | `{"query","tasks","spaces","folders","lists"}` (matches up to 50 tasks) |
| `search_tasks_by_type` | `(team_id: str, task_type="task") -> list[dict]` | `GET /team/{team_id}/task?types[]={task_type}` | formatted tasks |
| `search_tasks_by_tag` | `(team_id: str, tags: list[str]) -> list[dict]` | `GET /team/{team_id}/task?tags[]=<tags>` | formatted tasks |

#### list_tools.py (uses shared `tools/http` get/post/put)

| Tool | Signature | REST call | Returns |
|---|---|---|---|
| `move_task_to_list` | `(list_id: str, task_id: str) -> dict` | `POST /list/{list_id}/task/{task_id}` | `{"moved","to_list","result"}` |
| `add_task_to_list` | `(list_id: str, task_id: str) -> dict` | `POST /task/{task_id}/list/{list_id}` | raw |
| `create_folder` | `(space_id: str, name: str) -> dict` | `POST /space/{space_id}/folder` | raw |
| `update_folder` | `(folder_id: str, name: str) -> dict` | `PUT /folder/{folder_id}` | raw |
| `get_folder_details` | `(folder_id: str) -> dict` | `GET /folder/{folder_id}` | id, name, contained lists |
| `create_list` | `(name: str, space_id=None, folder_id=None) -> dict` | `POST /folder/{folder_id}/list` XOR `POST /space/{space_id}/list` (exactly one parent) | raw |
| `update_list` | `(list_id: str, fields: dict) -> dict` | `PUT /list/{list_id}` | raw |
| `get_list_details` | `(list_id: str) -> dict` | `GET /list/{list_id}` | id, name, content, statuses, task_count |
| `get_workspace_hierarchy` | `(team_id: str) -> dict` | depth walk: `GET /team/{team_id}/space`, per space `GET /space/{id}/list`, `GET /space/{id}/folder`, per folder `GET /folder/{id}/list` | nested `{"workspace_id","spaces":[{id,name,folders:[{id,name,lists}],lists}]}` |

#### bulk_tools.py (reuses create_task/update_task)

| Tool | Signature | Returns |
|---|---|---|
| `create_bulk_tasks` | `(list_id: str, names: list[str], assignee_ids=None, priority=None, due_date_epoch_ms=None) -> dict` | loops `create_task`; `{"created_count","created","failed"}` |
| `update_bulk_tasks` | `(task_ids: list[str], fields: dict) -> dict` | loops `update_task`; `{"updated_count","updated","failed"}` |

#### tag_tools.py (shared `tools/http` post / delete)

| Tool | Signature | REST call | Returns |
|---|---|---|---|
| `add_tag_to_task` | `(task_id: str, tag_name: str) -> dict` | `POST /task/{task_id}/tag/{tag}` (spaces → %20) | `{"task_id","tag_added"}` |
| `remove_tag_from_task` | `(task_id: str, tag_name: str) -> dict` | `DELETE /task/{task_id}/tag/{tag}` | `{"task_id","tag_removed"}` |

#### relation_tools.py (shared `tools/http` post/put/delete)

| Tool | Signature | REST call | Returns |
|---|---|---|---|
| `add_task_link` | `(task_id: str, linked_task_id: str) -> dict` | `PUT /task/{task_id}/link/{linked_task_id}` | `{"linked":[...]}` |
| `remove_task_link` | `(task_id: str, linked_task_id: str) -> dict` | `DELETE /task/{task_id}/link/{linked_task_id}` | `{"unlinked":[...]}` |
| `add_dependency` | `(task_id: str, depends_on=None, dependency_of=None) -> dict` | `POST /task/{task_id}/dependency` (exactly one direction) | `{"dependency_created":{...}}` |
| `remove_dependency` | `(task_id: str, depends_on=None, dependency_of=None) -> dict` | `DELETE /task/{task_id}/dependency?depends_on=… | ?dependency_of=…` | `{"dependency_removed":{...}}` |

#### attachment_tools.py (shared `tools/http` request, multipart)

| Tool | Signature | REST call | Returns |
|---|---|---|---|
| `attach_file_to_task` | `(task_id: str, file_path: str) -> dict` | `POST /task/{task_id}/attachment` (multipart `file`) | `{"attached","task_id","response"}` |

#### time_tracking_tools.py (shared `tools/http` get/post)

| Tool | Signature | REST call | Returns |
|---|---|---|---|
| `get_task_time_entries` | `(team_id: str, task_id: str) -> list[dict]` | `GET /team/{team_id}/time_entries?task_id=…` | id, task_id, duration_ms, start, end, user |
| `get_time_entries_summary` | `(team_id: str, task_ids: list[str]) -> dict` | per id `GET /team/{team_id}/time_entries` | `{"total_ms","total_hours","per_task_ms"}` |
| `start_time_tracking` | `(team_id: str, task_id: str) -> dict` | `POST /team/{team_id}/time_entries/start` `{"tid": task_id}` | raw |
| `stop_time_tracking` | `(team_id: str) -> dict` | `POST /team/{team_id}/time_entries/stop` | raw |
| `add_time_entry` | `(team_id: str, task_id: str, start_epoch_ms: int, duration_ms: int) -> dict` | `POST /team/{team_id}/time_entries` `{"tid","start","duration"}` | raw |
| `get_current_time_entry` | `(team_id: str) -> dict | None` | `GET /team/{team_id}/time_entries/current` | task_id, task_name, start, duration_so_far_ms |

#### status_time_tools.py (shared `tools/http` get) — time in status

| Tool | Signature | REST call |
|---|---|---|
| `get_task_time_in_status` | `(task_id: str) -> dict` | `GET /task/{task_id}/metric/time_in_status` |
| `get_list_time_in_status` | `(list_id: str) -> dict` | `GET /list/{list_id}/metric/time_in_status` |

#### member_tools.py (reuses `get_workspace_members`)

| Tool | Signature | Returns |
|---|---|---|
| `find_member_by_name` | `(team_id: str, query: str) -> list[dict]` | members whose username/email contains query |
| `resolve_assignees` | `(team_id: str, names: list[str]) -> dict` | `{"resolved":{name:{id,username}},"unresolved":[names]}` |

#### chat_tools.py (v3, shared `tools/http` get/post with `base=V3_URL`)

| Tool | Signature | REST call | Returns |
|---|---|---|---|
| `get_chat_channels` | `(workspace_id: str) -> list[dict]` | `GET https://api.clickup.com/api/v3/workspaces/{workspace_id}/chat/channels` | id, name, type, visibility |
| `send_chat_message` | `(workspace_id: str, channel_id: str, message_text: str) -> dict` | `POST https://api.clickup.com/api/v3/workspaces/{workspace_id}/chat/channels/{channel_id}/messages` (content as ClickUp doc JSON) | raw |

#### docs_tools.py (v3, shared `tools/http` get/patch/post with `base=V3_URL`)

| Tool | Signature | REST call | Returns |
|---|---|---|---|
| `create_document` | `(workspace_id: str, name: str, space_id=None) -> dict` | `POST …/v3/workspaces/{workspace_id}/docs` (parent type 4 = space) | raw |
| `list_document_pages` | `(workspace_id: str, doc_id: str) -> list[dict]` | `GET …/v3/workspaces/{workspace_id}/docs/{doc_id}/pages` | page summary tree |
| `get_document_pages` | `(workspace_id: str, doc_id: str, page_ids=None) -> list[dict]` | per page `GET …/v3/workspaces/{workspace_id}/docs/{doc_id}/pages/{page_id}` | id, name, content |
| `create_document_page` | `(doc_id: str, name: str, content_markdown="") -> dict` | `POST …/v3/docs/{doc_id}/pages` | raw |
| `update_document_page` | `(page_id: str, doc_id: str, content_markdown: str) -> dict` | `PATCH …/v3/docs/{doc_id}/pages/{page_id}` | raw |

### 5.B Bitbucket tools (`backend/bitbucket/`)

All URL paths below are relative to `https://api.bitbucket.org/2.0` and use HTTP
Basic auth `(BITBUCKET_EMAIL, BITBUCKET_API_TOKEN)`. `_workspace()` returns
`BITBUCKET_WORKSPACE`. Pattern: `GET/POST …/repositories/{ws}/{repo_slug}/…`.

#### bitbucket_http.py — foundation (not a tool)

- `class BitbucketError(requests.HTTPError)` — carries `status_code` and `message`.
- `_request(method, endpoint, *, params=None, json_body=None) -> Any` — 30s timeout, raises `BitbucketError` on `not resp.ok`.
- `_get/_post/_put/_del/_post_form`, and normalizers `_fmt_repo`, `_fmt_commit`, `_fmt_pr`, `_workspace()`.

#### repos_tools.py

| Tool | Signature | REST call | Returns |
|---|---|---|---|
| `create_repo` | `(repo_name: str, workspace="", is_private=True, description="", language="") -> dict` | `POST /repositories/{ws}/{repo_name}` | `_fmt_repo` |
| `delete_repo` | `(repo_slug: str, workspace="", confirmed=False) -> dict` | `DELETE /repositories/{ws}/{repo_slug}` (gated) | `{"deleted":True,…}` or `needs_confirmation` |
| `list_repos` | `(workspace="") -> list[dict]` | `GET /repositories/{ws}?pagelen=100` | `_fmt_repo` list |
| `pull_repo_info` | `(repo_slug: str, workspace="") -> dict` | `GET /repositories/{ws}/{repo_slug}` + `GET …/src` | `{"repo":_fmt_repo,"files":[…]}` |
| `push_to_repo` | `(repo_slug: str, file_path: str, content: str, message: str, branch="", workspace="") -> dict` | `POST …/src` (form-encoded: message, branch, `<path>:<content>`) | `{"action","repo","file","branch","commit_hash"}` |
| `get_raw_file` | `(repo_slug: str, path: str, revision="", workspace="") -> dict` | `GET …/src/{revision}/{path}` (Accept: text/plain; revision defaults HEAD) | `{"repo","path","revision","content"}` |
| `get_repository_permissions` | `(repo_slug: str, user_email_or_uuid="", workspace="") -> dict` | per-user `GET …/permissions-config/users/{id}` or all `GET …/permissions-config/users` | permission/role or user list |
| `invite_collaborator` | `(repo_slug: str, email_or_uuid: str, role="write", workspace="") -> dict` | `PUT …/permissions-config/users/{id}` (fallback `POST …/permissions-config/users`) | `{"action","user","role","repo","data"}` |
| `get_latest_commits` | `(repo_slug="", workspace="", limit=10) -> list[dict]` | all-or-one repo `GET …/commits?pagelen=…` | `_fmt_commit` list + `repo` field |
| `bitbucket_repo_list` | `(workspace="") -> dict` | `GET /repositories/{ws}?pagelen=100` | raw JSON |
| `bitbucket_repo_get` | `(repo_slug: str, workspace="") -> dict` | `GET /repositories/{ws}/{repo_slug}` | raw JSON |
| `bitbucket_repo_default_reviewers` | `(repo_slug: str, workspace="") -> dict` | `GET …/default-reviewers?pagelen=100` | raw JSON |
| `bitbucket_repo_files_get` | `(repo_slug: str, path: str, revision="", workspace="") -> dict` | `GET …/src/{revision}/{path}` | `{"repo","path","revision","content"}` |
| `bitbucket_repo_commit_get` | `(repo_slug: str, revision="", workspace="") -> dict` | `GET …/commits/{revision|HEAD}` | raw JSON |
| `bitbucket_repo_commit_create` | `(repo_slug: str, file_path: str, content: str, message: str, branch="", workspace="") -> dict` | `POST …/src` (form-encoded) | `{"action","workspace","repo","branch","file","commit_hash"}` |
| `bitbucket_repo_branch_get` | `(repo_slug: str, branch_name: str, workspace="") -> dict` | `GET …/refs/branches/{name}` | raw JSON |
| `bitbucket_repo_branch_create` | `(repo_slug: str, branch_name: str, from_commit="", workspace="") -> dict` | `POST …/refs/branches` (optional `target.hash`) | `{"workspace","repo","name","target"}` |

#### pr_tools.py

| Tool | Signature | REST call | Returns |
|---|---|---|---|
| `get_pr_diff` | `(workspace="", repo_slug="", pr_id=None) -> dict` | `GET …/pullrequests/{id}/diff` | raw diff |
| `post_pr_comment` | `(workspace="", repo_slug="", pr_id=None, content="") -> dict` | `POST …/pullrequests/{id}/comments` `{"content":{"raw":…}}` | id, content, created_on |
| `approve_pr` | `(workspace="", repo_slug="", pr_id=None, confirmed=False) -> dict` | gated `POST …/pullrequests/{id}/approve` | `{"approved":True,…}` or needs_confirmation |
| `decline_pr` | `(workspace="", repo_slug="", pr_id=None, confirmed=False) -> dict` | gated `POST …/pullrequests/{id}/decline` | `{"declined":True,…}` or needs_confirmation |
| `merge_pr` | `(workspace="", repo_slug="", pr_id=None, merge_strategy="merge_commit", confirmed=False) -> dict` | gated `POST …/pullrequests/{id}/merge` `{"merge_strategy":…}` | `{"merged":True,"state",…}` or needs_confirmation |
| `get_pending_prs` | `(repo_slug="", workspace="") -> list[dict]` | per repo `GET …/pullrequests?state=OPEN&pagelen=50` | `_fmt_pr` + `repo` |
| `bitbucket_pr_create` | `(repo_slug: str, title: str, source_branch="", destination_branch="", description="", workspace="") -> dict` | `POST …/pullrequests` (source/destination branch objects) | id, title, workspace, repo, link |
| `bitbucket_pr_list` | `(repo_slug: str, state="OPEN", workspace="", pagelen=50) -> dict` | `GET …/pullrequests?state=…&pagelen=…` | raw JSON |
| `bitbucket_pr_get` | `(repo_slug: str, pr_id=None, workspace="") -> dict` | `GET …/pullrequests/{id}` | raw JSON |
| `bitbucket_pr_diff` | `(repo_slug: str, pr_id=None, workspace="") -> dict` | `GET …/pullrequests/{id}/diff` | raw |
| `bitbucket_pr_merge` | `(repo_slug: str, pr_id=None, merge_strategy="merge_commit", workspace="", confirmed=False) -> dict` | gated `POST …/pullrequests/{id}/merge` | `{"merged","state"}` or needs_confirmation |
| `bitbucket_pr_approve` | `(repo_slug: str, pr_id=None, workspace="", confirmed=False) -> dict` | gated `POST …/pullrequests/{id}/approve` | `{"approved"}` or needs_confirmation |
| `bitbucket_pr_decline` | `(repo_slug: str, pr_id=None, workspace="", confirmed=False) -> dict` | gated `POST …/pullrequests/{id}/decline` | `{"declined"}` or needs_confirmation |
| `bitbucket_pr_comment_list` | `(repo_slug: str, pr_id=None, workspace="") -> dict` | `GET …/pullrequests/{id}/comments?pagelen=100` | raw JSON |
| `bitbucket_pr_comment_add` | `(repo_slug: str, pr_id=None, content="", workspace="") -> dict` | `POST …/pullrequests/{id}/comments` | id, content, created_on |
| `bitbucket_pr_comment_update` | `(repo_slug: str, pr_id=None, comment_id=None, content="", workspace="") -> dict` | `PUT …/pullrequests/{id}/comments/{comment_id}` | id, content |
| `bitbucket_pr_task_list` | `(repo_slug: str, pr_id=None, workspace="") -> dict` | `GET …/pullrequests/{id}/tasks?pagelen=100` | raw JSON |
| `bitbucket_pr_task_create` | `(repo_slug: str, pr_id=None, content="", workspace="") -> dict` | `POST …/pullrequests/{id}/tasks` | id, content, state |
| `bitbucket_pr_task_update` | `(repo_slug: str, pr_id=None, task_id=None, content="", state="", workspace="") -> dict` | `PUT …/pullrequests/{id}/tasks/{task_id}` | id, content, state |
| `bitbucket_user_pull_requests` | `(selected_user: str, workspace="", state="OPEN") -> dict` | `GET /workspaces/{ws}/pullrequests/{uuid}?state=…&pagelen=50` | raw JSON |

#### branch_tools.py

| Tool | Signature | REST call | Returns |
|---|---|---|---|
| `create_branch` | `(repo_slug: str, branch_name: str, from_commit="", workspace="") -> dict` | `POST …/refs/branches` (optional `target.hash`) | name, target, repo |
| `set_branch_permission` | `(repo_slug: str, branch_pattern: str, kind: str, value: str, workspace="", confirmed=False) -> dict` | gated `POST …/branch-restrictions` `{"kind","pattern","value"}` | restriction_id, kind, pattern |

#### webhook_tools.py

| Tool | Signature | REST call | Returns |
|---|---|---|---|
| `list_webhooks` | `(repo_slug: str, workspace="") -> list[dict]` | `GET …/hooks` | uuid, url, description, active, events |
| `add_webhook` | `(repo_slug: str, url: str, events=None, description="", workspace="") -> dict` | `POST …/hooks` | uuid, url, events, active |
| `remove_webhook` | `(repo_slug: str, hook_uuid: str, workspace="", confirmed=False) -> dict` | gated `DELETE …/hooks/{uuid}` | `{"deleted"}` or needs_confirmation |

#### property_tools.py (application properties)

| Tool | Signature | REST call | Returns |
|---|---|---|---|
| `get_application_properties` | `(repo_slug: str, app_key: str, name: str, scope="repository", pr_id="", commit="", workspace="") -> dict` | `GET …/{scope-path}/properties/{name}/` (scope path helper `_property_path`) | action, scope, app_key, name, value |
| `update_application_properties` | `(repo_slug: str, app_key: str, name: str, value: Any, scope="repository", pr_id="", commit="", workspace="") -> dict` | `PUT …/properties/{name}/` `{"value":…}` | `{"updated":True,"data"}` |
| `delete_application_properties` | `(repo_slug: str, app_key: str, name: str, scope="repository", pr_id="", commit="", workspace="", confirmed=False) -> dict` | gated `DELETE …/properties/{name}/` | `{"deleted"}` or needs_confirmation |

Path helper: `_property_path(ws, repo_slug, scope, pr_id, commit, name)` →
`/repositories/{ws}/{repo}/properties/{name}/` (repo) ·
`…/pullrequests/{pr_id}/properties/{name}/` (PR) ·
`…/commit/{commit}/properties/{name}/` (commit).

#### workspace_tools.py (Bitbucket)

| Tool | Signature | REST call | Returns |
|---|---|---|---|
| `list_workspace_members` | `(workspace="") -> list[dict]` | `GET /workspaces/{ws}/permissions?pagelen=100` | display_name, email, uuid, account_id, type, permission |
| `update_workspace_member_role` | `(selected_user_id: str, role: str, workspace="", confirmed=False) -> dict` | none (returns "not supported") | needs_confirmation or `{"error": "not supported"}` |
| `bitbucket_workspace_list` | `() -> dict` | `GET /user/workspaces` | raw JSON |
| `bitbucket_workspace_get` | `(workspace="") -> dict` | `GET /workspaces/{ws}` | raw JSON |

#### pipeline_tools.py

| Tool | Signature | REST call | Returns |
|---|---|---|---|
| `bitbucket_pipeline_list` | `(repo_slug: str, workspace="", pagelen=25) -> dict` | `GET …/pipelines?pagelen=…` | raw JSON |
| `bitbucket_pipeline_get` | `(repo_slug: str, pipeline_uuid="", workspace="") -> dict` | `GET …/pipelines/{uuid}` | raw JSON |
| `bitbucket_pipeline_run` | `(repo_slug: str, ref_type="branch", ref_name="", selector_type="custom", selector_pattern="**", variables=None, workspace="") -> dict` | `POST …/pipelines` (target selector/ref/commit) | raw JSON |
| `bitbucket_pipeline_steps` | `(repo_slug: str, pipeline_uuid="", workspace="", pagelen=25) -> dict` | `GET …/pipelines/{uuid}/steps` | raw JSON |
| `bitbucket_pipeline_step_get` | `(repo_slug: str, pipeline_uuid="", step_uuid="", workspace="") -> dict` | `GET …/pipelines/{uuid}/steps/{step_uuid}` | raw JSON |
| `bitbucket_pipeline_step_log` | `(repo_slug: str, pipeline_uuid="", step_uuid="", workspace="") -> dict` | `GET …/pipelines/{uuid}/steps/{step_uuid}/log` (direct requests, auth) | `{"log": text}` |
| `bitbucket_analyze_pr_commit_failures` | `(repo_slug: str, pr_id=None, workspace="") -> dict` | `GET …/pullrequests/{id}/statuses?pagelen=100` | failed-checks summary |
| `bitbucket_analyze_pipeline_step_failure` | `(repo_slug: str, pipeline_uuid="", step_uuid="", workspace="", log_lines=200) -> dict` | calls `bitbucket_pipeline_step_get` + `…_step_log` | step state, log tail, summary |

#### deployment_tools.py

| Tool | Signature | REST call | Returns |
|---|---|---|---|
| `bitbucket_deployment_list` | `(repo_slug: str, workspace="", pagelen=25) -> dict` | `GET …/deployments?pagelen=…` | raw JSON |
| `bitbucket_deployment_get` | `(repo_slug: str, deployment_uuid="", workspace="") -> dict` | `GET …/deployments/{uuid}` | raw JSON |
| `bitbucket_environment_list` | `(repo_slug: str, workspace="", pagelen=25) -> dict` | `GET …/environments?pagelen=…` | raw JSON |
| `bitbucket_environment_get` | `(repo_slug: str, environment_uuid="", workspace="") -> dict` | `GET …/environments/{uuid}` | raw JSON |
| `bitbucket_environment_create` | `(repo_slug: str, name: str, environment_type="Production", workspace="") -> dict` | `POST …/environments` | raw JSON |
| `bitbucket_environment_delete` | `(repo_slug: str, environment_uuid="", workspace="", confirmed=False) -> dict` | gated `DELETE …/environments/{uuid}` | `{"deleted"}` or needs_confirmation |
| `bitbucket_environment_update` | `(repo_slug: str, environment_uuid="", update=None, workspace="") -> dict` | `POST …/environments/{uuid}/changes` | raw JSON |

### 5.C Which agent calls which tool

- **ClickUp `Orchestrator`** can call any of the **59 tools** in `TOOL_MAP`
  (`backend/tools/__init__.py`). There is no per-agent allow-list; the LLM
  selects freely from the full registry via the system prompt.
- **Bitbucket `BitbucketAgent`** can call any of the **64 tools** in
  `BITBUCKET_TOOL_MAP` (`backend/bitbucket/bitbucket_tools.py`), likewise
  free selection.
- Dashboards and route-only tools (`/api/dashboard`, `/bitbucket/dashboard`,
  etc.) are invoked **directly by routes**, not by the LLM.

---

## 6. Agent ↔ Tool ↔ External-Service Wiring (flat table)

All ClickUp paths under `https://api.clickup.com/api/v2` (except Chat/Docs under
`…/api/v3`). All Bitbucket paths under `https://api.bitbucket.org/2.0`.
Bitbucket `{repo}` = repo slug, `{ws}` = workspace (default `BITBUCKET_WORKSPACE`).

### 6.A ClickUp (`TOOL_MAP`, dispatched by `Orchestrator`)

| Tool | External API | Method + URL |
|---|---|---|
| get_authorized_user | ClickUp | GET `/user` |
| get_workspaces | ClickUp | GET `/team` |
| get_spaces | ClickUp | GET `/team/{team_id}/space` |
| get_folders | ClickUp | GET `/space/{space_id}/folder` |
| get_lists | ClickUp | GET `/folder/{folder_id}/list` |
| get_folderless_lists | ClickUp | GET `/space/{space_id}/list` |
| get_workspace_members | ClickUp | GET `/team/{team_id}` |
| get_workspace_hierarchy | ClickUp | GET `/team/{1}/space` → `/space/{2}/list` → `/space/{2}/folder` → `/folder/{3}/list` |
| search_workspace | ClickUp | GET `/team/{1}/task`; `/team/{1}/space`; per space `/space/{2}/folder`, `/space/{2}/list`, `/folder/{3}/list` |
| search_tasks_by_type | ClickUp | GET `/team/{1}/task?types[]={type}` |
| search_tasks_by_tag | ClickUp | GET `/team/{1}/task?tags[]={tags}` |
| get_tasks | ClickUp | GET `/list/{list_id}/task` (paged) |
| get_task | ClickUp | GET `/task/{task_id}` |
| get_team_tasks | ClickUp | GET `/team/{team_id}/task` (paged) |
| classify_tasks | ClickUp | — (pure Python) |
| create_task | ClickUp | POST `/list/{list_id}/task` |
| update_task_status | ClickUp | PUT `/task/{task_id}` |
| update_task | ClickUp | PUT `/task/{task_id}` |
| delete_task | ClickUp | DELETE `/task/{task_id}` |
| get_list_custom_fields | ClickUp | GET `/list/{list_id}/field` |
| set_custom_field | ClickUp | POST `/task/{task_id}/field/{field_id}` |
| create_bulk_tasks | ClickUp | POST `/list/{list_id}/task` (n × ) |
| update_bulk_tasks | ClickUp | PUT `/task/{task_id}` (n × ) |
| attach_file_to_task | ClickUp | POST `/task/{task_id}/attachment` (multipart) |
| get_task_comments | ClickUp | GET `/task/{task_id}/comment` |
| post_task_comment | ClickUp | POST `/task/{task_id}/comment` |
| add_tag_to_task | ClickUp | POST `/task/{task_id}/tag/{tag}` |
| remove_tag_from_task | ClickUp | DELETE `/task/{task_id}/tag/{tag}` |
| add_task_link | ClickUp | PUT `/task/{task_id}/link/{linked_task_id}` |
| remove_task_link | ClickUp | DELETE `/task/{task_id}/link/{linked_task_id}` |
| add_dependency | ClickUp | POST `/task/{task_id}/dependency` |
| remove_dependency | ClickUp | DELETE `/task/{task_id}/dependency` |
| move_task_to_list | ClickUp | POST `/list/{list_id}/task/{task_id}` |
| add_task_to_list | ClickUp | POST `/task/{task_id}/list/{list_id}` |
| get_folder_details | ClickUp | GET `/folder/{folder_id}` |
| create_folder | ClickUp | POST `/space/{space_id}/folder` |
| update_folder | ClickUp | PUT `/folder/{folder_id}` |
| create_list | ClickUp | POST `/folder/{folder_id}/list` `|` `/space/{space_id}/list` |
| get_list_details | ClickUp | GET `/list/{list_id}` |
| update_list | ClickUp | PUT `/list/{list_id}` |
| get_task_time_entries | ClickUp | GET `/team/{team_id}/time_entries` |
| get_time_entries_summary | ClickUp | GET `/team/{team_id}/time_entries` (n × ) |
| start_time_tracking | ClickUp | POST `/team/{team_id}/time_entries/start` |
| stop_time_tracking | ClickUp | POST `/team/{team_id}/time_entries/stop` |
| add_time_entry | ClickUp | POST `/team/{team_id}/time_entries` |
| get_current_time_entry | ClickUp | GET `/team/{team_id}/time_entries/current` |
| get_task_time_in_status | ClickUp | GET `/task/{task_id}/metric/time_in_status` |
| get_list_time_in_status | ClickUp | GET `/list/{list_id}/metric/time_in_status` |
| get_workspace_members | ClickUp | GET `/team/{team_id}` |
| find_member_by_name | ClickUp | GET `/team/{team_id}` (then filter) |
| resolve_assignees | ClickUp | GET `/team/{team_id}` (then filter) |
| get_chat_channels | ClickUp v3 | GET `/api/v3/workspaces/{workspace_id}/chat/channels` |
| send_chat_message | ClickUp v3 | POST `/api/v3/workspaces/{ws}/chat/channels/{ch}/messages` |
| create_document | ClickUp v3 | POST `/api/v3/workspaces/{ws}/docs` |
| list_document_pages | ClickUp v3 | GET `/api/v3/workspaces/{ws}/docs/{doc}/pages` |
| get_document_pages | ClickUp v3 | GET `/api/v3/workspaces/{ws}/docs/{doc}/pages/{page}` (n × ) |
| create_document_page | ClickUp v3 | POST `/api/v3/docs/{doc}/pages` |
| update_document_page | ClickUp v3 | PATCH `/api/v3/docs/{doc}/pages/{page}` |
| build_dashboard | ClickUp | — (pure Python) |
| render_dashboard_text | ClickUp | — (pure Python) |

### 6.B Bitbucket (`BITBUCKET_TOOL_MAP`, dispatched by `BitbucketAgent`)

| Tool | Method + URL (`/repositories/{ws}/{repo}/…` unless shown) |
|---|---|
| create_repo | POST `/repositories/{ws}/{name}` |
| delete_repo | DELETE `/repositories/{ws}/{slug}` *(gated)* |
| list_repos | GET `/repositories/{ws}` |
| list_workspace_members | GET `/workspaces/{ws}/permissions` |
| update_workspace_member_role | — (not supported) |
| pull_repo_info | GET `/repositories/{ws}/{slug}`; GET `…/src` |
| push_to_repo | POST `…/src` (form) |
| get_raw_file | GET `…/src/{revision}/{path}` |
| get_repository_permissions | GET `…/permissions-config/users[/{id}]` |
| invite_collaborator | PUT `…/permissions-config/users/{id}` (fallback POST `…/users`) |
| get_latest_commits | GET `…/commits` (per repo or all) |
| get_pr_diff | GET `…/pullrequests/{id}/diff` |
| post_pr_comment | POST `…/pullrequests/{id}/comments` |
| approve_pr | POST `…/pullrequests/{id}/approve` *(gated)* |
| decline_pr | POST `…/pullrequests/{id}/decline` *(gated)* |
| merge_pr | POST `…/pullrequests/{id}/merge` *(gated)* |
| get_pending_prs | GET `…/pullrequests?state=OPEN&pagelen=50` (per repo/all) |
| create_branch | POST `…/refs/branches` |
| set_branch_permission | POST `…/branch-restrictions` *(gated)* |
| list_webhooks | GET `…/hooks` |
| add_webhook | POST `…/hooks` |
| remove_webhook | DELETE `…/hooks/{uuid}` *(gated)* |
| get_application_properties | GET `…/properties/{name}/` |
| update_application_properties | PUT `…/properties/{name}/` |
| delete_application_properties | DELETE `…/properties/{name}/` *(gated)* |
| bitbucket_workspace_list | GET `/user/workspaces` |
| bitbucket_workspace_get | GET `/workspaces/{ws}` |
| bitbucket_repo_list | GET `/repositories/{ws}` |
| bitbucket_repo_get | GET `/repositories/{ws}/{slug}` |
| bitbucket_repo_default_reviewers | GET `…/default-reviewers` |
| bitbucket_repo_files_get | GET `…/src/{revision}/{path}` |
| bitbucket_repo_commit_get | GET `…/commits/{revision}` |
| bitbucket_repo_commit_create | POST `…/src` (form) |
| bitbucket_repo_branch_get | GET `…/refs/branches/{name}` |
| bitbucket_repo_branch_create | POST `…/refs/branches` |
| bitbucket_pr_create | POST `…/pullrequests` |
| bitbucket_pr_list | GET `…/pullrequests?state=…` |
| bitbucket_pr_get | GET `…/pullrequests/{id}` |
| bitbucket_pr_diff | GET `…/pullrequests/{id}/diff` |
| bitbucket_pr_merge | POST `…/pullrequests/{id}/merge` *(gated)* |
| bitbucket_pr_approve | POST `…/pullrequests/{id}/approve` *(gated)* |
| bitbucket_pr_decline | POST `…/pullrequests/{id}/decline` *(gated)* |
| bitbucket_pr_comment_list | GET `…/pullrequests/{id}/comments` |
| bitbucket_pr_comment_add | POST `…/pullrequests/{id}/comments` |
| bitbucket_pr_comment_update | PUT `…/pullrequests/{id}/comments/{cid}` |
| bitbucket_pr_task_list | GET `…/pullrequests/{id}/tasks` |
| bitbucket_pr_task_create | POST `…/pullrequests/{id}/tasks` |
| bitbucket_pr_task_update | PUT `…/pullrequests/{id}/tasks/{tid}` |
| bitbucket_user_pull_requests | GET `/workspaces/{ws}/pullrequests/{uuid}` |
| bitbucket_pipeline_list | GET `…/pipelines` |
| bitbucket_pipeline_get | GET `…/pipelines/{uuid}` |
| bitbucket_pipeline_run | POST `…/pipelines` |
| bitbucket_pipeline_steps | GET `…/pipelines/{uuid}/steps` |
| bitbucket_pipeline_step_get | GET `…/pipelines/{uuid}/steps/{s}` |
| bitbucket_pipeline_step_log | GET `…/pipelines/{uuid}/steps/{s}/log` |
| bitbucket_analyze_pr_commit_failures | GET `…/pullrequests/{id}/statuses` |
| bitbucket_analyze_pipeline_step_failure | (composes pipeline_step_get + step_log) |
| bitbucket_deployment_list | GET `…/deployments` |
| bitbucket_deployment_get | GET `…/deployments/{uuid}` |
| bitbucket_environment_list | GET `…/environments` |
| bitbucket_environment_get | GET `…/environments/{uuid}` |
| bitbucket_environment_create | POST `…/environments` |
| bitbucket_environment_delete | DELETE `…/environments/{uuid}` *(gated)* |
| bitbucket_environment_update | POST `…/environments/{uuid}/changes` |

### 6.C LLM wiring

| Caller | Interface | Method + URL |
|---|---|---|
| Both agents | `BedrockLLM.chat(...)` | `boto3.client("bedrock-runtime").invoke_model(modelId=…, body=…)` (AWS Bedrock) |

---

## 7. User Conversation Flow (step-by-step trace)

Worked example: user types **"Show me the dashboard for workspace 123"** into the
ClickUp chat.

1. **Frontend** `api.js` → `POST /api/chat` with body `{"message":"Show me the dashboard for workspace 123"}` (proxied by Vite to `localhost:8000`).
2. **FastAPI** `chat()` in `server.py` receives it, calls
   `orch.run(body.message)`.
3. `Orchestrator.run()` **resolves relative dates** (`resolve_relative_dates`),
   appends the user turn to `self.history`, then enters the loop.
4. **Think**: `llm.chat(history, system)` where `system` = `_build_system_prompt()`
   (embeds all 59 tools + behaviour rules + `ist_now()`). The model returns a
   tool-call block, e.g. `{"tool":"get_workspaces","args":{}}`.
5. **Act**: `_dispatch("get_workspaces", {})` → `get_workspaces()` → `GET /team`
   → list of workspaces (dict). Result JSON appended to history as `[TOOL RESULT: …]`.
6. Loop repeats: model now knows the workspace IDs; likely calls
   `get_team_tasks(team_id="123")` → `GET /team/123/task` → formatted tasks.
7. Model then calls `classify_tasks(tasks)` → buckets; then `build_dashboard(classified)`
   → dashboard dict; then `render_dashboard_text(dash)` → `str` report.
8. Model sees the report text and emits a **plain-text final answer** (no JSON).
   `_extract_tool_call` returns `None`.
9. `run()` appends the answer to `self.history`, returns it.
10. `chat()` returns `{"reply": <answer>, "tool_calls": orch.tool_calls_log}`.
11. Frontend displays `reply` (and, if the UI shows it, the tool-call log).

Worked example, Bitbucket: user types **"show my pending PRs"** into `#/bitbucket`
chat → `POST /bitbucket/chat` → `BitbucketAgent.run(...)` → the loop chooses
`get_pending_prs()` → Bitbucket `GET /repositories/{ws}/*/pullrequests?state=OPEN`
→ summarised reply `{"reply", "tool_calls"}` back to the frontend.

Dashboards skip the agent entirely: `/api/dashboard` calls
`gather_all_tasks()` (walks the whole ClickUp hierarchy) →
`classify_tasks()` → `build_dashboard()` → `render_dashboard_text()`, all
server-side, no LLM.

---

## 8. Memory & State

- **Conversation history**: stored in-memory on the agent instance as
  `self.history: list[dict[str,str]]` (`{"role","content"}`). It is appended to
  every turn and sent to the LLM each iteration. Not persisted to any DB.
- **Tool-call log**: `self.tool_calls_log: list[dict]` — each entry
  `{"iteration","tool","args","result_preview"}` (preview capped at 300 chars);
  returned to the frontend after each chat call.
- **Durability / lifecycle**:
  - ClickUp: `server.py` builds **one** module-level `Orchestrator()`; `main.py`
    builds its **own** `Orchestrator()` for the CLI. Each keeps history until
    `reset()` is called (`POST /api/chat/reset` or CLI `reset`).
  - Bitbucket: `bitbucket_routes.py` builds **one** lazy singleton
    `BitbucketAgent` via `get_agent()`.
- **Shared state between agents**: **none functionally.** They share only the
  **LLM client** (the `get_llm()` singleton in `agent/llm.py`), the
  `time_utils`/`bitbucket_time_utils` helpers, and `config.settings`. Each agent
  keeps its own independent `history`/`tool_calls_log`. Cloning the loop code is
  the only "sharing" of behavior.
- **Time/date context**: `tools/time_utils.py` defines `IST = timezone(+5:30)`;
  `ist_now()` injects the current IST datetime into system prompts;
  `resolve_relative_dates()` rewrites relative words ("tomorrow", "next monday",
  "in 3 days", "this weekend", "next week") into concrete dates **before** the
  LLM sees them. `bitbucket_time_utils.py` parses Bitbucket ISO-8601 timestamps
  (`parse_iso`, `iso_to_epoch_sec`, `age_from_iso`, `format_commits`, etc.).

---

## 9. Error Handling & Fallbacks

- **Tool failure propagation (ClickUp)**: `_dispatch` wraps every tool call in
  try/except. On exception it returns `{"error": str(exc)}` — this dict is fed
  back into the LLM context so the model can see the problem and self-correct
  (e.g. retry with a real ID after a look-up). Tools that raise (e.g.
  `create_list` raising `ValueError`, `attach_file_to_task` raising
  `FileNotFoundError`) become this error dict.
- **Tool failure propagation (Bitbucket)**: `_dispatch` catches
  `BitbucketError` → `{"error": True, "message": str(exc), "status_code": n}`,
  and generic `Exception` → `{"error": True, "message": str(exc), "status_code": 0}`.
- **Unknown tool**: `{"error": "Unknown tool: <name>"}` (ClickUp) /
  structured Bitbucket error. Fed back to the LLM for self-correction.
- **Route-level handling**: every route wraps its work in try/except and
  returns `{"error": str(exc)}` (ClickUp & Bitbucket routes) on failure,
  logging via `logger.exception`. `/api/chat` returns
  `{"reply": "Agent error: …", "tool_calls": []}` on exception.
- **Max-iteration fallback**: after `MAX_ITERATIONS = 12` the agent returns a
  canned *"I reached the maximum number of steps…"* message and appends it to
  history. There is **no** retry/backoff, no fallback-to-second-agent, and no
  circuit breaker.
- **Human-gate (confirmation) fallback**: destructive Bitbucket tools return
  `{"needs_confirmation": True, "action", "summary", "reason"}` when
  `confirmed=False`; the system prompt instructs the LLM to ask the user first
  and **never** set `confirmed=True` on its own. The ClickUp `delete_task` is
  gated **by prompt only** (the system prompt says "NEVER call delete_task
  without explicit user confirmation") — there is no code-level `confirmed` flag.
- **Partial-collection resilience (Bitbucket)**: multi-repo scans
  (`get_pending_prs`, `get_latest_commits`) wrap each repo in try/except and
  `continue` on `requests.HTTPError`, so one bad repo doesn't kill the whole
  result. `pull_repo_info` returns `files=[]` if the `src` call fails.

---

## 10. File Map

### Backend root (`backend/`)

| File | Purpose |
|---|---|
| `server.py` | FastAPI app: CORS, mounts Bitbucket router, ClickUp `/api/*` routes (health, dashboard, chat, chat/reset), one global `Orchestrator`. |
| `main.py` | Interactive CLI REPL for the ClickUp agent (`Orchestrator`). |
| `requirements.txt` | `boto3, botocore, requests, python-dotenv, fastapi, uvicorn[standard]`. |
| `.env.example` | Template listing all env vars (ClickUp token, Bitbucket token/email/workspace, AWS keys/region/model). |

### `backend/agent/` — ClickUp agent

| File | Purpose |
|---|---|
| `llm.py` | `BedrockLLM` + `get_llm()` singleton; `chat`/`complete` wrapping `boto3` Bedrock `invoke_model`. |
| `orchestrator.py` | `Orchestrator` class: Observe→Think→Act loop, `_build_system_prompt`, `_dispatch`, `_extract_tool_call`, `MAX_ITERATIONS=12`. |
| `__init__.py` | Re-exports `Orchestrator`, `get_llm`, `BedrockLLM`. |

### `backend/bitbucket/` — Bitbucket agent

| File | Purpose |
|---|---|
| `bitbucket_agent.py` | `BitbucketAgent`: Observe→Think→Act loop (mirror of orchestrator) using `BITBUCKET_TOOL_MAP`. |
| `bitbucket_http.py` | Shared HTTP helpers `_request/_get/_post/_put/_del/_post_form`, `BitbucketError`, normalizers `_fmt_repo/_fmt_commit/_fmt_pr`, `_workspace()`. |
| `bitbucket_tools.py` | Central registry `BITBUCKET_TOOL_REGISTRY`/`BITBUCKET_TOOL_MAP` (64 tools) binding names to functions from the domain modules. |
| `bitbucket_prompts.py` | `build_bitbucket_system_prompt()` (builds prompt from registry) + `summarize_pending_pr`, `summarize_commit`. |
| `bitbucket_routes.py` | `APIRouter(prefix="/bitbucket")` — ~49 REST endpoints for chat, dashboard, and every `bitbucket_*` tool. |
| `bitbucket_time_utils.py` | Bitbucket ISO-8601 parsing/duration helpers (`parse_iso`, `age_from_iso`, `format_commits`, `format_branch_activity`, …). |
| `repos_tools.py` | Repository tools: create/delete/list, pull info, push file, raw file, permissions, invite, commits, `bitbucket_repo_*`. |
| `pr_tools.py` | PR tools: create/list/get/diff/comments/tasks, approve/decline/merge (gated), pending PRs, `bitbucket_pr_*`. |
| `branch_tools.py` | `create_branch`, `set_branch_permission` (gated). |
| `webhook_tools.py` | `list_webhooks`, `add_webhook`, `remove_webhook` (gated). |
| `property_tools.py` | Application-property get/update/delete (delete gated) via `_property_path`. |
| `workspace_tools.py` | `list_workspace_members`, `update_workspace_member_role` (not supported), `bitbucket_workspace_list/get`. |
| `pipeline_tools.py` | Pipeline list/get/run/steps/step/step-log + failure analysis helpers. |
| `deployment_tools.py` | Deployment + environment list/get/create/delete(gated)/update. |
| `bitbucket_dashboard_snapshot.json` | (data) snapshot artifact. |
| `live_dashboard.py` | (CLI) Bitbucket dashboard walker (not part of agent loop). |
| `__init__.py` | Re-exports `BITBUCKET_TOOL_MAP` / `BITBUCKET_TOOL_REGISTRY`. |

### `backend/config/`

| File | Purpose |
|---|---|
| `settings.py` | Loads `.env`; exposes `CLICKUP_API_TOKEN/_BASE_URL/_HEADERS`, `AWS_*`, `BITBUCKET_*` (`_auth` returns `(email, token)`), defaults for `BITBUCKET_WORKSPACE`. |
| `__init__.py` | Empty package marker. |

### `backend/tools/` — ClickUp tools

| File | Purpose |
|---|---|
| `__init__.py` | Central registry `TOOL_REGISTRY`/`TOOL_MAP` (59 tools) + `_t()` helper. |
| `http.py` | Shared HTTP helpers `request/get/post/put/patch/delete` + `V3_URL`. |
| `workspace_tools.py` | Workspace/Space/Folder/List/member navigation. |
| `task_tools.py` | Task fetch/create/update/delete, `_fmt_task` normalizer, `classify_tasks`, custom fields. |
| `comment_tools.py` | Task comment get/post. |
| `dashboard_tools.py` | Pure `build_dashboard` / `render_dashboard_text` aggregation. |
| `search_tools.py` | `search_workspace`, `search_tasks_by_type`, `search_tasks_by_tag`. |
| `list_tools.py` | List/folder CRUD, task↔list movement, `get_workspace_hierarchy`. |
| `bulk_tools.py` | `create_bulk_tasks`, `update_bulk_tasks`. |
| `tag_tools.py` | Add/remove task tags. |
| `relation_tools.py` | Task links + dependencies. |
| `attachment_tools.py` | `attach_file_to_task` (multipart upload). |
| `time_tracking_tools.py` | Time entries, start/stop, manual log, current entry. |
| `status_time_tools.py` | Time-in-status for task/list. |
| `member_tools.py` | `find_member_by_name`, `resolve_assignees`. |
| `chat_tools.py` | Chat channels + send message (v3). |
| `docs_tools.py` | Docs create/list/read/create-page/update-page (v3). |
| `time_utils.py` | `ist_now`, `resolve_relative_dates`, `compute_due_epoch_ms`, `IST`, weekday shift helpers. |

### `backend/dashboard/`

| File | Purpose |
|---|---|
| `live_dashboard.py` | `gather_all_tasks()` (full-hierarchy walk) + CLI dashboard renderer; used by `/api/dashboard`. |

### Frontend (context only — for wiring, not backend logic)

| File | Purpose |
|---|---|
| `frontend/vite.config.js` | Proxies `/api` and `/bitbucket` → `http://localhost:8000`. |
| `frontend/src/api.js` | ClickUp API client (`health`, `dashboard`, `chat`, `resetChat`). |
| `frontend/src/bitbucketApi.js` | Bitbucket API client (dashboard + all tool-backed methods). |
| `frontend/src/pages/BitbucketDashboard.jsx`, `frontend/src/App.jsx`, `frontend/src/Shell.jsx`, `frontend/src/components/*` | React UI (hash-routed ClickUp/Bitbucket sections, chat bots, confirmation modals, tabbed panels). |

---

## Appendix A — Diagram-ready summary of flows

1. **Shared brain**: `server.py` → both `Orchestrator` and `BitbucketAgent` →
   `get_llm()` → `BedrockLLM` → AWS Bedrock (`invoke_model`). Single node.
2. **Two paths**: ClickUp (`/api/*`) and Bitbucket (`/bitbucket/*`), mounted on
   one FastAPI app.
3. **Per path**: direct-REST routes (deterministic) AND agent-chat routes
   (`/api/chat`, `/bitbucket/chat` → Observe→Think→Act loop).
4. **Within agent**: loop → `_dispatch` → tool registry (`TOOL_MAP` /
   `BITBUCKET_TOOL_MAP`) → domain tool module → shared HTTP layer
   (`tools/http.py` / `bitbucket_http.py`) → external REST API →
   ClickUp/Bitbucket.
5. **Human-gate**: destructive tools return `needs_confirmation` → frontend
   modal → re-call with `confirmed=True`.
6. **Config**: `.env` → `config/settings.py` supplies credentials to LLM and
   both HTTP clients.

> Draw edges for: Frontend →(proxy)→ FastAPI →(router)→ Agent →(dispatch)→ Tool
> →(HTTP)→ Cloud API; and FastAPI → Orchestrator/Agent → get_llm → AWS Bedrock.
> Show the shared LLM node feeding both agent loops, and the two isolated
> tool registries.

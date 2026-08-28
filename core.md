# CORE — WorkSpace_Integration: Backend Architecture

> Reference for drawing a clear architecture / flow diagram (draw.io).
> This document covers the **backend** only: how a user request splits into two
> independent paths (ClickUp & Bitbucket), how tools are called, what role the
> LLM plays, how each tool talks to its remote REST API, and how the backend
> connects to the React frontend.

---

## 1. The Big Picture

A single web app ("AI Command Center") serves **two independent integration
paths** for the same user. Each path has its own agent, its own tool registry,
its own REST routes, and talks to one external service.

```
                    ┌────────────────────────────────────────────┐
                    │                  USER                       │
                    │   (React/Vite Frontend, port 5173)         │
                    └───────────────┬────────────────────────────┘
                          (HTTP /api/* , /bitbucket/*)
                                   │
                    ┌──────────────▼──────────────┐
                    │    FastAPI Backend (8000)   │
                    │        server.py             │
                    │  ┌───────────┐ ┌───────────┐ │
                    │  │  ClickUp  │ │ Bitbucket │ │   ← TWO PATHS
                    │  │  path     │ │  path     │ │
                    │  └─────┬─────┘ └─────┬─────┘ │
                    └────────┼─────────────┼───────┘
                             │             │
                   ┌─────────▼───┐  ┌──────▼─────┐
                   │ ClickUp API │  │ Bitbucket  │
                   │  (REST)     │  │  API (REST)│
                   └─────────────┘  └────────────┘

                  (one shared LLM: AWS Bedrock / Claude)
                   feeds BOTH agent brains
```

- **Frontend** (React, port 5173) talks to the backend only.
- The **backend** (FastAPI, port 8000) is the only thing that talks to the LLM
  and to the external ClickUp / Bitbucket REST APIs.
- The **LLM** (AWS Bedrock → Claude) is the shared "brain" for both agents.

---

## 2. Two Paths (What the User Can Do)

When the user lands in the app, the frontend navigates between two sections.
Each maps to a backend path.

| Path | Frontend route | Backend module | External API | Tool count |
|------|----------------|----------------|--------------|-----------|
| **ClickUp** | `#/clickup` | `server.py` + `agent/` | ClickUp Cloud REST (v2) | 59 tools |
| **Bitbucket** | `#/bitbucket/dashboard` | `bitbucket/` | Bitbucket Cloud REST (2.0) | 64 tools |

The **frontend** decides which path — it either:
- calls dashboard/chat endpoints (`/api/*`, `/bitbucket/*`), or
- sends a message to the corresponding **agent chat** when the user types a
  natural-language request.

---

## 3. Backend Entry Point — `backend/server.py`

One FastAPI app mounts both paths:

```python
app = FastAPI(title="ClickUp AI Agent API")
app.add_middleware(CORSMiddleware, ...)     # allow frontend origins (5173)
app.include_router(bitbucket_router)         # /bitbucket/* routes
# + ClickUp routes defined directly on `app` (/api/* routes)
```

**ClickUp REST routes** (defined directly on `app`, prefix `/api`):

| Method | Route | Purpose |
|--------|-------|---------|
| GET  | `/api/health`      | liveness check |
| GET  | `/api/dashboard`   | walk whole workspace → structured dashboard JSON |
| POST | `/api/chat`        | send message to the ClickUp agent |
| POST | `/api/chat/reset`  | clear ClickUp agent conversation history |

**Bitbucket REST routes** (mounted `APIRouter`, prefix `/bitbucket`, ~49 endpoints):

| Method | Route | Purpose |
|--------|-------|---------|
| POST | `/bitbucket/chat`       | send message to the Bitbucket agent |
| GET  | `/bitbucket/dashboard`  | commits + pending PRs summary |
| GET  | `/bitbucket/commits`    | latest commits |
| GET  | `/bitbucket/pending-prs`| open PRs waiting for review |
| POST | `/bitbucket/pr/{approve,decline,merge}` | human-GATED PR actions |
| POST | `/bitbucket/repo/create`, `/repo/delete` | repo CRUD (delete human-gated) |
| POST | `/bitbucket/branch/create`, `/branch/permission` | branch ops |
| POST | `/bitbucket/collaborator/invite` | invite collaborator |
| GET  | `/bitbucket/workspaces`, `/workspace` | workspace info |
| GET/POST | `/bitbucket/repos`, `/repo` (+ file, commit, branch, default-reviewers) | repo content |
| GET/POST/PUT | `/bitbucket/pr/*` (list, create, diff, comments, tasks, user) | PR management |
| GET/POST | `/bitbucket/pipeline*` (list, run, steps, step, step/log, analyze/*) | pipelines + AI failure analysis |
| GET/POST | `/bitbucket/deployment*`, `/environment*` (+ delete/update) | deployments & environments |

> **Human-gated tools.** Destructive/irreversible actions (PR approve/decline/merge,
> repo delete, environment delete) require `confirmed: true` in the request body.
> The backend returns `needs_confirmation: True` if it is missing, and the
> frontend shows a confirmation modal before the request is sent. The diagram
> should show this gate between the frontend action and the backend tool call.

---

## 4. The LLM (Shared Brain) — `backend/agent/llm.py`

- **One** `BedrockLLM` singleton created lazily via `get_llm()`.
- Wraps `boto3` → `bedrock-runtime` → `invoke_model`, Anthropic Messages format,
  `temperature = 0` (deterministic routing).
- **Both agents** (ClickUp `Orchestrator` and Bitbucket `BitbucketAgent`) share
  the exact same LLM client — no second client is ever created.
- The LLM **never** touches ClickUp/Bitbucket directly. It only returns either:
  - a **tool-call JSON block**, or
  - a plain-text **final answer**.

```
 LLM = BRAIN (decides WHAT to do)
 Tools = HANDS (deterministic Python that does it)
 Orchestrator/Agent = LOOP connecting brain ↔ hands
```

---

## 5. The Agent Loop (same pattern, two implementations)

Both `agent/orchestrator.py` (ClickUp) and `bitbucket/bitbucket_agent.py`
(Bitbucket) run the identical **Observe → Think → Act** loop.

```
 1. OBSERVE  append user message to history
 2. THINK    llm.chat(history, system_prompt)
              └─ either a tool-call JSON  ──or──  a final answer
 3. ACT      _extract_tool_call(text)
              └─ _dispatch(tool_name, args)  → calls the Python tool fn
              └─ result appended back into history
 4. REPEAT   back to step 2 (max MAX_ITERATIONS = 12)
 5. TERMINATE  when the LLM emits plain text → that is the reply
```

**Tool-call protocol (JSON-in-markdown):**

```json
{ "tool": "<tool_name>", "args": { "<param1>": "<value1>" } }
```

- `_extract_tool_call()` regex-scans for that JSON block.
- `_dispatch(tool, args)` looks up the tool function in the registry and calls
  it with the args. Errors are caught and returned as `{"error": ...}` so the
  LLM can see the problem and self-correct.

```
 User ──► Agent.run(msg) ──► [loop] ──► LLM ──► tool-call JSON
                                                │
                                                ▼
                                          _dispatch ──► Python tool fn
                                                │
                                                ▼
                                          REST API (ClickUp / Bitbucket)
                                                │
                                                ▼
                                         result JSON ──► back to LLM
                                                │
                                                ▼
                                     LLM emits plain text (final answer)
```

---

## 6. Tool Layer — How Each Tool Calls its REST API

### 6a. ClickUp path — `backend/tools/`

- Tools are grouped in modules: `workspace_tools.py`, `task_tools.py`,
  `comment_tools.py`, `dashboard_tools.py`, plus many more
  (`list_tools.py`, `member_tools.py`, `tag_tools.py`, `time_tracking_tools.py`,
  `search_tools.py`, `attachment_tools.py`, `relation_tools.py`, `chat_tools.py`,
  `docs_tools.py`, `bulk_tools.py`, `status_time_tools.py`, `property_tools.py`).
- `tools/http.py` provides the shared `_get`/HTTP helper (auth via
  `CLICKUP_API_TOKEN` header, 30s timeout).
- Every tool returns **plain JSON-serialisable dicts/lists** — never raw HTTP —
  so results drop straight into the LLM context.
- `tools/__init__.py` holds the single source of truth (`TOOL_REGISTRY` +
  `TOOL_MAP`). The registry is also rendered into the system prompt so the LLM
  knows which tools exist and their parameters.
- ClickUp hierarchy: **Workspace(Team) → Space → Folder → List → Task**.
  Navigation is always resolved top-down before acting.
- Task intelligence flags (is_complete, overdue, due_soon) are computed by the
  tool layer, not the LLM.

### 6b. Bitbucket path — `backend/bitbucket/`

- `bitbucket_http.py` — shared HTTP layer. Auth = HTTP Basic
  `BITBUCKET_EMAIL : BITBUCKET_API_TOKEN`; base URL `https://api.bitbucket.org/2.0`;
  workspace default from `BITBUCKET_WORKSPACE`.
- `bitbucket_tools.py` — the registry (`BITBUCKET_TOOL_MAP`, 64 tools) + system
  prompt build. This is the single source of truth: name, description, params.
- Tool modules: `workspace_tools.py`, `repos_tools.py`, `pr_tools.py`,
  `pipeline_tools.py`, `deployment_tools.py`, `branch_tools.py`,
  `property_tools.py`, `webhook_tools.py`, `bitbucket_time_utils.py`.
- Human-gated tools (merge/approve/decline/environment-delete) only execute when
  `confirmed=True`; otherwise they return `needs_confirmation`.
- All errors return a consistent shape:
  `{"error": true, "message": "...", "status_code": ...}`.

```
                    Agent loop          Tool layer          External REST API
   system prompt ──► LLM ──► JSON ──► _dispatch ──► bitbucket_http/requests
   (tool catalogue)                                          │
                          registry (TOOL_MAP)          https://api.bitbucket.org/2.0/
                          name → fn                     workspace/repos/pipelines/...
```

---

## 7. Backend ↔ Frontend Connection (REST Only)

The frontend never talks to ClickUp/Bitbucket or the LLM directly.

1. **Vite dev proxy** (`frontend/vite.config.js`) forwards:
   - `/api/*`      → `http://localhost:8000`  (ClickUp path)
   - `/bitbucket/*`→ `http://localhost:8000`  (Bitbucket path)
2. **Frontend API layer**:
   - `frontend/src/api.js`               → ClickUp (dashboard, chat, health, reset)
   - `frontend/src/bitbucketApi.js`      → Bitbucket (all tool-backed methods)
3. **CORS** is configured server-side to allow the frontend origins.
4. **Response shapes**:
   - Dashboard endpoints return structured JSON consumed directly by the React
     tables/cards.
   - Chat endpoints return `{ "reply": "...", "tool_calls": [...] }` so the UI can
     show the agent's reasoning/tool activity.

```
 React (5173)                        FastAPI (8000)                    External API
 ─────────────────                 ───────────────────              ─────────────────
 api.js / bitbucketApi.js   ──proxied──►  /api/*  &  /bitbucket/*   ──► ClickUp/Bitbucket
   (fetch /api, /bitbucket)                │
                                           ├─ dashboard endpoints  = read aggregation
                                           ├─ CRUD endpoints        = direct tool calls
                                           └─ /chat endpoints       = agent loop (+LLM)
```

**Two ways the frontend can get work done:**

| Acting directly (REST) | Acting via the agent (LLM) |
|------------------------|-----------------------------|
| Frontend calls a specific `/api` or `/bitbucket` endpoint (e.g. list PRs, create env). | Frontend sends one message to `/chat`; the backend runs the agent loop, calls multiple tools, and returns a natural-language reply. |
| Deterministic, single purpose. | Multi-step, conversational, handles ambiguity. |

---

## 8. Config & Secrets — `backend/config/settings.py`

`.env` loaded once; supplies credentials to the LLM and to both API clients.

| Variable | Used by | Purpose |
|---|---|---|
| `CLICKUP_API_TOKEN` | ClickUp tools | ClickUp auth header |
| `BITBUCKET_EMAIL` | Bitbucket HTTP | HTTP Basic auth (user) |
| `BITBUCKET_API_TOKEN` | Bitbucket HTTP | HTTP Basic auth (app password/token) |
| `BITBUCKET_WORKSPACE` | Bitbucket tools | default workspace slug (`approlabs001`) |
| `BITBUCKET_BASE_URL` | Bitbucket HTTP | `https://api.bitbucket.org/2.0` |
| `AWS_ACCESS_KEY` / `AWS_SECRET_KEY` | LLM | Bedrock credentials |
| `AWS_REGION` | LLM | region (`ap-south-1`) |
| `AWS_BEDROCK_MODEL_ID` | LLM | `global.anthropic.claude-sonnet-4-6` |

---

## 9. Diagram Checklist (for the draw.io file)

Flow to render top-down:

1. **User** opens the web app → two app sections (ClickUp / Bitbucket).
2. **Frontend** (React/Vite, 5173) → calls backend over HTTP `/api` & `/bitbucket`.
3. **Backend** (FastAPI, 8000) → two mounted paths.
4. For each path show the **sub-flow**:
   - **Direct REST**: route → Python tool → external REST API → JSON → frontend.
   - **Agent chat**: `/chat` route → agent loop (Observe→Think→Act) → shared
     LLM (Bedrock/Claude) → tool dispatch → external REST API → reply.
5. Show the **shared LLM** node feeding BOTH agent loops.
6. Show the **tool registry** (TOOL_MAP) between dispatch and the HTTP layer.
7. Show the **external APIs**: ClickUp Cloud REST and Bitbucket Cloud REST 2.0.
8. Show the **human-gate** (confirmation modal) before destructive actions.
9. Show **.env → settings** supplying secrets to the LLM + both API clients.

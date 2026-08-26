# CORE — ClickUp AI Agent: End-to-End Architecture

## 1. The Concept

This project is an **agentic AI system** that lets a team leader manage their ClickUp
workspace using plain English instead of clicking through the UI.

The core idea is the classic **Agent Loop** pattern:

```
LLM = the BRAIN (decides *what* to do)
Tools = the HANDS (deterministic Python functions that actually do it)
Orchestrator = the LOOP that connects brain ↔ hands
```

The LLM (AWS Bedrock / Claude) never touches ClickUp directly. It can only emit
JSON instructions like `{"tool": "get_workspaces", "args": {}}`. The orchestrator
executes those instructions against the real ClickUp REST API and feeds the results
back into the conversation until Claude has enough information to write a final answer.

---

## 2. Project Layout

```
WorkSpace_Integration/
├── main.py                     # Interactive CLI entry point
├── config/
│   └── settings.py             # Loads .env → ClickUp token, AWS creds, model ID
├── agent/
│   ├── llm.py                  # BedrockLLM — the ONLY place LLM calls happen
│   └── orchestrator.py         # Observe → Think → Act loop
├── tools/
│   ├── __init__.py             # TOOL_REGISTRY + TOOL_MAP (the tool catalogue)
│   ├── workspace_tools.py      # Hierarchy navigation (7 tools)
│   ├── task_tools.py           # Task CRUD + classification (7 tools)
│   ├── comment_tools.py        # Read/post comments (2 tools)
│   └── dashboard_tools.py      # Aggregation + rendering (2 tools)
└── dashboard/
    └── live_dashboard.py       # Standalone dashboard (no LLM involved)
```

---

## 3. End-to-End Flow

### Step 0 — Startup (`main.py`)

1. `python main.py` prints a banner and creates **one** `Orchestrator()` instance.
2. The Orchestrator constructor:
   - Builds a singleton `BedrockLLM` client (boto3 → `bedrock-runtime`).
   - Calls `_build_system_prompt()` which injects **all 18 tools** (name,
     description, parameter schema from `TOOL_REGISTRY`) into the system prompt.
   - Initialises empty conversation `history`.
3. A REPL loop starts: read user input → `agent.run(input)` → print reply.
   (`exit` quits, `reset` clears history.)

### Step 1 — Observe

The user message is appended to `history` as
`{"role": "user", "content": "..."}`.

### Step 2 — Think

The full `history` + `system` prompt are sent to Bedrock via
`BedrockLLM.chat()` (`invoke_model`, Anthropic Messages format, temperature=0).
Claude responds with either:
- a **tool-call JSON block**, or
- a **plain-text final answer**.

### Step 3 — Act (parse)

`_extract_tool_call()` regex-scans the reply for:

1. ```` ```json {"tool": "...", "args": {...}} ``` ```` blocks
2. bare `{...}` JSON objects containing a `"tool"` key

If nothing matches → this was the final answer; loop ends.

### Step 4 — Act (dispatch)

`_dispatch(tool_name, args)` looks up `TOOL_MAP[name]["fn"]` and calls it with
the args. Exceptions are caught and returned as `{"error": ...}` so the LLM can
self-correct instead of crashing the loop.

Tool results are serialised to JSON and pushed onto history as:
- assistant turn (Claude's tool-call text)
- user turn: `[TOOL RESULT: <name>] <json>`

Then the loop repeats (back to Step 2) — Claude sees the result and decides
whether another tool call or the final answer comes next.

### Step 5 — Terminate

- Plain-text reply returned and printed by `main.py`.
- Safety cap: **MAX_ITERATIONS = 12** prevents infinite loops; a fallback
  message is returned if exceeded.

### Example trace: *"Show me the dashboard"*

```
iter 1: Claude → get_workspaces()            → [team list]
iter 2: Claude → get_team_tasks(team_id)     → all tasks (paginated)
iter 3: Claude → classify_tasks(tasks)       → completed/pending/overdue/due_soon
iter 4: Claude → build_dashboard(classified) → summary + per-dev stats
iter 5: Claude → render_dashboard_text(dash) → formatted report
iter 6: Claude → final plain-text answer  ← loop ends
```

---

## 4. Tool Layer Details

Every tool returns **plain JSON-serialisable dicts/lists** — never raw HTTP
responses — so results can be dropped straight into the LLM context.

### workspace_tools.py — hierarchy navigation
ClickUp model: **Workspace(Team) → Space → Folder → List → Task**
`_get()` helper wraps `requests.get` with auth headers + 30s timeout.
Tools: `get_authorized_user`, `get_workspaces`, `get_spaces`,
`get_folders`, `get_lists`, `get_folderless_lists`, `get_workspace_members`.

### task_tools.py — CRUD + intelligence
- `_fmt_task()` normalises raw ClickUp tasks and computes derived flags:
  - `is_complete` — status ∈ {complete, closed, done, finished}
  - `overdue` — not complete AND due_date < now
  - `due_soon_5min` — not complete AND due within 300 seconds
- Pagination handled automatically (100 tasks/page loop in
  `get_tasks` / `get_team_tasks`).
- `classify_tasks()` buckets tasks into completed/pending/overdue/due_soon.
- Writers: `create_task`, `update_task_status`, `update_task`.

### comment_tools.py
`get_task_comments` / `post_task_comment` (optional `notify_all`).

### dashboard_tools.py — pure aggregation, zero API calls
- `build_dashboard(classified)` builds per-developer breakdowns, upcoming-24h
  list, overdue list, 5-minute alerts.
- `render_dashboard_text(dashboard)` formats it as a human-readable report.

### tools/__init__.py — the registry
Each entry = `{name, fn, description, params}`. This single source of truth
serves double duty:
1. Rendered into the system prompt (so Claude knows what exists),
2. Used by `TOOL_MAP` for dispatch.

**Adding a new tool = add function + one registry entry. Nothing else changes.**

---

## 5. Standalone Dashboard (no AI path)

`dashboard/live_dashboard.py` bypasses the agent entirely — proof the tool layer
works independently of the LLM:

```
gather_all_tasks()
  for each workspace → spaces → folders/lists (incl. folderless) → get_tasks()
→ classify_tasks() → build_dashboard() → print report
→ writes dashboard/dashboard_snapshot.json
```

---

## 6. Configuration & Secrets

`.env` → loaded once by `config/settings.py`:

| Variable | Purpose |
|---|---|
| `CLICKUP_API_TOKEN` | Personal API token (`pk_...`), sent as `Authorization` header |
| `AWS_ACCESS_KEY` / `AWS_SECRET_KEY` | Bedrock credentials |
| `REGION` | AWS region |
| `AWS_BEDROCK_MODEL_ID` | e.g. `global.anthropic.claude-sonnet-4-6` |

---

## 7. Key Design Decisions

| Decision | Why |
|---|---|
| JSON-in-markdown protocol instead of native tool-use API | Simple, provider-agnostic, easy to debug in logs |
| Temperature = 0 | Deterministic routing decisions |
| Tools catch their own errors | LLM sees the error and retries/self-corrects |
| Max 12 iterations | Bounded cost, no runaway loops |
| History as flat user/assistant messages with `[TOOL RESULT: ...]` turns | Keeps everything in one transcript |
| Singleton LLM client | One boto3 client per process |
| Registry pattern | Extensible without touching orchestrator code |

---

## 8. Sequence Diagram

```
 User          main.py        Orchestrator       Bedrock(Claude)      ClickUp API
  │               │                 │                   │                  │
  │ "show dash"   │                 │                   │                  │
  ├──────────────►│  run(msg)       │                   │                  │
  │               ├────────────────►│ chat(history+sys) │                  │
  │               │                 ├──────────────────►│                  │
  │               │                 │  ◄─ json{tool}────┤                  │
  │               │                 │ _dispatch("get_team_tasks")          │
  │               │                 ├──────────────────────────────────────►│
  │               │                 │◄──────────── tasks ──────────────────┤
  │               │                 │ result appended to history           │
  │               │                 ├──────────────────►│ (next iteration) │
  │               │                 │  ...more tools... │                  │
  │               │                 │  ◄─ plain text ───┤  ← FINAL ANSWER  │
  │◄──────────────┤◄────────────────┤                   │                  │
```

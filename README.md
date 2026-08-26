# ClickUp AI Agent

AI-powered ClickUp orchestrator using **AWS Bedrock (Claude)** as the brain and **19 purpose-built tools** to interact with the ClickUp API — no human required for task creation, classification, or dashboard reporting.

---

## Architecture

```
User message
    │
    ▼
ORCHESTRATOR LOOP  (Observe → Think → Act)
    │
    ├── LLM decides which tool to call (AWS Bedrock / Claude)
    │
    ├── TOOL CALLS (19 tools across 4 modules)
    │       ├── workspace_tools.py   → navigate hierarchy
    │       ├── task_tools.py        → CRUD + classify tasks
    │       ├── comment_tools.py     → read/post comments
    │       └── dashboard_tools.py  → build & render dashboard
    │
    └── Reply back to user
```

### File Structure

```
clickup_agent/
├── main.py                        # Interactive CLI
├── requirements.txt
├── .env.example                   # Copy to .env and fill in values
│
├── config/
│   └── settings.py                # Loads .env, exposes constants
│
├── agent/
│   ├── llm.py                     # BedrockLLM — all LLM calls go here
│   └── orchestrator.py            # Observe→Think→Act loop
│
├── tools/
│   ├── __init__.py                # TOOL_REGISTRY (19 tools)
│   ├── workspace_tools.py         # Workspace / Space / Folder / List
│   ├── task_tools.py              # Task CRUD + classifier
│   ├── comment_tools.py           # Comments
│   └── dashboard_tools.py        # Aggregation & rendering
│
└── dashboard/
    └── live_dashboard.py          # Standalone dashboard CLI
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
# ClickUp
CLICKUP_API_TOKEN=pk_xxxxxxxxxxxxxxxxxxxx

# AWS Bedrock
AWS_ACCESS_KEY=your_aws_access_key
AWS_SECRET_KEY=your_aws_secret_key
REGION=us-east-1
AWS_BEDROCK_MODEL_ID=global.anthropic.claude-sonnet-4-6
```

> Get your ClickUp token: **Settings → Apps → Generate Token**

### 3. Enable the Bedrock model in AWS

Go to **AWS Console → Bedrock → Model Access** and enable `Claude Sonnet` for your region.

---

## Running

### Interactive Agent

```bash
python main.py
```

Example prompts:
```
You: Show me all my workspaces
You: What tasks are overdue right now?
You: Create a task "Fix login bug" in list 901234567 assigned to user 12345, priority High
You: Show me the full team dashboard
You: What pending tasks does Alice have?
```

### Standalone Dashboard

```bash
python dashboard/live_dashboard.py
```

Walks the entire workspace hierarchy, fetches all tasks, and prints:
- Summary counts (total / completed / pending / overdue / due-soon)
- Per-developer breakdown
- Upcoming 24h deadlines
- Overdue & 5-minute alerts

Also writes `dashboard/dashboard_snapshot.json`.

---

## Tool Reference (19 tools)

| # | Tool | Module | Description |
|---|------|--------|-------------|
| 1 | `get_authorized_user` | workspace | Who is authenticated |
| 2 | `get_workspaces` | workspace | All workspaces |
| 3 | `get_spaces` | workspace | Spaces in a workspace |
| 4 | `get_folders` | workspace | Folders in a space |
| 5 | `get_lists` | workspace | Lists in a folder |
| 6 | `get_folderless_lists` | workspace | Lists without a folder |
| 7 | `get_workspace_members` | workspace | Members for assignment |
| 8 | `get_tasks` | task | All tasks in a list |
| 9 | `get_task` | task | Single task details |
| 10 | `get_team_tasks` | task | Tasks across workspace |
| 11 | `classify_tasks` | task | Completed/pending/overdue/due-soon |
| 12 | `create_task` | task | Create a task (AI-driven) |
| 13 | `update_task_status` | task | Change task status |
| 14 | `update_task` | task | Generic task update |
| 15 | `get_task_comments` | comment | Read task comments |
| 16 | `post_task_comment` | comment | Post a comment |
| 17 | `build_dashboard` | dashboard | Structured dashboard dict |
| 18 | `render_dashboard_text` | dashboard | Human-readable report |
| 19 | `get_team_tasks` *(alias)* | task | Workspace-wide task fetch |

---

## How the Orchestrator Works

The `Orchestrator` class runs a bounded loop (max 12 iterations):

1. **Observe** — appends user message to conversation history
2. **Think** — sends history to AWS Bedrock Claude; LLM decides what to do
3. **Act** — if LLM returns a `{"tool": ..., "args": ...}` JSON block, the tool is executed and its result is fed back as the next message
4. **Repeat** — until LLM returns a plain-text final answer

```python
from agent import Orchestrator

agent = Orchestrator()
print(agent.run("Show me the dashboard for workspace 90120456"))
```

---

## Security Notes

- Never commit `.env` — add it to `.gitignore`
- Use AWS IAM roles with least-privilege Bedrock permissions in production
- ClickUp token is a personal API token (`pk_...`) — treat it like a password

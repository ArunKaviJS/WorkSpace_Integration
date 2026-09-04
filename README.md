# AI Command Center

Full-stack AI-powered developer operations hub that orchestrates **ClickUp** (project management), **Bitbucket** and **GitLab** (source control) through natural-language agents backed by **AWS Bedrock (Claude Sonnet 4.6)** and **~100 purpose-built tools** — all managed from a single React web UI. GitLab additionally ships a **dedicated AI code-review agent** that grades a merge request or commit range `good` / `need to check` / `bad` with a risk factor.

---

## Architecture

```
React Frontend (Vite, port 5173)
        │
        ▼
FastAPI Backend (port 8000)
        │
        ├── /api/*  ──►  ClickUp Agent (~30 tools)
        │                   └── ClickUp REST API
        │
        ├── /bitbucket/*  ──►  Bitbucket Agent (~50 tools)
        │                        └── Bitbucket Cloud REST API
        │
        └── /gitlab/*     ──►  GitLab Agent (~27 tools, python-gitlab SDK)
                                ├── GitLab REST API
                                └── GitLab Review Agent (single deterministic
                                    Bedrock call → structured verdict)

        All agents share a single AWS Bedrock LLM (Claude Sonnet 4.6)
        using the Observe → Think → Act orchestrator loop.
```

### Core AI Loop (shared by both agents)

1. **Observe** — append user message to conversation history
2. **Think** — send history to Claude via AWS Bedrock; LLM returns a `{"tool", "args"}` JSON block or a plain-text answer
3. **Act** — execute the tool against ClickUp / Bitbucket API, feed result back
4. **Repeat** — up to 12 iterations until a final answer is produced

Sensitive operations (delete, approve, merge, decline) require explicit user confirmation.

---

## File Structure

```
WorkSpace_Integration/
├── backend/
│   ├── main.py                       # ClickUp interactive CLI
│   ├── server.py                     # FastAPI app (mounts both agent route groups)
│   ├── requirements.txt
│   ├── .env.example
│   ├── config/
│   │   └── settings.py               # Central env loading
│   ├── agent/
│   │   ├── llm.py                    # BedrockLLM wrapper (shared singleton)
│   │   └── orchestrator.py           # ClickUp Observe→Think→Act loop
│   ├── tools/                        # ClickUp tools (~30 modules)
│   │   ├── __init__.py               # TOOL_REGISTRY
│   │   ├── workspace_tools.py, task_tools.py, comment_tools.py,
│   │   ├── dashboard_tools.py, search_tools.py, bulk_tools.py,
│   │   ├── tag_tools.py, relation_tools.py, list_tools.py,
│   │   ├── attachment_tools.py, time_tracking_tools.py,
│   │   ├── status_time_tools.py, member_tools.py, chat_tools.py,
│   │   ├── docs_tools.py, http.py, time_utils.py
│   ├── bitbucket/                    # Bitbucket agent + tools (~50 modules)
│   │   ├── bitbucket_agent.py        # Bitbucket Observe→Think→Act loop
│   │   ├── bitbucket_routes.py       # /bitbucket/* FastAPI endpoints
│   │   ├── bitbucket_http.py         # Shared HTTP + response normalizers
│   │   ├── bitbucket_tools.py        # BITBUCKET_TOOL_REGISTRY
│   │   ├── bitbucket_prompts.py      # Bitbucket system prompts
│   │   ├── repos_tools.py, pr_tools.py, branch_tools.py,
│   │   ├── pipeline_tools.py, deployment_tools.py,
│   │   ├── webhook_tools.py, property_tools.py,
│   │   ├── workspace_tools.py, live_dashboard.py,
│   │   └── bitbucket_time_utils.py
│   ├── gitlab_int/                   # GitLab agent + tools (python-gitlab SDK)
│   │   ├── gitlab_client.py          # python-gitlab singleton + GitLabError
│   │   ├── gitlab_agent.py           # GitLab Observe→Think→Act loop
│   │   ├── review_agent.py           # DEDICATED AI code-review agent
│   │   ├── gitlab_routes.py          # /gitlab/* FastAPI endpoints
│   │   ├── gitlab_tools.py           # GITLAB_TOOL_REGISTRY
│   │   ├── gitlab_prompts.py         # GitLab system prompts
│   │   ├── project_tools.py, mr_tools.py, branch_tools.py,
│   │   ├── pipeline_tools.py
│   │   └── gitlab_time_utils.py
│   └── dashboard/
│       └── live_dashboard.py         # Standalone dashboard CLI + snapshot
│
└── frontend/
    ├── package.json
    ├── vite.config.js                # Dev proxy /api & /bitbucket → :8000
    └── src/
        ├── main.jsx, App.jsx, Shell.jsx (hash router)
        ├── api.js, bitbucketApi.js
        ├── styles.css, bitbucket.css
        ├── api.js, bitbucketApi.js, gitlabApi.js
        ├── styles.css, bitbucket.css, gitlab.css
        ├── pages/
        │   ├── BitbucketDashboard.jsx
        │   └── GitLabDashboard.jsx
        └── components/
            ├── ChatBot.jsx, BitbucketChatBot.jsx, GitLabChatBot.jsx
            ├── TaskCard.jsx, TaskModal.jsx, Countdown.jsx, ConfirmModal.jsx
            ├── bb/ (Workspaces, Repos, Files, Branches, PullRequests,
            │        Pipelines, Deployments panels + FormModal + ui)
            └── gl/ (Projects, Branches, MergeRequests panels +
                     ReviewModal + ui)
```

---

## Features

### ClickUp Agent (~30 tools)

- Workspace navigation & hierarchy (workspaces, spaces, folders, lists)
- Task CRUD, bulk operations, custom fields, status updates
- Search (by type, tag, keyword)
- Comments, tags, task relationships & dependencies
- Attachments, time tracking, time-in-status reporting
- Member & assignee resolution
- Chat channels & Docs (ClickUp v3 API)
- Dashboard with summary stats, per-developer breakdown, overdue/due-soon alerts

### Bitbucket Agent (~50 tools)

- Workspaces & repositories (CRUD, default reviewers, collaborator invites)
- Source code access (files, commits, branches, push)
- Pull requests (diff, comments, tasks, approve / decline / merge, pending reviews)
- Branches & branch permissions
- Pipelines (list, run, steps, logs, automated failure analysis)
- Deployments & environments (CRUD)
- Webhooks & application properties
- Live dashboard with PR review notifications & urgency highlighting

### GitLab Agent (~27 tools, `python-gitlab` SDK)

- Auth is token-only (`GITLAB_TOKEN` + `GITLAB_URL`) — no interactive login, no OAuth dance
- Projects, commits, files and arbitrary ref comparison
- Merge requests: list, diff (`changes`), notes, create
- **Every write is human-gated** (`confirmed=True` required, agent can never self-confirm): project create/delete, branch create/delete, MR create, MR comment, approve / unapprove / merge / close. Read tools (list/get/diff/compare/file/commit/pipeline/review) are not gated.
- Any GitLab rejection is surfaced in plain language — `403` → "you don't have permission (role/scope) …", `401` → bad/expired token, plus unreachable-host / not-found messages
- Pipelines & jobs (read-only)
- **Dedicated AI code-review agent** (`review_agent.py`): one deterministic Bedrock call over the *previous vs proposed* diff returns a structured verdict —
  `rating` (`good` / `need_to_check` / `bad`), `risk_factor` (`low` / `medium` / `high`), `risk_score` 0–100, `summary`, `findings[]` (severity-ranked), `good_points[]`, `recommendation`. Callable for a merge request, a single commit vs its parent, or a `from..to` commit range.

### Web UI (React + Vite)

- Hash-based navigation between ClickUp, Bitbucket and GitLab dashboards
- **ClickUp dashboard**: summary cards, overdue sidebar, due-in-5-min / due-next-24h, per-developer view, task modal, embedded chatbot
- **Bitbucket dashboard**: tabbed panels (Overview, Workspaces, Repositories, Files, Branches, Pull Requests, Pipelines, Deployments), PR review notifications, commit feed, embedded chatbot
- **GitLab dashboard**: tabbed panels (Overview, Projects, Branches, Merge Requests). Overview shows recent commits + MR review notifications (urgency-highlighted) with inline **Approve / Merge** (confirm-modal gated) and a **🔍 AI Review** button that opens a verdict card (rating badge, risk meter, ranked findings, good points). Embedded GitLab chatbot with the same gating.

---

## Setup

### Prerequisites

- Python 3.13+
- Node.js 18+
- AWS account with Bedrock access (`Claude Sonnet` model enabled)
- ClickUp API token
- Bitbucket app credentials (token, client ID, client secret)
- GitLab personal access token with `api` scope + your GitLab base URL

### Backend

```bash
cd backend
pip install -r requirements.txt
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

# Bitbucket
BITBUCKET_API_TOKEN=your_bitbucket_token
BITBUCKET_WORKSPACE=your_workspace
BITBUCKET_CLIENT_ID=your_client_id
BITBUCKET_CLIENT_SECRET=your_client_secret

# GitLab (personal access token with `api` scope — no interactive login)
GITLAB_URL=https://gitlab.com
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
```

> The GitLab tab stays dormant until `GITLAB_TOKEN` is set; the rest of the app runs without it.

### Frontend

```bash
cd frontend
npm install
```

---

## Running

Both servers must run concurrently — the Vite dev server proxies API requests to the FastAPI backend.

### Backend

```bash
cd backend
uvicorn server:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm run dev        # http://localhost:5173
```

### CLI alternatives

```bash
# ClickUp interactive CLI
python backend/main.py

# Standalone dashboard
python backend/dashboard/live_dashboard.py
```

### Build for production

```bash
cd frontend
npm run build     # output in dist/
npm run preview   # preview production build
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite 6, JSX, CSS |
| Backend | Python 3.13, FastAPI, Uvicorn |
| AI | AWS Bedrock (Claude Sonnet 4.6) |
| ClickUp API | REST v2 / v3 |
| Bitbucket API | REST v2 |
| GitLab API | `python-gitlab` SDK (token auth) |
| HTTP client | `requests` (Python) |
| Build | Vite |

---

## Security Notes

- Never commit `.env` — it is listed in `.gitignore`
- Use AWS IAM roles with least-privilege Bedrock permissions in production
- ClickUp token (`pk_...`) and Bitbucket credentials should be treated as passwords
- Sensitive tool operations (delete, approve, merge, decline) require explicit user confirmation and refuse to self-confirm

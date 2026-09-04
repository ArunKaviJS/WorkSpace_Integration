"""
backend/server.py
FastAPI server exposing the ClickUp AI Agent to the React frontend.

Endpoints:
    GET  /api/health          → liveness check
    GET  /api/dashboard       → full dashboard JSON (summary + per-dev + overdue + due soon)
    POST /api/chat            → send a message to the agent chatbot
    POST /api/chat/reset      → clear conversation history

Run:
    cd backend
    uvicorn server:app --reload --port 8000
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent.orchestrator import Orchestrator
from bitbucket.bitbucket_routes import router as bitbucket_router
from gitlab_int.gitlab_routes import router as gitlab_router
from dashboard.live_dashboard import gather_all_tasks
from tools.dashboard_tools import build_dashboard, render_dashboard_text
from tools.task_tools import classify_tasks

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ClickUp AI Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orch = Orchestrator()

# Bitbucket routes (separate module — mounted alongside ClickUp routes)
app.include_router(bitbucket_router)

# GitLab routes (separate module — mounted alongside ClickUp & Bitbucket routes)
app.include_router(gitlab_router)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ChatIn(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/dashboard")
def dashboard() -> dict:
    """Walk the whole ClickUp workspace and return a structured dashboard."""
    try:
        tasks = gather_all_tasks()
        classified = classify_tasks(tasks)
        dash = build_dashboard(classified)
        dash["report_text"] = render_dashboard_text(dash)
        return dash
    except Exception as exc:  # noqa: BLE001
        logger.exception("Dashboard build failed")
        return {"error": str(exc)}


@app.post("/api/chat")
def chat(body: ChatIn) -> dict:
    """Send a user message to the AI agent; returns the final reply."""
    try:
        reply = orch.run(body.message)
        return {
            "reply": reply,
            "tool_calls": orch.tool_calls_log,
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Chat failed")
        return {"reply": f"Agent error: {exc}", "tool_calls": []}


@app.post("/api/chat/reset")
def reset_chat() -> dict:
    orch.reset()
    return {"status": "reset"}

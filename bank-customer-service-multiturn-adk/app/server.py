"""FastAPI server for the demo chat UI.

Importing app.conversation first is deliberate: it initializes telemetry before
anything touches ADK.
"""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import conversation, db

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Meridian Bank — demo customer service chat")


class LoginRequest(BaseModel):
    customer_id: str


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ResetRequest(BaseModel):
    session_id: str


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/customers")
async def customers():
    return db.list_customers()


@app.post("/api/login")
async def login(req: LoginRequest):
    try:
        return await conversation.create_chat_session(req.customer_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/chat")
async def chat(req: ChatRequest):
    try:
        return await conversation.run_turn(req.session_id, req.message)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc
    except Exception as exc:  # surface a readable reason in the UI bubble
        detail = str(exc)
        if "API key" in detail:
            detail = (
                "The model rejected the request: no Google API key. "
                "Set GOOGLE_API_KEY in .env and restart."
            )
        logger.exception("chat turn failed")
        raise HTTPException(status_code=500, detail=detail[:300]) from exc


@app.post("/api/reset")
async def reset(req: ResetRequest):
    return {"dropped": conversation.drop_session(req.session_id)}

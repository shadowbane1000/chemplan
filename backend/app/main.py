from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app import chat, retro

app = FastAPI(title="chemplan", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class PlanRequest(BaseModel):
    smiles: str = Field(..., min_length=1, max_length=500)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    history: list[ChatMessage]
    canvas_smiles: str | None = None
    plan: dict[str, Any] | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/plan")
def plan(req: PlanRequest) -> dict:
    try:
        return retro.plan(req.smiles)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/chat")
def chat_endpoint(req: ChatRequest) -> StreamingResponse:
    history = [{"role": m.role, "content": m.content} for m in req.history]
    return StreamingResponse(
        chat.stream_chat(history, req.canvas_smiles, req.plan),
        media_type="application/x-ndjson",
    )

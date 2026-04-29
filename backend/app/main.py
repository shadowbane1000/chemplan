from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import retro

app = FastAPI(title="chemplan", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class PlanRequest(BaseModel):
    smiles: str = Field(..., min_length=1, max_length=500)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/plan")
def plan(req: PlanRequest) -> dict:
    try:
        return retro.plan(req.smiles)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

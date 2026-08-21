"""
ADE Extraction inference server.

Loads Qwen2.5-7B + QLoRA adapter once at startup, then serves requests.

Run:
    uvicorn llm.ade_api:app --host 0.0.0.0 --port 8001

Endpoints:
    POST /extract   { "sentence": "..." }  ->  { drug, adverse_effect, sentence }
    GET  /health    ->  { status, model_loaded }
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from llm.ade_model import AdeModel

_model = AdeModel()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _model.load()
    yield


app = FastAPI(title="ADE Extraction API", version="1.0.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ExtractRequest(BaseModel):
    sentence: str


class ExtractResponse(BaseModel):
    drug: Optional[str] = None
    adverse_effect: Optional[str] = None
    sentence: Optional[str] = None
    raw: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/extract", response_model=ExtractResponse)
def extract(req: ExtractRequest) -> ExtractResponse:
    if not req.sentence.strip():
        raise HTTPException(status_code=422, detail="sentence must not be empty")
    result = _model.extract(req.sentence)
    return ExtractResponse(**result)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model_loaded": _model.loaded}

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine
from .routers import chat, documents


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.index_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="AI Knowledge Assistant", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(chat.router)


@app.get("/api/health")
def health():
    """Reports whether Ollama is reachable and the required models are pulled."""
    status = {
        "api": "ok",
        "llm_model": settings.llm_model,
        "embedding_model": settings.embedding_model,
        "ollama": "unreachable",
        "missing_models": [],
    }
    try:
        resp = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=3)
        resp.raise_for_status()
        installed = {m["name"] for m in resp.json().get("models", [])}
        installed |= {n.split(":")[0] for n in installed}
        status["ollama"] = "ok"
        status["missing_models"] = [
            m for m in (settings.llm_model, settings.embedding_model)
            if m not in installed and f"{m}:latest" not in installed
        ]
    except Exception:
        pass
    return status

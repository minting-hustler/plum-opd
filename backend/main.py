import os
import json
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run RAG indexing on startup."""
    logger.info("Starting up — initialising RAG index...")
    try:
        from services.rag.indexer import ensure_indexed
        await ensure_indexed()
        logger.info("RAG index ready.")
    except Exception as e:
        logger.error(f"RAG indexing failed (non-fatal): {e}")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Plum OPD Adjudicator API",
    version="1.0.0",
    lifespan=lifespan,
)

allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")
allowed_origins = [o.strip() for o in allowed_origins_raw.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers import documents, claims, adjudicate, members

app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(claims.router, prefix="/claims", tags=["claims"])
app.include_router(adjudicate.router, prefix="/claims", tags=["adjudicate"])
app.include_router(members.router, prefix="/members", tags=["members"])


@app.get("/health")
async def health():
    return {"status": "ok"}

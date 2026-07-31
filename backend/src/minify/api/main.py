"""FastAPI entrypoint.

Per design.md, this is meant to be the single place concrete adapters
(SQLite repository, LLM provider, job runner, etc.) get wired together via
dependency injection — modules themselves never construct their own
dependencies. Only `/health` exists so far (M0); real routes and DI wiring
land in M8.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from minify.config import get_settings

settings = get_settings()

app = FastAPI(title="Minify API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}

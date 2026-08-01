"""FastAPI entrypoint.

Per design.md, this is the single place concrete adapters (SQLite
repository, LLM provider, job runner, etc.) get wired together via
dependency injection — see `api/dependencies.py` for the actual provider
functions; modules themselves never construct their own dependencies.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from minify.api.routes import router
from minify.config import get_settings

settings = get_settings()

app = FastAPI(title="Minify API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}

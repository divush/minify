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

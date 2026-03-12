from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routers import projects_router

app = FastAPI(title="Manju Platform API", version="0.1.0")
static_root = Path(__file__).resolve().parent / "static"
static_root.mkdir(parents=True, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(projects_router)
app.mount("/assets", StaticFiles(directory=static_root), name="assets")

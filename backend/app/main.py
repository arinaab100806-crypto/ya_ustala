from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .bootstrap import ensure_admin
from .config import LANGUAGES, judge_label, judge_mode
from .database import Base, SessionLocal, engine
from .routers import admin, arena, auth, contest_reports, contests, dashboard, fairplay, organizations, problems, submissions, teams
from .schema_sync import ensure_columns
from .schemas import SystemOut
from .seed import ensure_seed_categories, seed_if_empty


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_columns(engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
        ensure_seed_categories(db)
        ensure_admin(db)
    finally:
        db.close()
    yield


app = FastAPI(title="ВолгаКод", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(organizations.router, prefix="/api")
app.include_router(teams.router, prefix="/api")
app.include_router(problems.router, prefix="/api")
app.include_router(submissions.router, prefix="/api")
app.include_router(contests.router, prefix="/api")
app.include_router(fairplay.router, prefix="/api")
app.include_router(contest_reports.router, prefix="/api")
app.include_router(arena.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/system", response_model=SystemOut)
def system() -> SystemOut:
    return SystemOut(judge_mode=judge_mode(), judge_label=judge_label(), languages=list(LANGUAGES))

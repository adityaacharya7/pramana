from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import Settings, load_settings
from .db import Base, check_deployment, make_engine, make_sessionmaker
from .routers import auth, cases, demo, evidence, graph, ledger, review

log = logging.getLogger("pramana")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    if settings.evidence_store == "file":
        settings.evidence_dir.mkdir(parents=True, exist_ok=True)
    engine = make_engine(settings.db_url, settings.serverless)
    if settings.manage_schema:
        Base.metadata.create_all(engine)
    sessionmaker = make_sessionmaker(engine)

    # Serverless instances never create schema or seed on a cold start: many
    # can start at once. They check the database was prepared by the CLI.
    with sessionmaker() as db:
        fresh = check_deployment(db, settings.build, create=settings.manage_schema)
        if settings.is_demo and settings.auto_seed:
            from .seed import is_seeded, seed_demo
            if fresh or not is_seeded(db):
                summary = seed_demo(db, settings)
                log.warning("Demo build seeded from synthetic dataset: %s", summary)

    app = FastAPI(
        title="PRAMANA",
        version=__version__,
        description="Find the Connection. Show the Evidence. Test the Lead. "
                    "Investigation support: the system proposes, the officer decides.",
    )
    app.state.settings = settings
    app.state.sessionmaker = sessionmaker
    app.state.engine = engine
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=False,
                       allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"],
                       expose_headers=["X-Evidence-SHA256"])

    for r in (auth.router, cases.router, evidence.router, ledger.router, review.router, graph.router):
        app.include_router(r)
    if settings.is_demo:
        app.include_router(demo.router)

    @app.get("/health", tags=["meta"])
    def health():
        return {"status": "ok", "build": settings.build, "version": __version__}

    return app

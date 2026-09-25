import logging

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_analytics import router as analytics_router
from app.api.routes_auth import router as auth_router
from app.api.routes_auth import seed_default_users
from app.api.routes_cases import router as cases_router
from app.api.routes_integrations import router as integrations_router
from app.api.routes_intel import router as intel_router
from app.api.routes_live import router as live_router
from app.api.routes_trace import router as trace_router
from app.auth.dependencies import get_current_user
from app.auth.ratelimit import limiter
from app.config import get_settings
from app.db.neo4j_client import load_seed_labels_into_neo4j
from app.db.postgres import Base, SessionLocal, engine, ensure_additive_schema
from app.live.monitor import live_monitor
from app.worker.reaper import reap_stale_traces
from scripts.seed_demo import seed_if_empty

def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Say plainly what happened and when to retry.

    A bare 429 reads like a fault in the system. Naming the limit tells an
    investigator this is a deliberate cap, not the trace failing.
    """
    return JSONResponse(
        status_code=429,
        content={
            "detail": (
                f"Rate limit reached ({exc.detail}). This is a deliberate cap to protect "
                f"the shared block-explorer quota, not a failure - wait a moment and retry."
            )
        },
    )


app = FastAPI(
    title="LedgerLens — Real-Time Crypto Fraud Attribution System",
    description="Traces victim-reported wallet addresses to the nearest known exchange/VASP.",
    version="0.1.0",
)

# Rate limiting is registered before the routers so the handler is in place
# for every route that declares a limit.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"^https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.get("/", tags=["system"])
def root():
    return {
        "status": "online",
        "service": "LedgerLens Forensics API",
        "version": "0.1.0",
        "documentation": "/docs",
        "health": "/health",
        "message": "API backend is fully operational.",
    }


@app.get("/health", tags=["system"])
def health_check():
    return {"status": "ok", "service": "LedgerLens"}


authenticated = [Depends(get_current_user)]

app.include_router(auth_router)  # login is necessarily public
app.include_router(trace_router, dependencies=authenticated)
app.include_router(cases_router, dependencies=authenticated)
app.include_router(analytics_router, dependencies=authenticated)
app.include_router(intel_router, dependencies=authenticated)
app.include_router(integrations_router)  # mixed: NCRP intake is a public-facing webhook, see below
# The live stream authenticates itself: a browser's EventSource cannot send
# an Authorization header, so the token arrives in the query string and is
# checked inside the route. Every other route on this router declares the
# usual dependency.
app.include_router(live_router)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_additive_schema()
    load_seed_labels_into_neo4j()
    db = SessionLocal()
    try:
        seed_default_users(db)
        # A restart is the clearest evidence that whatever was mid-trace is
        # not running any more. Clearing those rows here stops the interface
        # showing a spinner for work that stopped before the process began.
        reaped = reap_stale_traces(db)
        if reaped:
            logging.getLogger(__name__).info(
                f"Marked {reaped} trace(s) as failed - their worker did not survive")
    finally:
        db.close()

    # A fresh clone should show a working, populated product on first run,
    # not an empty shell someone has to fill in before it means anything -
    # so an empty database is seeded with a demonstration caseload covering
    # every feature. A database that already holds a single real case is
    # never touched. Best-effort: a seeding failure must not stop the API
    # from starting.
    try:
        if seed_if_empty():
            logging.getLogger(__name__).info(
                "Database was empty - seeded the demonstration caseload")
    except Exception:  # noqa: BLE001 - startup must survive this either way
        logging.getLogger(__name__).exception("Demo data seeding failed; continuing with an empty database")

    # A finished trace is not the end of the story - the wallets in it keep
    # moving. This watches the ones somebody is actually looking at.
    live_monitor.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    live_monitor.stop()


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return JSONResponse(status_code=204, content=None)


# ── Static Frontend Serving (Unified Deployment) ──────────────────────────────
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
if os.path.isdir(static_dir):
    assets_dir = os.path.join(static_dir, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.middleware("http")
    async def spa_middleware(request: Request, call_next):
        accept = request.headers.get("accept", "")
        path = request.url.path
        if (
            request.method == "GET"
            and "text/html" in accept
            and not path.startswith(("/docs", "/redoc", "/openapi.json", "/health", "/auth/login"))
            and os.path.exists(os.path.join(static_dir, "index.html"))
        ):
            return FileResponse(os.path.join(static_dir, "index.html"))
        return await call_next(request)

    @app.get("/{full_path:path}")
    async def serve_static_fallback(full_path: str):
        file_path = os.path.join(static_dir, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        index_file = os.path.join(static_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return JSONResponse(status_code=404, content={"detail": "Not found"})


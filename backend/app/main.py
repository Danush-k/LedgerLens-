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
from app.api.routes_trace import router as trace_router
from app.auth.dependencies import get_current_user
from app.auth.ratelimit import limiter
from app.config import get_settings
from app.db.neo4j_client import load_seed_labels_into_neo4j
from app.db.postgres import Base, SessionLocal, engine, ensure_additive_schema

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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

authenticated = [Depends(get_current_user)]

app.include_router(auth_router)  # login is necessarily public
app.include_router(trace_router, dependencies=authenticated)
app.include_router(cases_router, dependencies=authenticated)
app.include_router(analytics_router, dependencies=authenticated)
app.include_router(intel_router, dependencies=authenticated)
app.include_router(integrations_router)  # mixed: NCRP intake is a public-facing webhook, see below


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_additive_schema()
    load_seed_labels_into_neo4j()
    db = SessionLocal()
    try:
        seed_default_users(db)
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}

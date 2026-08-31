from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_cases import router as cases_router
from app.api.routes_integrations import router as integrations_router
from app.api.routes_trace import router as trace_router
from app.config import get_settings
from app.db.neo4j_client import load_seed_labels_into_neo4j
from app.db.postgres import Base, engine

app = FastAPI(
    title="Real-Time Crypto Fraud Attribution System",
    description="Traces victim-reported wallet addresses to the nearest known exchange/VASP.",
    version="0.1.0",
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trace_router)
app.include_router(cases_router)
app.include_router(integrations_router)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    load_seed_labels_into_neo4j()


@app.get("/health")
def health():
    return {"status": "ok"}

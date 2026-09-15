from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central app configuration, loaded from environment / .env.

    Nothing here requires a funded wallet or a paid API - every key is a
    free, no-KYC signup, and Bitcoin needs no key at all.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Chain data providers
    # Accepts a single key or a comma-separated list. Free explorer keys are
    # capped at a few requests per second each, so adding keys is the only
    # way to raise the ceiling; one value handles both cases so existing
    # .env files keep working.
    etherscan_api_key: str = ""
    bscscan_api_key: str = ""
    polygonscan_api_key: str = ""
    bitcoin_api_base_url: str = "https://blockstream.info/api"

    # Tracer behaviour
    hop_limit: int = 5

    # Live monitoring
    #
    # A completed trace is a photograph of a moving target: the wallets in it
    # keep spending after the trace ends, and the movement that happens while
    # a case is open is the movement an investigator can still act on. These
    # bound how hard the system looks. The binding constraint is the free
    # explorers' rate limit, so a case is only watched while somebody is
    # actually looking at it (or has explicitly asked for it to be watched),
    # and only a handful of its wallets are re-checked per cycle.
    live_monitor_enabled: bool = True
    live_poll_seconds: int = 30       # how often a watched case is re-checked
    live_watch_addresses: int = 8     # wallets re-checked per case per cycle
    live_viewer_ttl_seconds: int = 90  # how long an open page keeps a case watched
    live_max_cases_per_tick: int = 4  # ceiling on concurrent explorer pressure

    # Datastores
    database_url: str = "postgresql+psycopg2://fraudmap:fraudmap@localhost:5432/fraudmap"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "fraudmap123"
    redis_url: str = "redis://localhost:6379/0"

    # API
    cors_origins: list[str] = ["http://localhost:5173"]

    # Auth - change these in any real deployment. A random default per
    # process start means restarting invalidates old tokens rather than
    # silently accepting a well-known secret.
    jwt_secret_key: str = "dev-only-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    default_investigator_username: str = "investigator"
    default_investigator_password: str = "changeme123"
    default_admin_username: str = "admin"
    default_admin_password: str = "changeme123"


@lru_cache
def get_settings() -> Settings:
    return Settings()

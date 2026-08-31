from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central app configuration, loaded from environment / .env.

    Nothing here requires a funded wallet or a paid API - every key is a
    free, no-KYC signup, and Bitcoin needs no key at all.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Chain data providers
    etherscan_api_key: str = ""
    bscscan_api_key: str = ""
    polygonscan_api_key: str = ""
    bitcoin_api_base_url: str = "https://blockstream.info/api"

    # Tracer behaviour
    hop_limit: int = 5

    # Datastores
    database_url: str = "postgresql+psycopg2://fraudmap:fraudmap@localhost:5432/fraudmap"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "fraudmap123"
    redis_url: str = "redis://localhost:6379/0"

    # API
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()

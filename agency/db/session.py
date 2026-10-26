import os

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine


def database_url() -> str:
    """DATABASE_URL from the environment (or a local .env file). Never hardcoded."""
    load_dotenv()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set (run `make env`)")
    return url


def make_engine(url: str | None = None) -> Engine:
    return create_engine(url or database_url(), pool_pre_ping=True)

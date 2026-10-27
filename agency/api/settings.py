import os
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path

from dotenv import load_dotenv

from agency.db.session import database_url


@dataclass(frozen=True)
class Settings:
    database_url: str
    config_path: Path = Path("config/agency.yaml")
    env: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))
    cors_origins: tuple[str, ...] = ("http://localhost:3001", "http://127.0.0.1:3001")
    workspaces_root: Path | None = None
    chat_token_delay: float = 0.02  # seconds between streamed words (stub responder)

    @property
    def base_dir(self) -> Path:
        """Repo root: prompt files in config are relative to it."""
        return self.config_path.resolve().parent.parent


def load_settings() -> Settings:
    load_dotenv()
    settings = Settings(database_url=database_url())
    origins = os.environ.get("AGENCY_CORS_ORIGINS")
    if origins:
        settings = replace(settings, cors_origins=tuple(o.strip() for o in origins.split(",")))
    return settings

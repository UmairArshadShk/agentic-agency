import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

from agency.db.session import database_url

load_dotenv()


@pytest.fixture(scope="session")
def migrated_engine() -> Iterator[Engine]:
    """A throwaway database migrated to head with Alembic, dropped afterwards."""
    base = make_url(database_url())
    name = f"agency_test_{uuid.uuid4().hex[:8]}"
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    test_url = base.set(database=name).render_as_string(hide_password=False)

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", test_url.replace("%", "%%"))
    command.upgrade(cfg, "head")

    engine = create_engine(test_url)
    yield engine
    engine.dispose()
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    admin.dispose()

import asyncio

import pytest

from app.config import settings
from app.db.database import Base, engine
from app.http_client import shutdown_http_client, startup_http_client
from app.services.graph_defaults import wrap_graph_with_trigger_end

# The app no longer calls Base.metadata.create_all on startup (Alembic owns the
# schema). Relax the startup migration gate under test so the TestClient
# lifespan does not refuse to boot before this fixture has migrated the DB.
settings.migration_check_strict = False


def _stamp_alembic_head() -> None:
    """Stamp the DB at Alembic head so the startup migration gate sees it current.

    The app no longer calls create_all; startup gates on the DB being at head.
    Under SQLite the historical migrations render some UUID columns with a type
    affinity SQLite mishandles on round-trip, so the harness builds the schema
    from the models (create_all — the sanctioned option) and then stamps the
    Alembic version so the gate is satisfied. The full migration chain is
    verified separately against a clean database.
    """
    from pathlib import Path

    try:
        from alembic import command
        from alembic.config import Config

        backend_dir = Path(__file__).resolve().parents[1]
        cfg = Config(str(backend_dir / "alembic.ini"))
        cfg.set_main_option("script_location", str(backend_dir / "alembic"))
        cfg.set_main_option("sqlalchemy.url", settings.database_url)
        command.stamp(cfg, "head")
    except Exception:  # noqa: BLE001 — stamping is best-effort for the gate
        pass


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    # Alembic owns the schema in production, but SQLite tests build it from the
    # models (create_all) to avoid SQLite-only UUID affinity artifacts in the
    # historical migrations. We stamp Alembic head so the startup gate passes.
    Base.metadata.create_all(bind=engine)
    _stamp_alembic_head()
    yield


@pytest.fixture(scope="session", autouse=True)
def init_http_client():
    asyncio.run(startup_http_client())
    yield
    asyncio.run(shutdown_http_client())


def valid_graph(nodes: list, edges: list | None = None, **kwargs) -> dict:
    """Build a graph that satisfies Trigger → … → End validation."""
    return wrap_graph_with_trigger_end(nodes, edges or [], **kwargs)
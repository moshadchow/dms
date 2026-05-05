"""
migrations/env.py
─────────────────
Alembic migration environment.

Run from the backend/ directory:
    alembic upgrade head          # apply all migrations
    alembic revision --autogenerate -m "description"  # generate new migration
    alembic downgrade -1          # roll back one step
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

# ── Make sure backend/ is on sys.path so all modules are importable ──
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ── Import every model module so SQLModel.metadata is fully populated ──
# Alembic's autogenerate compares metadata against the live DB schema;
# any model not imported here will be invisible to --autogenerate.
import users.models        # noqa: F401  — User, Role, Permission, link tables
import categories.models   # noqa: F401  — Category
import directories.models  # noqa: F401  — Directory (self-referencing)
import documents.models    # noqa: F401  — Document

from core.config import settings  # noqa: E402  (after sys.path insert)

# ── Alembic Config object ─────────────────────
config = context.config

# Override sqlalchemy.url with the value from .env so alembic.ini
# never needs a hard-coded production URL.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Apply logging config from alembic.ini if present
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# SQLModel.metadata contains all tables registered via table=True
target_metadata = SQLModel.metadata


# ── Migration runners ─────────────────────────

def run_migrations_offline() -> None:
    """
    Run migrations without a live DB connection.
    Generates SQL statements to stdout instead of executing them.
    Useful for reviewing changes before applying to production.

    Usage:  alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Render column-level CHECK constraints, etc.
        render_as_batch=False,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations against a live DB connection.
    This is the normal path used by `alembic upgrade head`.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,   # NullPool is recommended for migrations
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,          # detect column type changes
            compare_server_default=True, # detect default value changes
        )
        with context.begin_transaction():
            context.run_migrations()


# ── Entry point ───────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
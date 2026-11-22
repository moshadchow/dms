"""
migrations/env.py
─────────────────
Alembic migration environment.

Run from the backend/ directory:
    alembic upgrade head          # apply all migrations
    alembic revision --autogenerate -m 'description'  # generate new migration
    alembic downgrade -1          # roll back one step
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool, text
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
import user_levels.models  # noqa: F401  — UserLevel
import workflow.models     # noqa: F401  — WorkflowDefinition, WorkflowStep, WorkflowStepApprover
import notifications.models  # noqa: F401  — EmailNotification
import antivirus.models      # noqa: F401  — AntivirusScan
import company_profile.models  # noqa: F401  — Company
import memos.models          # noqa: F401  — Memo
import backups.models        # noqa: F401  — CompanyBackup
import storage_usage.models  # noqa: F401  — SystemSetting
import db_backups.models     # noqa: F401  — DBBackup
import audit.models          # noqa: F401  — AuditEvent
import correspondence.models  # noqa: F401  — Correspondence
import rbac.models           # noqa: F401  — RBAC models

from core.config import settings  # noqa: E402  (after sys.path insert)

# ── Alembic Config object ─────────────────────
config = context.config

# Override sqlalchemy.url with the value from .env so alembic.ini
# never needs a hard-coded production URL.
config.set_main_option('sqlalchemy.url', settings.DATABASE_URL)

# Apply logging config from alembic.ini if present
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# SQLModel.metadata contains all tables registered via table=True
target_metadata = SQLModel.metadata


# ── Migration runners ─────────────────────────

def run_migrations_offline() -> None:
    '''
    Run migrations without a live DB connection.
    Generates SQL statements to stdout instead of executing them.
    Useful for reviewing changes before applying to production.

    Usage:  alembic upgrade head --sql
    '''
    url = config.get_main_option('sqlalchemy.url')
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
        # Render column-level CHECK constraints, etc.
        render_as_batch=False,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    '''
    Run migrations against a live DB connection.
    This is the normal path used by alembic upgrade head.
    '''
    url = config.get_main_option('sqlalchemy.url')
    connectable = create_engine(
        url,
        poolclass=pool.NullPool,   # NullPool is recommended for migrations
        connect_args={'options': '-csearch_path=public'},
    )

    with connectable.connect() as connection:
        # Create public schema if it doesn't exist (some PG instances use template0)
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
        connection.execute(text("SET search_path TO public"))
        # SQLAlchemy 2.0 "begin once" leaves an implicit transaction open after
        # the two execute() calls above. Commit it now so that alembic's own
        # context.begin_transaction() starts a clean transaction whose commit
        # persists the migration DDL. Without this, the connection close rolls
        # back the implicit transaction and undoes every CREATE TABLE.
        connection.commit()
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
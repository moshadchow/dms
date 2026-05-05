from typing import Generator

from sqlmodel import Session, SQLModel, create_engine

from core.config import settings

# ──────────────────────────────────────────────
# Engine
# ──────────────────────────────────────────────

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,          # SQL logging — True in dev, False in prod
    pool_pre_ping=True,             # Detect stale connections before use
    pool_size=10,
    max_overflow=20,
)


# ──────────────────────────────────────────────
# Table creation (used only outside Alembic)
# In production, migrations are managed by Alembic.
# ──────────────────────────────────────────────

def create_db_and_tables() -> None:
    """
    Create all tables defined via SQLModel metadata.
    Call this on startup during development.
    In production, run: `alembic upgrade head` instead.
    """
    # Import all models so SQLModel metadata is populated before create_all
    import categories.models   # noqa: F401
    import directories.models  # noqa: F401
    import documents.models    # noqa: F401
    import users.models        # noqa: F401

    SQLModel.metadata.create_all(engine)


# ──────────────────────────────────────────────
# Session dependency
# ──────────────────────────────────────────────

def get_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session per request.

    Usage in a router:
        @router.get("/items")
        def list_items(session: Session = Depends(get_session)):
            ...
    """
    with Session(engine) as session:
        yield session

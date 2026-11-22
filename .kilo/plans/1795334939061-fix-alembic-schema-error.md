# Plan: Fix Alembic "no schema has been selected to create in" Error

## Root Cause

The PostgreSQL user (`postgres` in the default DATABASE_URL) lacks CREATE permission on the default schema (`public`), or the `public` schema doesn't exist in the target database. When Alembic tries to create its `alembic_version` table, PostgreSQL returns `InvalidSchemaName: no schema has been selected to create in`.

## Solution Options

### Option 1: Set search_path in SQLAlchemy Engine (Recommended)
Add `connect_args={'options': '-csearch_path=public'}` to the engine in `migrations/env.py`. This ensures the connection uses the `public` schema explicitly.

### Option 2: Grant Permissions on Database (DBA Task)
Run as PostgreSQL superuser:
```sql
GRANT CREATE ON SCHEMA public TO postgres;
-- Or create a dedicated schema:
CREATE SCHEMA dms AUTHORIZATION postgres;
GRANT ALL ON SCHEMA dms TO postgres;
-- Then set search_path to 'dms' in connection
```

### Option 3: Configure Alembic to Use Specific Schema
Set `version_table_schema` in `context.configure()` to a schema the user owns.

## Implementation Plan

### Step 1: Modify `migrations/env.py`
Add `connect_args` to the `engine_from_config` call to set `search_path=public`:

```python
connectable = engine_from_config(
    config.get_section(config.config_ini_section, {}),
    prefix='sqlalchemy.',
    poolclass=pool.NullPool,
    connect_args={'options': '-csearch_path=public'},  # ADD THIS
)
```

### Step 2: Also Update `core/database.py` for Consistency
Add the same `connect_args` to the main application engine so runtime connections behave identically:

```python
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args={'options': '-csearch_path=public'},  # ADD THIS
)
```

### Step 3: Test the Fix
1. Run `alembic upgrade head` from `backend/` directory
2. Verify `alembic_version` table is created
3. Run application and verify database operations work

## Risk Assessment
- **Low risk**: Only adds connection parameter, no schema changes
- **Rollback**: Remove `connect_args` if issues arise
- **Compatibility**: Works with existing PostgreSQL setup

## Validation
- `alembic upgrade head` succeeds without schema error
- Application starts and can create/query tables
- No regression in existing migrations
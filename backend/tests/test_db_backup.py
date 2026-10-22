"""
PostgreSQL database backup service tests (spec 36).

`db_backups/` is deployment-scoped — deliberately no `company_id` anywhere,
because one pg_dump holds every tenant's rows in a single file. The isolation
risk here is therefore *role* isolation, not tenant isolation: every route
must stay SuperAdmin-only, and a company ADMIN reaching a dump would be a
cross-tenant leak. Those cases get their own file (repo convention for
isolation regressions).

No test ever shells out: conftest points PG_DUMP_PATH at a file that cannot
exist, and every success path monkeypatches `db_backups.service._run_pg_dump`
— the single seam between our code and the child process.
"""

import logging
import subprocess
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlmodel import Session, select

import db_backups.scheduler
import db_backups.service
from audit.models import AuditLog
from db_backups.models import DbBackupRun, DbBackupStatus, DbBackupTrigger
from db_backups.service import (
    DB_BACKUP_ENABLED_KEY,
    DB_BACKUP_INTERVAL_KEY,
    DB_BACKUP_RETENTION_KEY,
    DbDumpResult,
    _build_command,
    _build_env,
    _parse_database_url,
    _redact,
    _set_setting,
    get_db_backup_root,
    run_due_db_backups,
)
from core.config import get_settings

# Every route on the module — the authorization matrix runs over all of them.
ROUTES = [
    ("get", "/api/v1/db-backups", None),
    ("post", "/api/v1/db-backups/run", None),
    ("get", "/api/v1/db-backups/settings", None),
    ("put", "/api/v1/db-backups/settings",
     {"enabled": True, "interval_hours": 24, "retention_count": 7}),
    ("get", "/api/v1/db-backups/999999", None),
    ("get", "/api/v1/db-backups/999999/download", None),
]

PAYLOAD = b"FAKE-PG-DUMP-CUSTOM-ARCHIVE"
VERSION = "pg_dump (PostgreSQL) 18.3"

# A password only ever reaches tests through a URL we control, so the
# redaction assertions are deterministic regardless of the real DATABASE_URL.
FAKE_URL = "postgresql+psycopg2://postgres:L3akMe-Not-Secret@db.internal:5432/dms_db"
FAKE_PASSWORD = "L3akMe-Not-Secret"


def _call(test_client, method, path, headers, json_body=None):
    kwargs = {"headers": headers}
    if json_body is not None:
        kwargs["json"] = json_body
    return getattr(test_client, method)(path, **kwargs)


def _ok_dump(payload: bytes = PAYLOAD, version: str = VERSION):
    """A stand-in for `_run_pg_dump` that writes the target file and reports
    success. It must write to the EXACT path it is handed: `_execute` renames
    `<name>.dump.part` into place only when the file is really there."""

    def fake(target_path: Path) -> DbDumpResult:
        target_path.write_bytes(payload)
        return DbDumpResult(returncode=0, stderr="", duration_ms=7, version=version)

    return fake


def _set_policy(engine, enabled: bool, hours: int = 24, retention: int = 7) -> None:
    """Write the schedule policy straight into `system_settings` — the same
    store `update_settings` uses, without its audit side effect."""
    with Session(engine) as session:
        _set_setting(session, DB_BACKUP_ENABLED_KEY,
                     "true" if enabled else "false", "test policy")
        _set_setting(session, DB_BACKUP_INTERVAL_KEY, str(hours), "test policy")
        _set_setting(session, DB_BACKUP_RETENTION_KEY, str(retention), "test policy")
        session.commit()


def _seed_runs(engine, n: int = 3) -> list[int]:
    """Insert finished runs directly. `ids[0]` is the NEWEST (the service
    orders by created_at desc, id desc)."""
    ids: list[int] = []
    with Session(engine) as session:
        for i in range(n):
            row = DbBackupRun(
                status=DbBackupStatus.SUCCESS,
                trigger=DbBackupTrigger.MANUAL,
                dump_path=f"dms_seed_{i}.dump",
                dump_size_bytes=100 + i,
                created_at=datetime.utcnow() - timedelta(minutes=i),
            )
            session.add(row)
            session.flush()
            ids.append(row.id)
        session.commit()
    return ids


class _override_settings:
    """Swap one or more `settings` values for the duration of a `with` block,
    restoring them even when the body raises."""

    def __init__(self, **overrides):
        self.overrides = overrides
        self._saved: dict = {}

    def __enter__(self):
        from core.config import settings

        for key, value in self.overrides.items():
            self._saved[key] = getattr(settings, key)
            setattr(settings, key, value)
        return self

    def __exit__(self, *exc):
        from core.config import settings

        for key, value in self._saved.items():
            setattr(settings, key, value)
        return False


def _settings_with(url: str):
    """A settings stand-in whose DATABASE_URL we control, so `_redact` has a
    known password to strip regardless of what the real .env holds."""

    from core.config import settings

    class _Shim:
        def __getattr__(self, name):
            if name == "DATABASE_URL":
                return url
            return getattr(settings, name)

    return _Shim()


class TestAuthorization:
    def test_unauthenticated_is_401_on_every_route(self, client, seeded_data):
        test_client, _, _ = client
        for method, path, body in ROUTES:
            resp = _call(test_client, method, path, headers=None, json_body=body)
            assert resp.status_code == 401, f"{method.upper()} {path} → {resp.status_code}"

    def test_company_admin_rejected_on_every_route(self, client, seeded_data, auth_headers):
        """The load-bearing guard. `User.is_admin()` lets ADMIN sail past
        rbac_middleware (its ROUTE_PERMISSION_MAP entries never run), so
        `SuperAdminUser` is the only thing standing between a tenant admin
        and a file containing every company's rows."""
        test_client, _, _ = client
        for who in ("admin", "other_admin"):
            for method, path, body in ROUTES:
                resp = _call(test_client, method, path, auth_headers[who], body)
                assert resp.status_code == 403, (
                    f"{who}: {method.upper()} {path} → {resp.status_code}"
                )

    def test_maker_rejected_on_every_route(self, client, seeded_data, auth_headers):
        test_client, _, _ = client
        for method, path, body in ROUTES:
            resp = _call(test_client, method, path, auth_headers["maker"], body)
            assert resp.status_code == 403, f"{method.upper()} {path} → {resp.status_code}"

    def test_superadmin_allowed_on_every_route(self, client, seeded_data, auth_headers,
                                               monkeypatch):
        """SUPERADMIN may *read and run* — the deliberate exception to the
        'SUPERADMIN mutations are 403' invariant, because this resource is
        deployment-scoped and only they can administer the whole deployment."""
        test_client, engine, _ = client
        monkeypatch.setattr(db_backups.service, "_run_pg_dump", _ok_dump())

        assert _call(test_client, "get", ROUTES[2][1],
                     auth_headers["superadmin"]).status_code == 200
        assert _call(test_client, "put", ROUTES[3][1],
                     auth_headers["superadmin"], ROUTES[3][2]).status_code == 200
        assert _call(test_client, "get", ROUTES[0][1],
                     auth_headers["superadmin"]).status_code == 200

        run = test_client.post("/api/v1/db-backups/run", headers=auth_headers["superadmin"])
        assert run.status_code == 200 and run.json()["status"] == "success"
        run_id = run.json()["id"]

        assert test_client.get(
            f"/api/v1/db-backups/{run_id}", headers=auth_headers["superadmin"]
        ).status_code == 200
        assert test_client.get(
            f"/api/v1/db-backups/{run_id}/download", headers=auth_headers["superadmin"]
        ).status_code == 200
        # Unknown ids answer 404 for everyone allowed to look — never 403,
        # so existence is not leaked to callers who lack the role.
        assert _call(test_client, "get", ROUTES[4][1],
                     auth_headers["superadmin"]).status_code == 404

    def test_no_company_id_in_run_payload(self, client, seeded_data, auth_headers,
                                          monkeypatch):
        """A dump spans every tenant; a `company_id` on it would be a lie
        about who owns the data — and a bug waiting to leak."""
        test_client, _, _ = client
        monkeypatch.setattr(db_backups.service, "_run_pg_dump", _ok_dump())

        body = test_client.post(
            "/api/v1/db-backups/run", headers=auth_headers["superadmin"]
        ).json()
        assert "company_id" not in body
        listing = test_client.get(
            "/api/v1/db-backups", headers=auth_headers["superadmin"]
        ).json()
        assert "company_id" not in listing
        assert all("company_id" not in item for item in listing["items"])


class TestRun:
    def test_successful_dump_records_everything(self, client, seeded_data, auth_headers,
                                                monkeypatch):
        test_client, engine, _ = client
        monkeypatch.setattr(db_backups.service, "_run_pg_dump", _ok_dump())

        resp = test_client.post("/api/v1/db-backups/run", headers=auth_headers["superadmin"])
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "success"
        assert body["trigger"] == "manual"
        assert body["triggered_by"] == seeded_data["superadmin_id"]
        assert body["triggered_by_name"] == "Super Administrator"
        assert body["dump_path"].endswith(".dump")
        assert body["dump_size_bytes"] == len(PAYLOAD)
        assert body["duration_ms"] == 7
        assert body["pg_dump_version"] == VERSION
        assert body["error_message"] is None
        assert body["started_at"] and body["finished_at"]

        # The bytes are on disk under DB_BACKUP_ROOT, and the `.part`
        # staging file was renamed into place (never left behind).
        root = get_db_backup_root()
        dump = root / body["dump_path"]
        assert dump.is_file()
        assert dump.read_bytes() == PAYLOAD
        assert list(root.glob("*.part")) == []

        with Session(engine) as session:
            runs = session.exec(select(DbBackupRun)).all()
            assert len(runs) == 1
            assert runs[0].status == DbBackupStatus.SUCCESS
            assert runs[0].triggered_by == seeded_data["superadmin_id"]

            audits = session.exec(
                select(AuditLog).where(AuditLog.action == "create_db_backup")
            ).all()
            assert len(audits) == 1
            assert audits[0].module == "db_backups"
            assert audits[0].company_id is None          # deployment-scoped
            assert audits[0].user_id == seeded_data["superadmin_id"]

    def test_missing_binary_is_failed_data_not_error(self, client, seeded_data, auth_headers):
        """conftest points PG_DUMP_PATH at a file that cannot exist, so the
        real `_run_pg_dump` raises FileNotFoundError → DbDumpError. Failure
        is data: HTTP 200 with status=failed, the app keeps serving."""
        test_client, engine, _ = client
        resp = test_client.post("/api/v1/db-backups/run", headers=auth_headers["superadmin"])
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"
        assert "pg_dump executable not found" in body["error_message"]
        assert body["dump_path"] is None

        with Session(engine) as session:
            assert session.exec(select(DbBackupRun)).one().status == DbBackupStatus.FAILED
            failures = session.exec(
                select(AuditLog).where(AuditLog.action == "db_backup_failed")
            ).all()
            assert len(failures) == 1
            assert failures[0].is_success is False
            assert failures[0].company_id is None

        # A failed attempt never leaves a partial file behind.
        root = get_db_backup_root()
        if root.exists():
            assert list(root.glob("*.dump")) == []
            assert list(root.glob("*.part")) == []

        resp = test_client.get("/api/v1/db-backups", headers=auth_headers["superadmin"])
        assert resp.status_code == 200

    def test_nonzero_exit_keeps_the_fatal_line(self, client, seeded_data, auth_headers,
                                               monkeypatch):
        """pg_dump prints its real error LAST — `_summarize_stderr` keeps that
        line (truncated) instead of an empty 'failed' message."""
        test_client, engine, _ = client

        def fake(target_path):
            target_path.write_bytes(b"partial junk")  # must not survive
            return DbDumpResult(
                returncode=1,
                stderr="pg_dump: building index\npg_dump: error: aborting because of server version mismatch",
                duration_ms=4,
                version=None,
            )

        monkeypatch.setattr(db_backups.service, "_run_pg_dump", fake)
        body = test_client.post(
            "/api/v1/db-backups/run", headers=auth_headers["superadmin"]
        ).json()
        assert body["status"] == "failed"
        assert "server version mismatch" in body["error_message"]

        root = get_db_backup_root()
        assert list(root.glob("*.part")) == []
        assert list(root.glob("*.dump")) == []
        with Session(engine) as session:
            run = session.exec(select(DbBackupRun)).one()
            assert run.dump_path is None and run.dump_size_bytes is None

    def test_timeout_is_recorded_as_failed(self, client, seeded_data, auth_headers,
                                           monkeypatch):
        """Exercise the REAL `except subprocess.TimeoutExpired` branch inside
        `_run_pg_dump` by swapping this module's `subprocess` reference for a
        stub — nothing else in the process is affected."""
        class _Stub:
            TimeoutExpired = subprocess.TimeoutExpired

            @staticmethod
            def run(*args, **kwargs):
                raise subprocess.TimeoutExpired(
                    cmd="pg_dump", timeout=get_settings().PG_DUMP_TIMEOUT_SECONDS
                )

        monkeypatch.setattr(db_backups.service, "subprocess", _Stub)
        test_client, engine, _ = client
        resp = test_client.post("/api/v1/db-backups/run", headers=auth_headers["superadmin"])
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"
        assert "timed out" in body["error_message"]
        assert "was killed" in body["error_message"]
        with Session(engine) as session:
            assert session.exec(select(DbBackupRun)).one().status == DbBackupStatus.FAILED

    def test_conflict_when_already_running(self, client, seeded_data, auth_headers):
        test_client, engine, _ = client
        with Session(engine) as session:
            session.add(DbBackupRun(status=DbBackupStatus.RUNNING,
                                    trigger=DbBackupTrigger.SCHEDULED))
            session.commit()

        resp = test_client.post("/api/v1/db-backups/run", headers=auth_headers["superadmin"])
        assert resp.status_code == 409
        assert "already running" in resp.json()["detail"].lower()

        # The guard must not have created a second row.
        with Session(engine) as session:
            assert len(session.exec(select(DbBackupRun)).all()) == 1

    def test_back_to_back_runs_are_uniquely_named(self, client, seeded_data, auth_headers,
                                                  monkeypatch):
        """Two dumps inside the same second must not collide on the
        timestamped filename (the service suffixes them)."""
        test_client, _, _ = client
        monkeypatch.setattr(db_backups.service, "_run_pg_dump", _ok_dump())
        ids = set()
        for _ in range(2):
            resp = test_client.post("/api/v1/db-backups/run",
                                    headers=auth_headers["superadmin"])
            assert resp.status_code == 200 and resp.json()["status"] == "success"
            ids.add(resp.json()["id"])
        assert len(ids) == 2

        root = get_db_backup_root()
        names = sorted(p.name for p in root.glob("*.dump"))
        assert len(names) == 2 and len(set(names)) == 2


class TestListDetail:
    def test_pagination_and_order(self, client, seeded_data, auth_headers):
        test_client, engine, _ = client
        ids = _seed_runs(engine, 3)

        resp = test_client.get("/api/v1/db-backups", headers=auth_headers["superadmin"],
                               params={"skip": 0, "limit": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3 and data["page"] == 1 and data["limit"] == 2
        assert len(data["items"]) == 2
        assert data["next_page"] == 2 and data["prev_page"] is None
        # Newest first: seed ids[0] carries the newest created_at.
        assert data["items"][0]["id"] == ids[0]
        assert data["items"][1]["id"] == ids[1]

        resp = test_client.get("/api/v1/db-backups", headers=auth_headers["superadmin"],
                               params={"skip": 2, "limit": 2})
        data = resp.json()
        assert data["page"] == 2
        assert [item["id"] for item in data["items"]] == [ids[2]]
        assert data["next_page"] is None and data["prev_page"] == 1

    def test_unknown_detail_and_download_are_404(self, client, seeded_data, auth_headers):
        test_client, _, _ = client
        for path in ("/api/v1/db-backups/999999",
                     "/api/v1/db-backups/999999/download"):
            resp = test_client.get(path, headers=auth_headers["superadmin"])
            assert resp.status_code == 404, path
            assert resp.json()["detail"] == "Database backup run not found"

    def test_seed_rows_cannot_be_downloaded(self, client, seeded_data, auth_headers):
        """`dump_path` pointing at a file that was never written resolves to
        the explicit retention 404, not a stack trace."""
        test_client, engine, _ = client
        ids = _seed_runs(engine, 1)
        resp = test_client.get(
            f"/api/v1/db-backups/{ids[0]}/download", headers=auth_headers["superadmin"]
        )
        assert resp.status_code == 404
        assert "retention" in resp.json()["detail"].lower()


class TestSettings:
    def test_defaults(self, client, seeded_data, auth_headers):
        test_client, _, _ = client
        resp = test_client.get("/api/v1/db-backups/settings",
                               headers=auth_headers["superadmin"])
        assert resp.status_code == 200
        # Same defaults seed.py writes when it runs.
        assert resp.json() == {"enabled": True, "interval_hours": 24, "retention_count": 7}

    def test_update_roundtrip_and_audit(self, client, seeded_data, auth_headers):
        test_client, engine, _ = client
        resp = test_client.put(
            "/api/v1/db-backups/settings",
            headers=auth_headers["superadmin"],
            json={"enabled": False, "interval_hours": 12, "retention_count": 3},
        )
        assert resp.status_code == 200
        assert resp.json() == {"enabled": False, "interval_hours": 12, "retention_count": 3}

        resp = test_client.put(
            "/api/v1/db-backups/settings",
            headers=auth_headers["superadmin"],
            json={"enabled": True, "interval_hours": 48, "retention_count": 5},
        )
        assert resp.status_code == 200
        assert resp.json() == {"enabled": True, "interval_hours": 48, "retention_count": 5}

        # A second read proves the values round-tripped through storage.
        resp = test_client.get("/api/v1/db-backups/settings",
                               headers=auth_headers["superadmin"])
        assert resp.json() == {"enabled": True, "interval_hours": 48, "retention_count": 5}

        with Session(engine) as session:
            audits = session.exec(
                select(AuditLog).where(AuditLog.action == "update_db_backup_settings")
            ).all()
            assert len(audits) == 2
            assert all(a.module == "db_backups" for a in audits)
            assert all(a.company_id is None for a in audits)
            assert all(a.user_id == seeded_data["superadmin_id"] for a in audits)

    def test_validation_rejects_out_of_range(self, client, seeded_data, auth_headers):
        test_client, _, _ = client
        bad_bodies = [
            {"enabled": True, "interval_hours": 0, "retention_count": 5},
            {"enabled": True, "interval_hours": 169, "retention_count": 5},
            {"enabled": True, "interval_hours": 24, "retention_count": 0},
            {"enabled": True, "interval_hours": 24, "retention_count": 101},
        ]
        for body in bad_bodies:
            resp = test_client.put("/api/v1/db-backups/settings",
                                   headers=auth_headers["superadmin"], json=body)
            assert resp.status_code == 422, f"{body} → {resp.status_code}"

    def test_corrupt_int_falls_back_to_default(self, client, seeded_data, auth_headers):
        """`system_settings` is a free-form store; a hand-edited garbage value
        must not 500 the endpoint."""
        test_client, engine, _ = client
        with Session(engine) as session:
            _set_setting(session, DB_BACKUP_INTERVAL_KEY, "not-a-number", "corrupt")
            session.commit()
        resp = test_client.get("/api/v1/db-backups/settings",
                               headers=auth_headers["superadmin"])
        assert resp.status_code == 200
        assert resp.json()["interval_hours"] == 24


class TestRetention:
    def test_prunes_files_not_rows(self, client, seeded_data, auth_headers, monkeypatch):
        test_client, engine, _ = client
        monkeypatch.setattr(db_backups.service, "_run_pg_dump", _ok_dump())

        resp = test_client.put(
            "/api/v1/db-backups/settings",
            headers=auth_headers["superadmin"],
            json={"enabled": True, "interval_hours": 24, "retention_count": 2},
        )
        assert resp.status_code == 200

        run_ids = []
        for _ in range(3):
            r = test_client.post("/api/v1/db-backups/run", headers=auth_headers["superadmin"])
            assert r.status_code == 200 and r.json()["status"] == "success"
            run_ids.append(r.json()["id"])

        with Session(engine) as session:
            runs = session.exec(select(DbBackupRun).order_by(DbBackupRun.id)).all()
            assert len(runs) == 3  # history survives
            archived = [r for r in runs if r.dump_path]
            pruned = [r for r in runs if not r.dump_path]
            assert len(archived) == 2
            assert len(pruned) == 1 and pruned[0].id == run_ids[0]  # the oldest

        root = get_db_backup_root()
        assert len(list(root.glob("*.dump"))) == 2
        assert list(root.glob("*.part")) == []

        # The pruned row is still readable — only its bytes are gone.
        detail = test_client.get(f"/api/v1/db-backups/{run_ids[0]}",
                                 headers=auth_headers["superadmin"])
        assert detail.status_code == 200
        assert detail.json()["dump_path"] is None

        resp = test_client.get(f"/api/v1/db-backups/{run_ids[0]}/download",
                               headers=auth_headers["superadmin"])
        assert resp.status_code == 404
        assert "retention" in resp.json()["detail"].lower()


class TestDownload:
    def test_download_streams_the_dump_and_audits(self, client, seeded_data, auth_headers,
                                                  monkeypatch):
        test_client, engine, _ = client
        monkeypatch.setattr(db_backups.service, "_run_pg_dump", _ok_dump())
        run = test_client.post("/api/v1/db-backups/run",
                               headers=auth_headers["superadmin"]).json()
        assert run["status"] == "success"

        resp = test_client.get(f"/api/v1/db-backups/{run['id']}/download",
                               headers=auth_headers["superadmin"])
        assert resp.status_code == 200
        # A `.dump` has no registered MIME type — never guessed, never zipped.
        assert resp.headers["content-type"] == "application/octet-stream"
        assert resp.content == PAYLOAD
        assert run["dump_path"] in resp.headers["content-disposition"]

        with Session(engine) as session:
            audits = session.exec(
                select(AuditLog).where(AuditLog.action == "download_db_backup")
            ).all()
            assert len(audits) == 1
            assert audits[0].module == "db_backups"
            assert audits[0].company_id is None
            assert audits[0].user_id == seeded_data["superadmin_id"]
            assert audits[0].entity_id == str(run["id"])

    def test_download_refuses_to_escape_the_dump_root(self, client, seeded_data,
                                                      auth_headers):
        """A tampered `dump_path` such as `../../etc/passwd` must be rejected
        by the containment check, not served."""
        test_client, engine, _ = client
        with Session(engine) as session:
            row = DbBackupRun(status=DbBackupStatus.SUCCESS,
                              trigger=DbBackupTrigger.MANUAL,
                              dump_path="../../outside.dump")
            session.add(row)
            session.commit()
            session.refresh(row)
            run_id = row.id

        resp = test_client.get(f"/api/v1/db-backups/{run_id}/download",
                               headers=auth_headers["superadmin"])
        # Either the traversal or the missing file resolves to 4xx — never 200.
        assert resp.status_code in (400, 404)


class TestScheduler:
    def test_disabled_blocks_scheduler(self, client, seeded_data):
        test_client, engine, _ = client
        _set_policy(engine, enabled=False)  # default is "true" — must be explicit
        assert run_due_db_backups(engine) == 0
        with Session(engine) as session:
            assert session.exec(select(DbBackupRun)).all() == []

    def test_due_run_started_when_no_history(self, client, seeded_data):
        test_client, engine, _ = client
        _set_policy(engine, enabled=True, hours=24)
        assert run_due_db_backups(engine) == 1
        with Session(engine) as session:
            runs = session.exec(
                select(DbBackupRun).where(DbBackupRun.trigger == DbBackupTrigger.SCHEDULED)
            ).all()
            assert len(runs) == 1
            assert runs[0].triggered_by is None          # scheduled runs have no user
            # pg_dump is unavailable in tests → the attempt is recorded, not raised.
            assert runs[0].status == DbBackupStatus.FAILED
            failures = session.exec(
                select(AuditLog).where(AuditLog.action == "db_backup_failed")
            ).all()
            assert len(failures) == 1
            assert failures[0].user_id is None
            assert failures[0].company_id is None

    def test_interval_prevents_immediate_rerun(self, client, seeded_data):
        test_client, engine, _ = client
        _set_policy(engine, enabled=True, hours=24)
        assert run_due_db_backups(engine) == 1
        # A FAILED attempt also counts as "recently attempted" — no retry storm.
        assert run_due_db_backups(engine) == 0
        with Session(engine) as session:
            assert len(session.exec(select(DbBackupRun)).all()) == 1

    def test_aged_run_becomes_due_again(self, client, seeded_data):
        test_client, engine, _ = client
        _set_policy(engine, enabled=True, hours=24)
        with Session(engine) as session:
            session.add(DbBackupRun(status=DbBackupStatus.SUCCESS,
                                    trigger=DbBackupTrigger.SCHEDULED,
                                    dump_path="dms_old.dump",
                                    created_at=datetime.utcnow() - timedelta(hours=25)))
            session.commit()
        assert run_due_db_backups(engine) == 1
        with Session(engine) as session:
            assert len(session.exec(select(DbBackupRun)).all()) == 2

    def test_running_dump_is_skipped_quietly(self, client, seeded_data):
        """The scheduler must never fight the manual trigger with a 409 — it
        just tries again next tick."""
        test_client, engine, _ = client
        _set_policy(engine, enabled=True, hours=24)
        with Session(engine) as session:
            session.add(DbBackupRun(status=DbBackupStatus.RUNNING,
                                    trigger=DbBackupTrigger.MANUAL,
                                    created_at=datetime.utcnow() - timedelta(hours=25)))
            session.commit()
        assert run_due_db_backups(engine) == 0
        with Session(engine) as session:
            assert len(session.exec(select(DbBackupRun)).all()) == 1

    def test_loop_never_starts_under_test_client(self, client, seeded_data):
        # conftest disables DB_BACKUP_SCHEDULER_ENABLED; entering the
        # TestClient (the fixture) runs lifespan — the tick loop must not start.
        assert db_backups.scheduler._task is None


class TestSecrets:
    """The database password may travel in exactly one place: the child
    process's PGPASSWORD environment variable."""

    def test_password_never_appears_in_argv(self, client, seeded_data):
        conn = _parse_database_url(FAKE_URL)
        assert conn.password == FAKE_PASSWORD
        argv = _build_command(conn, Path("target.dump"))

        assert all(FAKE_PASSWORD not in part for part in argv), argv
        assert not any("L3akMe" in part for part in argv), argv
        # The pieces pg_dump does need.
        assert argv[0] == get_settings().PG_DUMP_PATH
        assert argv[-1] == "dms_db"
        assert "--host" in argv and "db.internal" in argv
        assert "--port" in argv and "5432" in argv
        assert "--username" in argv and "postgres" in argv
        # Without this pg_dump prompts on a TTY and hangs forever.
        assert "--no-password" in argv

    def test_password_travels_only_via_env(self, client, seeded_data):
        env = _build_env(FAKE_PASSWORD)
        assert env["PGPASSWORD"] == FAKE_PASSWORD

        # No password configured → the inherited PGPASSWORD must be dropped,
        # or pg_dump could authenticate with some unrelated credential.
        cleaned = _build_env(None)
        assert "PGPASSWORD" not in cleaned

    def test_redact_strips_every_password_form(self, client, seeded_data, monkeypatch):
        # `_redact` reads the password out of settings.DATABASE_URL — point it
        # at a URL we control so the assertion does not depend on the .env.
        monkeypatch.setattr(db_backups.service, "get_settings",
                            lambda: _settings_with(FAKE_URL))
        encoded = (
            f"hello {FAKE_PASSWORD} and {urllib.parse.quote_plus(FAKE_PASSWORD)}"
            f" and {urllib.parse.quote(FAKE_PASSWORD)} end"
        )
        out = _redact(encoded)
        assert FAKE_PASSWORD not in out
        assert "%21" not in out  # the URL-encoded trailing '!'
        assert "hello" in out and "end" in out
        assert out.count("***") >= 2

    def test_pg_dump_path_cannot_exist(self, client, seeded_data):
        """The conftest guard: if this ever fails, a test could shell out to a
        real pg_dump against a real database. Fail loudly."""
        assert not Path(get_settings().PG_DUMP_PATH).exists()

    def test_pg_dump_stderr_is_redacted_everywhere(self, client, seeded_data,
                                                   auth_headers, monkeypatch, caplog):
        test_client, engine, _ = client
        monkeypatch.setattr(db_backups.service, "get_settings",
                            lambda: _settings_with(FAKE_URL))
        monkeypatch.setattr(
            db_backups.service, "_run_pg_dump",
            lambda target_path: DbDumpResult(
                returncode=1,
                stderr="pg_dump: connecting...\npg_dump: FATAL: password authentication failed for user \"postgres\" using password "
                       + FAKE_PASSWORD,
                duration_ms=3, version=None,
            ),
        )

        with caplog.at_level(logging.ERROR, logger="dms.db_backups"):
            resp = test_client.post("/api/v1/db-backups/run",
                                    headers=auth_headers["superadmin"])

        assert resp.status_code == 200 and resp.json()["status"] == "failed"
        error = resp.json()["error_message"] or ""
        assert FAKE_PASSWORD not in error
        assert "authentication failed" in error          # the useful part survives
        assert "password authentication failed" in caplog.text  # something was logged
        assert FAKE_PASSWORD not in caplog.text

        with Session(engine) as session:
            run = session.exec(select(DbBackupRun)).one()
            assert FAKE_PASSWORD not in (run.error_message or "")
            failure = session.exec(
                select(AuditLog).where(AuditLog.action == "db_backup_failed")
            ).one()
            assert FAKE_PASSWORD not in (failure.description or "")
            assert FAKE_PASSWORD not in (failure.failure_reason or "")

    def test_exception_message_is_redacted_everywhere(self, client, seeded_data,
                                                      auth_headers, monkeypatch, caplog):
        """The OTHER redaction seam: `run_dump`'s `except` block redacts
        whatever exception text it catches before persisting it."""
        test_client, engine, _ = client
        monkeypatch.setattr(db_backups.service, "get_settings",
                            lambda: _settings_with(FAKE_URL))
        monkeypatch.setattr(
            db_backups.service, "_run_pg_dump",
            lambda target_path: (_ for _ in ()).throw(
                db_backups.service.DbDumpError(f"boom while using {FAKE_PASSWORD}")
            ),
        )

        with caplog.at_level(logging.ERROR, logger="dms.db_backups"):
            resp = test_client.post("/api/v1/db-backups/run",
                                    headers=auth_headers["superadmin"])

        assert resp.status_code == 200 and resp.json()["status"] == "failed"
        assert FAKE_PASSWORD not in (resp.json()["error_message"] or "")
        assert "***" in resp.json()["error_message"]
        assert FAKE_PASSWORD not in caplog.text

        with Session(engine) as session:
            run = session.exec(select(DbBackupRun)).one()
            assert FAKE_PASSWORD not in (run.error_message or "")


class TestAudit:
    def test_audit_never_carries_a_company(self, client, seeded_data, auth_headers,
                                           monkeypatch):
        """Deployment-scoped: company_id is None on every db_backups audit
        row, in success AND failure."""
        test_client, engine, _ = client
        monkeypatch.setattr(db_backups.service, "_run_pg_dump", _ok_dump())
        ok = test_client.post("/api/v1/db-backups/run",
                              headers=auth_headers["superadmin"]).json()
        assert ok["status"] == "success"

        monkeypatch.setattr(db_backups.service, "_run_pg_dump",
                            lambda target_path: (_ for _ in ()).throw(
                                db_backups.service.DbDumpError("forced failure")))
        bad = test_client.post("/api/v1/db-backups/run",
                               headers=auth_headers["superadmin"]).json()
        assert bad["status"] == "failed"

        with Session(engine) as session:
            rows = session.exec(
                select(AuditLog).where(AuditLog.module == "db_backups")
            ).all()
            assert len(rows) == 2
            assert {r.action for r in rows} == {"create_db_backup", "db_backup_failed"}
            assert all(r.company_id is None for r in rows)
            assert all(r.user_id == seeded_data["superadmin_id"] for r in rows)
            by_action = {r.action: r for r in rows}
            assert by_action["create_db_backup"].is_success is not False
            assert by_action["db_backup_failed"].is_success is False
            assert by_action["create_db_backup"].entity_id == str(ok["id"])
            assert by_action["db_backup_failed"].entity_id == str(bad["id"])

    def test_download_audit_written_once_per_request(self, client, seeded_data,
                                                     auth_headers, monkeypatch):
        test_client, engine, _ = client
        monkeypatch.setattr(db_backups.service, "_run_pg_dump", _ok_dump())
        run = test_client.post("/api/v1/db-backups/run",
                               headers=auth_headers["superadmin"]).json()
        test_client.get(f"/api/v1/db-backups/{run['id']}/download",
                        headers=auth_headers["superadmin"])
        test_client.get(f"/api/v1/db-backups/{run['id']}/download",
                        headers=auth_headers["superadmin"])
        with Session(engine) as session:
            rows = session.exec(
                select(AuditLog).where(AuditLog.action == "download_db_backup")
            ).all()
            assert len(rows) == 2
            assert all(r.company_id is None for r in rows)


class TestStorageRootGuard:
    """DB_BACKUP_ROOT must stay outside both STORAGE_ROOT and BACKUP_ROOT:
    a dump must never be written into the tree it is meant to complement, and
    archives must never contain each other. The guard runs BEFORE any write,
    so a bad root degrades to `failed` instead of polluting the wrong tree."""

    def test_root_inside_storage_root_is_refused(self, client, seeded_data):
        from core.storage import storage_service

        target = storage_service.storage_root / "dumps"
        with _override_settings(DB_BACKUP_ROOT=str(target)):
            with pytest.raises(RuntimeError, match="outside STORAGE_ROOT"):
                get_db_backup_root()

    def test_root_inside_backup_root_is_refused(self, client, seeded_data):
        from backups.service import get_backup_root

        target = get_backup_root() / "dumps"
        with _override_settings(DB_BACKUP_ROOT=str(target)):
            with pytest.raises(RuntimeError, match="outside BACKUP_ROOT"):
                get_db_backup_root()

    def test_relative_root_resolves_against_app_root(self, client, seeded_data):
        from core.config import APP_ROOT

        with _override_settings(DB_BACKUP_ROOT="db_backups_data"):
            root = get_db_backup_root()
        assert root.is_absolute()
        # The app root (where main.py lives), never the process CWD.
        assert root == (APP_ROOT / "db_backups_data").resolve()

    def test_good_root_restores_after_override(self, client, seeded_data):
        """The helper must put settings back — a leaked override would corrupt
        every later test in the session."""
        before = get_db_backup_root()
        with _override_settings(DB_BACKUP_ROOT=str(before / "nested")):
            assert get_db_backup_root() == before / "nested"
        assert get_db_backup_root() == before

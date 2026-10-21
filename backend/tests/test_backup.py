"""
Company-wise folder backup service tests (spec 35).

Backup is company-scoped, so the isolation cases live here rather than
growing an existing feature file (repo convention).
"""

import io
import zipfile
from pathlib import Path

from sqlmodel import Session, select

import backups.scheduler
from audit.models import AuditLog
from backups.models import BackupRun, BackupStatus, BackupTrigger
from backups.service import get_backup_root, run_due_backups
from storage_usage.models import SystemSetting


def _make_source_files(storage_path: Path, short_name: str = "TESTCO") -> None:
    """Create a small company storage tree: one uploads file, one memo file."""
    root = storage_path / short_name
    uploads = root / "uploads" / "cat" / "dir"
    uploads.mkdir(parents=True, exist_ok=True)
    (uploads / "contract.pdf").write_bytes(b"%PDF-1.4 fake pdf bytes")
    memos = root / "memos"
    memos.mkdir(parents=True, exist_ok=True)
    (memos / "note.html").write_text("<p>memo</p>", encoding="utf-8")


class TestManualBackup:
    def test_manual_backup_success(self, client, seeded_data, auth_headers):
        test_client, engine, storage_path = client
        _make_source_files(storage_path)

        resp = test_client.post("/api/v1/backups/run", headers=auth_headers["admin"])
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "success"
        assert body["trigger"] == "manual"
        assert body["file_count"] == 2
        assert body["total_bytes"] > 0
        assert body["company_short_name"] == "TESTCO"
        assert body["archive_path"].startswith("TESTCO/backup_")
        assert body["archive_size_bytes"] > 0

        # The archive exists on disk under BACKUP_ROOT and unzips to the
        # exact company folder tree.
        archive = get_backup_root() / body["archive_path"]
        assert archive.is_file()
        with zipfile.ZipFile(archive) as zf:
            names = zf.namelist()
        assert "uploads/cat/dir/contract.pdf" in names
        assert "memos/note.html" in names

        # Run row + audit row
        with Session(engine) as session:
            runs = session.exec(select(BackupRun)).all()
            assert len(runs) == 1
            assert runs[0].status == BackupStatus.SUCCESS
            assert runs[0].triggered_by == seeded_data["admin_id"]
            audits = session.exec(
                select(AuditLog).where(AuditLog.action == "create_backup")
            ).all()
            assert len(audits) == 1
            assert audits[0].module == "backups"
            assert audits[0].company_id == seeded_data["company_id"]

    def test_conflict_when_already_running(self, client, seeded_data, auth_headers):
        test_client, engine, storage_path = client
        _make_source_files(storage_path)
        with Session(engine) as session:
            session.add(BackupRun(
                company_id=seeded_data["company_id"],
                status=BackupStatus.RUNNING,
            ))
            session.commit()

        resp = test_client.post("/api/v1/backups/run", headers=auth_headers["admin"])
        assert resp.status_code == 409


class TestCompanyIsolation:
    def test_admin_sees_only_own_company_runs(self, client, seeded_data, auth_headers):
        test_client, engine, storage_path = client
        _make_source_files(storage_path)

        own = test_client.post("/api/v1/backups/run", headers=auth_headers["admin"])
        assert own.status_code == 200 and own.json()["status"] == "success"
        # OTHERCO has no storage tree → failed run, but a row exists
        other = test_client.post("/api/v1/backups/run", headers=auth_headers["other_admin"])
        assert other.status_code == 200 and other.json()["status"] == "failed"

        resp = test_client.get("/api/v1/backups", headers=auth_headers["admin"])
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["company_short_name"] == "TESTCO"

        resp = test_client.get("/api/v1/backups", headers=auth_headers["other_admin"])
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["company_short_name"] == "OTHERCO"

    def test_superadmin_sees_all_and_can_filter(self, client, seeded_data, auth_headers):
        test_client, engine, storage_path = client
        _make_source_files(storage_path)
        test_client.post("/api/v1/backups/run", headers=auth_headers["admin"])
        test_client.post("/api/v1/backups/run", headers=auth_headers["other_admin"])

        resp = test_client.get("/api/v1/backups", headers=auth_headers["superadmin"])
        assert resp.json()["total"] == 2

        resp = test_client.get(
            "/api/v1/backups",
            headers=auth_headers["superadmin"],
            params={"company_id": seeded_data["company_id"]},
        )
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["company_short_name"] == "TESTCO"

    def test_detail_cross_company_is_404(self, client, seeded_data, auth_headers):
        test_client, engine, storage_path = client
        _make_source_files(storage_path)
        run_id = test_client.post(
            "/api/v1/backups/run", headers=auth_headers["admin"]
        ).json()["id"]

        resp = test_client.get(f"/api/v1/backups/{run_id}", headers=auth_headers["other_admin"])
        assert resp.status_code == 404  # 404 by design, not 403 (oracle avoidance)
        resp = test_client.get(f"/api/v1/backups/{run_id}", headers=auth_headers["admin"])
        assert resp.status_code == 200

    def test_download_cross_company_is_404(self, client, seeded_data, auth_headers):
        test_client, engine, storage_path = client
        _make_source_files(storage_path)
        run_id = test_client.post(
            "/api/v1/backups/run", headers=auth_headers["admin"]
        ).json()["id"]

        resp = test_client.get(
            f"/api/v1/backups/{run_id}/download", headers=auth_headers["other_admin"]
        )
        assert resp.status_code == 404

    def test_client_supplied_company_id_ignored_on_run(self, client, seeded_data, auth_headers):
        test_client, engine, storage_path = client
        _make_source_files(storage_path)

        resp = test_client.post(
            "/api/v1/backups/run",
            headers=auth_headers["admin"],
            params={"company_id": seeded_data["other_company_id"]},  # ignored, not honored
        )
        assert resp.status_code == 200
        assert resp.json()["company_id"] == seeded_data["company_id"]


class TestPermissions:
    def test_superadmin_cannot_trigger(self, client, seeded_data, auth_headers):
        test_client, _, _ = client
        resp = test_client.post("/api/v1/backups/run", headers=auth_headers["superadmin"])
        assert resp.status_code == 403

    def test_non_admin_rejected_on_all_routes(self, client, seeded_data, auth_headers):
        test_client, _, _ = client
        cases = [
            ("get", "/api/v1/backups", None),
            ("get", "/api/v1/backups/settings", None),
            ("post", "/api/v1/backups/run", None),
            ("put", "/api/v1/backups/settings", {"enabled": True, "interval_hours": 24, "retention_count": 7}),
        ]
        for method, path, json_body in cases:
            kwargs = {"headers": auth_headers["maker"]}
            if json_body is not None:
                kwargs["json"] = json_body
            resp = getattr(test_client, method)(path, **kwargs)
            assert resp.status_code == 403, f"{method.upper()} {path} → {resp.status_code}"

    def test_unauthenticated_is_401(self, client, seeded_data):
        test_client, _, _ = client
        resp = test_client.get("/api/v1/backups")
        assert resp.status_code == 401  # RBAC middleware map is active


class TestSettings:
    def test_defaults(self, client, seeded_data, auth_headers):
        test_client, _, _ = client
        resp = test_client.get("/api/v1/backups/settings", headers=auth_headers["admin"])
        assert resp.status_code == 200
        assert resp.json() == {"enabled": True, "interval_hours": 24, "retention_count": 7}

    def test_update_roundtrip_and_audit(self, client, seeded_data, auth_headers):
        test_client, engine, _ = client

        resp = test_client.put(
            "/api/v1/backups/settings",
            headers=auth_headers["admin"],
            json={"enabled": False, "interval_hours": 12, "retention_count": 3},
        )
        assert resp.status_code == 200
        assert resp.json() == {"enabled": False, "interval_hours": 12, "retention_count": 3}

        # SUPERADMIN may update settings (storage-capacity precedent)
        resp = test_client.put(
            "/api/v1/backups/settings",
            headers=auth_headers["superadmin"],
            json={"enabled": True, "interval_hours": 48, "retention_count": 5},
        )
        assert resp.status_code == 200
        assert resp.json() == {"enabled": True, "interval_hours": 48, "retention_count": 5}

        with Session(engine) as session:
            audits = session.exec(
                select(AuditLog).where(AuditLog.action == "update_backup_settings")
            ).all()
            assert len(audits) == 2

    def test_validation_rejects_out_of_range(self, client, seeded_data, auth_headers):
        test_client, _, _ = client
        bad_bodies = [
            {"enabled": True, "interval_hours": 0, "retention_count": 5},
            {"enabled": True, "interval_hours": 169, "retention_count": 5},
            {"enabled": True, "interval_hours": 24, "retention_count": 0},
            {"enabled": True, "interval_hours": 24, "retention_count": 101},
        ]
        for body in bad_bodies:
            resp = test_client.put(
                "/api/v1/backups/settings", headers=auth_headers["admin"], json=body
            )
            assert resp.status_code == 422, f"{body} → {resp.status_code}"


class TestRetention:
    def test_prunes_files_not_rows(self, client, seeded_data, auth_headers):
        test_client, engine, storage_path = client
        _make_source_files(storage_path)

        resp = test_client.put(
            "/api/v1/backups/settings",
            headers=auth_headers["admin"],
            json={"enabled": True, "interval_hours": 24, "retention_count": 2},
        )
        assert resp.status_code == 200

        run_ids = []
        for _ in range(3):
            r = test_client.post("/api/v1/backups/run", headers=auth_headers["admin"])
            assert r.status_code == 200 and r.json()["status"] == "success"
            run_ids.append(r.json()["id"])

        with Session(engine) as session:
            runs = session.exec(select(BackupRun).order_by(BackupRun.id)).all()
            assert len(runs) == 3
            archived = [r for r in runs if r.archive_path]
            pruned = [r for r in runs if not r.archive_path]
            assert len(archived) == 2
            assert len(pruned) == 1 and pruned[0].id == run_ids[0]  # oldest

        assert len(list((get_backup_root() / "TESTCO").glob("*.zip"))) == 2

        # Downloading a pruned run → explicit retention 404
        resp = test_client.get(
            f"/api/v1/backups/{run_ids[0]}/download", headers=auth_headers["admin"]
        )
        assert resp.status_code == 404
        assert "retention" in resp.json()["detail"].lower()


class TestFailureHandling:
    def test_failed_backup_is_data_not_error(self, client, seeded_data, auth_headers):
        test_client, engine, storage_path = client
        # The company storage root does not exist (storage misconfiguration
        # simulation) — the run must record the failure, not crash.
        resp = test_client.post("/api/v1/backups/run", headers=auth_headers["admin"])
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"
        assert body["error_message"]

        with Session(engine) as session:
            audits = session.exec(
                select(AuditLog).where(AuditLog.action == "backup_failed")
            ).all()
            assert len(audits) == 1
            assert audits[0].is_success is False
            assert audits[0].company_id == seeded_data["company_id"]

        # The app keeps serving requests afterwards
        resp = test_client.get("/api/v1/backups", headers=auth_headers["admin"])
        assert resp.status_code == 200


class TestDownload:
    def test_download_streams_valid_zip(self, client, seeded_data, auth_headers):
        test_client, engine, storage_path = client
        _make_source_files(storage_path)
        run = test_client.post("/api/v1/backups/run", headers=auth_headers["admin"]).json()

        resp = test_client.get(
            f"/api/v1/backups/{run['id']}/download", headers=auth_headers["admin"]
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
        assert resp.content[:2] == b"PK"
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            assert "uploads/cat/dir/contract.pdf" in zf.namelist()

        with Session(engine) as session:
            audits = session.exec(
                select(AuditLog).where(AuditLog.action == "download_backup")
            ).all()
            assert len(audits) == 1
            assert audits[0].company_id == seeded_data["company_id"]


class TestScheduler:
    def test_run_due_backups_creates_scheduled_runs(self, client, seeded_data):
        test_client, engine, storage_path = client
        _make_source_files(storage_path)

        started = run_due_backups(engine)
        # TESTCO (due, no runs) + OTHERCO (due, missing root → failed) — both
        # companies are active, so both get a scheduled attempt.
        assert started == 2

        with Session(engine) as session:
            runs = session.exec(
                select(BackupRun).where(BackupRun.trigger == BackupTrigger.SCHEDULED)
            ).all()
            assert len(runs) == 2
            assert all(r.triggered_by is None for r in runs)
            testco = next(r for r in runs if r.company_id == seeded_data["company_id"])
            assert testco.status == BackupStatus.SUCCESS

            audits = session.exec(
                select(AuditLog).where(AuditLog.action == "create_backup")
            ).all()
            # TESTCO succeeded → create_backup; OTHERCO (missing root) failed
            # → backup_failed. Scheduled runs have no user; company always set.
            assert len(audits) == 1
            assert audits[0].user_id is None
            assert audits[0].company_id == seeded_data["company_id"]
            failures = session.exec(
                select(AuditLog).where(AuditLog.action == "backup_failed")
            ).all()
            assert len(failures) == 1
            assert failures[0].company_id == seeded_data["other_company_id"]

    def test_interval_prevents_immediate_rerun(self, client, seeded_data):
        test_client, engine, storage_path = client
        _make_source_files(storage_path)

        assert run_due_backups(engine) == 2
        # A failed attempt also counts as "recently attempted" — no retry storm
        assert run_due_backups(engine) == 0

    def test_disabled_setting_blocks_scheduler(self, client, seeded_data):
        test_client, engine, _ = client
        with Session(engine) as session:
            row = session.get(SystemSetting, "backup_enabled")
            if row:
                row.value = "false"
                session.add(row)
            else:
                session.add(SystemSetting(
                    key="backup_enabled", value="false",
                    description="Company-wise folder backup scheduler enabled",
                ))
            session.commit()

        assert run_due_backups(engine) == 0
        with Session(engine) as session:
            assert session.exec(select(BackupRun)).all() == []

    def test_loop_never_starts_under_test_client(self, client, seeded_data):
        # conftest disables BACKUP_SCHEDULER_ENABLED; entering the TestClient
        # context (the fixture) runs lifespan — the tick loop must not start.
        assert backups.scheduler._task is None

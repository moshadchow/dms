"""Regression tests for the storage-root / env-file resolution.

Background
----------
`core/config.py` used to load its env file from ``./.env`` — resolved against
the *process working directory*. The backend runs from ``backend/`` (where
``main.py`` and the venv live) while the shared ``.env`` sits at the repo
root, so the file was never found and every setting silently fell back to its
code default. The fatal default was ``STORAGE_ROOT="storage"`` (the repo
``.env`` says ``storage/uploads``), which moved the company storage root to
``backend/storage/BAL`` while the files actually lived under
``backend/storage/uploads/BAL`` — so every document read answered 404
("File not found on disk") even though the row, directory, category, company
and user-level links were all valid.

These tests pin the two properties that make that impossible to regress:

1. the storage root is derived from the application root, never from the CWD;
2. a stored path written on Windows (backslashes) resolves on every platform.
"""

import io
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlmodel import Session

import core.config
from core.config import APP_ROOT, REPO_ROOT, Settings
from core.storage import storage_service
from documents.models import Document, DocumentStatus
from documents.utils import resolve_storage_path


# ──────────────────────────────────────────────
# Env-file discovery
# ──────────────────────────────────────────────

class TestEnvFileDiscovery:
    def test_env_file_candidates_cover_repo_root_and_app_root(self):
        """The repo-root .env must be a candidate, not just ./.env."""
        candidates = [Path(f) for f in Settings.Config.env_file]

        assert REPO_ROOT / ".env" in candidates, (
            "the repo-root .env must be searched — that is where the "
            "documented .env lives while the backend package is in backend/"
        )
        assert APP_ROOT / ".env" in candidates
        assert Path(".env") in candidates

    def test_last_env_file_wins(self, tmp_path):
        """pydantic-settings gives the LAST file in the list precedence.

        The candidate order in core/config.py relies on this, so pin it.
        """
        from pydantic_settings import BaseSettings

        first = tmp_path / "first.env"
        first.write_text("DMS_TEST_VALUE=from_first\n", encoding="utf-8")
        second = tmp_path / "second.env"
        second.write_text("DMS_TEST_VALUE=from_second\n", encoding="utf-8")

        class Probe(BaseSettings):
            DMS_TEST_VALUE: str = "default"

            class Config:
                env_file = (str(first), str(second))
                extra = "ignore"

        assert Probe().DMS_TEST_VALUE == "from_second"

    def test_missing_env_files_are_ignored(self, tmp_path):
        """A missing candidate must not stop the app from booting."""
        from pydantic_settings import BaseSettings

        present = tmp_path / "present.env"
        present.write_text("DMS_TEST_VALUE=present\n", encoding="utf-8")

        class Probe(BaseSettings):
            DMS_TEST_VALUE: str = "default"

            class Config:
                env_file = (str(tmp_path / "missing.env"), str(present))
                extra = "ignore"

        assert Probe().DMS_TEST_VALUE == "present"


# ──────────────────────────────────────────────
# Storage root resolution
# ──────────────────────────────────────────────

class TestStorageRootResolution:
    def test_relative_storage_root_is_anchored_to_app_root(self, monkeypatch):
        """A relative STORAGE_ROOT resolves against the app root, not the CWD."""
        monkeypatch.setattr(core.config.settings, "STORAGE_ROOT", "storage/uploads")

        expected = (APP_ROOT / "storage" / "uploads").resolve()
        assert storage_service.storage_root == expected

    def test_storage_root_does_not_follow_the_working_directory(self, monkeypatch, tmp_path):
        """Changing the CWD must not move the storage root.

        This is the exact defect that broke the dev environment: the app was
        launched from backend/ while the .env (and therefore STORAGE_ROOT)
        was resolved against a different working directory.
        """
        monkeypatch.setattr(core.config.settings, "STORAGE_ROOT", "storage/uploads")
        before = storage_service.storage_root

        monkeypatch.chdir(tmp_path)

        assert storage_service.storage_root == before
        assert storage_service.storage_root == (APP_ROOT / "storage" / "uploads").resolve()

    def test_absolute_storage_root_is_used_as_is(self, monkeypatch, tmp_path):
        """An absolute STORAGE_ROOT (tests, containers, prod) is untouched."""
        monkeypatch.setattr(core.config.settings, "STORAGE_ROOT", str(tmp_path))

        assert storage_service.storage_root == tmp_path.resolve()

    def test_windows_style_path_resolves_to_the_same_file(self, monkeypatch, tmp_path):
        """Rows written on Windows hold backslashes — they must still resolve."""
        root = tmp_path / "storage"
        company = SimpleNamespace(short_name="BAL")

        target = root / "BAL" / "uploads" / "1" / "2" / "report.pdf"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"pdf-bytes")

        monkeypatch.setattr(core.config.settings, "STORAGE_ROOT", str(root))

        posix = storage_service.resolve_path(company, "uploads/1/2/report.pdf")
        windows = storage_service.resolve_path(company, r"uploads\1\2\report.pdf")

        assert posix == target
        assert windows == target

    def test_missing_company_root_is_logged(self, monkeypatch, tmp_path, caplog):
        """A misconfigured root must be visible in the log, not just a 404.

        A missing file and a missing storage root are both answered with 404,
        which is indistinguishable from an access denial — the log line is
        what tells them apart.
        """
        root = tmp_path / "storage"
        root.mkdir()
        company = SimpleNamespace(short_name="BAL")

        monkeypatch.setattr(core.config.settings, "STORAGE_ROOT", str(root))

        with caplog.at_level(logging.WARNING, logger="dms.storage"):
            with pytest.raises(HTTPException) as exc:
                storage_service.resolve_path(company, "uploads/1/2/missing.pdf")

        assert exc.value.status_code == 404
        assert any("Storage company root" in rec.message for rec in caplog.records)


# ──────────────────────────────────────────────
# End-to-end: a document read must not 404
# ──────────────────────────────────────────────

def _upload_doc(test_client, headers, directory_id, title, user_level_ids, content=b"pdf-bytes"):
    return test_client.post(
        "/api/v1/documents/upload",
        headers=headers,
        data={
            "title": title,
            "directory_id": str(directory_id),
            "user_level_ids": json.dumps(user_level_ids),
        },
        files={"file": (f"{title}.pdf", io.BytesIO(content), "application/pdf")},
    )


class TestDocumentViewReadsTheFile:
    """GET /documents/{id}/view must stream the file, not 404."""

    def test_view_after_upload_returns_the_file(self, client, seeded_data, auth_headers):
        test_client, engine, _ = client

        resp = _upload_doc(
            test_client,
            auth_headers["admin"],
            seeded_data["finance_directory_id"],
            "View Regression",
            [seeded_data["high_level_id"]],
        )
        assert resp.status_code == 201, resp.text
        doc_id = resp.json()["id"]

        view = test_client.get(
            f"/api/v1/documents/{doc_id}/view",
            headers=auth_headers["admin"],
        )
        assert view.status_code == 200, view.text
        assert view.content == b"pdf-bytes"

    def test_view_resolves_a_row_stored_with_backslashes(self, client, seeded_data, auth_headers):
        """A row written on Windows (`uploads\\1\\2\\file.pdf`) must resolve.

        Every document row created on a Windows workstation holds backslashes;
        on Linux they are literal filename characters, so the row silently
        404s unless the resolver normalizes them.
        """
        test_client, engine, storage_root = client

        company_dir = storage_root / "TESTCO"
        target = company_dir / "finance" / "finance.pdf"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"seeded-bytes")

        with Session(engine) as session:
            doc = session.get(Document, seeded_data["finance_document_id"])
            assert doc is not None
            doc.storage_path = r"finance\finance.pdf"
            session.add(doc)
            session.commit()

        view = test_client.get(
            f"/api/v1/documents/{seeded_data['finance_document_id']}/view",
            headers=auth_headers["admin"],
        )
        assert view.status_code == 200, view.text
        assert view.content == b"seeded-bytes"

    def test_view_of_a_document_without_the_file_is_404(self, client, seeded_data, auth_headers):
        """A genuinely missing file stays a 404 — the guard must not be masked."""
        test_client, engine, _ = client

        with Session(engine) as session:
            doc = session.get(Document, seeded_data["finance_document_id"])
            doc.status = DocumentStatus.ACTIVE
            doc.storage_path = "finance/does-not-exist.pdf"
            session.add(doc)
            session.commit()

        view = test_client.get(
            f"/api/v1/documents/{seeded_data['finance_document_id']}/view",
            headers=auth_headers["admin"],
        )
        assert view.status_code == 404

"""Tests for the Signature module — Phase 3: Signature & History."""

import io
import pytest
from sqlmodel import Session
from starlette.datastructures import UploadFile

from core.security import create_access_token
from workflow.models import Signature, SignatureType
from workflow.service import SignatureService


# ── Helpers ──────────────────────────────────────


JPEG_CONTENT = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
PNG_CONTENT = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde'


def _make_upload_file(content: bytes, filename: str, content_type: str) -> UploadFile:
    from starlette.datastructures import Headers
    headers = Headers(raw=[(b"content-type", content_type.encode())])
    return UploadFile(filename=filename, file=io.BytesIO(content), headers=headers)


# ── Service Tests ────────────────────────────────


class TestSignatureService:
    def test_upload_signature_jpeg(self, seeded_data, client):
        _, engine, tmp_path = client
        with Session(engine) as session:
            from users.models import User
            admin = session.get(User, seeded_data["admin_id"])

            svc = SignatureService(session)
            file = _make_upload_file(JPEG_CONTENT, "signature.jpg", "image/jpeg")

            result = svc.upload_signature(file, admin, SignatureType.E_SIGNATURE)

            assert result.id is not None
            assert result.user_id == seeded_data["admin_id"]
            assert result.file_name == "signature.jpg"
            assert result.mime_type == "image/jpeg"
            assert result.sig_type == SignatureType.E_SIGNATURE
            assert result.is_active is True

    def test_upload_signature_png(self, seeded_data, client):
        _, engine, tmp_path = client
        with Session(engine) as session:
            from users.models import User
            admin = session.get(User, seeded_data["admin_id"])

            svc = SignatureService(session)
            file = _make_upload_file(PNG_CONTENT, "signature.png", "image/png")

            result = svc.upload_signature(file, admin, SignatureType.WET_SIGNATURE)

            assert result.id is not None
            assert result.sig_type == SignatureType.WET_SIGNATURE

    def test_upload_signature_invalid_type(self, seeded_data, client):
        _, engine, tmp_path = client
        with Session(engine) as session:
            from users.models import User
            from fastapi import HTTPException
            admin = session.get(User, seeded_data["admin_id"])

            svc = SignatureService(session)
            file = _make_upload_file(b"not an image", "signature.txt", "text/plain")

            with pytest.raises(HTTPException) as exc_info:
                svc.upload_signature(file, admin, SignatureType.E_SIGNATURE)
            assert exc_info.value.status_code == 422
            assert "not supported" in exc_info.value.detail

    def test_get_signature(self, seeded_data, client):
        _, engine, tmp_path = client
        with Session(engine) as session:
            from users.models import User
            admin = session.get(User, seeded_data["admin_id"])

            svc = SignatureService(session)
            file = _make_upload_file(JPEG_CONTENT, "signature.jpg", "image/jpeg")
            created = svc.upload_signature(file, admin, SignatureType.E_SIGNATURE)

            result = svc.get_signature(created.id, admin)
            assert result.id == created.id

    def test_get_signature_not_found(self, seeded_data, client):
        _, engine, tmp_path = client
        with Session(engine) as session:
            from users.models import User
            from fastapi import HTTPException
            admin = session.get(User, seeded_data["admin_id"])

            svc = SignatureService(session)
            with pytest.raises(HTTPException) as exc_info:
                svc.get_signature(99999, admin)
            assert exc_info.value.status_code == 404

    def test_get_signature_forbidden(self, seeded_data, client):
        _, engine, tmp_path = client
        with Session(engine) as session:
            from users.models import User
            from fastapi import HTTPException
            admin = session.get(User, seeded_data["admin_id"])
            maker = session.get(User, seeded_data["maker_id"])

            svc = SignatureService(session)
            file = _make_upload_file(JPEG_CONTENT, "signature.jpg", "image/jpeg")
            created = svc.upload_signature(file, admin, SignatureType.E_SIGNATURE)

            with pytest.raises(HTTPException) as exc_info:
                svc.get_signature(created.id, maker)
            assert exc_info.value.status_code == 403

    def test_soft_delete_signature(self, seeded_data, client):
        _, engine, tmp_path = client
        with Session(engine) as session:
            from users.models import User
            admin = session.get(User, seeded_data["admin_id"])

            svc = SignatureService(session)
            file = _make_upload_file(JPEG_CONTENT, "signature.jpg", "image/jpeg")
            created = svc.upload_signature(file, admin, SignatureType.E_SIGNATURE)

            result = svc.soft_delete_signature(created.id, admin)
            assert result.is_active is False

            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                svc.get_signature(created.id, admin)
            assert exc_info.value.status_code == 404

    def test_soft_delete_signature_forbidden(self, seeded_data, client):
        _, engine, tmp_path = client
        with Session(engine) as session:
            from users.models import User
            from fastapi import HTTPException
            admin = session.get(User, seeded_data["admin_id"])
            maker = session.get(User, seeded_data["maker_id"])

            svc = SignatureService(session)
            file = _make_upload_file(JPEG_CONTENT, "signature.jpg", "image/jpeg")
            created = svc.upload_signature(file, admin, SignatureType.E_SIGNATURE)

            with pytest.raises(HTTPException) as exc_info:
                svc.soft_delete_signature(created.id, maker)
            assert exc_info.value.status_code == 403

    def test_validate_signature_exists(self, seeded_data, client):
        _, engine, tmp_path = client
        with Session(engine) as session:
            from users.models import User
            from fastapi import HTTPException
            admin = session.get(User, seeded_data["admin_id"])

            svc = SignatureService(session)
            file = _make_upload_file(JPEG_CONTENT, "signature.jpg", "image/jpeg")
            created = svc.upload_signature(file, admin, SignatureType.E_SIGNATURE)

            sig = svc.validate_signature_exists(created.id)
            assert sig.id == created.id

            with pytest.raises(HTTPException) as exc_info:
                svc.validate_signature_exists(99999)
            assert exc_info.value.status_code == 404


# ── API Tests ────────────────────────────────────


class TestSignatureAPI:
    def test_upload_signature_endpoint(self, seeded_data, client):
        test_client, engine, tmp_path = client
        headers = {"Authorization": f"Bearer {create_access_token(seeded_data['admin_id'])}"}

        response = test_client.post(
            "/api/v1/signatures",
            headers=headers,
            files={"file": ("signature.jpg", io.BytesIO(JPEG_CONTENT), "image/jpeg")},
            data={"sig_type": "e_signature"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["sig_type"] == "e_signature"
        assert data["mime_type"] == "image/jpeg"

    def test_get_signature_endpoint(self, seeded_data, client):
        test_client, engine, tmp_path = client
        headers = {"Authorization": f"Bearer {create_access_token(seeded_data['admin_id'])}"}

        upload_response = test_client.post(
            "/api/v1/signatures",
            headers=headers,
            files={"file": ("signature.jpg", io.BytesIO(JPEG_CONTENT), "image/jpeg")},
            data={"sig_type": "e_signature"},
        )
        sig_id = upload_response.json()["id"]

        response = test_client.get(f"/api/v1/signatures/{sig_id}", headers=headers)
        assert response.status_code == 200
        assert response.json()["id"] == sig_id

    def test_delete_signature_endpoint(self, seeded_data, client):
        test_client, engine, tmp_path = client
        headers = {"Authorization": f"Bearer {create_access_token(seeded_data['admin_id'])}"}

        upload_response = test_client.post(
            "/api/v1/signatures",
            headers=headers,
            files={"file": ("signature.jpg", io.BytesIO(JPEG_CONTENT), "image/jpeg")},
            data={"sig_type": "e_signature"},
        )
        sig_id = upload_response.json()["id"]

        response = test_client.delete(f"/api/v1/signatures/{sig_id}", headers=headers)
        assert response.status_code == 200
        assert response.json()["is_active"] is False

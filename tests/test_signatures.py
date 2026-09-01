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


# ── Admin Signature Management Tests ─────────────


class TestAdminSignatureService:
    def test_admin_upload_for_user(self, seeded_data, client):
        _, engine, tmp_path = client
        with Session(engine) as session:
            from users.models import User
            admin = session.get(User, seeded_data["admin_id"])
            maker = session.get(User, seeded_data["maker_id"])

            svc = SignatureService(session)
            file = _make_upload_file(JPEG_CONTENT, "maker_sig.jpg", "image/jpeg")

            result = svc.admin_upload_for_user(seeded_data["maker_id"], file, admin, SignatureType.E_SIGNATURE)

            assert result.id is not None
            assert result.user_id == seeded_data["maker_id"]
            assert result.file_name == "maker_sig.jpg"
            assert result.is_active is True

    def test_admin_upload_replaces_existing(self, seeded_data, client):
        _, engine, tmp_path = client
        with Session(engine) as session:
            from users.models import User
            admin = session.get(User, seeded_data["admin_id"])

            svc = SignatureService(session)
            file1 = _make_upload_file(JPEG_CONTENT, "sig1.jpg", "image/jpeg")
            first = svc.admin_upload_for_user(seeded_data["maker_id"], file1, admin, SignatureType.E_SIGNATURE)

            file2 = _make_upload_file(PNG_CONTENT, "sig2.png", "image/png")
            second = svc.admin_upload_for_user(seeded_data["maker_id"], file2, admin, SignatureType.WET_SIGNATURE)

            assert first.id != second.id
            assert second.user_id == seeded_data["maker_id"]

            # Old signature should be soft-deleted
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                svc.get_signature(first.id, admin)
            assert exc_info.value.status_code == 404

    def test_admin_upload_non_admin_forbidden(self, seeded_data, client):
        _, engine, tmp_path = client
        with Session(engine) as session:
            from users.models import User
            from fastapi import HTTPException
            maker = session.get(User, seeded_data["maker_id"])

            svc = SignatureService(session)
            file = _make_upload_file(JPEG_CONTENT, "sig.jpg", "image/jpeg")

            with pytest.raises(HTTPException) as exc_info:
                svc.admin_upload_for_user(seeded_data["admin_id"], file, maker, SignatureType.E_SIGNATURE)
            assert exc_info.value.status_code == 403

    def test_admin_upload_invalid_user(self, seeded_data, client):
        _, engine, tmp_path = client
        with Session(engine) as session:
            from users.models import User
            from fastapi import HTTPException
            admin = session.get(User, seeded_data["admin_id"])

            svc = SignatureService(session)
            file = _make_upload_file(JPEG_CONTENT, "sig.jpg", "image/jpeg")

            with pytest.raises(HTTPException) as exc_info:
                svc.admin_upload_for_user(99999, file, admin, SignatureType.E_SIGNATURE)
            assert exc_info.value.status_code == 404

    def test_list_user_signatures(self, seeded_data, client):
        _, engine, tmp_path = client
        with Session(engine) as session:
            from users.models import User
            admin = session.get(User, seeded_data["admin_id"])

            svc = SignatureService(session)
            file = _make_upload_file(JPEG_CONTENT, "sig.jpg", "image/jpeg")
            svc.admin_upload_for_user(seeded_data["maker_id"], file, admin, SignatureType.E_SIGNATURE)

            result = svc.list_user_signatures(seeded_data["maker_id"], admin)
            assert len(result) == 1
            assert result[0].user_id == seeded_data["maker_id"]

    def test_list_user_signatures_non_admin_forbidden(self, seeded_data, client):
        _, engine, tmp_path = client
        with Session(engine) as session:
            from users.models import User
            from fastapi import HTTPException
            maker = session.get(User, seeded_data["maker_id"])

            svc = SignatureService(session)
            with pytest.raises(HTTPException) as exc_info:
                svc.list_user_signatures(seeded_data["admin_id"], maker)
            assert exc_info.value.status_code == 403

    def test_admin_delete_signature(self, seeded_data, client):
        _, engine, tmp_path = client
        with Session(engine) as session:
            from users.models import User
            admin = session.get(User, seeded_data["admin_id"])

            svc = SignatureService(session)
            file = _make_upload_file(JPEG_CONTENT, "sig.jpg", "image/jpeg")
            created = svc.admin_upload_for_user(seeded_data["maker_id"], file, admin, SignatureType.E_SIGNATURE)

            result = svc.admin_delete_signature(seeded_data["maker_id"], created.id, admin)
            assert result.is_active is False

    def test_admin_delete_wrong_user_forbidden(self, seeded_data, client):
        _, engine, tmp_path = client
        with Session(engine) as session:
            from users.models import User
            from fastapi import HTTPException
            admin = session.get(User, seeded_data["admin_id"])

            svc = SignatureService(session)
            file = _make_upload_file(JPEG_CONTENT, "sig.jpg", "image/jpeg")
            created = svc.admin_upload_for_user(seeded_data["maker_id"], file, admin, SignatureType.E_SIGNATURE)

            with pytest.raises(HTTPException) as exc_info:
                svc.admin_delete_signature(seeded_data["admin_id"], created.id, admin)
            assert exc_info.value.status_code == 400


class TestAdminSignatureAPI:
    def test_admin_list_signatures_endpoint(self, seeded_data, client):
        test_client, engine, tmp_path = client
        headers = {"Authorization": f"Bearer {create_access_token(seeded_data['admin_id'])}"}

        response = test_client.get(
            f"/api/v1/signatures/admin/{seeded_data['maker_id']}",
            headers=headers,
        )
        assert response.status_code == 200

    def test_admin_upload_for_user_endpoint(self, seeded_data, client):
        test_client, engine, tmp_path = client
        headers = {"Authorization": f"Bearer {create_access_token(seeded_data['admin_id'])}"}

        response = test_client.post(
            f"/api/v1/signatures/admin/{seeded_data['maker_id']}",
            headers=headers,
            files={"file": ("maker_sig.jpg", io.BytesIO(JPEG_CONTENT), "image/jpeg")},
            data={"sig_type": "e_signature"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == seeded_data["maker_id"]
        assert data["sig_type"] == "e_signature"

    def test_admin_delete_for_user_endpoint(self, seeded_data, client):
        test_client, engine, tmp_path = client
        headers = {"Authorization": f"Bearer {create_access_token(seeded_data['admin_id'])}"}

        upload_response = test_client.post(
            f"/api/v1/signatures/admin/{seeded_data['maker_id']}",
            headers=headers,
            files={"file": ("maker_sig.jpg", io.BytesIO(JPEG_CONTENT), "image/jpeg")},
            data={"sig_type": "e_signature"},
        )
        sig_id = upload_response.json()["id"]

        response = test_client.delete(
            f"/api/v1/signatures/admin/{seeded_data['maker_id']}/{sig_id}",
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_non_admin_cannot_access_admin_endpoints(self, seeded_data, client):
        test_client, engine, tmp_path = client
        headers = {"Authorization": f"Bearer {create_access_token(seeded_data['maker_id'])}"}

        response = test_client.get(
            f"/api/v1/signatures/admin/{seeded_data['admin_id']}",
            headers=headers,
        )
        assert response.status_code == 403

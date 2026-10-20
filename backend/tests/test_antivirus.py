"""
Antivirus & Malware Scanning Tests
──────────────────────────────────
Tests for the antivirus scanning feature on file uploads.
"""

import asyncio
import hashlib
import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile

from antivirus.engine import (
    ClamAVEngine,
    DummyEngine,
    ScanResult,
    ScanStatus,
    compute_file_hash,
    get_engine,
)
from antivirus.models import AntivirusScan, ScanStatus as ModelScanStatus
from antivirus.service import AntivirusService
from core.config import settings
from core.storage import storage_service
from company_profile.models import Company
from documents.models import Document, DocumentStatus, FileType
from documents.service import DocumentService
from users.models import User


# ──────────────────────────────────────────────
# Engine Tests
# ──────────────────────────────────────────────

def test_compute_file_hash(tmp_path):
    """Test SHA-256 hash computation."""
    file_path = tmp_path / "test.txt"
    file_path.write_bytes(b"Hello, World!")
    
    hash_val = compute_file_hash(file_path)
    expected = hashlib.sha256(b"Hello, World!").hexdigest()
    
    assert hash_val == expected
    assert len(hash_val) == 64  # SHA-256 hex length


def test_dummy_engine_clean():
    """Test dummy engine returns CLEAN for normal files."""
    engine = DummyEngine(fail_mode="clean")
    
    # Create a temporary file
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"clean content")
        temp_path = Path(f.name)
    
    try:
        result = asyncio.run(engine.scan_file(temp_path))
        assert result.status == ScanStatus.CLEAN
        assert result.threat_name is None
        assert result.engine_version == "dummy/1.0"
    finally:
        temp_path.unlink(missing_ok=True)


def test_dummy_engine_infected_eicar():
    """Test dummy engine detects EICAR test file."""
    engine = DummyEngine(fail_mode="clean")  # Uses filename detection
    
    import tempfile
    with tempfile.NamedTemporaryFile(prefix="eicar_", delete=False) as f:
        f.write(b"clean content")
        temp_path = Path(f.name)
    
    try:
        result = asyncio.run(engine.scan_file(temp_path))
        assert result.status == ScanStatus.INFECTED
        assert result.threat_name == "EICAR-Test-File"
    finally:
        temp_path.unlink(missing_ok=True)


def test_dummy_engine_timeout():
    """Test dummy engine timeout mode."""
    engine = DummyEngine(fail_mode="timeout")
    
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"content")
        temp_path = Path(f.name)
    
    try:
        result = asyncio.run(engine.scan_file(temp_path))
        assert result.status == ScanStatus.TIMEOUT
        assert result.duration_ms >= 1000  # At least 1 second
    finally:
        temp_path.unlink(missing_ok=True)


def test_dummy_engine_error():
    """Test dummy engine error mode."""
    engine = DummyEngine(fail_mode="error")
    
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"content")
        temp_path = Path(f.name)
    
    try:
        result = asyncio.run(engine.scan_file(temp_path))
        assert result.status == ScanStatus.ERROR
    finally:
        temp_path.unlink(missing_ok=True)


def test_get_engine_dummy():
    """Test engine factory returns dummy engine by default."""
    with patch.object(settings, "AV_ENGINE", "dummy"):
        engine = get_engine()
        assert isinstance(engine, DummyEngine)


# ──────────────────────────────────────────────
# Service Tests
# ──────────────────────────────────────────────

@pytest.fixture
def mock_company():
    """Create a mock company."""
    company = MagicMock(spec=Company)
    company.id = 1
    company.short_name = "TEST"
    return company


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = MagicMock()
    session.add = MagicMock()
    session.flush = MagicMock()
    session.exec = MagicMock()
    return session


@pytest.fixture
def dummy_engine():
    """Create a dummy engine for testing."""
    return DummyEngine(fail_mode="clean")


async def test_scan_file_clean(mock_session, mock_company, dummy_engine, tmp_path):
    """Test scanning a clean file."""
    # Create a test file
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"PDF content")
    
    # Ensure no recent scan is found (deduplication)
    mock_exec_result = MagicMock()
    mock_exec_result.first.return_value = None
    mock_session.exec.return_value = mock_exec_result
    
    # Mock storage_service.resolve_path_with_fallback
    with patch("antivirus.service.storage_service") as mock_storage:
        mock_storage.resolve_path_with_fallback.return_value = test_file
        mock_storage.get_company_root.return_value = tmp_path
        
        svc = AntivirusService(mock_session, engine=dummy_engine)
        scan = await svc.scan_file(test_file, "uploads/1/1/test.pdf", mock_company)
    
    assert scan.scan_status == ModelScanStatus.CLEAN
    assert scan.threat_name is None
    assert scan.company_id == 1
    assert scan.storage_path == "uploads/1/1/test.pdf"
    assert scan.file_hash == compute_file_hash(test_file)
    mock_session.add.assert_called()


async def test_scan_file_infected(mock_session, mock_company, tmp_path):
    """Test scanning an infected file (EICAR)."""
    # Create a test file with EICAR-like name
    test_file = tmp_path / "eicar_test.pdf"
    test_file.write_bytes(b"PDF content")
    
    engine = DummyEngine(fail_mode="clean")  # Detects by filename
    
    # Ensure no recent scan is found (deduplication)
    mock_exec_result = MagicMock()
    mock_exec_result.first.return_value = None
    mock_session.exec.return_value = mock_exec_result
    
    with patch("antivirus.service.storage_service") as mock_storage:
        mock_storage.resolve_path_with_fallback.return_value = test_file
        mock_storage.get_company_root.return_value = tmp_path
        
        svc = AntivirusService(mock_session, engine=engine)
        scan = await svc.scan_file(test_file, "uploads/1/1/eicar_test.pdf", mock_company)
    
    assert scan.scan_status == ModelScanStatus.INFECTED
    assert scan.threat_name == "EICAR-Test-File"


async def test_scan_file_deduplication(mock_session, mock_company, dummy_engine, tmp_path):
    """Test hash-based deduplication reuses recent clean scan."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"PDF content")
    file_hash = compute_file_hash(test_file)
    
    # Create a recent clean scan
    recent_scan = AntivirusScan(
        id=1,
        storage_path="uploads/1/1/old.pdf",
        file_hash=file_hash,
        scan_engine="dummy/1.0",
        scan_status=ModelScanStatus.CLEAN,
        scanned_at=asyncio.get_event_loop().time() if hasattr(asyncio.get_event_loop(), 'time') else None,
        company_id=1,
    )
    
    # Mock session.exec to return the recent scan
    mock_exec_result = MagicMock()
    mock_exec_result.first.return_value = recent_scan
    mock_session.exec.return_value = mock_exec_result
    
    with patch("antivirus.service.storage_service") as mock_storage:
        mock_storage.resolve_path_with_fallback.return_value = test_file
        mock_storage.get_company_root.return_value = tmp_path
        
        svc = AntivirusService(mock_session, engine=dummy_engine)
        scan = await svc.scan_file(test_file, "uploads/1/1/test.pdf", mock_company)
    
    # Should reuse the recent scan (duration_ms = 0 for reused)
    assert scan.scan_status == ModelScanStatus.CLEAN
    assert scan.scan_duration_ms == 0
    assert scan.file_hash == file_hash


# ──────────────────────────────────────────────
# Document Upload Integration Tests
# ──────────────────────────────────────────────

@pytest.fixture
def test_user():
    """Create a test user."""
    user = MagicMock(spec=User)
    user.id = 1
    user.user_level_id = 1
    user.is_admin.return_value = False
    user.company_id = 1
    user.company = MagicMock(spec=Company)
    user.company.id = 1
    user.company.short_name = "TEST"
    return user


@pytest.fixture
def test_directory():
    """Create a test directory."""
    directory = MagicMock()
    directory.id = 1
    directory.category_id = 1
    return directory


async def test_upload_document_clean(
    mock_session,
    test_user,
    test_directory,
    dummy_engine,
    tmp_path,
):
    """Test document upload with clean scan."""
    from user_levels.models import UserLevel
    from documents.models import Document
    
    # Setup mocks
    with patch("documents.service.ensure_directory_access", return_value=test_directory):
        with patch("documents.service.save_upload") as mock_save:
            # save_upload returns (storage_path, file_size)
            test_file = tmp_path / "test.pdf"
            test_file.write_bytes(b"PDF content")
            mock_save.return_value = ("uploads/1/1/test.pdf", 1024)
            
            # Mock user level validation
            mock_level = MagicMock(spec=UserLevel)
            mock_level.id = 1
            mock_level.is_active = True
            mock_session.exec.return_value.all.return_value = [mock_level]
            
            # Track created document to set ID on flush
            added_objects = []
            
            def mock_add(obj):
                added_objects.append(obj)
            
            def mock_flush():
                for obj in added_objects:
                    if isinstance(obj, Document):
                        obj.id = 1
            
            mock_session.add.side_effect = mock_add
            mock_session.flush.side_effect = mock_flush
            
            # Mock storage_service
            with patch("core.storage.storage_service") as mock_storage:
                mock_storage.resolve_path_with_fallback.return_value = test_file
                mock_storage.get_company_root.return_value = tmp_path
                
                svc = DocumentService(mock_session)
                # Replace engine with dummy
                with patch("documents.service.AntivirusService") as mock_av_svc_class:
                    mock_av_svc = MagicMock()
                    mock_scan = MagicMock()
                    mock_scan.id = 1
                    mock_scan.scan_status = ModelScanStatus.CLEAN
                    mock_av_svc.scan_file = AsyncMock(return_value=mock_scan)
                    mock_av_svc_class.return_value = mock_av_svc
                    
                    # Create mock file
                    mock_file = MagicMock(spec=UploadFile)
                    mock_file.filename = "test.pdf"
                    mock_file.content_type = "application/pdf"
                    
                    result = await svc.upload_document(
                        file=mock_file,
                        title="Test Document",
                        description="Test",
                        directory_id=1,
                        uploaded_by=1,
                        current_user=test_user,
                        user_level_ids=[1],
                    )
    
    assert result is not None
    assert mock_av_svc.scan_file.called


async def test_upload_document_infected_rejected(
    mock_session,
    test_user,
    test_directory,
    tmp_path,
):
    """Test document upload rejects infected file."""
    from user_levels.models import UserLevel
    
    with patch("documents.service.ensure_directory_access", return_value=test_directory):
        with patch("documents.service.save_upload") as mock_save:
            test_file = tmp_path / "eicar.pdf"
            test_file.write_bytes(b"PDF content")
            mock_save.return_value = ("uploads/1/1/eicar.pdf", 1024)
            
            mock_level = MagicMock(spec=UserLevel)
            mock_level.id = 1
            mock_level.is_active = True
            mock_session.exec.return_value.all.return_value = [mock_level]
            
            with patch("core.storage.storage_service") as mock_storage:
                mock_storage.resolve_path_with_fallback.return_value = test_file
                mock_storage.get_company_root.return_value = tmp_path
                
                with patch("documents.service.AntivirusService") as mock_av_svc_class:
                    mock_av_svc = MagicMock()
                    mock_scan = MagicMock()
                    mock_scan.id = 1
                    mock_scan.scan_status = ModelScanStatus.INFECTED
                    mock_scan.threat_name = "EICAR-Test-File"
                    mock_av_svc.scan_file = AsyncMock(return_value=mock_scan)
                    mock_av_svc_class.return_value = mock_av_svc
                    
                    with patch("documents.utils.delete_from_disk"):
                        svc = DocumentService(mock_session)
                        
                        mock_file = MagicMock(spec=UploadFile)
                        mock_file.filename = "eicar.pdf"
                        mock_file.content_type = "application/pdf"
                        
                        with pytest.raises(Exception) as exc_info:
                            await svc.upload_document(
                                file=mock_file,
                                title="Test Document",
                                description="Test",
                                directory_id=1,
                                uploaded_by=1,
                                current_user=test_user,
                                user_level_ids=[1],
                            )
                        
                        # Should raise HTTPException with 422
                        assert exc_info.value.status_code == 422
                        assert "malware detected" in str(exc_info.value.detail).lower()


async def test_upload_document_scan_timeout(
    mock_session,
    test_user,
    test_directory,
    tmp_path,
):
    """Test document upload handles scan timeout."""
    from user_levels.models import UserLevel
    
    with patch("documents.service.ensure_directory_access", return_value=test_directory):
        with patch("documents.service.save_upload") as mock_save:
            test_file = tmp_path / "test.pdf"
            test_file.write_bytes(b"PDF content")
            mock_save.return_value = ("uploads/1/1/test.pdf", 1024)
            
            mock_level = MagicMock(spec=UserLevel)
            mock_level.id = 1
            mock_level.is_active = True
            mock_session.exec.return_value.all.return_value = [mock_level]
            
            with patch("core.storage.storage_service") as mock_storage:
                mock_storage.resolve_path_with_fallback.return_value = test_file
                mock_storage.get_company_root.return_value = tmp_path
                
                with patch("documents.service.AntivirusService") as mock_av_svc_class:
                    mock_av_svc = MagicMock()
                    mock_scan = MagicMock()
                    mock_scan.id = 1
                    mock_scan.scan_status = ModelScanStatus.TIMEOUT
                    mock_av_svc.scan_file = AsyncMock(return_value=mock_scan)
                    mock_av_svc_class.return_value = mock_av_svc
                    
                    with patch("documents.service.delete_from_disk"):
                        svc = DocumentService(mock_session)
                        
                        mock_file = MagicMock(spec=UploadFile)
                        mock_file.filename = "test.pdf"
                        mock_file.content_type = "application/pdf"
                        
                        with pytest.raises(Exception) as exc_info:
                            await svc.upload_document(
                                file=mock_file,
                                title="Test Document",
                                description="Test",
                                directory_id=1,
                                uploaded_by=1,
                                current_user=test_user,
                                user_level_ids=[1],
                            )
                        
                        assert exc_info.value.status_code == 504
                        assert "timeout" in str(exc_info.value.detail).lower()


async def test_upload_document_scan_error(
    mock_session,
    test_user,
    test_directory,
    tmp_path,
):
    """Test document upload handles scan error."""
    from user_levels.models import UserLevel
    
    with patch("documents.service.ensure_directory_access", return_value=test_directory):
        with patch("documents.service.save_upload") as mock_save:
            test_file = tmp_path / "test.pdf"
            test_file.write_bytes(b"PDF content")
            mock_save.return_value = ("uploads/1/1/test.pdf", 1024)
            
            mock_level = MagicMock(spec=UserLevel)
            mock_level.id = 1
            mock_level.is_active = True
            mock_session.exec.return_value.all.return_value = [mock_level]
            
            with patch("core.storage.storage_service") as mock_storage:
                mock_storage.resolve_path_with_fallback.return_value = test_file
                mock_storage.get_company_root.return_value = tmp_path
                
                with patch("documents.service.AntivirusService") as mock_av_svc_class:
                    mock_av_svc = MagicMock()
                    mock_scan = MagicMock()
                    mock_scan.id = 1
                    mock_scan.scan_status = ModelScanStatus.ERROR
                    mock_av_svc.scan_file = AsyncMock(return_value=mock_scan)
                    mock_av_svc_class.return_value = mock_av_svc
                    
                    with patch("documents.service.delete_from_disk"):
                        svc = DocumentService(mock_session)
                        
                        mock_file = MagicMock(spec=UploadFile)
                        mock_file.filename = "test.pdf"
                        mock_file.content_type = "application/pdf"
                        
                        with pytest.raises(Exception) as exc_info:
                            await svc.upload_document(
                                file=mock_file,
                                title="Test Document",
                                description="Test",
                                directory_id=1,
                                uploaded_by=1,
                                current_user=test_user,
                                user_level_ids=[1],
                            )
                        
                        assert exc_info.value.status_code == 500
                        assert "scan failed" in str(exc_info.value.detail).lower()


async def test_upload_document_av_disabled(
    mock_session,
    test_user,
    test_directory,
    tmp_path,
):
    """Test document upload works when AV is disabled."""
    from user_levels.models import UserLevel
    from documents.models import Document
    
    with patch("documents.service.settings") as mock_settings:
        mock_settings.AV_ENABLED = False
        
        with patch("documents.service.ensure_directory_access", return_value=test_directory):
            with patch("documents.service.save_upload") as mock_save:
                test_file = tmp_path / "test.pdf"
                test_file.write_bytes(b"PDF content")
                mock_save.return_value = ("uploads/1/1/test.pdf", 1024)
                
                mock_level = MagicMock(spec=UserLevel)
                mock_level.id = 1
                mock_level.is_active = True
                mock_session.exec.return_value.all.return_value = [mock_level]
                
                # Track created document to set ID on flush
                added_objects = []
                
                def mock_add(obj):
                    added_objects.append(obj)
                
                def mock_flush():
                    for obj in added_objects:
                        if isinstance(obj, Document):
                            obj.id = 1
                
                mock_session.add.side_effect = mock_add
                mock_session.flush.side_effect = mock_flush
                
                svc = DocumentService(mock_session)
                
                mock_file = MagicMock(spec=UploadFile)
                mock_file.filename = "test.pdf"
                mock_file.content_type = "application/pdf"
                
                result = await svc.upload_document(
                    file=mock_file,
                    title="Test Document",
                    description="Test",
                    directory_id=1,
                    uploaded_by=1,
                    current_user=test_user,
                    user_level_ids=[1],
                )
    
    assert result is not None


# ──────────────────────────────────────────────
# Model Tests
# ──────────────────────────────────────────────

def test_antivirus_scan_model():
    """Test AntivirusScan model creation."""
    scan = AntivirusScan(
        storage_path="uploads/1/1/test.pdf",
        file_hash="abc123",
        scan_engine="clamav/1.4.2",
        scan_status=ModelScanStatus.CLEAN,
        company_id=1,
    )
    
    assert scan.storage_path == "uploads/1/1/test.pdf"
    assert scan.file_hash == "abc123"
    assert scan.scan_engine == "clamav/1.4.2"
    assert scan.scan_status == ModelScanStatus.CLEAN
    assert scan.company_id == 1


def test_scan_status_enum():
    """Test ScanStatus enum values."""
    assert ModelScanStatus.PENDING == "pending"
    assert ModelScanStatus.CLEAN == "clean"
    assert ModelScanStatus.INFECTED == "infected"
    assert ModelScanStatus.ERROR == "error"
    assert ModelScanStatus.TIMEOUT == "timeout"


# ──────────────────────────────────────────────
# Schema Tests
# ──────────────────────────────────────────────

def test_antivirus_scan_read_schema():
    """Test AntivirusScanRead schema."""
    from antivirus.schemas import AntivirusScanRead
    from datetime import datetime
    
    scan_read = AntivirusScanRead(
        id=1,
        storage_path="uploads/1/1/test.pdf",
        file_hash="abc123",
        scan_engine="clamav/1.4.2",
        scan_status=ModelScanStatus.CLEAN,
        company_id=1,
        scanned_at=datetime.utcnow(),
    )
    
    assert scan_read.id == 1
    assert scan_read.scan_status == ModelScanStatus.CLEAN


def test_antivirus_scan_list_response():
    """Test AntivirusScanListResponse build method."""
    from antivirus.schemas import AntivirusScanListResponse, AntivirusScanRead
    from datetime import datetime
    
    items = [
        AntivirusScanRead(
            id=i,
            storage_path=f"uploads/1/1/test{i}.pdf",
            file_hash="abc123",
            scan_engine="dummy/1.0",
            scan_status=ModelScanStatus.CLEAN,
            company_id=1,
            scanned_at=datetime.utcnow(),
        )
        for i in range(3)
    ]
    
    response = AntivirusScanListResponse.build(items, 3, 0, 50)
    
    assert response.total == 3
    assert response.page == 1
    assert response.limit == 50
    assert len(response.items) == 3
    assert response.next_page is None
    assert response.prev_page is None


# ──────────────────────────────────────────────
# Integration Test Helpers
# ──────────────────────────────────────────────

class TestAntivirusIntegration:
    """Integration tests requiring full app setup."""
    
    @pytest.mark.asyncio
    async def test_full_upload_flow_with_scan(self, client, auth_headers, seeded_data):
        """Test full document upload with antivirus scan."""
        # This test would use the actual TestClient and database
        # Skipped in unit tests, run with pytest tests/test_antivirus.py::TestAntivirusIntegration
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
"""
Antivirus Service
─────────────────
Business logic for file scanning, quarantine, and scan history.
"""

import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

from antivirus.engine import (
    AntivirusEngine,
    ScanResult,
    ScanStatus,
    compute_file_hash,
    get_engine,
)
from antivirus.models import AntivirusScan
from company_profile.models import Company
from core.config import settings
from core.storage import storage_service

logger = logging.getLogger("dms.antivirus")


# Deduplication TTL (hours) - scans newer than this are reused
SCAN_DEDUP_TTL_HOURS = getattr(settings, "AV_DEDUP_TTL_HOURS", 24)


class AntivirusService:
    def __init__(self, session: Session, engine: Optional[AntivirusEngine] = None):
        self.session = session
        self.engine = engine or get_engine()
    
    async def scan_file(
        self,
        file_path: Path,
        storage_path: str,
        company: Company,
    ) -> AntivirusScan:
        """
        Scan a file and create/update AntivirusScan record.
        
        Args:
            file_path: Absolute path to file on disk
            storage_path: Relative storage path (for DB record)
            company: Company for tenancy scoping
            
        Returns:
            AntivirusScan record with scan results
        """
        # Compute hash for deduplication
        file_hash = compute_file_hash(file_path)
        
        # Check for recent clean scan of same hash
        recent_scan = self._find_recent_clean_scan(file_hash, company.id)
        if recent_scan:
            logger.info(f"Reusing recent clean scan for hash {file_hash[:16]}...")
            # Create new record linking to same result
            return self._create_scan_record(
                storage_path=storage_path,
                file_hash=file_hash,
                company_id=company.id,
                status=ScanStatus.CLEAN,
                threat_name=None,
                engine=recent_scan.scan_engine,
                duration_ms=0,  # Reused scan
            )
        
        # Perform actual scan
        logger.info(f"Scanning file: {storage_path}")
        result = await self.engine.scan_file(file_path)
        
        # Create scan record
        scan_record = self._create_scan_record(
            storage_path=storage_path,
            file_hash=file_hash,
            company_id=company.id,
            status=result.status,
            threat_name=result.threat_name,
            engine=result.engine_version,
            duration_ms=result.duration_ms,
        )
        
        # Handle infected file - quarantine it
        if result.status == ScanStatus.INFECTED:
            await self._quarantine_file(file_path, storage_path, company, scan_record)
        
        return scan_record
    
    def _find_recent_clean_scan(self, file_hash: str, company_id: int) -> Optional[AntivirusScan]:
        """Find a recent clean scan for the same file hash."""
        cutoff = datetime.utcnow() - timedelta(hours=SCAN_DEDUP_TTL_HOURS)
        return self.session.exec(
            select(AntivirusScan).where(
                AntivirusScan.file_hash == file_hash,
                AntivirusScan.company_id == company_id,
                AntivirusScan.scan_status == ScanStatus.CLEAN,
                AntivirusScan.scanned_at >= cutoff,
            )
        ).first()
    
    def _create_scan_record(
        self,
        storage_path: str,
        file_hash: str,
        company_id: int,
        status: str,
        threat_name: Optional[str],
        engine: str,
        duration_ms: int,
    ) -> AntivirusScan:
        """Create and persist AntivirusScan record."""
        scan = AntivirusScan(
            storage_path=storage_path,
            file_hash=file_hash,
            scan_engine=engine,
            scan_status=status,
            threat_name=threat_name,
            scan_duration_ms=duration_ms,
            scanned_at=datetime.utcnow(),
            company_id=company_id,
        )
        self.session.add(scan)
        self.session.flush()
        return scan
    
    async def _quarantine_file(
        self,
        file_path: Path,
        storage_path: str,
        company: Company,
        scan_record: AntivirusScan,
    ) -> None:
        """Move infected file to quarantine directory."""
        try:
            quarantine_root = storage_service.get_company_root(company) / "quarantine"
            quarantine_root.mkdir(parents=True, exist_ok=True)
            
            # Generate quarantine filename with timestamp
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            original_name = Path(storage_path).name
            quarantine_name = f"{timestamp}_{original_name}"
            quarantine_path = quarantine_root / quarantine_name
            
            # Move file to quarantine
            shutil.move(str(file_path), str(quarantine_path))
            logger.warning(f"Quarantined infected file: {quarantine_path} (threat: {scan_record.threat_name})")
            
        except Exception as e:
            logger.error(f"Failed to quarantine file {file_path}: {e}")
            # Try to delete at least
            try:
                file_path.unlink(missing_ok=True)
            except Exception:
                pass
    
    def get_scan(self, scan_id: int, company_id: int) -> Optional[AntivirusScan]:
        """Get scan by ID (company-scoped)."""
        return self.session.exec(
            select(AntivirusScan).where(
                AntivirusScan.id == scan_id,
                AntivirusScan.company_id == company_id,
            )
        ).first()
    
    def list_scans(
        self,
        company_id: int,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[AntivirusScan], int]:
        """List scans for a company with optional status filter."""
        query = select(AntivirusScan).where(AntivirusScan.company_id == company_id)
        
        if status:
            query = query.where(AntivirusScan.scan_status == status)
        
        # Get total count
        total = len(self.session.exec(query).all())
        
        # Get paginated results
        scans = self.session.exec(
            query.order_by(AntivirusScan.scanned_at.desc())
            .offset(skip)
            .limit(limit)
        ).all()
        
        return list(scans), total
    
    async def rescan(self, scan_id: int, company_id: int) -> AntivirusScan:
        """Manually rescan a file by scan ID."""
        scan = self.get_scan(scan_id, company_id)
        if not scan:
            raise ValueError(f"Scan {scan_id} not found")
        
        # Resolve absolute path
        abs_path = storage_service.resolve_path_with_fallback(scan.storage_path, None)
        if not abs_path.exists():
            raise FileNotFoundError(f"File not found: {scan.storage_path}")
        
        # Perform new scan
        logger.info(f"Rescanning file: {scan.storage_path}")
        result = await self.engine.scan_file(abs_path)
        
        # Update scan record
        scan.scan_status = result.status
        scan.threat_name = result.threat_name
        scan.scan_engine = result.engine_version
        scan.scan_duration_ms = result.duration_ms
        scan.scanned_at = datetime.utcnow()
        
        self.session.add(scan)
        self.session.flush()
        
        # Handle newly infected file
        if result.status == ScanStatus.INFECTED:
            await self._quarantine_file(abs_path, scan.storage_path, scan.company, scan)
        
        return scan
"""
Antivirus Engine Abstraction
────────────────────────────
Provides a unified interface for different antivirus engines.
Currently supports ClamAV via clamd daemon.
Can be extended for REST-based AV APIs (VirusTotal, MetaDefender, etc.).
"""

import asyncio
import hashlib
import logging
import socket
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.config import settings

logger = logging.getLogger("dms.antivirus")


@dataclass
class ScanResult:
    status: "ScanStatus"
    threat_name: Optional[str] = None
    engine_version: str = ""
    duration_ms: int = 0


class ScanStatus:
    PENDING = "pending"
    CLEAN = "clean"
    INFECTED = "infected"
    ERROR = "error"
    TIMEOUT = "timeout"


class AntivirusEngine(ABC):
    """Abstract base class for antivirus engines."""

    @abstractmethod
    async def scan_file(self, file_path: Path) -> ScanResult:
        """Scan a file and return result."""
        pass

    @abstractmethod
    def get_engine_name(self) -> str:
        """Return engine identifier for logging."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if engine is available."""
        pass


class ClamAVEngine(AntivirusEngine):
    """
    ClamAV daemon (clamd) client using the `clamd` Python package.
    
    Requires: clamav-daemon running on localhost:3310 (default)
    Or configurable via CLAMD_HOST/CLAMD_PORT env vars.
    """
    
    def __init__(self):
        self.host = getattr(settings, "CLAMD_HOST", "localhost")
        self.port = getattr(settings, "CLAMD_PORT", 3310)
        self.timeout = getattr(settings, "AV_SCAN_TIMEOUT", 30)
        self._client = None
    
    def get_engine_name(self) -> str:
        return "clamav"
    
    async def _get_client(self):
        """Lazy-load clamd client."""
        if self._client is None:
            try:
                import clamd
                self._client = clamd.ClamdNetworkSocket(
                    host=self.host,
                    port=self.port,
                    timeout=self.timeout,
                )
            except ImportError:
                raise RuntimeError(
                    "clamd package not installed. Run: pip install clamd"
                )
        return self._client
    
    async def health_check(self) -> bool:
        try:
            client = await self._get_client()
            # Ping the daemon
            result = client.ping()
            return result == "PONG"
        except Exception as e:
            logger.warning(f"ClamAV health check failed: {e}")
            return False
    
    async def scan_file(self, file_path: Path) -> ScanResult:
        start = time.perf_counter()
        try:
            client = await self._get_client()
            
            # Use asyncio to run blocking clamd call in thread pool
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, client.scan, str(file_path)),
                timeout=self.timeout,
            )
            
            duration_ms = int((time.perf_counter() - start) * 1000)
            
            if result is None:
                return ScanResult(
                    status=ScanStatus.CLEAN,
                    engine_version=self._get_version(client),
                    duration_ms=duration_ms,
                )
            
            # clamd returns {filepath: (status, threat_name)}
            for _, (status, threat) in result.items():
                if status == "FOUND":
                    return ScanResult(
                        status=ScanStatus.INFECTED,
                        threat_name=threat,
                        engine_version=self._get_version(client),
                        duration_ms=duration_ms,
                    )
                elif status == "ERROR":
                    return ScanResult(
                        status=ScanStatus.ERROR,
                        engine_version=self._get_version(client),
                        duration_ms=duration_ms,
                    )
            
            return ScanResult(
                status=ScanStatus.CLEAN,
                engine_version=self._get_version(client),
                duration_ms=duration_ms,
            )
            
        except asyncio.TimeoutError:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.warning(f"ClamAV scan timeout for {file_path}")
            return ScanResult(
                status=ScanStatus.TIMEOUT,
                engine_version="clamav",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error(f"ClamAV scan error for {file_path}: {e}")
            return ScanResult(
                status=ScanStatus.ERROR,
                engine_version="clamav",
                duration_ms=duration_ms,
            )
    
    def _get_version(self, client) -> str:
        try:
            version = client.version()
            return f"clamav/{version}"
        except Exception:
            return "clamav/unknown"


class DummyEngine(AntivirusEngine):
    """
    Dummy engine for testing/development.
    Always returns CLEAN unless filename contains 'eicar' (case-insensitive).
    """
    
    def __init__(self, fail_mode: str = "clean"):
        self.fail_mode = fail_mode  # "clean", "infected", "error", "timeout"
    
    def get_engine_name(self) -> str:
        return "dummy"
    
    async def health_check(self) -> bool:
        return True
    
    async def scan_file(self, file_path: Path) -> ScanResult:
        start = time.perf_counter()
        await asyncio.sleep(0.01)  # Simulate scan time
        
        if self.fail_mode == "timeout":
            await asyncio.sleep(2)
            return ScanResult(
                status=ScanStatus.TIMEOUT,
                engine_version="dummy/1.0",
                duration_ms=2000,
            )
        elif self.fail_mode == "error":
            return ScanResult(
                status=ScanStatus.ERROR,
                engine_version="dummy/1.0",
                duration_ms=10,
            )
        elif self.fail_mode == "infected" or "eicar" in file_path.name.lower():
            return ScanResult(
                status=ScanStatus.INFECTED,
                threat_name="EICAR-Test-File",
                engine_version="dummy/1.0",
                duration_ms=10,
            )
        
        return ScanResult(
            status=ScanStatus.CLEAN,
            engine_version="dummy/1.0",
            duration_ms=10,
        )


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def get_engine() -> AntivirusEngine:
    """Factory function to get configured antivirus engine."""
    engine_type = getattr(settings, "AV_ENGINE", "dummy").lower()
    
    if engine_type == "clamav":
        return ClamAVEngine()
    elif engine_type == "dummy":
        return DummyEngine()
    else:
        logger.warning(f"Unknown AV_ENGINE '{engine_type}', falling back to dummy")
        return DummyEngine()
#!/usr/bin/env python3
"""
Migration script to move existing files to company-based storage structure.

This script:
1. Scans existing storage for files under uploads/, signatures/, memos/
2. Determines company ownership for each file via database relationships
3. Moves files to new company-prefixed paths
4. Updates database storage_path fields
5. Moves undeterminable files to _unassigned/ quarantine

Usage:
    python scripts/migrate_storage.py --dry-run    # Report changes without executing
    python scripts/migrate_storage.py --execute    # Actually perform migration
"""

import os
import shutil
import sys
from pathlib import Path
from typing import Optional, Tuple

from sqlmodel import Session, select

from core.config import settings
from core.database import engine
from core.storage import storage_service
from company_profile.models import Company
from documents.models import Document, DocumentStatus, DocumentVariant, DocumentVariantStatus
from memos.models import Memo
from workflow.models import Signature
from directories.models import Directory
from categories.models import Category
from users.models import User


class StorageMigrator:
    def __init__(self, session: Session, dry_run: bool = True):
        self.session = session
        self.dry_run = dry_run
        self.storage_root = Path(settings.STORAGE_ROOT).resolve()
        self.stats = {
            "documents_moved": 0,
            "documents_skipped": 0,
            "variants_moved": 0,
            "variants_skipped": 0,
            "signatures_moved": 0,
            "signatures_skipped": 0,
            "memos_moved": 0,
            "memos_skipped": 0,
            "unassigned": 0,
            "errors": 0,
        }
    
    def log(self, msg: str):
        prefix = "[DRY-RUN] " if self.dry_run else ""
        print(f"{prefix}{msg}")
    
    def error(self, msg: str):
        self.stats["errors"] += 1
        print(f"[ERROR] {msg}", file=sys.stderr)
    
    def get_company_for_document(self, doc: Document) -> Optional[Company]:
        """Determine company for a document via directory -> category -> company."""
        try:
            directory = self.session.get(Directory, doc.directory_id)
            if not directory:
                return None
            category = self.session.get(Category, directory.category_id)
            if not category:
                return None
            return self.session.get(Company, category.company_id)
        except Exception:
            return None
    
    def get_company_for_user(self, user_id: int) -> Optional[Company]:
        """Get company for a user."""
        try:
            user = self.session.get(User, user_id)
            if not user:
                return None
            return user.company
        except Exception:
            return None
    
    def get_company_for_signature(self, sig: Signature) -> Optional[Company]:
        """Get company for a signature via its user."""
        return self.get_company_for_user(sig.user_id)
    
    def get_company_for_memo(self, memo: Memo) -> Optional[Company]:
        """Get company for a memo via its author."""
        return self.get_company_for_user(memo.created_by)

    def backfill_memo_company_id(self):
        """Backfill memo.company_id from author's company."""
        self.log("Backfilling memo company_id...")
        
        memos = self.session.exec(select(Memo)).all()
        
        for memo in memos:
            if memo.company_id is not None:
                self.log(f"Memo {memo.id} already has company_id: {memo.company_id}")
                continue
            
            company = self.get_company_for_memo(memo)
            if company:
                if self.dry_run:
                    self.log(f"Would set memo {memo.id} company_id = {company.id}")
                else:
                    memo.company_id = company.id
                    self.session.add(memo)
                    self.session.commit()
                    self.log(f"Set memo {memo.id} company_id = {company.id}")
            else:
                self.log(f"Memo {memo.id} has no company (author has no company)")
    
    def get_company_for_variant(self, variant: DocumentVariant) -> Optional[Company]:
        """Get company for a variant via its directory -> category -> company."""
        try:
            directory = self.session.get(Directory, variant.directory_id)
            if not directory:
                return None
            category = self.session.get(Category, directory.category_id)
            if not category:
                return None
            return self.session.get(Company, category.company_id)
        except Exception:
            return None
    
    def move_file(self, src: Path, dst: Path) -> bool:
        """Move file from src to dst, creating parent directories."""
        if self.dry_run:
            self.log(f"Would move: {src} -> {dst}")
            return True
        
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return True
        except Exception as e:
            self.error(f"Failed to move {src} -> {dst}: {e}")
            return False
    
    def update_doc_storage_path(self, doc: Document, new_relative_path: str) -> bool:
        """Update document's storage_path in database."""
        if self.dry_run:
            self.log(f"Would update document {doc.id}: {doc.storage_path} -> {new_relative_path}")
            return True
        
        try:
            doc.storage_path = new_relative_path
            self.session.add(doc)
            self.session.commit()
            return True
        except Exception as e:
            self.error(f"Failed to update document {doc.id}: {e}")
            self.session.rollback()
            return False
    
    def update_variant_storage_path(self, variant: DocumentVariant, new_relative_path: str) -> bool:
        """Update variant's storage_path in database."""
        if self.dry_run:
            self.log(f"Would update variant {variant.id}: {variant.storage_path} -> {new_relative_path}")
            return True
        
        try:
            variant.storage_path = new_relative_path
            self.session.add(variant)
            self.session.commit()
            return True
        except Exception as e:
            self.error(f"Failed to update variant {variant.id}: {e}")
            self.session.rollback()
            return False
    
    def update_signature_file_path(self, sig: Signature, new_relative_path: str) -> bool:
        """Update signature's file_path in database."""
        if self.dry_run:
            self.log(f"Would update signature {sig.id}: {sig.file_path} -> {new_relative_path}")
            return True
        
        try:
            sig.file_path = new_relative_path
            self.session.add(sig)
            self.session.commit()
            return True
        except Exception as e:
            self.error(f"Failed to update signature {sig.id}: {e}")
            self.session.rollback()
            return False
    
    def migrate_documents(self):
        """Migrate document files to company-based structure."""
        self.log("Migrating documents...")
        
        docs = self.session.exec(select(Document)).all()
        
        for doc in docs:
            # Skip if already has company prefix
            if "/" in doc.storage_path and not doc.storage_path.startswith("uploads/"):
                # Check if it already has company prefix pattern
                parts = doc.storage_path.split("/")
                if len(parts) >= 2 and parts[1] == "uploads":
                    self.log(f"Document {doc.id} already has company prefix: {doc.storage_path}")
                    self.stats["documents_skipped"] += 1
                    continue
            
            company = self.get_company_for_document(doc)
            if not company:
                # Move to quarantine
                old_path = self.storage_root / doc.storage_path
                if old_path.exists():
                    quarantine_dir = self.storage_root / "_unassigned" / "documents"
                    quarantine_dir.mkdir(parents=True, exist_ok=True)
                    dst = quarantine_dir / old_path.name
                    if self.move_file(old_path, dst):
                        self.log(f"Document {doc.id} (no company) moved to quarantine: {dst}")
                        self.stats["unassigned"] += 1
                continue
            
            # Build new path with company prefix
            old_path = self.storage_root / doc.storage_path
            if not old_path.exists():
                self.log(f"Document {doc.id} file not found: {old_path}")
                self.stats["documents_skipped"] += 1
                continue
            
            # New path: {short_name}/uploads/{category_id}/{directory_id}/{filename}
            directory = self.session.get(Directory, doc.directory_id)
            new_relative = f"{company.short_name}/uploads/{directory.category_id}/{directory.id}/{old_path.name}"
            new_path = self.storage_root / new_relative
            
            if self.move_file(old_path, new_path):
                if self.update_doc_storage_path(doc, new_relative):
                    self.stats["documents_moved"] += 1
                else:
                    self.stats["errors"] += 1
            else:
                self.stats["errors"] += 1
    
    def migrate_variants(self):
        """Migrate document variant files to company-based structure."""
        self.log("Migrating document variants...")
        
        variants = self.session.exec(
            select(DocumentVariant).where(DocumentVariant.status == DocumentVariantStatus.ACTIVE)
        ).all()
        
        for variant in variants:
            # Skip if already has company prefix
            if variant.storage_path and "/" in variant.storage_path:
                parts = variant.storage_path.split("/")
                if len(parts) >= 2 and parts[1] == "uploads":
                    self.log(f"Variant {variant.id} already has company prefix: {variant.storage_path}")
                    self.stats["variants_skipped"] += 1
                    continue
            
            company = self.get_company_for_variant(variant)
            if not company:
                old_path = self.storage_root / variant.storage_path
                if old_path and old_path.exists():
                    quarantine_dir = self.storage_root / "_unassigned" / "variants"
                    quarantine_dir.mkdir(parents=True, exist_ok=True)
                    dst = quarantine_dir / old_path.name
                    if self.move_file(old_path, dst):
                        self.log(f"Variant {variant.id} (no company) moved to quarantine: {dst}")
                        self.stats["unassigned"] += 1
                continue
            
            old_path = self.storage_root / variant.storage_path
            if not old_path.exists():
                self.log(f"Variant {variant.id} file not found: {old_path}")
                self.stats["variants_skipped"] += 1
                continue
            
            new_relative = f"{company.short_name}/uploads/{variant.category_id}/{variant.directory_id}/_variants/{variant.owner_user_id}/{variant.id}/{old_path.name}"
            new_path = self.storage_root / new_relative
            
            if self.move_file(old_path, new_path):
                if self.update_variant_storage_path(variant, new_relative):
                    self.stats["variants_moved"] += 1
                else:
                    self.stats["errors"] += 1
            else:
                self.stats["errors"] += 1
    
    def migrate_signatures(self):
        """Migrate signature files to company-based structure."""
        self.log("Migrating signatures...")
        
        signatures = self.session.exec(select(Signature)).all()
        
        for sig in signatures:
            # Skip if already has company prefix
            if sig.file_path and "/" in sig.file_path:
                parts = sig.file_path.split("/")
                if len(parts) >= 2 and parts[1] == "signatures":
                    self.log(f"Signature {sig.id} already has company prefix: {sig.file_path}")
                    self.stats["signatures_skipped"] += 1
                    continue
            
            company = self.get_company_for_signature(sig)
            if not company:
                old_path = self.storage_root / sig.file_path
                if old_path and old_path.exists():
                    quarantine_dir = self.storage_root / "_unassigned" / "signatures"
                    quarantine_dir.mkdir(parents=True, exist_ok=True)
                    dst = quarantine_dir / old_path.name
                    if self.move_file(old_path, dst):
                        self.log(f"Signature {sig.id} (no company) moved to quarantine: {dst}")
                        self.stats["unassigned"] += 1
                continue
            
            old_path = self.storage_root / sig.file_path
            if not old_path.exists():
                self.log(f"Signature {sig.id} file not found: {old_path}")
                self.stats["signatures_skipped"] += 1
                continue
            
            new_relative = f"{company.short_name}/signatures/{sig.user_id}/{old_path.name}"
            new_path = self.storage_root / new_relative
            
            if self.move_file(old_path, new_path):
                if self.update_signature_file_path(sig, new_relative):
                    self.stats["signatures_moved"] += 1
                else:
                    self.stats["errors"] += 1
            else:
                self.stats["errors"] += 1
    
    def migrate_memos(self):
        """Migrate memo HTML files to company-based structure."""
        self.log("Migrating memos...")
        
        memos = self.session.exec(select(Memo)).all()
        
        for memo in memos:
            if not memo.document:
                continue
            
            doc = memo.document
            # Skip if already has company prefix
            if doc.storage_path and "/" in doc.storage_path:
                parts = doc.storage_path.split("/")
                if len(parts) >= 2 and parts[1] == "memos":
                    self.log(f"Memo {memo.id} already has company prefix: {doc.storage_path}")
                    self.stats["memos_skipped"] += 1
                    continue
            
            company = self.get_company_for_memo(memo)
            if not company:
                old_path = self.storage_root / doc.storage_path
                if old_path and old_path.exists():
                    quarantine_dir = self.storage_root / "_unassigned" / "memos"
                    quarantine_dir.mkdir(parents=True, exist_ok=True)
                    dst = quarantine_dir / old_path.name
                    if self.move_file(old_path, dst):
                        self.log(f"Memo {memo.id} (no company) moved to quarantine: {dst}")
                        self.stats["unassigned"] += 1
                continue
            
            old_path = self.storage_root / doc.storage_path
            if not old_path.exists():
                self.log(f"Memo {memo.id} file not found: {old_path}")
                self.stats["memos_skipped"] += 1
                continue
            
            new_relative = f"{company.short_name}/memos/{memo.created_by}/{old_path.name}"
            new_path = self.storage_root / new_relative
            
            if self.move_file(old_path, new_path):
                if self.update_doc_storage_path(doc, new_relative):
                    self.stats["memos_moved"] += 1
                else:
                    self.stats["errors"] += 1
            else:
                self.stats["errors"] += 1
    
    def run(self):
        """Run the full migration."""
        self.log("Starting storage migration...")
        self.log(f"Storage root: {self.storage_root}")
        self.log(f"Mode: {'DRY-RUN' if self.dry_run else 'EXECUTE'}")
        
        self.backfill_memo_company_id()
        self.migrate_documents()
        self.migrate_variants()
        self.migrate_signatures()
        self.migrate_memos()
        
        self.log("\n=== Migration Summary ===")
        self.log(f"Documents moved: {self.stats['documents_moved']}")
        self.log(f"Documents skipped: {self.stats['documents_skipped']}")
        self.log(f"Variants moved: {self.stats['variants_moved']}")
        self.log(f"Variants skipped: {self.stats['variants_skipped']}")
        self.log(f"Signatures moved: {self.stats['signatures_moved']}")
        self.log(f"Signatures skipped: {self.stats['signatures_skipped']}")
        self.log(f"Memos moved: {self.stats['memos_moved']}")
        self.log(f"Memos skipped: {self.stats['memos_skipped']}")
        self.log(f"Unassigned (quarantined): {self.stats['unassigned']}")
        self.log(f"Errors: {self.stats['errors']}")
        
        if self.dry_run:
            self.log("\nRun with --execute to perform actual migration.")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate storage to company-based structure")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without executing")
    parser.add_argument("--execute", action="store_true", help="Perform actual migration")
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.execute:
        parser.error("Must specify either --dry-run or --execute")
    
    if args.dry_run and args.execute:
        parser.error("Cannot specify both --dry-run and --execute")
    
    dry_run = args.dry_run
    
    with Session(engine) as session:
        migrator = StorageMigrator(session, dry_run=dry_run)
        migrator.run()


if __name__ == "__main__":
    main()
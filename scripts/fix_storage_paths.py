#!/usr/bin/env python3
"""
Migration script to fix double-prefixed storage paths in the database.

Problem: After spec 21 (company-based storage), paths were stored relative to
STORAGE_ROOT (e.g., "BAL/uploads/2/8/file.pdf") but resolve_path() prepends
the company root again (e.g., storage/BAL/ + BAL/uploads/2/8/file.pdf),
creating a doubled path that doesn't exist.

Fix: Strip the company short_name prefix from stored paths so they become
company-relative (e.g., "uploads/2/8/file.pdf"). No file moves needed.

Affected tables:
  - documents.storage_path
  - signatures.file_path
  - document_variants.storage_path

Usage:
    python scripts/fix_storage_paths.py --dry-run    # Preview changes
    python scripts/fix_storage_paths.py --execute    # Apply changes
"""

import sys
from typing import Optional
from pathlib import Path

from sqlmodel import Session, select

from core.config import settings
from core.database import engine
from core.storage import storage_service
from company_profile.models import Company
from documents.models import Document, DocumentVariant, DocumentVariantStatus
from memos.models import Memo
from workflow.models import Signature
from directories.models import Directory
from categories.models import Category


class StoragePathFixer:
    def __init__(self, session: Session, dry_run: bool = True):
        self.session = session
        self.dry_run = dry_run
        self.stats = {
            "documents_fixed": 0,
            "documents_skipped": 0,
            "signatures_fixed": 0,
            "signatures_skipped": 0,
            "variants_fixed": 0,
            "variants_skipped": 0,
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
            from users.models import User
            user = self.session.get(User, user_id)
            if not user:
                return None
            return user.company
        except Exception:
            return None

    def strip_company_prefix(self, storage_path: str, company: Company) -> Optional[str]:
        """Strip company short_name prefix from path if present.
        
        Returns None if path doesn't have the prefix (no change needed).
        """
        # Handle both forward and backward slashes
        prefix_fwd = f"{company.short_name}/"
        prefix_bwd = f"{company.short_name}\\"
        
        if storage_path.startswith(prefix_fwd):
            return storage_path[len(prefix_fwd):]
        elif storage_path.startswith(prefix_bwd):
            return storage_path[len(prefix_bwd):]
        return None

    def fix_document(self, doc: Document) -> bool:
        """Fix a single document's storage_path. Returns True if changed."""
        company = self.get_company_for_document(doc)
        if not company:
            self.log(f"Document {doc.id}: no company found, skipping")
            self.stats["documents_skipped"] += 1
            return False

        new_path = self.strip_company_prefix(doc.storage_path, company)
        if new_path is None:
            self.log(f"Document {doc.id}: no prefix to strip, skipping")
            self.stats["documents_skipped"] += 1
            return False

        if self.dry_run:
            self.log(f"Would fix document {doc.id}: {doc.storage_path} -> {new_path}")
            self.stats["documents_fixed"] += 1
            return True

        old_path = doc.storage_path
        doc.storage_path = new_path
        self.session.add(doc)
        self.session.commit()
        self.log(f"Fixed document {doc.id}: {old_path} -> {new_path}")
        self.stats["documents_fixed"] += 1
        return True

    def fix_signature(self, sig: Signature) -> bool:
        """Fix a single signature's file_path. Returns True if changed."""
        company = self.get_company_for_user(sig.user_id)
        if not company:
            self.log(f"Signature {sig.id}: no company found, skipping")
            self.stats["signatures_skipped"] += 1
            return False

        new_path = self.strip_company_prefix(sig.file_path, company)
        if new_path is None:
            self.log(f"Signature {sig.id}: no prefix to strip, skipping")
            self.stats["signatures_skipped"] += 1
            return False

        if self.dry_run:
            self.log(f"Would fix signature {sig.id}: {sig.file_path} -> {new_path}")
            self.stats["signatures_fixed"] += 1
            return True

        old_path = sig.file_path
        sig.file_path = new_path
        self.session.add(sig)
        self.session.commit()
        self.log(f"Fixed signature {sig.id}: {old_path} -> {new_path}")
        self.stats["signatures_fixed"] += 1
        return True

    def fix_variant(self, variant: DocumentVariant) -> bool:
        """Fix a single variant's storage_path. Returns True if changed."""
        company = self.get_company_for_document(variant.source_document)
        if not company:
            self.log(f"Variant {variant.id}: no company found, skipping")
            self.stats["variants_skipped"] += 1
            return False

        new_path = self.strip_company_prefix(variant.storage_path, company)
        if new_path is None:
            self.log(f"Variant {variant.id}: no prefix to strip, skipping")
            self.stats["variants_skipped"] += 1
            return False

        if self.dry_run:
            self.log(f"Would fix variant {variant.id}: {variant.storage_path} -> {new_path}")
            self.stats["variants_fixed"] += 1
            return True

        old_path = variant.storage_path
        variant.storage_path = new_path
        self.session.add(variant)
        self.session.commit()
        self.log(f"Fixed variant {variant.id}: {old_path} -> {new_path}")
        self.stats["variants_fixed"] += 1
        return True

    def run(self):
        """Run the full fix."""
        self.log("Starting storage path fix...")
        self.log(f"Storage root: {storage_service.storage_root}")
        self.log(f"Mode: {'DRY-RUN' if self.dry_run else 'EXECUTE'}")

        # Fix documents
        self.log("\n--- Fixing documents ---")
        docs = self.session.exec(select(Document)).all()
        for doc in docs:
            self.fix_document(doc)

        # Fix signatures
        self.log("\n--- Fixing signatures ---")
        sigs = self.session.exec(select(Signature)).all()
        for sig in sigs:
            self.fix_signature(sig)

        # Fix variants
        self.log("\n--- Fixing document variants ---")
        variants = self.session.exec(
            select(DocumentVariant).where(DocumentVariant.status == DocumentVariantStatus.ACTIVE)
        ).all()
        for variant in variants:
            self.fix_variant(variant)

        # Summary
        self.log("\n=== Fix Summary ===")
        self.log(f"Documents fixed: {self.stats['documents_fixed']}")
        self.log(f"Documents skipped: {self.stats['documents_skipped']}")
        self.log(f"Signatures fixed: {self.stats['signatures_fixed']}")
        self.log(f"Signatures skipped: {self.stats['signatures_skipped']}")
        self.log(f"Variants fixed: {self.stats['variants_fixed']}")
        self.log(f"Variants skipped: {self.stats['variants_skipped']}")
        self.log(f"Errors: {self.stats['errors']}")

        if self.dry_run:
            self.log("\nRun with --execute to apply fixes.")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fix double-prefixed storage paths")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    parser.add_argument("--execute", action="store_true", help="Apply changes")

    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        parser.error("Must specify either --dry-run or --execute")

    if args.dry_run and args.execute:
        parser.error("Cannot specify both --dry-run and --execute")

    with Session(engine) as session:
        fixer = StoragePathFixer(session, dry_run=args.dry_run)
        fixer.run()


if __name__ == "__main__":
    main()

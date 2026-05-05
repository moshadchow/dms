from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status
from sqlmodel import Session, func, select

from categories.models import Category
from directories.models import Directory, DirectoryCreate, DirectoryNode, DirectoryUpdate
from documents.models import Document, DocumentStatus
from users.models import User


class DirectoryService:
    def __init__(self, session: Session):
        self.session = session

    # ──────────────────────────────────────────
    # Queries
    # ──────────────────────────────────────────

    def get_directory(self, directory_id: int) -> Directory:
        d = self.session.get(Directory, directory_id)
        if not d:
            raise HTTPException(status_code=404, detail=f"Directory {directory_id} not found")
        return d

    def list_by_category(self, category_id: int) -> List[Directory]:
        """Return root-level directories (parent_id IS NULL) for a category."""
        self._check_category(category_id)
        return list(
            self.session.exec(
                select(Directory)
                .where(
                    Directory.category_id == category_id,
                    Directory.parent_id == None,  # noqa: E711
                )
                .order_by(Directory.name)
            ).all()
        )

    def get_tree(self, category_id: int) -> List[DirectoryNode]:
        """Return the full nested directory tree for a category."""
        self._check_category(category_id)
        all_dirs = self.session.exec(
            select(Directory).where(Directory.category_id == category_id)
        ).all()
        return self._build_tree(all_dirs, parent_id=None)

    def _build_tree(
        self, all_dirs: List[Directory], parent_id: Optional[int]
    ) -> List[DirectoryNode]:
        nodes = []
        for d in all_dirs:
            if d.parent_id == parent_id:
                node = DirectoryNode(
                    **d.model_dump(),
                    children=self._build_tree(all_dirs, parent_id=d.id),
                )
                nodes.append(node)
        return sorted(nodes, key=lambda n: n.name)

    # ──────────────────────────────────────────
    # Mutations
    # ──────────────────────────────────────────

    def create_directory(self, data: DirectoryCreate, created_by: int) -> Directory:
        self._check_category(data.category_id)

        # Treat parent_id=0 the same as null — means root-level directory
        if data.parent_id == 0:
            data = data.model_copy(update={"parent_id": None})

        if data.parent_id is not None:
            parent = self.session.get(Directory, data.parent_id)
            if not parent:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"Parent directory {data.parent_id} not found. "
                        "To create a root-level directory, omit parent_id or set it to null."
                    ),
                )
            if parent.category_id != data.category_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Parent directory does not belong to the specified category",
                )

        # Duplicate name check within the same parent
        exists = self.session.exec(
            select(Directory).where(
                Directory.name == data.name,
                Directory.category_id == data.category_id,
                Directory.parent_id == data.parent_id,
            )
        ).first()
        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A directory named '{data.name}' already exists here",
            )

        directory = Directory(
            **data.model_dump(),
            created_by=created_by,
        )
        self.session.add(directory)
        self.session.commit()
        self.session.refresh(directory)
        return directory

    def update_directory(self, directory_id: int, data: DirectoryUpdate) -> Directory:
        directory = self.get_directory(directory_id)
        updates = data.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(directory, field, value)
        directory.updated_at = datetime.utcnow()
        self.session.add(directory)
        self.session.commit()
        self.session.refresh(directory)
        return directory

    def delete_directory(self, directory_id: int) -> None:
        directory = self.get_directory(directory_id)

        # Block delete if subdirectories exist
        children = self.session.exec(
            select(Directory).where(Directory.parent_id == directory_id).limit(1)
        ).first()
        if children:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Remove all subdirectories before deleting this directory.",
            )

        # Block delete if any active or archived documents exist
        active_docs = self.session.exec(
            select(Document).where(
                Document.directory_id == directory_id,
                Document.status != DocumentStatus.DELETED,
            ).limit(1)
        ).first()
        if active_docs:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Remove or delete all documents in this directory before deleting it.",
            )

        # Hard-delete any soft-deleted (status=deleted) documents so FK constraint
        # is not violated when the directory row is removed from the database.
        soft_deleted_docs = self.session.exec(
            select(Document).where(
                Document.directory_id == directory_id,
                Document.status == DocumentStatus.DELETED,
            )
        ).all()
        for doc in soft_deleted_docs:
            self.session.delete(doc)

        self.session.flush()  # remove orphaned docs before deleting directory

        self.session.delete(directory)
        self.session.commit()

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    def _check_category(self, category_id: int) -> None:
        cat = self.session.get(Category, category_id)
        if not cat:
            raise HTTPException(status_code=404, detail=f"Category {category_id} not found")

from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status
from sqlmodel import Session, select

from core.access import (
    ensure_category_access,
    ensure_directory_access,
    ensure_directory_read_access,
    get_effective_directory_ids,
    get_user_category_ids,
    get_user_directory_grant_ids,
    has_directory_content_access,
)
from audit.models import AuditAction, AuditModule
from audit.service import AuditService
from directories.models import (
    Directory,
    DirectoryCreate,
    DirectoryNode,
    DirectoryRead,
    DirectoryUpdate,
)
from documents.models import Document, DocumentStatus
from users.models import User


class DirectoryService:
    def __init__(self, session: Session):
        self.session = session

    # ──────────────────────────────────────────
    # Queries
    # ──────────────────────────────────────────

    def get_directory(self, directory_id: int, current_user: User) -> DirectoryRead:
        """Read access: direct, or navigation via an accessible descendant."""
        directory = ensure_directory_read_access(self.session, current_user, directory_id)
        return DirectoryRead(
            **directory.model_dump(),
            navigation_only=not has_directory_content_access(
                self.session, current_user, directory
            ),
        )

    def list_by_category(self, category_id: int, current_user: User) -> List[DirectoryRead]:
        """Return root-level directories (parent_id IS NULL) for a category.

        Partial-access users see only granted roots (or roots that are
        ancestors of a granted subtree).
        """
        try:
            ensure_category_access(self.session, current_user, category_id)
            roots = self.session.exec(
                select(Directory)
                .where(
                    Directory.category_id == category_id,
                    Directory.parent_id == None,  # noqa: E711
                )
                .order_by(Directory.name)
            ).all()
            return [DirectoryRead(**d.model_dump()) for d in roots]
        except HTTPException:
            if current_user.is_admin():
                raise
        effective = get_effective_directory_ids(self.session, current_user, category_id)
        if not effective:
            raise HTTPException(status_code=404, detail="Category not found")
        all_dirs = list(
            self.session.exec(
                select(Directory).where(Directory.category_id == category_id)
            ).all()
        )
        visible_roots = [
            d for d in all_dirs if d.parent_id is None and self._subtree_has(d, all_dirs, effective)
        ]
        visible_roots = sorted(visible_roots, key=lambda d: d.name)
        return [
            DirectoryRead(**d.model_dump(), navigation_only=d.id not in effective)
            for d in visible_roots
        ]

    def get_tree(self, category_id: int, current_user: User) -> List[DirectoryNode]:
        """Return the nested directory tree for a category.

        Full-tree for category-granted users; pruned to granted subtrees
        (keeping ancestor path nodes) for directory-only grants.
        """
        try:
            ensure_category_access(self.session, current_user, category_id)
            all_dirs = self.session.exec(
                select(Directory).where(Directory.category_id == category_id)
            ).all()
            return self._build_tree(all_dirs, parent_id=None)
        except HTTPException:
            if current_user.is_admin():
                raise
        effective = get_effective_directory_ids(self.session, current_user, category_id)
        if not effective:
            raise HTTPException(status_code=404, detail="Category not found")
        all_dirs = self.session.exec(
            select(Directory).where(Directory.category_id == category_id)
        ).all()
        return self._build_pruned_tree(all_dirs, parent_id=None, effective=effective)

    def _subtree_has(self, root: Directory, all_dirs: List[Directory], effective: set) -> bool:
        if root.id in effective:
            return True
        return any(
            d.id in effective
            for d in all_dirs
            if self._is_descendant(d, root.id, {x.id: x.parent_id for x in all_dirs})
        )

    @staticmethod
    def _is_descendant(node: Directory, ancestor_id: int, parent_of: dict) -> bool:
        current = node.parent_id
        seen = set()
        while current is not None and current not in seen:
            if current == ancestor_id:
                return True
            seen.add(current)
            current = parent_of.get(current)
        return False

    def _build_pruned_tree(
        self, all_dirs: List[Directory], parent_id: Optional[int], effective: set
    ) -> List[DirectoryNode]:
        nodes = []
        for d in all_dirs:
            if d.parent_id == parent_id and self._subtree_has(d, all_dirs, effective):
                node = DirectoryNode(
                    **d.model_dump(),
                    navigation_only=d.id not in effective,
                    children=self._build_pruned_tree(all_dirs, parent_id=d.id, effective=effective),
                )
                nodes.append(node)
        return sorted(nodes, key=lambda n: n.name)

    def list_all(self, current_user: User) -> List[Directory]:
        """Return all directories the user has category or directory access to."""
        if current_user.is_admin():
            dirs = list(self.session.exec(
                select(Directory).order_by(Directory.name)
            ).all())
        else:
            accessible_cat_ids = list(get_user_category_ids(self.session, current_user.id))
            grant_ids = get_user_directory_grant_ids(self.session, current_user.id)
            conditions = []
            if accessible_cat_ids:
                conditions.append(Directory.category_id.in_(accessible_cat_ids))
            effective: set = set()
            if grant_ids:
                all_dirs = list(self.session.exec(select(Directory)).all())
                from core.access import expand_descendant_ids

                effective = expand_descendant_ids(all_dirs, set(grant_ids))
            if effective:
                conditions.append(Directory.id.in_(sorted(effective)))
            if not conditions:
                return []
            query = select(Directory).order_by(Directory.name)
            if len(conditions) == 1:
                query = query.where(conditions[0])
            else:
                query = query.where(conditions[0] | conditions[1])
            dirs = list(self.session.exec(query).all())
        return dirs

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

    def create_directory(self, data: DirectoryCreate, created_by: int, current_user: User) -> Directory:
        ensure_category_access(self.session, current_user, data.category_id)

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

        # Log audit event
        AuditService(self.session).log_event(
            action=AuditAction.CREATE_DIRECTORY,
            module=AuditModule.DIRECTORIES,
            company_id=current_user.company_id,
            entity_name="directory",
            entity_id=str(directory.id),
            new_value={"name": data.name, "category_id": data.category_id},
            description=f"Created directory '{data.name}'",
            is_success=True,
            user=current_user,
        )

        return directory

    def update_directory(self, directory_id: int, data: DirectoryUpdate, current_user: User) -> Directory:
        directory = ensure_directory_access(self.session, current_user, directory_id)
        old_values = {"name": directory.name}
        updates = data.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(directory, field, value)
        directory.updated_at = datetime.utcnow()
        self.session.add(directory)
        self.session.commit()
        self.session.refresh(directory)

        # Log audit event
        AuditService(self.session).log_event(
            action=AuditAction.RENAME_DIRECTORY,
            module=AuditModule.DIRECTORIES,
            company_id=current_user.company_id,
            entity_name="directory",
            entity_id=str(directory_id),
            old_value=old_values,
            new_value=updates,
            description=f"Updated directory {directory_id}",
            is_success=True,
            user=current_user,
        )

        return directory

    def delete_directory(self, directory_id: int, current_user: User) -> None:
        directory = ensure_directory_access(self.session, current_user, directory_id)

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

        dir_name = directory.name
        self.session.delete(directory)
        self.session.commit()

        # Log audit event
        AuditService(self.session).log_event(
            action=AuditAction.DELETE_DIRECTORY,
            module=AuditModule.DIRECTORIES,
            company_id=current_user.company_id,
            entity_name="directory",
            entity_id=str(directory_id),
            old_value={"name": dir_name},
            description=f"Deleted directory '{dir_name}'",
            is_success=True,
            user=current_user,
        )

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────


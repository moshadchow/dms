from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status
from sqlmodel import Session, func, select

from audit.models import AuditAction, AuditModule
from audit.service import AuditService
from categories.models import Category, CategoryCreate, CategoryReadWithStats, CategoryUpdate
from core.access import (
    ensure_category_read_access,
    get_effective_directory_ids,
    get_user_category_ids,
    get_user_directory_grant_ids,
)
from directories.models import Directory
from documents.models import Document, DocumentStatus
from users.models import RoleName, User


class CategoryService:
    def __init__(self, session: Session):
        self.session = session

    def list_categories(
        self,
        current_user: User,
        include_inactive: bool = False,
    ) -> List[CategoryReadWithStats]:
        # SUPERADMIN has no access to categories
        if any(r.name == RoleName.SUPERADMIN for r in current_user.roles):
            return []

        query = select(Category)

        if current_user.is_admin():
            # ADMIN: scope to own company
            query = query.where(Category.company_id == current_user.company_id)
            if not include_inactive:
                query = query.where(Category.is_active == True)
        else:
            # Non-admin: categories with a full category grant OR with at
            # least one directory grant inside (visible as a container).
            category_ids = get_user_category_ids(self.session, current_user.id)
            grant_dir_ids = get_user_directory_grant_ids(self.session, current_user.id)
            partial_category_ids: set = set()
            if grant_dir_ids:
                grant_dirs = self.session.exec(
                    select(Directory).where(Directory.id.in_(grant_dir_ids))
                ).all()
                partial_category_ids = {d.category_id for d in grant_dirs}
            visible_ids = set(category_ids) | partial_category_ids
            if not visible_ids:
                return []
            query = query.where(
                Category.id.in_(visible_ids),
                Category.is_active == True,
                Category.company_id == current_user.company_id,
            )

        categories = self.session.exec(query.order_by(Category.name)).all()
        granted_category_ids = (
            get_user_category_ids(self.session, current_user.id)
            if not current_user.is_admin()
            else {c.id for c in categories}
        )
        result = []
        for cat in categories:
            access_type = "full"
            granted_directory_ids: list = []
            if not current_user.is_admin() and cat.id not in granted_category_ids:
                access_type = "partial"
                granted_directory_ids = sorted(
                    get_effective_directory_ids(self.session, current_user, cat.id)
                )

            dir_count_query = select(func.count(Directory.id)).where(Directory.category_id == cat.id)
            doc_count_query = (
                select(func.count(Document.id))
                .join(Directory, Document.directory_id == Directory.id)
                .where(
                    Directory.category_id == cat.id,
                    Document.status == DocumentStatus.ACTIVE,
                )
            )

            if access_type == "partial":
                # Never count content the user cannot open: scope stats to
                # the granted subtrees (navigation-only ancestors excluded).
                if not granted_directory_ids:
                    dir_count = 0
                    doc_count = 0
                else:
                    dir_count_query = dir_count_query.where(
                        Directory.id.in_(granted_directory_ids)
                    )
                    doc_count_query = doc_count_query.where(
                        Directory.id.in_(granted_directory_ids)
                    )
                    dir_count = self.session.exec(dir_count_query).one()
                    doc_count = self.session.exec(doc_count_query).one()
            else:
                dir_count = self.session.exec(dir_count_query).one()
                doc_count = self.session.exec(doc_count_query).one()

            item = CategoryReadWithStats(
                **cat.model_dump(),
                directory_count=dir_count,
                document_count=doc_count,
                access_type=access_type,
                granted_directory_ids=granted_directory_ids,
            )
            result.append(item)
        return result

    def get_category(self, category_id: int, current_user: User) -> Category:
        # Read-only: directory-grant users may fetch metadata for a category
        # that holds one of their granted directories (page headers).
        return ensure_category_read_access(self.session, current_user, category_id)

    def create_category(self, data: CategoryCreate, current_user: User) -> Category:
        if current_user.company_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin must belong to a company to create categories",
            )

        # Check for duplicate name within the same company
        exists = self.session.exec(
            select(Category).where(
                Category.name == data.name,
                Category.company_id == current_user.company_id,
            )
        ).first()
        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Category '{data.name}' already exists in your company",
            )

        cat = Category(
            **data.model_dump(),
            company_id=current_user.company_id,
            created_by=current_user.id,
        )
        self.session.add(cat)
        self.session.commit()
        self.session.refresh(cat)

        AuditService(self.session).log_event(
            action=AuditAction.CREATE_CATEGORY,
            module=AuditModule.CATEGORIES,
            company_id=current_user.company_id,
            entity_name="category",
            entity_id=str(cat.id),
            new_value={"name": data.name},
            description=f"Created category '{data.name}'",
            is_success=True,
        )

        return cat

    def update_category(self, category_id: int, data: CategoryUpdate, current_user: User) -> Category:
        cat = self._get_category_or_404(category_id)

        # Enforce company ownership
        if cat.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Category belongs to another company",
            )

        old_values = {"name": cat.name, "description": cat.description, "is_active": cat.is_active}
        updates = data.model_dump(exclude_unset=True)

        # Check name uniqueness within company if renaming
        if "name" in updates and updates["name"] != cat.name:
            dup = self.session.exec(
                select(Category).where(
                    Category.name == updates["name"],
                    Category.company_id == current_user.company_id,
                    Category.id != category_id,
                )
            ).first()
            if dup:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Category '{updates['name']}' already exists in your company",
                )

        for field, value in updates.items():
            setattr(cat, field, value)
        cat.updated_at = datetime.utcnow()
        self.session.add(cat)
        self.session.commit()
        self.session.refresh(cat)

        AuditService(self.session).log_event(
            action=AuditAction.UPDATE_CATEGORY,
            module=AuditModule.CATEGORIES,
            company_id=current_user.company_id,
            entity_name="category",
            entity_id=str(category_id),
            old_value=old_values,
            new_value=updates,
            description=f"Updated category {category_id}",
            is_success=True,
        )

        return cat

    def delete_category(self, category_id: int, current_user: User) -> None:
        cat = self._get_category_or_404(category_id)

        # Enforce company ownership
        if cat.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Category belongs to another company",
            )

        # Check for existing directories before hard delete
        dirs = self.session.exec(
            select(Directory).where(Directory.category_id == category_id).limit(1)
        ).first()
        if dirs:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete category with existing directories. Archive it instead.",
            )
        cat_name = cat.name
        self.session.delete(cat)
        self.session.commit()

        AuditService(self.session).log_event(
            action=AuditAction.DELETE_CATEGORY,
            module=AuditModule.CATEGORIES,
            company_id=current_user.company_id,
            entity_name="category",
            entity_id=str(category_id),
            old_value={"name": cat_name},
            description=f"Deleted category '{cat_name}'",
            is_success=True,
        )

    def _get_category_or_404(self, category_id: int) -> Category:
        cat = self.session.get(Category, category_id)
        if not cat:
            raise HTTPException(status_code=404, detail=f"Category {category_id} not found")
        return cat

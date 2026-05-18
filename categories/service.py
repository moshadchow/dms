from datetime import datetime
from typing import List

from fastapi import HTTPException, status
from sqlmodel import Session, func, select

from categories.models import Category, CategoryCreate, CategoryReadWithStats, CategoryUpdate
from core.access import ensure_category_access
from directories.models import Directory
from documents.models import Document, DocumentStatus
from users.models import User, UserCategoryLink


class CategoryService:
    def __init__(self, session: Session):
        self.session = session

    def list_categories(
        self,
        current_user: User,
        include_inactive: bool = False,
    ) -> List[CategoryReadWithStats]:
        query = select(Category)

        if current_user.is_admin():
            if not include_inactive:
                query = query.where(Category.is_active == True)
        else:
            query = (
                query.join(UserCategoryLink, UserCategoryLink.category_id == Category.id)
                .where(
                    UserCategoryLink.user_id == current_user.id,
                    Category.is_active == True,
                )
            )

        categories = self.session.exec(query.order_by(Category.name)).all()
        result = []
        for cat in categories:
            dir_count_query = select(func.count(Directory.id)).where(Directory.category_id == cat.id)
            doc_count_query = (
                select(func.count(Document.id))
                .join(Directory, Document.directory_id == Directory.id)
                .where(
                    Directory.category_id == cat.id,
                    Document.status == DocumentStatus.ACTIVE,
                )
            )

            dir_count = self.session.exec(dir_count_query).one()
            doc_count = self.session.exec(doc_count_query).one()
            item = CategoryReadWithStats(
                **cat.model_dump(),
                directory_count=dir_count,
                document_count=doc_count,
            )
            result.append(item)
        return result

    def get_category(self, category_id: int, current_user: User) -> Category:
        return ensure_category_access(self.session, current_user, category_id)

    def create_category(self, data: CategoryCreate) -> Category:
        exists = self.session.exec(
            select(Category).where(Category.name == data.name)
        ).first()
        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Category '{data.name}' already exists",
            )
        cat = Category(**data.model_dump())
        self.session.add(cat)
        self.session.commit()
        self.session.refresh(cat)
        return cat

    def update_category(self, category_id: int, data: CategoryUpdate) -> Category:
        cat = self._get_category_or_404(category_id)
        updates = data.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(cat, field, value)
        cat.updated_at = datetime.utcnow()
        self.session.add(cat)
        self.session.commit()
        self.session.refresh(cat)
        return cat

    def delete_category(self, category_id: int) -> None:
        cat = self._get_category_or_404(category_id)
        # Check for existing directories before hard delete
        dirs = self.session.exec(
            select(Directory).where(Directory.category_id == category_id).limit(1)
        ).first()
        if dirs:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete category with existing directories. Archive it instead.",
            )
        self.session.delete(cat)
        self.session.commit()

    def _get_category_or_404(self, category_id: int) -> Category:
        cat = self.session.get(Category, category_id)
        if not cat:
            raise HTTPException(status_code=404, detail=f"Category {category_id} not found")
        return cat

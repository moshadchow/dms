from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status
from sqlmodel import Session, func, select

from categories.models import Category, CategoryCreate, CategoryReadWithStats, CategoryUpdate
from directories.models import Directory
from documents.models import Document, DocumentStatus


class CategoryService:
    def __init__(self, session: Session):
        self.session = session

    def list_categories(
        self,
        include_inactive: bool = False,
    ) -> List[CategoryReadWithStats]:
        query = select(Category)
        if not include_inactive:
            query = query.where(Category.is_active == True)

        categories = self.session.exec(query).all()
        result = []
        for cat in categories:
            dir_count = self.session.exec(
                select(func.count(Directory.id)).where(Directory.category_id == cat.id)
            ).one()
            doc_count = self.session.exec(
                select(func.count(Document.id))
                .join(Directory, Document.directory_id == Directory.id)
                .where(
                    Directory.category_id == cat.id,
                    Document.status == DocumentStatus.ACTIVE,
                )
            ).one()
            item = CategoryReadWithStats(
                **cat.model_dump(),
                directory_count=dir_count,
                document_count=doc_count,
            )
            result.append(item)
        return result

    def get_category(self, category_id: int) -> Category:
        cat = self.session.get(Category, category_id)
        if not cat:
            raise HTTPException(status_code=404, detail=f"Category {category_id} not found")
        return cat

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
        cat = self.get_category(category_id)
        updates = data.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(cat, field, value)
        cat.updated_at = datetime.utcnow()
        self.session.add(cat)
        self.session.commit()
        self.session.refresh(cat)
        return cat

    def delete_category(self, category_id: int) -> None:
        cat = self.get_category(category_id)
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

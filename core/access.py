from fastapi import HTTPException, status
from sqlmodel import Session, select

from categories.models import Category
from directories.models import Directory
from documents.models import Document, DocumentStatus
from users.models import User, UserCategoryLink


def ensure_category_access(
    session: Session,
    user: User,
    category_id: int,
) -> Category:
    if user.is_admin():
        category = session.get(Category, category_id)
        if not category:
            raise HTTPException(status_code=404, detail=f"Category {category_id} not found")
        return category

    category = session.exec(
        select(Category)
        .join(UserCategoryLink, UserCategoryLink.category_id == Category.id)
        .where(
            Category.id == category_id,
            Category.is_active == True,
            UserCategoryLink.user_id == user.id,
        )
    ).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category


def ensure_directory_access(
    session: Session,
    user: User,
    directory_id: int,
) -> Directory:
    directory = session.get(Directory, directory_id)
    if not directory:
        raise HTTPException(status_code=404, detail=f"Directory {directory_id} not found")

    ensure_category_access(session, user, directory.category_id)
    return directory


def ensure_document_access(
    session: Session,
    user: User,
    document_id: int,
    *,
    include_deleted: bool = False,
) -> Document:
    document = session.get(Document, document_id)
    if not document or (document.status == DocumentStatus.DELETED and not include_deleted):
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

    directory = session.get(Directory, document.directory_id)
    if not directory:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

    ensure_category_access(session, user, directory.category_id)
    return document

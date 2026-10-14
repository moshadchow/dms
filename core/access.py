from typing import Optional, Set

from fastapi import HTTPException, status
from sqlmodel import Session, select

from categories.models import Category
from directories.models import Directory
from documents.models import Document, DocumentStatus, DocumentUserLevelLink
from users.models import RoleName, User, UserCategoryLink


def _is_superadmin(user: User) -> bool:
    return any(r.name == RoleName.SUPERADMIN for r in user.roles)


def ensure_category_access(
    session: Session,
    user: User,
    category_id: int,
) -> Category:
    if user.is_admin():
        # SUPERADMIN has no access to categories
        if _is_superadmin(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Super Admin cannot access categories",
            )
        # ADMIN: scope to own company
        category = session.exec(
            select(Category).where(
                Category.id == category_id,
                Category.company_id == user.company_id,
            )
        ).first()
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
            Category.company_id == user.company_id,
        )
    ).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category


def get_user_category_ids(session: Session, user_id: int) -> Set[int]:
    """Category ids granted to a user via UserCategoryLink."""
    return {
        link.category_id
        for link in session.exec(
            select(UserCategoryLink).where(UserCategoryLink.user_id == user_id)
        ).all()
    }


def get_user_directory_grant_ids(session: Session, user_id: int) -> Set[int]:
    """Directory ids explicitly granted to a user (lazy import avoids cycles)."""
    from users.models import UserDirectoryLink

    return {
        link.directory_id
        for link in session.exec(
            select(UserDirectoryLink).where(UserDirectoryLink.user_id == user_id)
        ).all()
    }


def expand_descendant_ids(
    all_dirs: list,
    root_ids: Set[int],
) -> Set[int]:
    """Expand granted ids to include all descendants (subtree semantics)."""
    effective = set(root_ids)
    children_of: dict = {}
    for d in all_dirs:
        children_of.setdefault(d.parent_id, []).append(d.id)
    stack = list(root_ids)
    while stack:
        current = stack.pop()
        for child_id in children_of.get(current, []):
            if child_id not in effective:
                effective.add(child_id)
                stack.append(child_id)
    return effective


def get_effective_directory_ids(
    session: Session,
    user: User,
    category_id: Optional[int] = None,
) -> Set[int]:
    """All directory ids a non-admin can access in a category scope.

    Union of: every directory in a category-granted category, plus the
    subtree (granted dir + descendants) of each explicit directory grant.
    Admins bypass grants (company-scoped); returns empty set for them.
    """
    if user.is_admin():
        return set()
    category_ids = get_user_category_ids(session, user.id)
    grant_ids = get_user_directory_grant_ids(session, user.id)
    if not category_ids and not grant_ids:
        return set()

    query = select(Directory)
    if category_id is not None:
        query = query.where(Directory.category_id == category_id)
    all_dirs = list(session.exec(query).all())

    effective: Set[int] = set()
    if category_id is not None:
        if category_id in category_ids:
            effective.update(d.id for d in all_dirs)
    else:
        effective.update(d.id for d in all_dirs if d.category_id in category_ids)

    scoped_grants = (
        {g for g in grant_ids if any(d.id == g for d in all_dirs)}
        if category_id is not None
        else set(grant_ids)
    )
    if scoped_grants:
        scope_dirs = all_dirs if category_id is not None else list(
            session.exec(select(Directory)).all()
        )
        effective.update(expand_descendant_ids(scope_dirs, scoped_grants))
    return effective


def _directory_grant_covers(
    session: Session,
    user: User,
    directory: Directory,
) -> bool:
    """True if any explicit grant on the directory or its ancestors applies.

    The covering grant's category must be active and same-company.
    """
    grant_ids = get_user_directory_grant_ids(session, user.id)
    if not grant_ids:
        return False
    current: Optional[Directory] = directory
    seen = set()
    while current is not None and current.id not in seen:
        seen.add(current.id)
        if current.id in grant_ids:
            category = session.get(Category, current.category_id)
            if (
                category is not None
                and category.is_active == True
                and category.company_id == user.company_id
            ):
                return True
            return False
        if current.parent_id is None:
            break
        current = session.get(Directory, current.parent_id)
    return False


def ensure_directory_access(
    session: Session,
    user: User,
    directory_id: int,
) -> Directory:
    directory = session.get(Directory, directory_id)
    if not directory:
        raise HTTPException(status_code=404, detail=f"Directory {directory_id} not found")

    if user.is_admin():
        ensure_category_access(session, user, directory.category_id)
        return directory

    try:
        ensure_category_access(session, user, directory.category_id)
        return directory
    except HTTPException:
        pass

    if _directory_grant_covers(session, user, directory):
        return directory
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")


def has_directory_content_access(
    session: Session,
    user: User,
    directory: Directory,
) -> bool:
    """Non-raising direct-access check: category grant or covering grant."""
    if user.is_admin():
        try:
            ensure_category_access(session, user, directory.category_id)
            return True
        except HTTPException:
            return False
    try:
        ensure_category_access(session, user, directory.category_id)
        return True
    except HTTPException:
        pass
    return _directory_grant_covers(session, user, directory)


def can_navigate_directory(
    session: Session,
    user: User,
    directory: Directory,
) -> bool:
    """True if `directory` may be opened for traversal only.

    Direct access always qualifies. Otherwise the directory must have at
    least one accessible descendant (recursive), so users granted a
    subdirectory can walk up through its ancestor chain — and only that
    chain. The directory's own category must be active and same-company.
    """
    if has_directory_content_access(session, user, directory):
        return True

    category = session.get(Category, directory.category_id)
    if (
        category is None
        or category.is_active != True  # noqa: E712
        or category.company_id != user.company_id
    ):
        return False

    effective = get_effective_directory_ids(session, user)
    if not effective:
        return False

    all_dirs = list(session.exec(select(Directory)).all())
    children_of: dict = {}
    for d in all_dirs:
        children_of.setdefault(d.parent_id, []).append(d)
    stack = list(children_of.get(directory.id, []))
    seen: set = set()
    while stack:
        node = stack.pop()
        if node.id in seen:
            continue
        seen.add(node.id)
        if node.id in effective:
            return True
        stack.extend(children_of.get(node.id, []))
    return False


def ensure_directory_read_access(
    session: Session,
    user: User,
    directory_id: int,
) -> Directory:
    """Read/navigation guard for GET on a directory.

    Direct access passes unchanged; ancestor traversal is allowed when an
    accessible descendant exists. Everything else 404s (no oracle).
    """
    directory = session.get(Directory, directory_id)
    if not directory:
        raise HTTPException(status_code=404, detail=f"Directory {directory_id} not found")
    try:
        return ensure_directory_access(session, user, directory_id)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
    if can_navigate_directory(session, user, directory):
        return directory
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")


def ensure_category_read_access(
    session: Session,
    user: User,
    category_id: int,
) -> Category:
    """Read guard for category metadata (headers, breadcrumbs).

    Category grants behave as before; directory-grant users may read a
    category that holds at least one of their granted directories — metadata
    only, content stays filtered by directory/user-level guards.
    """
    try:
        return ensure_category_access(session, user, category_id)
    except HTTPException as exc:
        if exc.status_code != 404 or user.is_admin():
            raise
    grant_ids = get_user_directory_grant_ids(session, user.id)
    category = session.get(Category, category_id)
    if (
        not grant_ids
        or category is None
        or category.is_active != True  # noqa: E712
        or category.company_id != user.company_id
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    has_grant = session.exec(
        select(Directory).where(
            Directory.id.in_(sorted(grant_ids)),
            Directory.category_id == category_id,
        )
    ).first()
    if has_grant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category


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

    ensure_directory_access(session, user, directory.id)
    return document


def ensure_document_user_level_access(
    session: Session,
    user: User,
    document: Document,
) -> None:
    if user.is_admin():
        return

    permitted_level_ids = [
        link.user_level_id
        for link in session.exec(
            select(DocumentUserLevelLink).where(
                DocumentUserLevelLink.document_id == document.id,
            )
        ).all()
    ]

    # If no user level links exist, the document is not visible to anyone except admins
    if not permitted_level_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this document",
        )

    if user.user_level_id not in permitted_level_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this document",
        )

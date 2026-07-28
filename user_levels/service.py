from datetime import datetime
from typing import List

from fastapi import HTTPException, status
from sqlmodel import Session, select

from user_levels.models import (
    UserLevel,
    UserLevelCreate,
    UserLevelRead,
    UserLevelUpdate,
)


class UserLevelService:
    def __init__(self, session: Session):
        self.session = session

    def list_user_levels(self) -> List[UserLevelRead]:
        levels = self.session.exec(
            select(UserLevel).order_by(UserLevel.name)
        ).all()
        return [UserLevelRead.model_validate(lv) for lv in levels]

    def list_active_user_levels(self) -> List[UserLevelRead]:
        levels = self.session.exec(
            select(UserLevel)
            .where(UserLevel.is_active == True)
            .order_by(UserLevel.name)
        ).all()
        return [UserLevelRead.model_validate(lv) for lv in levels]

    def get_user_level(self, level_id: int) -> UserLevelRead:
        level = self._get_or_404(level_id)
        return UserLevelRead.model_validate(level)

    def create_user_level(self, data: UserLevelCreate) -> UserLevelRead:
        exists = self.session.exec(
            select(UserLevel).where(UserLevel.name == data.name)
        ).first()
        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User level '{data.name}' already exists",
            )
        level = UserLevel(**data.model_dump())
        self.session.add(level)
        self.session.commit()
        self.session.refresh(level)
        return UserLevelRead.model_validate(level)

    def update_user_level(self, level_id: int, data: UserLevelUpdate) -> UserLevelRead:
        level = self._get_or_404(level_id)
        updates = data.model_dump(exclude_unset=True)
        if "name" in updates and updates["name"] != level.name:
            exists = self.session.exec(
                select(UserLevel).where(
                    UserLevel.name == updates["name"],
                    UserLevel.id != level_id,
                )
            ).first()
            if exists:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"User level '{updates['name']}' already exists",
                )
        for field, value in updates.items():
            setattr(level, field, value)
        level.updated_at = datetime.utcnow()
        self.session.add(level)
        self.session.commit()
        self.session.refresh(level)
        return UserLevelRead.model_validate(level)

    def delete_user_level(self, level_id: int) -> None:
        from users.models import User
        level = self._get_or_404(level_id)
        assigned = self.session.exec(
            select(User).where(User.user_level_id == level_id).limit(1)
        ).first()
        if assigned:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete user level with assigned users. Reassign users first.",
            )
        self.session.delete(level)
        self.session.commit()

    def _get_or_404(self, level_id: int) -> UserLevel:
        level = self.session.get(UserLevel, level_id)
        if not level:
            raise HTTPException(
                status_code=404,
                detail=f"User level {level_id} not found",
            )
        return level

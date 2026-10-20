from datetime import datetime
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


class UserLevelBase(SQLModel):
    name:        str           = Field(max_length=100, min_length=1)
    description: Optional[str] = Field(default=None, max_length=255)
    is_active:   bool          = Field(default=True)


class UserLevel(UserLevelBase, table=True):
    __tablename__ = "user_levels"

    id:         Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime      = Field(default_factory=datetime.utcnow)
    updated_at: datetime      = Field(default_factory=datetime.utcnow)

    users: List["User"] = Relationship(
        back_populates="user_level",
        sa_relationship_kwargs={"lazy": "selectin"},
    )


class UserLevelCreate(UserLevelBase):
    pass


class UserLevelUpdate(SQLModel):
    name:        Optional[str]  = None
    description: Optional[str]  = None
    is_active:   Optional[bool] = None


class UserLevelRead(UserLevelBase):
    id:         int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

from typing import Optional

from sqlmodel import Field, SQLModel


class SystemSetting(SQLModel, table=True):
    """Key-value store for admin-configurable system settings."""

    key: str = Field(max_length=100, primary_key=True)
    value: str = Field(max_length=500)
    description: Optional[str] = Field(default=None, max_length=500)

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class EmailNotification(SQLModel, table=True):
    __tablename__ = "email_notifications"

    id: Optional[int] = Field(default=None, primary_key=True)
    instance_id: int = Field(foreign_key="workflow_instances.id", index=True)
    step_order: int = Field(default=1)
    recipient_user_id: int = Field(foreign_key="users.id", index=True)
    notification_type: str = Field(max_length=30, index=True)
    status: str = Field(default="pending", max_length=20, index=True)
    error_message: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = Field(default=None)

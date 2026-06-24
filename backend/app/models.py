"""
SQLAlchemy 數據模型 - TodoItem
"""
import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum as SAEnum
from app.database import Base
import enum


class TodoStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TodoPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TodoItem(Base):
    __tablename__ = "todos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(200), nullable=False, index=True)
    description = Column(Text, default="")
    status = Column(
        SAEnum(TodoStatus),
        default=TodoStatus.PENDING,
        nullable=False,
        index=True,
    )
    priority = Column(
        SAEnum(TodoPriority),
        default=TodoPriority.MEDIUM,
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value if self.status else None,
            "priority": self.priority.value if self.priority else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

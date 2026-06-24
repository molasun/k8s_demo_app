"""
Pydantic 請求/響應模型
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.models import TodoStatus, TodoPriority


class TodoCreate(BaseModel):
    """創建 Todo 的請求體"""
    title: str = Field(..., min_length=1, max_length=200, description="標題")
    description: str = Field(default="", max_length=2000, description="描述")
    priority: TodoPriority = Field(default=TodoPriority.MEDIUM, description="優先級")


class TodoUpdate(BaseModel):
    """更新 Todo 的請求體（所有字段可選）"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[TodoStatus] = None
    priority: Optional[TodoPriority] = None


class TodoResponse(BaseModel):
    """Todo 響應體"""
    id: int
    title: str
    description: str
    status: str
    priority: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


class HealthResponse(BaseModel):
    """健康檢查響應"""
    status: str = "ok"
    service: str = "backend"
    trace_id: Optional[str] = None


class ErrorResponse(BaseModel):
    """錯誤響應"""
    detail: str
    error_code: Optional[str] = None

"""
API 路由定義 - Todo CRUD 端點
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from opentelemetry import trace

from app import crud, schemas, models
from app.database import get_db

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

router = APIRouter(prefix="/api", tags=["todos"])


def get_metrics(request: Request):
    """從 app state 獲取 metrics 對象"""
    return request.app.state.metrics


@router.get("/health", response_model=schemas.HealthResponse)
async def health_check():
    """健康檢查端點 - 返回當前 trace_id"""
    current_span = trace.get_current_span()
    span_context = current_span.get_span_context() if current_span else None

    trace_id_hex = None
    if span_context and span_context.is_valid:
        trace_id_hex = format(span_context.trace_id, "032x")

    logger.info("Health check", extra={"trace_id": trace_id_hex})

    return schemas.HealthResponse(
        status="ok",
        service="backend",
        trace_id=trace_id_hex,
    )


@router.get("/todos/count")
async def count_todos(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """獲取 Todo 總數（用於分頁）"""
    count = crud.get_todo_count(db, status=status, priority=priority, search=search)
    return {"count": count}


@router.get("/todos", response_model=list[schemas.TodoResponse])
async def list_todos(
    status: Optional[str] = Query(None, description="按狀態篩選"),
    priority: Optional[str] = Query(None, description="按優先級篩選"),
    search: Optional[str] = Query(None, description="搜索標題"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """獲取 Todo 列表"""
    with tracer.start_as_current_span("api.list_todos"):
        items = crud.get_todos(
            db,
            status=status,
            priority=priority,
            search=search,
            skip=skip,
            limit=limit,
        )
        return [item.to_dict() for item in items]


@router.get("/todos/{todo_id}", response_model=schemas.TodoResponse)
async def get_todo(
    todo_id: int,
    db: Session = Depends(get_db),
):
    """獲取單個 Todo"""
    with tracer.start_as_current_span("api.get_todo") as span:
        span.set_attribute("api.todo_id", todo_id)

        todo = crud.get_todo(db, todo_id)
        if not todo:
            logger.warning("Todo not found", extra={"todo_id": todo_id})
            raise HTTPException(status_code=404, detail="Todo not found")

        return todo.to_dict()


@router.post("/todos", response_model=schemas.TodoResponse, status_code=201)
async def create_todo(
    todo_data: schemas.TodoCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """創建 Todo"""
    with tracer.start_as_current_span("api.create_todo") as span:
        span.set_attribute("api.todo_title", todo_data.title)

        try:
            metrics = get_metrics(request)
            todo = crud.create_todo(db, todo_data, metrics)
            return todo.to_dict()
        except ValueError as e:
            logger.error("Validation error", extra={"error": str(e)})
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(
                "Failed to create todo",
                extra={"error": str(e), "title": todo_data.title},
                exc_info=True,
            )
            raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/todos/{todo_id}", response_model=schemas.TodoResponse)
async def update_todo(
    todo_id: int,
    todo_data: schemas.TodoUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    """更新 Todo"""
    with tracer.start_as_current_span("api.update_todo") as span:
        span.set_attribute("api.todo_id", todo_id)

        metrics = get_metrics(request)
        todo = crud.update_todo(db, todo_id, todo_data, metrics)

        if not todo:
            raise HTTPException(status_code=404, detail="Todo not found")

        return todo.to_dict()


@router.delete("/todos/{todo_id}", status_code=204)
async def delete_todo(
    todo_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """刪除 Todo"""
    with tracer.start_as_current_span("api.delete_todo") as span:
        span.set_attribute("api.todo_id", todo_id)

        metrics = get_metrics(request)
        success = crud.delete_todo(db, todo_id, metrics)

        if not success:
            raise HTTPException(status_code=404, detail="Todo not found")

        return None

"""
CRUD 業務邏輯 - 包含手動 Span 埋點用於展示追蹤能力
"""
import time
import random
import logging
from sqlalchemy.orm import Session
from opentelemetry import trace

from app import models, schemas

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


def get_todos(
    db: Session,
    status: str | None = None,
    priority: str | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[models.TodoItem]:
    """獲取 Todo 列表，支持篩選和搜索"""
    with tracer.start_as_current_span("crud.get_todos") as span:
        span.set_attribute("crud.operation", "read")
        span.set_attribute("crud.filters.status", status or "all")
        span.set_attribute("crud.filters.priority", priority or "all")
        span.set_attribute("crud.skip", skip)
        span.set_attribute("crud.limit", limit)

        query = db.query(models.TodoItem)

        if status:
            query = query.filter(models.TodoItem.status == status)
        if priority:
            query = query.filter(models.TodoItem.priority == priority)
        if search:
            query = query.filter(
                models.TodoItem.title.ilike(f"%{search}%")
            )

        # 模擬數據庫查詢耗時
        with tracer.start_as_current_span("db.query_todos"):
            results = query.order_by(
                models.TodoItem.created_at.desc()
            ).offset(skip).limit(limit).all()

        span.set_attribute("crud.result_count", len(results))

        # 模擬數據處理
        with tracer.start_as_current_span("crud.format_results"):
            formatted = [item.to_dict() for item in results]

        logger.info(
            "Retrieved todos",
            extra={
                "operation": "read",
                "count": len(formatted),
                "filters": {"status": status, "priority": priority, "search": search},
            },
        )

        return results


def get_todo(db: Session, todo_id: int) -> models.TodoItem | None:
    """獲取單個 Todo"""
    with tracer.start_as_current_span("crud.get_todo") as span:
        span.set_attribute("crud.operation", "read_one")
        span.set_attribute("crud.todo_id", todo_id)

        with tracer.start_as_current_span("db.query_todo_by_id"):
            todo = db.query(models.TodoItem).filter(
                models.TodoItem.id == todo_id
            ).first()

        if todo:
            logger.info("Retrieved todo", extra={"operation": "read_one", "todo_id": todo_id})
        else:
            logger.warning("Todo not found", extra={"operation": "read_one", "todo_id": todo_id})

        return todo


def create_todo(db: Session, todo_data: schemas.TodoCreate, metrics: dict) -> models.TodoItem:
    """創建 Todo - 包含多步驟 Span 展示"""
    with tracer.start_as_current_span("crud.create_todo") as span:
        span.set_attribute("crud.operation", "create")
        span.set_attribute("crud.todo_title", todo_data.title)
        span.set_attribute("crud.todo_priority", todo_data.priority.value)

        # Step 1: 參數驗證
        with tracer.start_as_current_span("crud.validate_input"):
            _validate_title(todo_data.title)
            # 模擬驗證耗時
            time.sleep(random.uniform(0.001, 0.005))

        # Step 2: 數據庫插入
        with tracer.start_as_current_span("db.insert_todo"):
            db_todo = models.TodoItem(
                title=todo_data.title,
                description=todo_data.description,
                priority=todo_data.priority,
            )
            db.add(db_todo)
            db.commit()
            db.refresh(db_todo)

        # Step 3: 後處理
        with tracer.start_as_current_span("crud.post_process"):
            # 模擬通知/事件發送
            time.sleep(random.uniform(0.002, 0.008))
            _simulate_notification(db_todo)

        # 更新指標
        metrics["todo_operations_total"].labels(operation="create").inc()
        _update_all_metrics(db, metrics)

        logger.info(
            "Todo created",
            extra={
                "operation": "create",
                "todo_id": db_todo.id,
                "title": todo_data.title,
            },
        )

        return db_todo


def update_todo(
    db: Session, todo_id: int, todo_data: schemas.TodoUpdate, metrics: dict
) -> models.TodoItem | None:
    """更新 Todo"""
    with tracer.start_as_current_span("crud.update_todo") as span:
        span.set_attribute("crud.operation", "update")
        span.set_attribute("crud.todo_id", todo_id)

        with tracer.start_as_current_span("db.query_todo_for_update"):
            db_todo = db.query(models.TodoItem).filter(
                models.TodoItem.id == todo_id
            ).first()

        if not db_todo:
            logger.warning(
                "Todo not found for update",
                extra={"operation": "update", "todo_id": todo_id},
            )
            return None

        # 記錄變更字段
        changed_fields = []
        update_data = todo_data.model_dump(exclude_unset=True)

        with tracer.start_as_current_span("db.update_todo"):
            for field, value in update_data.items():
                if hasattr(db_todo, field):
                    old_value = getattr(db_todo, field)
                    setattr(db_todo, field, value)
                    if old_value != value:
                        changed_fields.append(field)

            db.commit()
            db.refresh(db_todo)

        span.set_attribute("crud.changed_fields", ",".join(changed_fields))

        metrics["todo_operations_total"].labels(operation="update").inc()
        _update_all_metrics(db, metrics)

        logger.info(
            "Todo updated",
            extra={
                "operation": "update",
                "todo_id": todo_id,
                "changed_fields": changed_fields,
            },
        )

        return db_todo


def delete_todo(db: Session, todo_id: int, metrics: dict) -> bool:
    """刪除 Todo"""
    with tracer.start_as_current_span("crud.delete_todo") as span:
        span.set_attribute("crud.operation", "delete")
        span.set_attribute("crud.todo_id", todo_id)

        with tracer.start_as_current_span("db.query_todo_for_delete"):
            db_todo = db.query(models.TodoItem).filter(
                models.TodoItem.id == todo_id
            ).first()

        if not db_todo:
            logger.warning(
                "Todo not found for delete",
                extra={"operation": "delete", "todo_id": todo_id},
            )
            return False

        with tracer.start_as_current_span("db.delete_todo"):
            db.delete(db_todo)
            db.commit()

        metrics["todo_operations_total"].labels(operation="delete").inc()
        _update_all_metrics(db, metrics)

        logger.info(
            "Todo deleted",
            extra={"operation": "delete", "todo_id": todo_id},
        )

        return True


# ── 輔助函數 ──────────────────────────────────────────────────

def _validate_title(title: str):
    """驗證標題（演示用）"""
    if not title or not title.strip():
        raise ValueError("Title cannot be empty")
    if len(title) > 200:
        raise ValueError("Title too long")


def _simulate_notification(todo: models.TodoItem):
    """模擬發送通知（演示跨服務調用追蹤）"""
    logger.debug(
        "Notification sent for new todo",
        extra={"todo_id": todo.id, "title": todo.title},
    )


def _update_all_metrics(db: Session, metrics: dict):
    """更新所有業務指標"""
    from app.observability import update_todo_metrics
    update_todo_metrics(metrics, db)

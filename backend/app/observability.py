"""
可觀測性統一初始化模塊

負責：
1. OpenTelemetry TracerProvider 配置（追蹤）
2. Prometheus 指標註冊（監控）
3. 結構化 JSON 日誌配置（日誌）
"""
import os
import logging
import sys
from pythonjsonlogger import jsonlogger

# ─────────────────────────────────────────────────────────────
# 1. 結構化 JSON 日誌配置（接入 Loki）
# ─────────────────────────────────────────────────────────────

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """自定義 JSON 日誌格式，包含 trace_id 和 span_id"""
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["service"] = os.environ.get("OTEL_SERVICE_NAME", "backend")
        log_record["level"] = record.levelname
        if not log_record.get("timestamp"):
            log_record["timestamp"] = self.formatTime(record, self.datefmt)


def setup_logging():
    """配置結構化 JSON 日誌輸出到 stdout"""
    logger = logging.getLogger()
    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

    # 清除已有的 handler
    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    formatter = CustomJsonFormatter(
        "%(timestamp)s %(level)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S.%fZ"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # 設置 uvicorn 的日誌也使用 JSON 格式
    for _log in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        _logger = logging.getLogger(_log)
        _logger.handlers.clear()
        _logger.addHandler(handler)
        _logger.propagate = False

    return logger


# ─────────────────────────────────────────────────────────────
# 2. OpenTelemetry 追蹤配置（接入已有 OTel Collector）
# ─────────────────────────────────────────────────────────────

def setup_opentelemetry():
    """
    初始化 OpenTelemetry SDK。

    支持以下模式：
    1. OpenTelemetry Operator 自動注入（K8s 環境）
    2. 手動 SDK 初始化（本地測試 / Docker Compose）
    3. 優雅降級（DISABLE_OTEL=true 時跳過追蹤初始化，本地測試可用）

    關鍵環境變量：
    - DISABLE_OTEL: 設爲 "true" 跳過 OTel 初始化
    - OTEL_EXPORTER_OTLP_ENDPOINT: Collector OTLP 端點
    - OTEL_SERVICE_NAME: 服務名稱
    """
    import logging
    _logger = logging.getLogger(__name__)

    # 支持通過環境變量禁用 OTel（本地測試用）
    if os.environ.get("DISABLE_OTEL", "").lower() == "true":
        from opentelemetry import trace as _trace
        _logger.info("OpenTelemetry disabled via DISABLE_OTEL=true — running without tracing")
        return _trace.get_tracer(__name__)

    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_NAMESPACE
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.instrumentation.logging import LoggingInstrumentor

    service_name = os.environ.get("OTEL_SERVICE_NAME", "backend")
    otel_endpoint = os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "http://localhost:4318"
    )

    resource = Resource.create({
        SERVICE_NAME: service_name,
        SERVICE_NAMESPACE: "observability-demo",
        "deployment.environment": os.environ.get("ENVIRONMENT", "development"),
    })

    # 嘗試使用 OTLP 導出器，失敗則降級爲 Console（本地調試）或不導出
    try:
        tracer_provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=f"{otel_endpoint}/v1/traces", timeout=5)
        tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(tracer_provider)
        _logger.info("OpenTelemetry initialized with OTLP exporter → %s", otel_endpoint)
    except Exception as e:
        _logger.warning(
            "Cannot connect to OTel Collector at %s, using Console exporter for local debugging. Error: %s",
            otel_endpoint, e,
        )
        # 本地測試降級：輸出 span 到 console 而非遠程 Collector
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(
            BatchSpanProcessor(ConsoleSpanExporter())
        )
        trace.set_tracer_provider(tracer_provider)

    # 自動埋點 - FastAPI
    try:
        FastAPIInstrumentor().instrument()
    except Exception as e:
        _logger.warning("FastAPI instrumentation failed: %s", e)

    # 自動埋點 - 日誌（將 trace_id 注入日誌記錄）
    try:
        LoggingInstrumentor().instrument(set_logging_format=True)
    except Exception as e:
        _logger.warning("Logging instrumentation failed: %s", e)

    # 自動埋點 - HTTP 客戶端
    try:
        RequestsInstrumentor().instrument()
    except Exception as e:
        _logger.warning("Requests instrumentation failed: %s", e)

    tracer = trace.get_tracer(__name__)
    return tracer


# ─────────────────────────────────────────────────────────────
# 3. Prometheus 指標配置（接入已有 Prometheus）
# ─────────────────────────────────────────────────────────────

def setup_prometheus(app, instrumentator):
    """
    配置 Prometheus 指標採集。
    
    通過 prometheus_fastapi_instrumentator 自動生成 HTTP 指標，
    並註冊自定義業務指標。
    """
    from prometheus_client import Counter, Gauge, Histogram, generate_latest, REGISTRY

    # 自定義業務指標
    metrics = {
        # CRUD 操作計數
        "todo_operations_total": Counter(
            "todo_operations_total",
            "Total number of Todo CRUD operations",
            ["operation"],  # create, read, update, delete
            registry=REGISTRY,
        ),
        # 按狀態統計 Todo 數量
        "todo_items_by_status": Gauge(
            "todo_items_by_status",
            "Number of Todo items by status",
            ["status"],  # pending, in_progress, completed
            registry=REGISTRY,
        ),
        # 按優先級統計 Todo 數量
        "todo_items_by_priority": Gauge(
            "todo_items_by_priority",
            "Number of Todo items by priority",
            ["priority"],  # low, medium, high
            registry=REGISTRY,
        ),
        # 總 Todo 數量
        "todo_items_total": Gauge(
            "todo_items_total",
            "Total number of Todo items",
            registry=REGISTRY,
        ),
        # 自定義延遲直方圖（更細粒度）
        "todo_operation_duration_seconds": Histogram(
            "todo_operation_duration_seconds",
            "Duration of Todo operations in seconds",
            ["operation"],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
            registry=REGISTRY,
        ),
    }

    # 使用 Instrumentator 自動暴露 HTTP 指標
    instrumentator.instrument(app).expose(app, endpoint="/metrics", include_in_schema=True)

    return metrics


def update_todo_metrics(metrics, db_session):
    """根據數據庫狀態更新 Todo 業務指標"""
    from app.models import TodoItem
    from sqlalchemy import func

    try:
        # 按狀態統計
        status_counts = db_session.query(
            TodoItem.status, func.count(TodoItem.id)
        ).group_by(TodoItem.status).all()

        # 重置所有狀態計數
        for status in ["pending", "in_progress", "completed"]:
            metrics["todo_items_by_status"].labels(status=status).set(0)

        for status, count in status_counts:
            if status:
                metrics["todo_items_by_status"].labels(status=status).set(count)

        # 按優先級統計
        priority_counts = db_session.query(
            TodoItem.priority, func.count(TodoItem.id)
        ).group_by(TodoItem.priority).all()

        for priority in ["low", "medium", "high"]:
            metrics["todo_items_by_priority"].labels(priority=priority).set(0)

        for priority, count in priority_counts:
            if priority:
                metrics["todo_items_by_priority"].labels(priority=priority).set(count)

        # 總數量
        total = db_session.query(func.count(TodoItem.id)).scalar()
        metrics["todo_items_total"].set(total or 0)

    except Exception:
        pass  # 指標更新失敗不影響主流程

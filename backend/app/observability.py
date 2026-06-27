"""
可觀測性配置模塊

統一管理：
- 結構化 JSON 日誌（→ Loki）
- OpenTelemetry 追蹤（→ 已有 Collector / Operator 自動注入）
- Prometheus 指標（→ 已有 Prometheus via ServiceMonitor）
"""
import os
import sys
import logging
import json
from datetime import datetime, timezone


# ─────────────────────────────────────────────────────────────
# 1. 結構化 JSON 日誌（輸出到 stdout → Loki 自動采集）
# ─────────────────────────────────────────────────────────────

def setup_logging():
    """配置結構化 JSON 日誌輸出到 stdout"""
    logger = logging.getLogger("root")
    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())

    # 清除已有 handlers
    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)

    class JSONFormatter(logging.Formatter):
        def format(self, record):
            log_entry = {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "level": record.levelname,
                "name": record.name,
                "message": record.getMessage(),
                "taskName": getattr(record, "taskName", None),
                "otelSpanID": getattr(record, "otelSpanID", "0"),
                "otelTraceID": getattr(record, "otelTraceID", "0"),
                "otelTraceSampled": getattr(record, "otelTraceSampled", False),
                "otelServiceName": os.environ.get("OTEL_SERVICE_NAME", "backend"),
                "service": "backend",
            }
            return json.dumps(log_entry, ensure_ascii=False)

    handler.setFormatter(JSONFormatter())
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
    初始化 OpenTelemetry SDK（手動模式）。
    同時配置自動埋點（FastAPI/HTTP/日誌）和 OTLP 導出器。

    K8s 環境通過 OTEL_EXPORTER_OTLP_ENDPOINT 配置 Collector。
    本地測試可設置 DISABLE_OTEL=true 跳過。
    """
    import logging
    _logger = logging.getLogger(__name__)

    from opentelemetry import trace as otel_trace

    # 支持通過環境變量禁用 OTel（本地快速測試用）
    if os.environ.get("DISABLE_OTEL", "").lower() == "true":
        _logger.info("OpenTelemetry disabled via DISABLE_OTEL=true")
        return otel_trace.get_tracer(__name__)

    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_NAMESPACE
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

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

    try:
        tracer_provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=otel_endpoint, timeout=5)
        tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
        otel_trace.set_tracer_provider(tracer_provider)
        _logger.info("OpenTelemetry SDK initialized -> %s", otel_endpoint)
    except Exception as e:
        _logger.warning("OTel Collector unreachable, using Console exporter: %s", e)
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        otel_trace.set_tracer_provider(tracer_provider)

    return otel_trace.get_tracer(__name__)


# ─────────────────────────────────────────────────────────────
# 3. Prometheus 指標配置（接入已有 Prometheus）
# ─────────────────────────────────────────────────────────────

def setup_http_metrics():
    """註冊 HTTP 請求級別指標（替代 prometheus_fastapi_instrumentator）"""
    from prometheus_client import Counter, Histogram

    return {
        "http_requests_total": Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "handler", "status"],
        ),
        "http_request_duration_seconds": Histogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "handler"],
            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5],
        ),
    }


def setup_prometheus():
    """
    配置 Prometheus 指標採集。

    註冊自定義業務指標，返回 metrics 字典。
    /metrics 端點由 main.py 中的原生 prometheus_client 處理。
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
        # CRUD 操作延遲
        "todo_operation_duration_seconds": Histogram(
            "todo_operation_duration_seconds",
            "Duration of Todo CRUD operations in seconds",
            ["operation"],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
            registry=REGISTRY,
        ),
    }

    return metrics


def update_todo_metrics(metrics, db):
    """更新業務指標（統計各狀態/優先級的 Todo 數量）"""
    from app.models import TodoItem
    from app.database import SessionLocal

    items = db.query(TodoItem).all()

    # Reset gauges
    for status in ["pending", "in_progress", "completed"]:
        metrics["todo_items_by_status"].labels(status=status).set(0)
    for priority in ["low", "medium", "high"]:
        metrics["todo_items_by_priority"].labels(priority=priority).set(0)

    # 統計
    for item in items:
        metrics["todo_items_by_status"].labels(status=item.status.value).inc()
        metrics["todo_items_by_priority"].labels(priority=item.priority.value).inc()

    metrics["todo_items_total"].set(len(items))

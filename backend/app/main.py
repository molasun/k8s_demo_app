"""
FastAPI 應用入口

啓動時初始化：
- 數據庫
- 結構化 JSON 日誌（→ Loki）
- OpenTelemetry 追蹤（→ 已有 Collector）
- Prometheus 指標（→ 已有 Prometheus via ServiceMonitor）
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.database import init_db, engine, DATABASE_URL
from app.routes import router
from app.observability import (
    setup_logging,
    setup_opentelemetry,
    setup_prometheus,
    update_todo_metrics,
)

# ── 初始化日誌 ──────────────────────────────────────────────
logger = setup_logging()

# ── 初始化 OpenTelemetry ───────────────────────────────────
tracer = setup_opentelemetry()
logger.info("OpenTelemetry tracer initialized")

# ── 初始化 Prometheus Instrumentator ───────────────────────
instrumentator = Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_respect_env_var=True,
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/metrics", "/health"],
    env_var_name="ENABLE_METRICS",
    inprogress_name="http_requests_inprogress",
    inprogress_labels=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用生命週期管理"""
    # 啓動時
    logger.info("Starting backend service...")

    # 初始化數據庫
    init_db()
    logger.info("Database initialized")

    # 初始化 Prometheus 指標
    app.state.metrics = setup_prometheus(app, instrumentator)
    logger.info("Prometheus metrics initialized")

    # 初始更新一次業務指標
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        update_todo_metrics(app.state.metrics, db)
    finally:
        db.close()

    yield

    # 關閉時
    logger.info("Shutting down backend service...")
    engine.dispose()

    # 清理 SQLite 數據庫文件，下次啓動重新創建
    if "sqlite" in DATABASE_URL:
        db_path = DATABASE_URL.replace("sqlite:///", "")
        if os.path.exists(db_path):
            os.remove(db_path)
            logger.info("Database file cleaned up: %s", db_path)


# ── 創建 FastAPI 應用 ──────────────────────────────────────
app = FastAPI(
    title="Observability Demo - Backend",
    description="Todo CRUD API with full observability (Prometheus, OTel, Loki)",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 註冊路由
app.include_router(router)


# ── 根路徑 ─────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "service": "Observability Demo Backend",
        "version": "1.0.0",
        "docs": "/docs",
        "metrics": "/metrics",
        "health": "/api/health",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )

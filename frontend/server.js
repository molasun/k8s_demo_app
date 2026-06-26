/**
 * Express 服務端 - Todo CRUD 前端應用
 *
 * 功能：
 * - SSR 渲染 Todo 管理頁面（EJS 模板）
 * - 代理 API 請求到後端
 * - OpenTelemetry 追蹤傳遞
 * - Prometheus 指標暴露
 */
"use strict";

const express = require("express");
const path = require("path");
const axios = require("axios");
const opentelemetry = require("@opentelemetry/api");
const { logger, setupOpenTelemetry, setupPrometheus } = require("./observability");

// ── 初始化 OpenTelemetry（必須在最前面） ─────────────────
setupOpenTelemetry();

const app = express();
const PORT = process.env.PORT || 3000;
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";
const ITEMS_PER_PAGE = 10;

// ── 初始化 Prometheus ────────────────────────────────────
const promMetrics = setupPrometheus(app);

// ── Express 中間件 ───────────────────────────────────────
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, "public")));

// EJS 模板引擎
app.set("view engine", "ejs");
app.set("views", path.join(__dirname, "views"));

// ── 健康檢查 ─────────────────────────────────────────────
app.get("/health", (req, res) => {
  const span = opentelemetry.trace.getActiveSpan();
  const traceId = span ? span.spanContext().traceId : null;

  res.json({
    status: "ok",
    service: "frontend",
    trace_id: traceId,
  });
});

// ── 頁面路由 ─────────────────────────────────────────────
app.get("/", async (req, res) => {
  const span = opentelemetry.trace.getActiveSpan();
  if (span) {
    span.setAttribute("page.name", "home");
  }

  promMetrics.pageLoadsTotal.inc();

  try {
    // 獲取查詢參數用於篩選和分頁
    const { status, priority, search, page } = req.query;
    const currentPage = Math.max(1, parseInt(page) || 1);
    const skip = (currentPage - 1) * ITEMS_PER_PAGE;

    const params = { skip, limit: ITEMS_PER_PAGE };
    if (status) params.status = status;
    if (priority) params.priority = priority;
    if (search) params.search = search;

    // 調用後端 API 獲取 Todo 列表
    const response = await makeBackendRequest("/api/todos", { params });

    // 獲取總數
    const countParams = {};
    if (status) countParams.status = status;
    if (priority) countParams.priority = priority;
    if (search) countParams.search = search;
    const countResponse = await makeBackendRequest("/api/todos/count", { params: countParams });
    const totalCount = countResponse.data.count;
    const totalPages = Math.ceil(totalCount / ITEMS_PER_PAGE);

    res.render("index", {
      todos: response.data,
      filters: { status, priority, search },
      pagination: {
        page: currentPage,
        totalPages,
        totalCount,
        hasPrev: currentPage > 1,
        hasNext: currentPage < totalPages,
      },
      backendUrl: BACKEND_URL,
    });
  } catch (err) {
    logger.error("Failed to fetch todos", {
      error: err.message,
      backendUrl: BACKEND_URL,
    });

    res.render("index", {
      todos: [],
      filters: {},
      pagination: { page: 1, totalPages: 0, totalCount: 0, hasPrev: false, hasNext: false },
      backendUrl: BACKEND_URL,
      error: "Failed to connect to backend service",
    });
  }
});

// ── API 代理路由 ─────────────────────────────────────────

// 獲取 Todo 列表
app.get("/api/todos", async (req, res) => {
  try {
    const params = {};
    if (req.query.status) params.status = req.query.status;
    if (req.query.priority) params.priority = req.query.priority;
    if (req.query.search) params.search = req.query.search;

    const response = await makeBackendRequest("/api/todos", { params });
    res.json(response.data);
  } catch (err) {
    handleProxyError(res, err, "Failed to fetch todos");
  }
});

// 獲取單個 Todo
app.get("/api/todos/:id", async (req, res) => {
  try {
    const response = await makeBackendRequest(`/api/todos/${req.params.id}`);
    res.json(response.data);
  } catch (err) {
    handleProxyError(res, err, "Failed to fetch todo");
  }
});

// 創建 Todo
app.post("/api/todos", async (req, res) => {
  try {
    const response = await makeBackendRequest("/api/todos", {
      method: "POST",
      data: req.body,
    });
    res.status(201).json(response.data);
  } catch (err) {
    handleProxyError(res, err, "Failed to create todo");
  }
});

// 更新 Todo
app.put("/api/todos/:id", async (req, res) => {
  try {
    const response = await makeBackendRequest(`/api/todos/${req.params.id}`, {
      method: "PUT",
      data: req.body,
    });
    res.json(response.data);
  } catch (err) {
    handleProxyError(res, err, "Failed to update todo");
  }
});

// 刪除 Todo
app.delete("/api/todos/:id", async (req, res) => {
  try {
    await makeBackendRequest(`/api/todos/${req.params.id}`, {
      method: "DELETE",
    });
    res.status(204).send();
  } catch (err) {
    handleProxyError(res, err, "Failed to delete todo");
  }
});

// ── 輔助函數 ─────────────────────────────────────────────

/**
 * 向後端發起請求，傳遞 W3C TraceContext 實現全鏈路追蹤
 */
async function makeBackendRequest(path, options = {}) {
  const tracer = opentelemetry.trace.getTracer("frontend-http-client");
  const activeSpan = opentelemetry.trace.getActiveSpan();

  const headers = { ...options.headers };

  // 傳遞 trace context 到後端
  if (activeSpan) {
    const ctx = opentelemetry.trace.setSpan(
      opentelemetry.context.active(),
      activeSpan
    );
    opentelemetry.propagation.inject(ctx, headers);
  }

  const startTime = Date.now();

  try {
    const response = await axios({
      url: `${BACKEND_URL}${path}`,
      method: options.method || "GET",
      data: options.data,
      params: options.params,
      headers,
      timeout: 10000,
    });

    logger.info("Backend request succeeded", {
      path,
      method: options.method || "GET",
      statusCode: response.status,
      duration_ms: Date.now() - startTime,
    });

    return response;
  } catch (err) {
    logger.error("Backend request failed", {
      path,
      method: options.method || "GET",
      error: err.message,
      statusCode: err.response?.status,
      duration_ms: Date.now() - startTime,
    });
    throw err;
  }
}

function handleProxyError(res, err, defaultMessage) {
  const statusCode = err.response?.status || 500;
  const message =
    err.response?.data?.detail || err.message || defaultMessage;

  logger.error("API proxy error", {
    error: message,
    statusCode,
  });

  res.status(statusCode).json({
    detail: message,
    error_code: `PROXY_${statusCode}`,
  });
}

// ── 404 處理 ─────────────────────────────────────────────
app.use((req, res) => {
  res.status(404).json({ detail: "Not found", path: req.path });
});

// ── 啓動服務 ─────────────────────────────────────────────
app.listen(PORT, () => {
  logger.info("Frontend server started", {
    port: PORT,
    backendUrl: BACKEND_URL,
    environment: process.env.ENVIRONMENT || "development",
  });
});

module.exports = app;

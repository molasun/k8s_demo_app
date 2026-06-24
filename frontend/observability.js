/**
 * 可觀測性統一初始化模塊 - Node.js 前端
 *
 * 負責：
 * 1. OpenTelemetry 追蹤初始化（→ 已有 Collector）
 * 2. Prometheus 指標採集（→ 已有 Prometheus via ServiceMonitor）
 * 3. 結構化 JSON 日誌（→ Loki）
 */
"use strict";

const os = require("os");
const opentelemetry = require("@opentelemetry/api");

// ─────────────────────────────────────────────────────────────
// 1. 結構化 JSON 日誌（接入 Loki）
// ─────────────────────────────────────────────────────────────
const winston = require("winston");

const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || "info",
  format: winston.format.combine(
    winston.format.timestamp({ format: "YYYY-MM-DDTHH:mm:ss.SSSZ" }),
    winston.format.errors({ stack: true }),
    winston.format.json()
  ),
  defaultMeta: {
    service: process.env.OTEL_SERVICE_NAME || "frontend",
  },
  transports: [
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.timestamp({ format: "YYYY-MM-DDTHH:mm:ss.SSSZ" }),
        winston.format.json()
      ),
    }),
  ],
});

// 將 trace_id 注入到日誌條目中
const originalLog = logger.log.bind(logger);
logger.log = function (level, message, meta = {}) {
  const span = opentelemetry.trace.getActiveSpan();
  if (span) {
    const ctx = span.spanContext();
    if (ctx && ctx.traceId) {
      meta.trace_id = ctx.traceId;
      meta.span_id = ctx.spanId;
    }
  }
  return originalLog(level, message, meta);
};

// ─────────────────────────────────────────────────────────────
// 2. OpenTelemetry 追蹤初始化（接入已有 Collector）
// ─────────────────────────────────────────────────────────────

function setupOpenTelemetry() {
  // 支持通過環境變量禁用 OTel（本地測試用）
  if (process.env.DISABLE_OTEL === "true") {
    logger.info("OpenTelemetry disabled via DISABLE_OTEL=true — running without tracing");
    return null;
  }

  try {
    const { NodeSDK } = require("@opentelemetry/sdk-node");
    const { OTLPTraceExporter } = require("@opentelemetry/exporter-trace-otlp-http");
    const { ConsoleSpanExporter } = require("@opentelemetry/sdk-trace-node");
    const { Resource } = require("@opentelemetry/resources");
    const {
      SemanticResourceAttributes,
    } = require("@opentelemetry/semantic-conventions");
    const {
      getNodeAutoInstrumentations,
    } = require("@opentelemetry/auto-instrumentations-node");

    const otelEndpoint =
      process.env.OTEL_EXPORTER_OTLP_ENDPOINT || "http://localhost:4318";

    // 嘗試 OTLP 導出器，失敗則降級爲 Console
    let traceExporter;
    try {
      traceExporter = new OTLPTraceExporter({
        url: `${otelEndpoint}/v1/traces`,
        timeoutMillis: 5000,
      });
    } catch (exporterErr) {
      logger.warn("Cannot create OTLP exporter, using Console exporter for local dev", {
        error: exporterErr.message,
      });
      traceExporter = new ConsoleSpanExporter();
    }

    const sdk = new NodeSDK({
      resource: new Resource({
        [SemanticResourceAttributes.SERVICE_NAME]:
          process.env.OTEL_SERVICE_NAME || "frontend",
        [SemanticResourceAttributes.SERVICE_NAMESPACE]: "observability-demo",
        [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]:
          process.env.ENVIRONMENT || "development",
        [SemanticResourceAttributes.HOST_NAME]: os.hostname(),
      }),
      traceExporter,
      instrumentations: [
        getNodeAutoInstrumentations({
          "@opentelemetry/instrumentation-http": {
            ignoreIncomingRequestHook: (req) => {
              return (
                req.url === "/metrics" ||
                req.url === "/health" ||
                req.url === "/favicon.ico"
              );
            },
          },
        }),
      ],
    });

    // 優雅關閉
    process.on("SIGTERM", () => {
      sdk
        .shutdown()
        .then(() => logger.info("OpenTelemetry SDK shut down"))
        .catch((err) =>
          logger.error("Error shutting down OTel SDK", { error: err.message })
        )
        .finally(() => process.exit(0));
    });

    sdk.start();
    logger.info("OpenTelemetry SDK initialized", {
      endpoint: otelEndpoint,
      exporter: traceExporter.constructor.name,
      serviceName: process.env.OTEL_SERVICE_NAME || "frontend",
    });

    return sdk;
  } catch (err) {
    logger.warn("Failed to initialize OpenTelemetry SDK, running without tracing", {
      error: err.message,
    });
    return null;
  }
}

// ─────────────────────────────────────────────────────────────
// 3. Prometheus 指標初始化（接入已有 Prometheus）
// ─────────────────────────────────────────────────────────────

function setupPrometheus(app) {
  const promClient = require("prom-client");

  // 創建 Registry
  const register = new promClient.Registry();
  register.setDefaultLabels({
    app: "observability-demo-frontend",
    service: "frontend",
  });

  // 默認指標（CPU、內存等）
  promClient.collectDefaultMetrics({ register });

  // 自定義 HTTP 指標
  const httpRequestDuration = new promClient.Histogram({
    name: "frontend_http_request_duration_seconds",
    help: "Duration of HTTP requests in seconds",
    labelNames: ["method", "route", "status_code"],
    buckets: [0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
    registers: [register],
  });

  const httpRequestsTotal = new promClient.Counter({
    name: "frontend_http_requests_total",
    help: "Total number of HTTP requests",
    labelNames: ["method", "route", "status_code"],
    registers: [register],
  });

  const pageLoadsTotal = new promClient.Counter({
    name: "frontend_page_loads_total",
    help: "Total number of page loads",
    registers: [register],
  });

  // HTTP 中間件：記錄請求指標
  app.use((req, res, next) => {
    const start = Date.now();

    // 在響應完成時記錄
    res.on("finish", () => {
      const duration = (Date.now() - start) / 1000;
      const route = req.route ? req.route.path : req.path;

      httpRequestDuration
        .labels(req.method, route, String(res.statusCode))
        .observe(duration);

      httpRequestsTotal
        .labels(req.method, route, String(res.statusCode))
        .inc();
    });

    next();
  });

  // 暴露 /metrics 端點
  app.get("/metrics", async (req, res) => {
    try {
      res.set("Content-Type", register.contentType);
      res.end(await register.metrics());
    } catch (err) {
      logger.error("Failed to expose metrics", { error: err.message });
      res.status(500).end(err.message);
    }
  });

  logger.info("Prometheus metrics initialized");

  return { register, pageLoadsTotal };
}

// ─────────────────────────────────────────────────────────────
// 導出
// ─────────────────────────────────────────────────────────────

module.exports = {
  logger,
  setupOpenTelemetry,
  setupPrometheus,
};

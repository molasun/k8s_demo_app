# Observability Demo - OpenShift/Kubernetes 可觀測性演示項目

一個完整的 CRUD Todo 應用，展示如何在 OpenShift/Kubernetes 環境中接入五大可觀測性支柱。

## 架構概覽

```
┌──────────────────┐     HTTP      ┌──────────────────┐
│  Frontend (Node) │──────────────▶│  Backend (Python) │
│  Express + EJS   │               │  FastAPI + SQLite │
│  Port: 3000      │               │  Port: 8000       │
└────────┬─────────┘               └────────┬──────────┘
         │                                  │
         │      OTLP (gRPC/HTTP)            │
         ▼                                  ▼
┌──────────────────────────────────────────────────────┐
│              已有基礎設施 (Operator 部署)               │
│                                                      │
│  Prometheus ← ServiceMonitor    AlertManager ← PrometheusRule
│  Loki       ← stdout JSON        Jaeger      ← OTLP
│  Network Observability ← eBPF (零侵入)               │
└──────────────────────────────────────────────────────┘
```

## 五大可觀測性支柱

| 支柱 | 應用側實現 | 接入方式 |
|------|-----------|---------|
| **Prometheus 指標** | `/metrics` 端點 + 自定義業務指標 | ServiceMonitor CR |
| **AlertManager 告警** | 6 條告警規則（錯誤率/延遲/宕機/重啓/CPU/流量下降） | PrometheusRule CR |
| **Loki 日誌** | 結構化 JSON 日誌輸出到 stdout | 已有采集管道自動拾取 |
| **OpenTelemetry 追蹤** | Python/Node.js SDK 自動埋點 + 手動 Span | Instrumentation CR 自動注入 |
| **Network Observability** | Pod 標籤規範化 | eBPF 自動採集（零代碼改動） |

## 項目結構

```
observability-demo/
├── README.md
├── PLAN.md                              # 詳細架構規劃
├── backend/                             # Python FastAPI 後端
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py                      # 應用入口
│       ├── observability.py             # 可觀測性初始化（OTel/Prometheus/日誌）
│       ├── database.py                  # SQLite 數據庫
│       ├── models.py                    # TodoItem 數據模型
│       ├── schemas.py                   # Pydantic 模型
│       ├── crud.py                      # CRUD 業務邏輯（含手動 Span）
│       └── routes.py                    # API 路由
├── frontend/                            # Node.js 前端
│   ├── Dockerfile
│   ├── package.json
│   ├── server.js                        # Express 服務端 + API 代理
│   ├── observability.js                 # 可觀測性初始化（OTel/Prometheus/Winston）
│   ├── public/
│   │   ├── style.css
│   │   └── app.js                       # 前端交互
│   └── views/
│       └── index.ejs                    # 頁面模板
├── scripts/                             # 輔助腳本
│   ├── test-local.sh                    # 本地測試（不依賴容器）
│   ├── test-podman.sh                   # Podman 容器測試
│   └── build-and-push-image.sh          # 構建並推送鏡像
└── helm/                                # Helm Chart
    └── observability-demo/
        ├── Chart.yaml
        ├── values.yaml                  # 主配置
        └── templates/
            ├── _helpers.tpl
            ├── namespace.yaml
            ├── backend/                 # 後端部署
            ├── frontend/                # 前端部署
            └── observability/           # 可觀測性接入配置（核心）
                ├── servicemonitor.yaml  # Prometheus 指標採集
                ├── prometheusrule.yaml  # AlertManager 告警規則
                ├── instrumentation.yaml # OTel 自動注入
                └── grafana-dashboard.yaml
```

## 快速開始

### 本地測試（先確認應用可用，無需 K8s 集羣）

兩種模式：

| 模式 | 覆蓋範圍 | Jaeger UI |
|------|---------|-----------|
| **快速模式** | CRUD + 指標 + JSON 日誌 ✅ | ❌ |
| **完整模式** | CRUD + 指標 + 日誌 + 全鏈路追蹤 ✅ | ✅ `:16686` |

```bash
# ── 方式一：本地直接運行（無需容器）──
./scripts/test-local.sh all              # 同時啟動前後端
./scripts/test-local.sh backend          # 只啟動後端
./scripts/test-local.sh frontend         # 只啟動前端

# ── 方式二：Podman 容器運行 ──
./scripts/test-podman.sh quick           # 快速模式 — 僅驗證 CRUD（無 OTel）
./scripts/test-podman.sh full            # 完整模式 — 含 OTel Collector + Jaeger
# 訪問 http://localhost:3000 (前端) + http://localhost:16686 (Jaeger)
```

> 快速模式下 `DISABLE_OTEL=true`，OTel SDK 不啓動，應用仍正常響應 CRUD、輸出 JSON 日誌到 stdout、暴露 `/metrics` 端點。

### 部署到 OpenShift

#### 前置條件

1. OpenShift/Kubernetes 集羣
2. 以下 Operator 已部署：
   - Prometheus Operator (monitoring)
   - Loki Operator (LokiStack)
   - OpenTelemetry Operator
   - Network Observability Operator
3. `helm` CLI 已安裝

#### 確認已有基礎設施

```bash
# 查看 Prometheus CR（獲取 serviceMonitorSelector 和 ruleSelector）
kubectl get prometheus -A -o yaml | grep -A5 serviceMonitorSelector
kubectl get prometheus -A -o yaml | grep -A5 ruleSelector

# 查看 OTel Collector 地址
kubectl get opentelemetrycollector -A

# 查看 LokiStack 狀態
kubectl get lokistack -A
```

#### 部署應用

```bash
# 1. 構建並推送鏡像（使用 Podman）
./scripts/build-and-push-image.sh quay.io/yourorg latest

# 或手動構建
cd backend
podman build -t quay.io/yourorg/observability-demo-backend:latest .
podman push quay.io/yourorg/observability-demo-backend:latest

cd ../frontend
podman build -t quay.io/yourorg/observability-demo-frontend:latest .
podman push quay.io/yourorg/observability-demo-frontend:latest

# 2. 安裝 Helm Chart
cd ../helm/observability-demo

helm upgrade --install observability-demo . \
  --namespace observability-demo \
  --create-namespace \
  --set backend.image.repository=quay.io/yourorg/observability-demo-backend \
  --set frontend.image.repository=quay.io/yourorg/observability-demo-frontend \
  --set observability.prometheus.serviceMonitorSelector.release=prometheus \
  --set observability.prometheus.ruleSelector.release=prometheus \
  --set observability.opentelemetry.collectorEndpoint=http://otel-collector.openshift-opentelemetry.svc.cluster.local:4318
```

### 驗證部署

```bash
# 檢查 Pod 狀態
kubectl get pods -n observability-demo

# 檢查 ServiceMonitor
kubectl get servicemonitor -n observability-demo

# 檢查 PrometheusRule
kubectl get prometheusrule -n observability-demo

# 檢查 Instrumentation
kubectl get instrumentation -n observability-demo

# 查看 OpenShift Route
kubectl get route -n observability-demo
```

### 訪問應用

```bash
# 獲取前端 URL
FRONTEND_URL=$(kubectl get route frontend -n observability-demo -o jsonpath='{.spec.host}')
echo "http://$FRONTEND_URL"

# 獲取後端 API 文檔
BACKEND_URL=$(kubectl get route backend -n observability-demo -o jsonpath='{.spec.host}')
echo "http://$BACKEND_URL/docs"
```

### 生成測試數據

訪問前端頁面，點擊 **"🎲 Generate Test Data"** 按鈕自動創建 12 條示例 Todo，用於觀測驗證。

或使用 curl：

```bash
for i in {1..20}; do
  curl -X POST "http://$BACKEND_URL/api/todos" \
    -H "Content-Type: application/json" \
    -d "{\"title\":\"Test Todo $i\",\"description\":\"Auto-generated for observability testing\",\"priority\":\"medium\"}"
  sleep 0.3
done
```

## 驗證可觀測性

### 1. Prometheus 指標

```bash
# 端口轉發 Prometheus
kubectl port-forward svc/prometheus-operated 9090:9090 -n openshift-monitoring

# 訪問 http://localhost:9090/targets
# 搜索 "observability-demo"，確認 ServiceMonitor targets 已上線

# 查詢示例
# - http_requests_total{namespace="observability-demo"}
# - todo_operations_total
# - todo_items_by_status
```

### 2. AlertManager 告警

```bash
# 端口轉發 AlertManager
kubectl port-forward svc/alertmanager-operated 9093:9093 -n openshift-monitoring

# 訪問 http://localhost:9093/#/alerts
# 查看 "observability-demo" 相關告警規則狀態
```

### 3. Loki 日誌

在 Grafana 中切換到 Loki 數據源，使用 LogQL 查詢：

```logql
{namespace="observability-demo"} | json | level="ERROR"

# 按 trace_id 關聯日誌和追蹤
{namespace="observability-demo"} | json | trace_id="<trace_id_from_jaeger>"
```

### 4. OpenTelemetry 追蹤

```bash
# 端口轉發 Jaeger
kubectl port-forward svc/jaeger-query 16686:16686 -n openshift-opentelemetry

# 訪問 http://localhost:16686
# 選擇 "backend" 或 "frontend" 服務查看追蹤
```

### 5. Network Observability

在 OpenShift Web Console 中：
- 導航到 Observe → Network Traffic
- 篩選 Namespace: `observability-demo`
- 查看 frontend ↔ backend 之間的流量拓撲

## 配置說明

### 關鍵 values.yaml 參數

```yaml
observability:
  prometheus:
    # 必須匹配已有 Prometheus CR 的標籤選擇器
    serviceMonitorSelector:
      release: prometheus
    ruleSelector:
      release: prometheus

  opentelemetry:
    # 已有 OTel Collector 的端點
    collectorEndpoint: "http://otel-collector.openshift-opentelemetry.svc.cluster.local:4318"
    # 是否使用 Operator 自動注入（推薦）
    useAutoInstrumentation: true
```

### OTel 自動注入 vs 手動 SDK

**自動注入（推薦）：**
- Helm 中創建 `Instrumentation` CR
- Pod 添加 annotation: `instrumentation.opentelemetry.io/inject-python: "true"`
- Operator 自動注入 OTel SDK，無需代碼改動

**手動 SDK：**
- 應用中已包含 OTel SDK 初始化代碼
- 通過環境變量 `OTEL_EXPORTER_OTLP_ENDPOINT` 配置 Collector 地址
- 如需切換爲手動模式，設置 `observability.opentelemetry.useAutoInstrumentation: false`

## API 文檔

| 方法 | 端點 | 描述 |
|------|------|------|
| GET | `/api/health` | 健康檢查（返回 trace_id） |
| GET | `/api/todos` | 獲取 Todo 列表（支持 ?status=&priority=&search=） |
| GET | `/api/todos/{id}` | 獲取單個 Todo |
| POST | `/api/todos` | 創建 Todo |
| PUT | `/api/todos/{id}` | 更新 Todo |
| DELETE | `/api/todos/{id}` | 刪除 Todo |
| GET | `/metrics` | Prometheus 指標端點 |

## 技術棧

| 組件 | 技術 |
|------|------|
| 後端 | Python 3.12, FastAPI, SQLAlchemy, SQLite |
| 前端 | Node.js 24, Express, EJS |
| 指標 | prometheus_client, prom-client, prometheus_fastapi_instrumentator |
| 追蹤 | OpenTelemetry SDK (Python + Node.js) |
| 日誌 | python-json-logger, winston (JSON → stdout) |
| 部署 | Helm 3, OpenShift Routes |
| 平臺 | OpenShift 4.x / Kubernetes 1.28+ |

# Observability Demo - OpenShift/Kubernetes 可觀測性演示項目

一個完整的 CRUD Todo 應用，展示如何在 OpenShift/Kubernetes 環境中接入五大可觀測性支柱。

## 架構概覽

![Architecture](<image/observability architecture.png>)

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
├── .gitignore
├── README.md
├── docker-compose.yml                   # 本地一鍵啓動
├── backend/                             # Python FastAPI 後端
│   ├── .dockerignore
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py
│       ├── main.py                      # 應用入口
│       ├── observability.py             # 可觀測性（OTel / Prometheus / 日誌）
│       ├── database.py                  # SQLite 數據庫
│       ├── models.py                    # TodoItem 數據模型
│       ├── schemas.py                   # Pydantic 請求/響應模型
│       ├── crud.py                      # CRUD 業務邏輯（含手動 Span）
│       └── routes.py                    # API 路由
├── config/                              # 本地測試用 OTel 配置
│   └── otel-collector-config.yaml
├── frontend/                            # Node.js Express 前端
│   ├── .dockerignore
│   ├── Dockerfile
│   ├── package.json
│   ├── server.js                        # Express 服務端 + API 代理
│   ├── observability.js                 # 可觀測性（OTel / Prometheus / Winston）
│   ├── public/
│   │   ├── style.css
│   │   └── app.js                       # 前端交互邏輯
│   └── views/
│       └── index.ejs                    # EJS 頁面模板
├── infra/                               # OpenShift 基礎設施部署 YAML
│   ├── logging.yaml                     # Logging (LokiStack)
│   ├── netobserv.yaml                   # Network Observability (FlowCollector)
│   └── tracing.yaml                     # Tracing (TempoStack + Collector)
├── scripts/                             # 輔助腳本
│   ├── build-and-push-image.sh          # 構建並推送鏡像
│   ├── test-local.sh                    # 本地測試（不依賴容器）
│   └── test-podman.sh                   # Podman 容器測試
└── helm/                                # Helm Chart
    └── observability-demo/
        ├── Chart.yaml
        ├── values.yaml                  # 主配置
        └── templates/
            ├── _helpers.tpl
            ├── backend/
            │   ├── deployment.yaml
            │   ├── route.yaml
            │   └── service.yaml
            ├── frontend/
            │   ├── deployment.yaml
            │   ├── route.yaml
            │   └── service.yaml
            └── observability/
                ├── alertmanagerconfig.yaml  # Webhook 告警通知
                ├── grafana-dashboard.yaml
                ├── instrumentation.yaml     # OTel 自動注入
                ├── prometheusrule.yaml      # AlertManager 告警規則
                └── servicemonitor.yaml      # Prometheus 指標採集
```

## 快速開始

## 環境準備 — 可觀測性基礎設施

部署應用前，需在 OpenShift 集群中配置以下四個基礎設施組件。
所有 YAML 文件位於 [`infra/`](infra/) 目錄，請先根據環境修改其中的 `<YOUR_...>` 佔位符。

---

### Logging（日誌）— LokiStack + ClusterLogForwarder

```bash
# 1. 創建 ServiceAccount 並綁定權限
oc create sa collector -n openshift-logging
oc adm policy add-cluster-role-to-user collect-application-logs -z collector -n openshift-logging
oc adm policy add-cluster-role-to-user collect-infrastructure-logs -z collector -n openshift-logging
oc adm policy add-cluster-role-to-user collect-audit-logs -z collector -n openshift-logging
oc adm policy add-cluster-role-to-user logging-collector-logs-writer -z collector -n openshift-logging

# 2. 部署（請先修改 infra/logging.yaml 中的 S3 認證）
oc apply -f infra/logging.yaml
```

> 📄 [`infra/logging.yaml`](infra/logging.yaml)

---

### Network Observability（網絡可觀測性）— FlowCollector

```bash
# 請先修改 infra/netobserv.yaml 中的 S3 認證後部署
oc apply -f infra/netobserv.yaml
```

> 📄 [`infra/netobserv.yaml`](infra/netobserv.yaml)

---

### OpenTelemetry / Tracing（追蹤）— TempoStack + Collector

```bash
# 1. 部署 TempoStack + Collector（請先修改 infra/tracing.yaml 中的 S3 認證）
oc apply -f infra/tracing.yaml

# 2. 授權 Collector 寫入 Tempo
oc adm policy add-cluster-role-to-user tempostack-traces-writer -z otel-collector -n tracing-system
```

> 📄 [`infra/tracing.yaml`](infra/tracing.yaml)

---

### User Monitoring（用戶監控）— enableUserWorkload

```bash
oc apply -f - <<EOF
kind: ConfigMap
apiVersion: v1
metadata:
  name: cluster-monitoring-config
  namespace: openshift-monitoring
data:
  config.yaml: |
    enableUserWorkload: true
EOF
```

> **驗證**：執行 `oc get prometheus -n openshift-user-workload-monitoring`，確認 `prometheus-user-workload` 已運行即表示 user-workload monitoring 啓用成功。

---

### 本地測試（先確認應用可用，無需 K8s 集群）

兩種模式：

| 模式 | 覆蓋範圍 | 追蹤 UI |
|------|---------|-----------|
| **快速模式** | CRUD + 指標 + JSON 日誌 ✅ | ❌ |
| **完整模式** | CRUD + 指標 + 日誌 + 全鏈路追蹤 ✅ | ✅ Grafana Tempo |

```bash
# ── 方式一：本地直接運行（無需容器）──
./scripts/test-local.sh all              # 同時啟動前後端
./scripts/test-local.sh backend          # 只啟動後端
./scripts/test-local.sh frontend         # 只啟動前端

# ── 方式二：Podman 容器運行 ──
./scripts/test-podman.sh quick           # 快速模式 — 僅驗證 CRUD（無 OTel）
./scripts/test-podman.sh full            # 完整模式 — 含 OTel Collector + Jaeger
# 訪問 http://localhost:3000 (前端) + http://localhost:16686 (Jaeger，僅本地測試）
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
```bash
# for any linux distro
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3

chmod 700 get_helm.sh./get_helm.sh

./get_helm.sh
```

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
  --force \
  --set backend.image.repository=quay.io/rhtw/observability-demo-backend \
  --set frontend.image.repository=quay.io/rhtw/observability-demo-frontend \
  --set observability.alertmanager.webhookUrl="https://webhook.site/your-unique-id" \
  --set observability.opentelemetry.collectorEndpoint=http://cluster-collector-collector.tracing-system.svc.cluster.local:4318
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

### 前置準備 — 獲取訪問 URL

```bash
# 獲取前端 URL
FRONTEND_URL="http://$(kubectl get route frontend -n observability-demo -o jsonpath='{.spec.host}')"
echo "Frontend: $FRONTEND_URL"

# 獲取後端 URL
BACKEND_URL="http://$(kubectl get route backend -n observability-demo -o jsonpath='{.spec.host}')"
echo "Backend API: $BACKEND_URL/docs"
```

> 💡 所有觀測驗證通過 **OpenShift Console** 進行：
> - **Metrics**：Observe → Metrics
> - **Alerts**：Observe → Alerting → Alerts / Alert Rules
> - **Logs**：Observe → Logs (Loki)
> - **Traces**：Observe → Trace

### 步驟 1 — 在 UI 上操作，生成數據

1. 打開瀏覽器訪問 **`$FRONTEND_URL`**
2. 點擊 **「🎲 Generate Test Data」** 創建 12 條微服務開發任務
3. 手動執行以下操作以生成更豐富的可觀測數據：
   - **創建** 2 條新 Todo（不同優先級）
   - **編輯** 1 條 Todo 的狀態（pending → in_progress）
   - **刪除** 1 條 Todo
   - 使用篩選功能按 `status`、`priority` 搜索

> 💡 持續操作 2-3 分鐘，確保 Prometheus 有足夠的數據點可查詢。

### 步驟 2 — 驗證 Prometheus 指標（PromQL）

開啟 **OpenShift Console → Observe → Metrics**，依次輸入以下 PromQL 查詢：

#### 2.1 確認 Target 上線
```
# Graph 頁籤 → 輸入
up{namespace="observability-demo"}
```
預期結果：`backend` 和 `frontend` 都顯示 `1`

#### 2.2 應用 HTTP 請求速率（QPS）
```
rate(http_requests_total{namespace="observability-demo"}[1m])
```
預期結果：顯示前後端每分鐘的請求速率曲線

#### 2.3 請求錯誤率
```
sum(rate(http_requests_total{namespace="observability-demo",status=~"5.."}[5m]))
/
sum(rate(http_requests_total{namespace="observability-demo"}[5m]))
```
預期結果：正常情況下趨近 0

#### 2.4 自定義業務指標 — Todo 操作計數
```
todo_operations_total
```
預期結果：顯示 CRUD 操作的次數分佈（action label: create/update/delete）

#### 2.5 Todo 按狀態分佈
```
todo_items_by_status
```
預期結果：顯示 pending、in_progress、completed 各狀態的數量

#### 2.6 請求延遲 P99
```
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{namespace="observability-demo"}[5m])) by (le, handler))
```

### 步驟 3 — 觸發告警並驗證 Webhook

#### 3.1 確認告警規則已加載
開啟 **OpenShift Console → Observe → Alerting → Alert Rules**，搜尋 `observability-demo`，確認規則均為 **Inactive**。

#### 3.2 觸發 BackendServiceDown 告警
```bash
# 將後端副本縮為 0，等待 2 分鐘
kubectl scale deployment backend -n observability-demo --replicas=0
```

在 **Observe → Alerting → Alerts** 中觀察 `BackendServiceDown` 狀態變化：**Inactive → Pending → Firing**。

驗證 webhook.site 收到 POST 請求（包含告警 JSON）。

```bash
# 驗證後恢復
kubectl scale deployment backend -n observability-demo --replicas=1
```

#### 3.3 壓測觸發 HighCPUUsage 告警
```bash
BACKEND_URL="http://$(kubectl get route backend -n observability-demo -o jsonpath='{.spec.host}')"

for i in {1..30}; do
  for j in {1..20}; do
    curl -s "$BACKEND_URL/api/todos" &
    curl -s "$BACKEND_URL/api/health" &
  done
  sleep 4
done
```

在 **Observe → Alerting → Alerts** 中觀察 `HighCPUUsage` 狀態。等 2 分鐘後觸發 Firing。

### 步驟 4 — 在 Loki 中查詢日誌（LogQL）

開啟 **OpenShift Console → Observe → Logs**，或 **Grafana → Explore → Loki** 數據源。

#### 4.1 查看所有應用的 JSON 日誌
```logql
{ k8s_namespace_name="observability-demo" } | json
```

#### 4.2 查詢錯誤日誌（先觸發錯誤以產生數據）
```logql
{ k8s_namespace_name="observability-demo" } | json | level=~"(?i)error"
```
預期結果：正常運行時無結果。若先執行 `kubectl scale deployment backend -n observability-demo --replicas=0` 再查詢會出現錯誤日誌。

#### 4.3 查詢特定服務的日誌
```logql
{ k8s_namespace_name="observability-demo", k8s_container_name="backend" } | json
```
或替換爲 `k8s_container_name="frontend"` 查詢前端日誌。

#### 4.4 按關鍵字搜索
```logql
{ k8s_namespace_name="observability-demo" } |= "POST /api/todos"
```
或搜索業務日誌關鍵字：
```logql
{ k8s_namespace_name="observability-demo" } |= "created"
```

#### 4.5 統計日誌級別分佈
```logql
sum by (level) (count_over_time({ k8s_namespace_name="observability-demo" } | json [5m]))
```

### 步驟 5 — 在 OCP Console 檢查 OpenTelemetry 追蹤

> 本集群使用 **TempoStack** 作為追蹤後端，通過 OCP Console **Observe → Traces** 查看。

#### 5.1 開啟 Traces 頁面
導航到 **OpenShift Console → Observe → Traces**，選擇：
- **Tempo instance**: `tracing-system / tempo-sample`
- **Tenant**: `dev`

#### 5.2 搜尋業務請求 Traces
在 **Query** 框輸入 TraceQL 查詢所有服務：
```traceql
{ resource.service.name =~ "backend|frontend" }
```

> **提示**：健康檢查（`/metrics`、`/api/health`）會頻繁觸發，建議通過 **Trace name** 列快速識別業務請求（如 `POST /api/todos`、`GET /api/todos`），點擊進入詳情查看完整追蹤鏈。

點擊任意一條 `POST /api/todos` Trace 進入詳情，頂部搜尋框輸入 `crud.create_todo` 定位手動 Span。

預期看到的完整追蹤鏈：
```
frontend: POST /api/todos
├── frontend: request handler - /api/todos
│   └── frontend: POST
│       └── frontend: tcp.connect
│           └── backend: POST /api/todos
│               ├── backend: POST /api/todos http receive
│               └── backend: api.create_todo  ← 手動 Span
│                   └── backend: crud.create_todo  ← 手動 Span
│                       ├── backend: crud.validate_input
│                       └── backend: db.insert_todo
│                           └── backend: INSERT /data/todos.db
```

點擊 **Run query** 查看追蹤散點圖和列表。

#### 5.3 按 Namespace 篩選
點擊 **Filter → Namespace**，勾選 `observability-demo`，只顯示本應用的追蹤。

預期看到的 Trace：
| Trace name | Spans | 說明 |
|------------|-------|------|
| `frontend: GET /health` | 8 spans | 前端健康檢查 |
| `backend: GET /metrics` | 6 spans | Prometheus 指標端點 |
| `backend: GET /api/health` | 6 spans | 後端健康檢查 |
| `backend: POST /api/todos` | 多個 spans | Todo CRUD 操作（含手動 Span） |

#### 5.4 驗證全鏈路追蹤
點擊任意一條 `backend: POST /api/todos` Trace 進入詳情：
- ✅ 確認能看到 **frontend → backend** 的跨服務追蹤（如果是前端觸發的請求）
- ✅ 確認手動 Span（如 `crud.create_todo`、`crud.validate_input`、`db.insert_todo`）
- ✅ 確認 Span 的時間層級關係正確（子 Span 在父 Span 範圍內）
- ✅ 展開任一 Span 查看 **Attributes**（如 `crud.todo_title`、`crud.todo_priority`）和 **Events**

### 步驟 6 — Network Observability

在 OpenShift Web Console 中：
1. 導航到 **Observe → Network Traffic**
2. 篩選 Namespace: `observability-demo`
3. 查看 frontend ↔ backend 之間的流量拓撲圖
4. 點擊連線查看流量詳情（DNS、TCP、HTTP）

### 驗證清單

| 項目 | 驗證方式 | 通過標準 |
|------|---------|---------|
| ✅ Prometheus Target | `up{namespace="observability-demo"}` | 全部為 1 |
| ✅ HTTP 指標 | `/metrics` 端點可訪問 | 返回 Prometheus 格式數據 |
| ✅ 自定義指標 | `todo_operations_total` | 有數據，action 標籤正確 |
| ✅ 告警規則 | Prometheus Alerts 頁籤 | 4 條規則均 Inactive |
| ✅ 觸發告警 | 縮副本到 0 | AlertManager 收到 Firing 告警 |
| ✅ 告警恢復 | 還原副本 | 告警自動恢復 |
| ✅ Loki 日誌 | LogQL 查詢 | JSON 結構化日誌，包含 level/trace_id |
| ✅ OTel 追蹤 | Observe → Traces → TraceQL | 跨服務 Trace，含手動 Span |
| ✅ 網路可視化 | Observe → Network Traffic | 顯示服務流量 |

## 配置說明

### 關鍵 values.yaml 參數

部署時通過 `--set` 覆蓋以下核心參數（完整列表見 [`values.yaml`](helm/observability-demo/values.yaml)）：

```yaml
# ── 可觀測性接入 ──
observability:
  prometheus:
    # Prometheus Operator 的 ServiceMonitor / Rule selector（需匹配現有 Prometheus CR）
    # ⚠️ 實際匹配依賴 openshift.io/user-monitoring: "true" 標籤
    serviceMonitorSelector:
      release: prometheus
    ruleSelector:
      release: prometheus
    scrapeInterval: 15s

  opentelemetry:
    # OTel Collector 的 OTLP HTTP 端點
    collectorEndpoint: "http://cluster-collector-collector.tracing-system.svc.cluster.local:4318"
    # 是否通過 Operator auto-instrumentation 自動注入 OTel SDK
    useAutoInstrumentation: true
    # 採樣率 (1.0 = 100%，演示推薦全採樣)
    samplingRatio: "1.0"

  alertmanager:
    # Webhook 接收端 URL（支援 Slack / Discord / webhook.site 等）
    webhookUrl: "https://webhook.site/your-unique-id-here"
    receiverName: "webhook-receiver"

  loki:
    # 日誌級別
    logLevel: "INFO"

# ── 應用配置 ──
backend:
  replicas: 1               # SQLite 不支援多副本
  image:
    repository: quay.io/rhtw/observability-demo-backend
    tag: v1.0.2

frontend:
  replicas: 2
  image:
    repository: quay.io/rhtw/observability-demo-frontend
    tag: v1.0.2

# ── Grafana Dashboards ──
grafana:
  dashboards:
    enabled: true
```

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
| 平臺 | OpenShift 4.20+ / Kubernetes 1.34+ |

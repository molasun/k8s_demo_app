/**
 * Todo Manager - 前端 CRUD 交互邏輯
 *
 * 通過前端 API 代理與後端交互，所有請求都會自動帶上 trace context
 */

(function () {
  "use strict";

  // ── Toast 通知 ────────────────────────────────────────────
  function showToast(message, type) {
    type = type || "info";
    var toast = document.createElement("div");
    toast.className = "toast toast-" + type;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(function () {
      toast.style.opacity = "0";
      toast.style.transition = "opacity 0.3s";
      setTimeout(function () {
        document.body.removeChild(toast);
      }, 300);
    }, 3000);
  }

  // ── 創建 Todo ─────────────────────────────────────────────
  var createForm = document.getElementById("createTodoForm");
  if (createForm) {
    createForm.addEventListener("submit", async function (e) {
      e.preventDefault();

      var titleInput = document.getElementById("todoTitle");
      var prioritySelect = document.getElementById("todoPriority");
      var descriptionInput = document.getElementById("todoDescription");

      var title = titleInput.value.trim();
      if (!title) {
        showToast("Title is required", "error");
        return;
      }

      var btn = createForm.querySelector('button[type="submit"]');
      btn.disabled = true;
      btn.textContent = "Creating...";

      try {
        var response = await fetch("/api/todos", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title: title,
            priority: prioritySelect.value,
            description: descriptionInput.value.trim(),
          }),
        });

        if (!response.ok) {
          var errData = await response.json();
          throw new Error(errData.detail || "Failed to create todo");
        }

        var todo = await response.json();
        showToast('Todo "' + todo.title + '" created!', "success");

        // 清空表單
        titleInput.value = "";
        descriptionInput.value = "";
        prioritySelect.value = "medium";

        // 刷新頁面
        setTimeout(function () {
          window.location.reload();
        }, 500);
      } catch (err) {
        showToast(err.message, "error");
      } finally {
        btn.disabled = false;
        btn.textContent = "➕ Create Todo";
      }
    });
  }

  // ── 篩選 ─────────────────────────────────────────────────
  var applyBtn = document.getElementById("applyFilterBtn");
  if (applyBtn) {
    applyBtn.addEventListener("click", function () {
      applyFilters();
    });
  }

  var clearBtn = document.getElementById("clearFilterBtn");
  if (clearBtn) {
    clearBtn.addEventListener("click", function () {
      document.getElementById("filterStatus").value = "";
      document.getElementById("filterPriority").value = "";
      document.getElementById("filterSearch").value = "";
      window.location.href = "/";
    });
  }

  // 回車搜索
  var searchInput = document.getElementById("filterSearch");
  if (searchInput) {
    searchInput.addEventListener("keypress", function (e) {
      if (e.key === "Enter") {
        applyFilters();
      }
    });
  }

  function applyFilters() {
    var params = new URLSearchParams();
    var status = document.getElementById("filterStatus").value;
    var priority = document.getElementById("filterPriority").value;
    var search = document.getElementById("filterSearch").value.trim();

    if (status) params.set("status", status);
    if (priority) params.set("priority", priority);
    if (search) params.set("search", search);

    window.location.href = "/?" + params.toString();
  }

  // ── 編輯 Todo ────────────────────────────────────────────
  window.editTodo = async function (id) {
    try {
      var response = await fetch("/api/todos/" + id);
      if (!response.ok) throw new Error("Failed to fetch todo");
      var todo = await response.json();

      // 使用 prompt 快速編輯（簡化交互）
      var newTitle = prompt("Edit Title:", todo.title);
      if (newTitle === null) return; // 取消
      if (!newTitle.trim()) {
        showToast("Title cannot be empty", "error");
        return;
      }

      var newStatus = prompt(
        "Status (pending / in_progress / completed):",
        todo.status
      );
      if (newStatus === null) return;

      var newPriority = prompt("Priority (low / medium / high):", todo.priority);
      if (newPriority === null) return;

      var updateData = {
        title: newTitle.trim(),
        description: todo.description,
        status: newStatus.trim(),
        priority: newPriority.trim(),
      };

      var updateResp = await fetch("/api/todos/" + id, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updateData),
      });

      if (!updateResp.ok) {
        var errData = await updateResp.json();
        throw new Error(errData.detail || "Failed to update todo");
      }

      showToast("Todo updated!", "success");
      setTimeout(function () {
        window.location.reload();
      }, 500);
    } catch (err) {
      showToast(err.message, "error");
    }
  };

  // ── 刪除 Todo ────────────────────────────────────────────
  window.deleteTodo = async function (id) {
    if (!confirm("Are you sure you want to delete this todo?")) return;

    try {
      var response = await fetch("/api/todos/" + id, {
        method: "DELETE",
      });

      if (!response.ok && response.status !== 204) {
        var errData = await response.json();
        throw new Error(errData.detail || "Failed to delete todo");
      }

      showToast("Todo deleted!", "success");
      setTimeout(function () {
        window.location.reload();
      }, 500);
    } catch (err) {
      showToast(err.message, "error");
    }
  };

  // ── 生成測試數據 ──────────────────────────────────────────
  var seedBtn = document.getElementById("seedDataBtn");
  if (seedBtn) {
    seedBtn.addEventListener("click", async function () {
      seedBtn.disabled = true;
      seedBtn.textContent = "⏳ Generating...";

      var testData = [
        { title: "Deploy microservice to OpenShift", description: "Create Deployment, Service, and Route for the user-service", priority: "high" },
        { title: "Configure Horizontal Pod Autoscaler", description: "Set up HPA with min=2, max=10 pods based on CPU 70% threshold", priority: "high" },
        { title: "Set up Service Mesh with Istio", description: "Enable mTLS and traffic splitting between v1 and v2 of payment-service", priority: "high" },
        { title: "Create ConfigMap for app settings", description: "Externalize database URL, log level, and feature flags into ConfigMap", priority: "medium" },
        { title: "Manage Secrets for database credentials", description: "Store DB password and API keys in Kubernetes Secrets, mount as env vars", priority: "high" },
        { title: "Configure Ingress with TLS termination", description: "Set up cert-manager + Let's Encrypt for automated TLS on the API gateway", priority: "medium" },
        { title: "Build Tekton CI/CD pipeline", description: "Create Pipeline for lint → test → build image → push → deploy", priority: "medium" },
        { title: "Write Helm chart for order-service", description: "Package order-service with values.yaml for dev/staging/prod environments", priority: "medium" },
        { title: "Set up Prometheus ServiceMonitor", description: "Add ServiceMonitor CR to scrape /metrics from all microservices", priority: "high" },
        { title: "Add liveness and readiness probes", description: "Configure HTTP GET probes on /health and /ready endpoints for all Deployments", priority: "high" },
        { title: "Define NetworkPolicy for namespace isolation", description: "Restrict ingress traffic to backend pods only from frontend and API gateway", priority: "medium" },
        { title: "Instrument services with OpenTelemetry", description: "Add OTel auto-instrumentation via Operator CR for Python and Node.js services", priority: "low" },
      ];

      var successCount = 0;
      var failCount = 0;

      for (var i = 0; i < testData.length; i++) {
        try {
          var response = await fetch("/api/todos", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(testData[i]),
          });

          if (response.ok) {
            successCount++;
          } else {
            failCount++;
          }

          // 添加小延遲以產生不同的時間戳和更真實的追蹤數據
          await new Promise(function (r) {
            setTimeout(r, 100 + Math.random() * 200);
          });
        } catch (err) {
          failCount++;
        }
      }

      showToast(
        "Generated " + successCount + " test todos" + (failCount > 0 ? " (" + failCount + " failed)" : ""),
        successCount > 0 ? "success" : "error"
      );

      seedBtn.disabled = false;
      seedBtn.textContent = "🎲 Generate Test Data";

      if (successCount > 0) {
        setTimeout(function () {
          window.location.reload();
        }, 800);
      }
    });
  }
})();

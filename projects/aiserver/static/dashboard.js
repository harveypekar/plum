(function () {
  const $ = (id) => document.getElementById(id);

  function formatTime(ts) {
    return new Date(ts * 1000).toLocaleTimeString();
  }

  function updateStats(data) {
    $("totalRequests").textContent = data.total_requests;
    $("requestsHour").textContent = data.requests_last_hour;
    $("avgTps").textContent = data.avg_tokens_per_second.toFixed(1);
    $("activeStreams").textContent = data.active_streams;
  }

  function createCell(text, className) {
    const td = document.createElement("td");
    td.textContent = text;
    if (className) td.className = className;
    return td;
  }

  function addLogRow(entry) {
    const tbody = $("logBody");
    const tr = document.createElement("tr");

    tr.appendChild(createCell(formatTime(entry.timestamp)));
    tr.appendChild(createCell(entry.model));
    const promptCell = createCell(entry.prompt, "prompt-cell");
    promptCell.title = entry.prompt;
    tr.appendChild(promptCell);
    tr.appendChild(createCell(String(entry.total_tokens)));
    tr.appendChild(createCell(entry.latency + "s"));

    tbody.insertBefore(tr, tbody.firstChild);

    // Keep table manageable
    while (tbody.children.length > 200) {
      tbody.removeChild(tbody.lastChild);
    }
  }

  function fetchModels() {
    fetch("/health")
      .then((r) => r.json())
      .then((data) => {
        if (data.ollama_connected) {
          $("statusDot").classList.add("connected");
          $("statusText").textContent = "Ollama connected";
        } else {
          $("statusDot").classList.remove("connected");
          $("statusText").textContent = "Ollama unavailable";
        }
        if (data.available_models && data.available_models.length > 0) {
          $("modelsSection").style.display = "";
          const list = $("modelsList");
          list.textContent = "";
          data.available_models.forEach((m) => {
            const span = document.createElement("span");
            span.className = "model-tag";
            span.textContent = m;
            list.appendChild(span);
          });
        }
      })
      .catch(() => {
        $("statusDot").classList.remove("connected");
        $("statusText").textContent = "Server unreachable";
      });
  }

  function connectWs() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(proto + "//" + location.host + "/ws/dashboard");

    ws.onopen = () => {
      $("statusDot").classList.add("connected");
      $("statusText").textContent = "Connected";
      fetchModels();
    };

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === "stats") {
        updateStats(data);
      } else if (data.type === "request_complete") {
        addLogRow(data);
      }
    };

    ws.onclose = () => {
      $("statusDot").classList.remove("connected");
      $("statusText").textContent = "Disconnected — reconnecting...";
      setTimeout(connectWs, 3000);
    };
  }

  connectWs();
})();

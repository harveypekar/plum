(function () {
  const $ = (id) => document.getElementById(id);
  let abortController = null;

  function formatSize(bytes) {
    if (!bytes) return "";
    var gb = bytes / (1024 * 1024 * 1024);
    return gb.toFixed(1) + "GB";
  }

  function modelLabel(m) {
    var label = m.alias ? m.alias + " (" + m.name + ")" : m.name;
    var parts = [];
    if (m.parameter_size) parts.push(m.parameter_size);
    if (m.quantization_level) parts.push(m.quantization_level);
    if (!m.parameter_size && m.size_bytes) parts.push(formatSize(m.size_bytes));
    if (parts.length > 0) label += " — " + parts.join(", ");
    return label;
  }

  async function loadDefaults() {
    try {
      var [defaultsResp, healthResp] = await Promise.all([
        fetch("/defaults"),
        fetch("/health"),
      ]);
      var defaults = await defaultsResp.json();
      var health = await healthResp.json();

      var select = $("model");

      // Populate from available Ollama models (with size/performance info)
      if (health.available_models && health.available_models.length > 0) {
        health.available_models.forEach(function (m) {
          var opt = document.createElement("option");
          opt.value = m.alias || m.name;
          opt.textContent = modelLabel(m);
          if (opt.value === defaults.default_model) opt.selected = true;
          select.appendChild(opt);
        });
      } else {
        // Fallback: show aliases from config (may not all be available)
        Object.entries(defaults.aliases).forEach(function ([alias, full]) {
          var opt = document.createElement("option");
          opt.value = alias;
          opt.textContent = alias + " (" + full + ")";
          if (alias === defaults.default_model) opt.selected = true;
          select.appendChild(opt);
        });
      }

      // Set parameter defaults
      var opts = defaults.default_options;
      if (opts.temperature != null) $("temperature").value = opts.temperature;
      if (opts.num_predict != null) $("numPredict").value = opts.num_predict;
      if (opts.top_p != null) $("topP").value = opts.top_p;
      if (opts.top_k != null) $("topK").value = opts.top_k;
      if (opts.think != null) $("think").checked = opts.think;
    } catch (e) {
      $("statsLine").textContent = "Failed to load defaults: " + e.message;
    }
  }

  function buildRequest() {
    const req = {
      prompt: $("prompt").value,
      model: $("model").value || undefined,
    };

    const system = $("systemPrompt").value.trim();
    if (system) req.system = system;

    const options = {};
    const temp = parseFloat($("temperature").value);
    if (!isNaN(temp)) options.temperature = temp;
    const np = parseInt($("numPredict").value);
    if (!isNaN(np)) options.num_predict = np;
    const tp = parseFloat($("topP").value);
    if (!isNaN(tp)) options.top_p = tp;
    const tk = parseInt($("topK").value);
    if (!isNaN(tk)) options.top_k = tk;
    if ($("think").checked) options.think = true;

    if (Object.keys(options).length > 0) req.options = options;
    return req;
  }

  async function generate() {
    const req = buildRequest();
    if (!req.prompt.trim()) return;

    $("generateBtn").disabled = true;
    $("stopBtn").style.display = "";
    $("statsLine").textContent = "Generating...";

    const output = $("output");
    output.textContent = "";

    let thinkingSection = null;
    let thinkingContent = null;
    let responseNode = null;
    let hasThinking = false;

    abortController = new AbortController();

    try {
      const resp = await fetch("/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
        signal: abortController.signal,
      });

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop(); // keep incomplete line

        for (const line of lines) {
          if (!line.trim()) continue;
          const chunk = JSON.parse(line);

          if (chunk.error) {
            const errNode = document.createElement("span");
            errNode.style.color = "#f85149";
            errNode.textContent = "Error: " + chunk.error;
            output.appendChild(errNode);
            break;
          }

          if (chunk.thinking) {
            if (!hasThinking) {
              hasThinking = true;
              thinkingSection = document.createElement("div");
              thinkingSection.className = "thinking-section";

              const toggle = document.createElement("div");
              toggle.className = "thinking-toggle";
              toggle.textContent = "Thinking...";
              toggle.addEventListener("click", () => {
                thinkingContent.classList.toggle("collapsed");
                toggle.textContent = thinkingContent.classList.contains("collapsed")
                  ? "Show thinking"
                  : "Hide thinking";
              });
              thinkingSection.appendChild(toggle);

              thinkingContent = document.createElement("div");
              thinkingContent.className = "thinking-content";
              thinkingSection.appendChild(thinkingContent);

              output.appendChild(thinkingSection);
            }
            thinkingContent.textContent += chunk.token;
          } else if (chunk.done) {
            if (thinkingContent) {
              const toggle = thinkingSection.querySelector(".thinking-toggle");
              toggle.textContent = "Hide thinking";
            }
            $("statsLine").textContent =
              chunk.total_tokens + " tokens | " +
              chunk.tokens_per_second + " tok/s";
          } else {
            if (!responseNode) {
              responseNode = document.createElement("span");
              output.appendChild(responseNode);
            }
            responseNode.textContent += chunk.token;
          }
        }
      }
    } catch (e) {
      if (e.name === "AbortError") {
        $("statsLine").textContent = "Stopped.";
      } else {
        $("statsLine").textContent = "Error: " + e.message;
      }
    } finally {
      abortController = null;
      $("generateBtn").disabled = false;
      $("stopBtn").style.display = "none";
    }
  }

  $("generateBtn").addEventListener("click", generate);
  $("stopBtn").addEventListener("click", () => {
    if (abortController) abortController.abort();
  });

  // Ctrl+Enter to generate
  $("prompt").addEventListener("keydown", (e) => {
    if (e.ctrlKey && e.key === "Enter") {
      e.preventDefault();
      generate();
    }
  });

  loadDefaults();
})();

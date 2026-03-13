(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  let currentView = "chat";
  let currentConvId = null;
  let currentConvDetail = null;
  let editingCardId = null;
  let editingScenarioId = null;
  let isStreaming = false;
  let abortController = null;
  let availableModels = [];
  let allCards = [];
  let allScenarios = [];
  let allConversations = [];

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------
  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (k === "className") node.className = v;
        else if (k === "textContent") node.textContent = v;
        else if (k.startsWith("on")) node.addEventListener(k.slice(2).toLowerCase(), v);
        else if (k === "style" && typeof v === "object") Object.assign(node.style, v);
        else node.setAttribute(k, v);
      }
    }
    if (children) {
      for (const c of Array.isArray(children) ? children : [children]) {
        if (typeof c === "string") node.appendChild(document.createTextNode(c));
        else if (c) node.appendChild(c);
      }
    }
    return node;
  }

  function renderDialogue(bubble, content, role) {
    var quoteClass = role === "user" ? "dialogue-quote-user" : "dialogue-quote-assistant";
    var regex = /"([^"]+)"/g;
    var lastIndex = 0;
    var match;
    while ((match = regex.exec(content)) !== null) {
      if (match.index > lastIndex) {
        bubble.appendChild(document.createTextNode(content.slice(lastIndex, match.index)));
      }
      var span = document.createElement("span");
      span.className = quoteClass;
      span.textContent = "\u201C" + match[1] + "\u201D";
      bubble.appendChild(span);
      lastIndex = regex.lastIndex;
    }
    if (lastIndex < content.length) {
      bubble.appendChild(document.createTextNode(content.slice(lastIndex)));
    }
    if (lastIndex === 0) {
      bubble.textContent = content;
    }
  }

  function avatarUrl(cardId, hasAvatar) {
    if (hasAvatar) return "/rp/cards/" + cardId + "/avatar";
    return null;
  }

  function setAvatarSrc(img, cardId, hasAvatar) {
    const url = avatarUrl(cardId, hasAvatar);
    if (url) {
      img.src = url;
    } else {
      img.style.background = "#30363d";
    }
  }

  function modelLabel(m) {
    let label = m.alias ? m.alias + " (" + m.name + ")" : m.name;
    const parts = [];
    if (m.parameter_size) parts.push(m.parameter_size);
    if (m.quantization_level) parts.push(m.quantization_level);
    if (parts.length > 0) label += " — " + parts.join(", ");
    return label;
  }

  function modelSupportsThink(modelValue) {
    const m = availableModels.find(function (x) {
      return (x.alias || x.name) === modelValue;
    });
    return m ? !!m.supports_think : false;
  }

  function updateThinkHint(selectEl) {
    var hint = $("scenarioThinkHint");
    var checkbox = $("scenarioThink");
    if (!hint) return;
    var modelVal = selectEl.value;
    if (!modelVal) {
      hint.textContent = "";
      hint.style.color = "#8b949e";
      checkbox.disabled = false;
      return;
    }
    if (modelSupportsThink(modelVal)) {
      hint.textContent = "supported by this model";
      hint.style.color = "#3fb950";
      checkbox.disabled = false;
    } else {
      hint.textContent = "not supported by this model";
      hint.style.color = "#8b949e";
      checkbox.disabled = true;
      checkbox.checked = false;
    }
  }

  function populateModelSelect(selectEl, selectedValue) {
    // Clear existing options (keep first if it's a placeholder)
    while (selectEl.options.length > 0) selectEl.remove(0);
    for (const m of availableModels) {
      const opt = document.createElement("option");
      opt.value = m.alias || m.name;
      opt.textContent = modelLabel(m);
      if (opt.value === selectedValue) opt.selected = true;
      selectEl.appendChild(opt);
    }
  }

  function timeAgo(dateStr) {
    const d = new Date(dateStr);
    const now = new Date();
    const diff = (now - d) / 1000;
    if (diff < 60) return "just now";
    if (diff < 3600) return Math.floor(diff / 60) + "m ago";
    if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
    return Math.floor(diff / 86400) + "d ago";
  }

  async function api(method, path, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const resp = await fetch(path, opts);
    if (!resp.ok) {
      const err = await resp.text();
      throw new Error(err);
    }
    return resp.json();
  }

  // ---------------------------------------------------------------------------
  // View switching
  // ---------------------------------------------------------------------------
  function switchView(view) {
    currentView = view;
    document.querySelectorAll(".sidebar-nav a").forEach((a) => {
      a.classList.toggle("active", a.dataset.view === view);
    });
    document.querySelectorAll(".view").forEach((v) => {
      v.classList.toggle("active", v.dataset.view === view);
    });
    // Show conversation list only in chat view
    $("conversationList").classList.toggle("hidden", view !== "chat");

    if (view === "cards") loadCards();
    else if (view === "scenarios") loadScenarios();
  }

  document.querySelectorAll(".sidebar-nav a").forEach((a) => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      switchView(a.dataset.view);
    });
  });

  // ---------------------------------------------------------------------------
  // Models
  // ---------------------------------------------------------------------------
  async function loadModels() {
    try {
      const health = await api("GET", "/health");
      availableModels = health.available_models || [];
    } catch (e) {
      availableModels = [];
    }
  }

  // ---------------------------------------------------------------------------
  // Conversations
  // ---------------------------------------------------------------------------
  async function loadConversations() {
    try {
      const convs = await api("GET", "/rp/conversations");
      allConversations = convs;
      renderConversationList(convs);
    } catch (e) {
      // silently fail
    }
  }

  function renderConversationList(convs) {
    const container = $("convListItems");
    container.textContent = "";
    for (const c of convs) {
      const item = el("div", { className: "conv-item" + (c.id === currentConvId ? " active" : "") });

      const avatar = el("img", { className: "conv-avatar", alt: "" });
      // We'll show AI card avatar if we know it
      avatar.style.background = "#30363d";
      // Try loading avatar
      const img = new Image();
      img.onload = () => { avatar.src = img.src; };
      img.src = "/rp/cards/" + c.ai_card_id + "/avatar";

      item.appendChild(avatar);

      const info = el("div", { className: "conv-info" });
      const name = el("div", { className: "conv-name", textContent: "Conv #" + c.id });
      const date = el("div", { className: "conv-date", textContent: timeAgo(c.updated_at) });
      info.appendChild(name);
      info.appendChild(date);
      item.appendChild(info);

      const del = el("span", {
        className: "conv-delete",
        textContent: "\u2715",
        onClick: async (e) => {
          e.stopPropagation();
          if (!confirm("Delete this conversation?")) return;
          await api("DELETE", "/rp/conversations/" + c.id);
          if (currentConvId === c.id) {
            currentConvId = null;
            currentConvDetail = null;
            renderChatEmpty();
          }
          loadConversations();
        },
      });
      item.appendChild(del);

      item.addEventListener("click", () => openConversation(c.id));
      container.appendChild(item);
    }
  }

  async function openConversation(convId) {
    currentConvId = convId;
    try {
      const detail = await api("GET", "/rp/conversations/" + convId);
      currentConvDetail = detail;
      renderChat(detail);
      loadConversations(); // refresh active state
    } catch (e) {
      // handle
    }
  }

  function renderChatEmpty() {
    $("chatHeader").style.display = "none";
    $("chatInputArea").style.display = "none";
    $("sceneStateToggle").style.display = "none";
    $("sceneStatePanel").style.display = "none";
    $("underHoodToggle").style.display = "none";
    $("underHood").classList.remove("open");
    const msgs = $("chatMessages");
    msgs.textContent = "";
    msgs.appendChild(el("div", { className: "chat-empty", textContent: "Select or start a conversation" }));
  }

  function renderChat(detail) {
    const { conversation, user_card, ai_card, scenario, messages } = detail;

    // Header
    $("chatHeader").style.display = "";
    setAvatarSrc($("chatHeaderAvatar"), ai_card.id, ai_card.has_avatar);
    const aiData = ai_card.card_data.data || ai_card.card_data;
    $("chatHeaderName").textContent = aiData.name || ai_card.name;
    $("chatHeaderModel").textContent = conversation.model + (scenario ? " | " + scenario.name : "");

    // Messages
    const container = $("chatMessages");
    container.textContent = "";

    // Scenario banner at top
    if (scenario && scenario.description) {
      const banner = el("div", { className: "scenario-banner" });
      const label = el("div", { className: "scenario-banner-label", textContent: "Scenario" });
      banner.appendChild(label);
      const bannerText = el("span");
      renderDialogue(bannerText, scenario.description, "assistant");
      banner.appendChild(bannerText);
      container.appendChild(banner);
    }

    for (const msg of messages) {
      appendMessageBubble(container, msg, user_card, ai_card);
    }

    // Scroll to bottom
    container.scrollTop = container.scrollHeight;

    // Input area
    $("chatInputArea").style.display = "";
    $("sceneStateToggle").style.display = "";
    $("underHoodToggle").style.display = "";

    // Scene state
    $("sceneStateEditor").value = conversation.scene_state || "";

    // Chat input avatars
    setAvatarSrc($("chatInputAvatarUser"), user_card.id, user_card.has_avatar);
    setAvatarSrc($("chatInputAvatarAi"), ai_card.id, ai_card.has_avatar);

    // Show last raw_response in under-the-hood
    const lastAi = [...messages].reverse().find((m) => m.role === "assistant");
    if (lastAi && lastAi.raw_response) {
      $("underHoodContent").textContent = JSON.stringify(lastAi.raw_response, null, 2);
    } else {
      $("underHoodContent").textContent = "No data yet.";
    }
  }

  function appendMessageBubble(container, msg, userCard, aiCard) {
    const isUser = msg.role === "user";
    const wrapper = el("div", { className: "message " + msg.role });

    const avatar = el("img", { className: "message-avatar", alt: "" });
    if (isUser) {
      setAvatarSrc(avatar, userCard.id, userCard.has_avatar);
    } else {
      setAvatarSrc(avatar, aiCard.id, aiCard.has_avatar);
    }
    wrapper.appendChild(avatar);

    const col = el("div");
    const bubble = el("div", { className: "message-bubble" });
    renderDialogue(bubble, msg.content, msg.role);
    col.appendChild(bubble);

    // Actions
    const actions = el("div", { className: "message-actions" });
    const editBtn = el("button", {
      textContent: "Edit",
      onClick: () => startEditMessage(msg, bubble),
    });
    const delBtn = el("button", {
      textContent: "Delete",
      onClick: async () => {
        if (!confirm("Delete this message?")) return;
        await api("DELETE", "/rp/messages/" + msg.id);
        openConversation(currentConvId);
      },
    });
    actions.appendChild(editBtn);
    actions.appendChild(delBtn);
    col.appendChild(actions);

    wrapper.appendChild(col);
    container.appendChild(wrapper);
    return { wrapper, bubble, col };
  }

  function startEditMessage(msg, bubble) {
    const ta = el("textarea", {
      className: "message-bubble",
      style: {
        background: "#0d1117",
        border: "1px solid #58a6ff",
        width: "100%",
        minHeight: "120px",
        resize: "vertical",
        fontFamily: "inherit",
        fontSize: "0.88em",
        color: "#c9d1d9",
        padding: "10px 14px",
        borderRadius: "12px",
        overflow: "hidden",
      },
    });
    ta.value = msg.content;
    bubble.replaceWith(ta);
    // Auto-size to content
    ta.style.height = "auto";
    ta.style.height = ta.scrollHeight + "px";
    ta.addEventListener("input", () => {
      ta.style.height = "auto";
      ta.style.height = ta.scrollHeight + "px";
    });
    ta.focus();

    const save = async () => {
      const newContent = ta.value.trim();
      if (newContent && newContent !== msg.content) {
        await api("PUT", "/rp/messages/" + msg.id, { content: newContent });
      }
      openConversation(currentConvId);
    };

    ta.addEventListener("blur", save);
    ta.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        ta.blur();
      }
      if (e.key === "Escape") {
        ta.removeEventListener("blur", save);
        openConversation(currentConvId);
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Streaming chat
  // ---------------------------------------------------------------------------
  async function sendMessage() {
    const input = $("chatInput");
    const content = input.value.trim();
    if (!content || !currentConvId || isStreaming) return;

    input.value = "";
    autoResizeInput();
    isStreaming = true;
    $("sendBtn").style.display = "none";
    $("stopBtn").style.display = "";

    // Append user bubble immediately
    const container = $("chatMessages");
    const userMsg = {
      id: null,
      role: "user",
      content: content,
    };
    appendMessageBubble(container, userMsg, currentConvDetail.user_card, currentConvDetail.ai_card);
    container.scrollTop = container.scrollHeight;

    // Stream AI response
    const hadError = await streamResponse("/rp/conversations/" + currentConvId + "/message", { content }, container);

    isStreaming = false;
    $("sendBtn").style.display = "";
    $("stopBtn").style.display = "none";

    // Reload to sync state (skip on error so the error message stays visible)
    if (!hadError) openConversation(currentConvId);
  }

  async function continueConversation() {
    if (!currentConvId || isStreaming) return;
    isStreaming = true;
    $("sendBtn").style.display = "none";
    $("stopBtn").style.display = "";

    const container = $("chatMessages");
    const hadError = await streamResponse("/rp/conversations/" + currentConvId + "/continue", undefined, container);

    isStreaming = false;
    $("sendBtn").style.display = "";
    $("stopBtn").style.display = "none";

    if (!hadError) openConversation(currentConvId);
  }

  async function regenerateResponse() {
    if (!currentConvId || isStreaming) return;
    isStreaming = true;
    $("sendBtn").style.display = "none";
    $("stopBtn").style.display = "";

    // Remove last AI message bubble from DOM
    const container = $("chatMessages");
    const allMsgs = container.querySelectorAll(".message.assistant");
    if (allMsgs.length > 0) {
      allMsgs[allMsgs.length - 1].remove();
    }

    const hadError = await streamResponse("/rp/conversations/" + currentConvId + "/regenerate", undefined, container);

    isStreaming = false;
    $("sendBtn").style.display = "";
    $("stopBtn").style.display = "none";

    if (!hadError) openConversation(currentConvId);
  }

  async function streamResponse(url, body, container) {
    abortController = new AbortController();
    const opts = {
      method: "POST",
      signal: abortController.signal,
    };
    if (body !== undefined) {
      opts.headers = { "Content-Type": "application/json" };
      opts.body = JSON.stringify(body);
    }

    // Create AI message bubble for streaming
    const wrapper = el("div", { className: "message assistant" });
    const avatar = el("img", { className: "message-avatar", alt: "" });
    if (currentConvDetail) {
      setAvatarSrc(avatar, currentConvDetail.ai_card.id, currentConvDetail.ai_card.has_avatar);
    }
    wrapper.appendChild(avatar);

    const col = el("div");
    let thinkingSection = null;
    let thinkingContent = null;
    let hasThinking = false;
    let hadError = false;

    const bubble = el("div", { className: "message-bubble streaming-cursor" });
    col.appendChild(bubble);
    wrapper.appendChild(col);
    container.appendChild(wrapper);

    try {
      const resp = await fetch(url, opts);
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.trim()) continue;
          const chunk = JSON.parse(line);

          if (chunk.debug_prompt !== undefined) {
            $("underHoodPromptContent").textContent = chunk.debug_prompt || "(empty)";
            $("underHoodUserPromptContent").textContent = chunk.debug_user_prompt || "(empty)";
            continue;
          }

          if (chunk.error) {
            hadError = true;
            bubble.classList.remove("streaming-cursor");
            const errSpan = el("span", {
              style: { color: "#f85149" },
              textContent: "Error: " + chunk.error,
            });
            bubble.appendChild(errSpan);
            break;
          }

          if (chunk.thinking) {
            if (!hasThinking) {
              hasThinking = true;
              thinkingSection = el("div", { className: "msg-thinking" });
              const toggle = el("div", {
                className: "msg-thinking-toggle",
                textContent: "Thinking...",
              });
              toggle.addEventListener("click", () => {
                thinkingContent.classList.toggle("collapsed");
                toggle.textContent = thinkingContent.classList.contains("collapsed")
                  ? "Show thinking"
                  : "Hide thinking";
              });
              thinkingSection.appendChild(toggle);
              thinkingContent = el("div", { className: "msg-thinking-content" });
              thinkingSection.appendChild(thinkingContent);
              // Insert thinking before the bubble
              col.insertBefore(thinkingSection, bubble);
            }
            thinkingContent.textContent += chunk.token;
          } else if (chunk.done) {
            bubble.classList.remove("streaming-cursor");
            // Re-render with dialogue coloring
            var fullText = bubble.textContent;
            bubble.textContent = "";
            renderDialogue(bubble, fullText, "assistant");
            if (thinkingContent) {
              const toggle = thinkingSection.querySelector(".msg-thinking-toggle");
              toggle.textContent = "Hide thinking";
            }
            // Update under-the-hood
            $("underHoodContent").textContent = JSON.stringify(chunk, null, 2);
          } else {
            bubble.textContent += chunk.token;
          }

          container.scrollTop = container.scrollHeight;
        }
      }
    } catch (e) {
      if (e.name !== "AbortError") {
        hadError = true;
        bubble.classList.remove("streaming-cursor");
        bubble.textContent += "\n[Stream error: " + e.message + "]";
      }
    } finally {
      bubble.classList.remove("streaming-cursor");
      abortController = null;
    }
    return hadError;
  }

  // ---------------------------------------------------------------------------
  // Chat input
  // ---------------------------------------------------------------------------
  $("sendBtn").addEventListener("click", sendMessage);
  $("stopBtn").addEventListener("click", () => {
    if (abortController) abortController.abort();
  });
  $("chatInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
  $("chatInput").addEventListener("input", autoResizeInput);

  function autoResizeInput() {
    const ta = $("chatInput");
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 150) + "px";
  }

  $("continueBtn").addEventListener("click", continueConversation);
  $("regenerateBtn").addEventListener("click", regenerateResponse);

  // Scene state toggle
  $("sceneStateToggle").addEventListener("click", () => {
    var panel = $("sceneStatePanel");
    var isOpen = panel.style.display !== "none";
    panel.style.display = isOpen ? "none" : "";
    $("sceneStateToggle").textContent = isOpen ? "Scene State" : "Hide Scene State";
  });
  $("sceneStateSave").addEventListener("click", async () => {
    if (!currentConvId) return;
    await api("PUT", "/rp/conversations/" + currentConvId + "/scene-state", {
      scene_state: $("sceneStateEditor").value,
    });
  });
  $("sceneStateRefresh").addEventListener("click", async () => {
    if (!currentConvId) return;
    $("sceneStateRefresh").disabled = true;
    $("sceneStateRefresh").textContent = "Generating...";
    // Trigger a refresh by sending current messages to generate scene state
    await api("POST", "/rp/conversations/" + currentConvId + "/refresh-scene-state");
    // Reload conversation to get updated state
    await openConversation(currentConvId);
    $("sceneStateRefresh").disabled = false;
    $("sceneStateRefresh").textContent = "Auto-generate";
    // Re-open the panel
    $("sceneStatePanel").style.display = "";
    $("sceneStateToggle").textContent = "Hide Scene State";
  });

  // Under the hood toggle
  $("underHoodToggle").addEventListener("click", () => {
    $("underHood").classList.toggle("open");
    $("underHoodToggle").textContent = $("underHood").classList.contains("open")
      ? "Hide Under the Hood"
      : "Under the Hood";
  });

  // Under the hood tab switching
  document.querySelectorAll(".under-hood-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".under-hood-tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".under-hood-pane").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      var pane = tab.getAttribute("data-pane");
      document.querySelector('.under-hood-pane[data-pane="' + pane + '"]').classList.add("active");
    });
  });

  // ---------------------------------------------------------------------------
  // New Chat Modal
  // ---------------------------------------------------------------------------
  $("newChatBtn").addEventListener("click", openNewChatModal);

  async function openNewChatModal() {
    // Refresh data
    await Promise.all([loadModels(), refreshCardsAndScenarios()]);

    // Defaults from most recent conversation
    const last = allConversations.length > 0 ? allConversations[0] : null;

    // Populate selects
    const userSelect = $("modalUserCard");
    const aiSelect = $("modalAiCard");
    const scenarioSelect = $("modalScenario");
    const modelSelect = $("modalModel");

    userSelect.textContent = "";
    aiSelect.textContent = "";

    for (const card of allCards) {
      const cardData = card.card_data.data || card.card_data;
      const label = cardData.name || card.name;

      const opt1 = document.createElement("option");
      opt1.value = card.id;
      opt1.textContent = label;
      if (last && card.id === last.user_card_id) opt1.selected = true;
      userSelect.appendChild(opt1);

      const opt2 = document.createElement("option");
      opt2.value = card.id;
      opt2.textContent = label;
      if (last && card.id === last.ai_card_id) opt2.selected = true;
      aiSelect.appendChild(opt2);
    }

    // Scenarios
    scenarioSelect.textContent = "";
    const noneOpt = document.createElement("option");
    noneOpt.value = "";
    noneOpt.textContent = "None";
    scenarioSelect.appendChild(noneOpt);
    for (const s of allScenarios) {
      const opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = s.name;
      if (last && s.id === last.scenario_id) opt.selected = true;
      scenarioSelect.appendChild(opt);
    }

    populateModelSelect(modelSelect, last ? last.model : undefined);

    $("newChatModal").classList.add("open");
  }

  $("modalCancel").addEventListener("click", () => {
    $("newChatModal").classList.remove("open");
  });
  $("newChatModal").addEventListener("click", (e) => {
    if (e.target === $("newChatModal")) $("newChatModal").classList.remove("open");
  });

  $("modalCreate").addEventListener("click", async () => {
    const userCardId = parseInt($("modalUserCard").value);
    const aiCardId = parseInt($("modalAiCard").value);
    const scenarioId = $("modalScenario").value ? parseInt($("modalScenario").value) : null;
    const model = $("modalModel").value;

    if (!userCardId || !aiCardId || !model) {
      alert("Please select all required fields.");
      return;
    }

    try {
      const conv = await api("POST", "/rp/conversations", {
        user_card_id: userCardId,
        ai_card_id: aiCardId,
        scenario_id: scenarioId,
        model: model,
      });
      $("newChatModal").classList.remove("open");
      switchView("chat");
      await loadConversations();
      openConversation(conv.id);
    } catch (e) {
      alert("Error creating conversation: " + e.message);
    }
  });

  // ---------------------------------------------------------------------------
  // Cards
  // ---------------------------------------------------------------------------
  async function refreshCardsAndScenarios() {
    try {
      const [cards, scenarios] = await Promise.all([
        api("GET", "/rp/cards"),
        api("GET", "/rp/scenarios"),
      ]);
      allCards = cards;
      allScenarios = scenarios;
    } catch (e) {
      // silently fail
    }
  }

  async function loadCards() {
    try {
      allCards = await api("GET", "/rp/cards");
      renderCards();
    } catch (e) {
      // silently fail
    }
  }

  function renderCards() {
    const grid = $("cardsGrid");
    grid.textContent = "";

    for (const card of allCards) {
      const cardData = card.card_data.data || card.card_data;
      const tile = el("div", { className: "card-tile" });

      const avatar = el("img", { className: "card-avatar", alt: "" });
      setAvatarSrc(avatar, card.id, card.has_avatar);
      tile.appendChild(avatar);

      const name = el("div", { className: "card-name", textContent: cardData.name || card.name });
      tile.appendChild(name);

      const tags = cardData.tags || [];
      if (tags.length > 0) {
        const tagsEl = el("div", { className: "card-tags", textContent: tags.join(", ") });
        tile.appendChild(tagsEl);
      }

      // Actions
      const actions = el("div", { className: "card-tile-actions" });
      const editBtn = el("button", {
        textContent: "Edit",
        onClick: (e) => { e.stopPropagation(); editCard(card); },
      });
      const exportBtn = el("button", {
        textContent: "Export",
        onClick: (e) => {
          e.stopPropagation();
          window.open("/rp/cards/" + card.id + "/export", "_blank");
        },
      });
      const delBtn = el("button", {
        className: "delete",
        textContent: "Del",
        onClick: async (e) => {
          e.stopPropagation();
          if (!confirm("Delete card \"" + card.name + "\"?")) return;
          await api("DELETE", "/rp/cards/" + card.id);
          loadCards();
        },
      });
      actions.appendChild(editBtn);
      actions.appendChild(exportBtn);
      actions.appendChild(delBtn);
      tile.appendChild(actions);

      tile.addEventListener("click", () => editCard(card));
      grid.appendChild(tile);
    }
  }

  // Card editor
  function editCard(card) {
    editingCardId = card ? card.id : null;
    const cardData = card ? (card.card_data.data || card.card_data) : {};

    $("cardEditorTitle").textContent = card ? "Edit Card" : "New Card";
    $("cardName").value = cardData.name || (card ? card.name : "");
    $("cardDescription").value = cardData.description || "";
    $("cardPersonality").value = cardData.personality || "";
    $("cardFirstMessage").value = cardData.first_mes || "";
    $("cardExampleMessages").value = cardData.mes_example || "";
    $("cardScenario").value = cardData.scenario || "";
    $("cardTags").value = (cardData.tags || []).join(", ");

    // Show extract button if card has scenario text
    const extractBtn = $("cardExtractScenario");
    extractBtn.style.display = (card && cardData.scenario) ? "" : "none";

    // Avatar preview (only for existing cards)
    const avatarGroup = $("cardAvatarGroup");
    const avatarPreview = $("cardAvatarPreview");
    if (card) {
      avatarGroup.style.display = "";
      if (card.has_avatar) {
        avatarPreview.src = "/rp/cards/" + card.id + "/avatar?" + Date.now();
      } else {
        avatarPreview.removeAttribute("src");
        avatarPreview.style.background = "#30363d";
      }
    } else {
      avatarGroup.style.display = "none";
    }

    $("cardEditor").classList.add("open");
  }

  $("cardExtractScenario").addEventListener("click", async () => {
    if (!editingCardId) return;
    try {
      const scenario = await api("POST", "/rp/cards/" + editingCardId + "/extract-scenario");
      alert("Created scenario: " + scenario.name);
    } catch (e) {
      alert("Error: " + e.message);
    }
  });

  $("cardAvatarPreview").addEventListener("click", () => $("cardAvatarPicker").click());
  $("cardAvatarPicker").addEventListener("change", async () => {
    const file = $("cardAvatarPicker").files[0];
    if (!file || !editingCardId) return;
    const formData = new FormData();
    formData.append("file", file);
    try {
      await fetch("/rp/cards/" + editingCardId + "/avatar", { method: "PUT", body: formData });
      $("cardAvatarPreview").src = "/rp/cards/" + editingCardId + "/avatar?" + Date.now();
      loadCards();
    } catch (e) {
      alert("Upload failed: " + e.message);
    }
    $("cardAvatarPicker").value = "";
  });

  $("newCardBtn").addEventListener("click", () => editCard(null));

  $("cardEditorCancel").addEventListener("click", () => {
    $("cardEditor").classList.remove("open");
    editingCardId = null;
  });

  $("cardEditorSave").addEventListener("click", async () => {
    const name = $("cardName").value.trim();
    if (!name) { alert("Name is required."); return; }

    const tagsRaw = $("cardTags").value.trim();
    const tags = tagsRaw ? tagsRaw.split(",").map((t) => t.trim()).filter(Boolean) : [];

    const cardData = {
      data: {
        name: name,
        description: $("cardDescription").value,
        personality: $("cardPersonality").value,
        first_mes: $("cardFirstMessage").value,
        mes_example: $("cardExampleMessages").value,
        scenario: $("cardScenario").value,
        tags: tags,
      },
    };

    try {
      if (editingCardId) {
        await api("PUT", "/rp/cards/" + editingCardId, { name, card_data: cardData });
      } else {
        await api("POST", "/rp/cards", { name, card_data: cardData });
      }
      $("cardEditor").classList.remove("open");
      editingCardId = null;
      loadCards();
    } catch (e) {
      alert("Error saving card: " + e.message);
    }
  });

  // Drag and drop / file picker for SillyTavern PNG import
  const dropZone = $("cardDropZone");
  const filePicker = $("cardFilePicker");

  $("cardFilePickerLink").addEventListener("click", (e) => {
    e.preventDefault();
    filePicker.click();
  });

  filePicker.addEventListener("change", () => {
    if (filePicker.files.length > 0) importCardPng(filePicker.files[0]);
  });

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });
  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
  });
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
      importCardPng(e.dataTransfer.files[0]);
    }
  });

  async function importCardPng(file) {
    const formData = new FormData();
    formData.append("file", file);

    try {
      const resp = await fetch("/rp/cards/import", {
        method: "POST",
        body: formData,
      });
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(text);
      }
      await resp.json();
      loadCards();
    } catch (e) {
      alert("Import failed: " + e.message);
    }
  }

  // ---------------------------------------------------------------------------
  // Scenarios
  // ---------------------------------------------------------------------------
  async function loadScenarios() {
    try {
      allScenarios = await api("GET", "/rp/scenarios");
      renderScenarios();
    } catch (e) {
      // silently fail
    }
  }

  function renderScenarios() {
    const list = $("scenarioList");
    list.textContent = "";

    for (const s of allScenarios) {
      const item = el("div", { className: "scenario-item" });

      const info = el("div");
      const name = el("div", { className: "scenario-name", textContent: s.name });
      info.appendChild(name);
      if (s.description) {
        const desc = el("div", { className: "scenario-desc" });
        desc.textContent = s.description.substring(0, 100) + (s.description.length > 100 ? "..." : "");
        info.appendChild(desc);
      }
      item.appendChild(info);

      const actions = el("div", { className: "scenario-item-actions" });
      const editBtn = el("button", {
        textContent: "Edit",
        onClick: (e) => { e.stopPropagation(); editScenario(s); },
      });
      const delBtn = el("button", {
        className: "delete",
        textContent: "Del",
        onClick: async (e) => {
          e.stopPropagation();
          if (!confirm("Delete scenario \"" + s.name + "\"?")) return;
          await api("DELETE", "/rp/scenarios/" + s.id);
          loadScenarios();
        },
      });
      actions.appendChild(editBtn);
      actions.appendChild(delBtn);
      item.appendChild(actions);

      item.addEventListener("click", () => editScenario(s));
      list.appendChild(item);
    }
  }

  function editScenario(s) {
    editingScenarioId = s ? s.id : null;
    $("scenarioEditorTitle").textContent = s ? "Edit Scenario" : "New Scenario";
    $("scenarioName").value = s ? s.name : "";
    $("scenarioDescription").value = s ? s.description : "";

    // Model override
    populateModelSelect($("scenarioModel"), s && s.settings ? s.settings.model : "");
    // Add "use default" option at start
    const defaultOpt = document.createElement("option");
    defaultOpt.value = "";
    defaultOpt.textContent = "Use conversation default";
    $("scenarioModel").insertBefore(defaultOpt, $("scenarioModel").firstChild);
    if (!s || !s.settings || !s.settings.model) defaultOpt.selected = true;

    // Context strategy
    if (s && s.settings && s.settings.context_strategy) {
      $("scenarioContext").value = s.settings.context_strategy;
    } else {
      $("scenarioContext").value = "sliding_window";
    }

    // Think toggle
    $("scenarioThink").checked = !!(s && s.settings && s.settings.think);
    updateThinkHint($("scenarioModel"));
    $("scenarioModel").addEventListener("change", function () {
      updateThinkHint(this);
    });

    // Ollama options
    var st = (s && s.settings) || {};
    $("scenarioRepeatPenalty").value = st.repeat_penalty || "";
    $("scenarioTemperature").value = st.temperature || "";
    $("scenarioMinP").value = st.min_p || "";
    $("scenarioTopK").value = (st.top_k !== undefined && st.top_k !== null) ? st.top_k : "";
    $("scenarioRepeatLastN").value = st.repeat_last_n || "";

    $("scenarioEditor").classList.add("open");
  }

  $("newScenarioBtn").addEventListener("click", async () => {
    await loadModels();
    editScenario(null);
  });

  $("scenarioEditorCancel").addEventListener("click", () => {
    $("scenarioEditor").classList.remove("open");
    editingScenarioId = null;
  });

  $("scenarioEditorSave").addEventListener("click", async () => {
    const name = $("scenarioName").value.trim();
    if (!name) { alert("Name is required."); return; }

    const settings = {
      context_strategy: $("scenarioContext").value,
    };
    if ($("scenarioThink").checked) settings.think = true;
    const modelOverride = $("scenarioModel").value;
    if (modelOverride) settings.model = modelOverride;
    const repeatPenalty = parseFloat($("scenarioRepeatPenalty").value);
    if (!isNaN(repeatPenalty)) settings.repeat_penalty = repeatPenalty;
    const temperature = parseFloat($("scenarioTemperature").value);
    if (!isNaN(temperature)) settings.temperature = temperature;
    const minP = parseFloat($("scenarioMinP").value);
    if (!isNaN(minP)) settings.min_p = minP;
    const topK = parseInt($("scenarioTopK").value);
    if (!isNaN(topK)) settings.top_k = topK;
    const repeatLastN = parseInt($("scenarioRepeatLastN").value);
    if (!isNaN(repeatLastN)) settings.repeat_last_n = repeatLastN;

    const data = {
      name,
      description: $("scenarioDescription").value,
      settings,
    };

    try {
      if (editingScenarioId) {
        await api("PUT", "/rp/scenarios/" + editingScenarioId, data);
      } else {
        await api("POST", "/rp/scenarios", data);
      }
      $("scenarioEditor").classList.remove("open");
      editingScenarioId = null;
      loadScenarios();
    } catch (e) {
      alert("Error saving scenario: " + e.message);
    }
  });

  // ---------------------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------------------
  async function init() {
    await loadModels();
    await loadConversations();
  }

  init();
})();

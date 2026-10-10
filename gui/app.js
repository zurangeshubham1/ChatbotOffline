(() => {
  const SYSTEM =
    "You are SuperBot, a helpful offline coding assistant. Prefer clear, correct code with short explanations. Support Python, Java, JavaScript, SQL, and algorithms.";
  const DEFAULT_MODEL = "qwen2.5-coder-1.5b-instruct-q4_k_m";

  const els = {
    status: document.getElementById("status"),
    model: document.getElementById("model"),
    thread: document.getElementById("thread"),
    form: document.getElementById("form"),
    input: document.getElementById("input"),
    send: document.getElementById("send"),
    chatList: document.getElementById("chatList"),
    newChat: document.getElementById("newChat"),
    search: document.getElementById("search"),
    chatTitle: document.getElementById("chatTitle"),
    deleteChat: document.getElementById("deleteChat"),
    sidebar: document.getElementById("sidebar"),
    toggleSidebar: document.getElementById("toggleSidebar"),
  };

  /** @type {{role: string, content: string}[]} */
  let messages = [{ role: "system", content: SYSTEM }];
  let conversationId = null;
  let busy = false;
  let searchTimer = null;

  function setStatus(text, kind = "") {
    els.status.textContent = text;
    els.status.className = "status" + (kind ? " " + kind : "");
  }

  function setTitle(title) {
    els.chatTitle.textContent = title || "New chat";
  }

  function setChatActionsEnabled(on) {
    els.deleteChat.disabled = !on;
  }

  function escapeHtml(text) {
    return String(text)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  function formatContent(text) {
    const parts = String(text).split(/```/);
    return parts
      .map((part, i) => {
        if (i % 2 === 1) {
          const nl = part.indexOf("\n");
          const code = nl >= 0 ? part.slice(nl + 1) : part;
          return `<pre><code>${escapeHtml(code.replace(/\n$/, ""))}</code></pre>`;
        }
        return escapeHtml(part);
      })
      .join("");
  }

  function ensureInner() {
    let inner = els.thread.querySelector(".thread-inner");
    if (!inner) {
      els.thread.innerHTML = `<div class="thread-inner"></div>`;
      inner = els.thread.querySelector(".thread-inner");
    }
    return inner;
  }

  function renderEmpty() {
    els.thread.innerHTML = `
      <div class="empty">
        <div>
          <strong>SuperBot</strong>
          Ask for code, debug help, or explanations. Chats stay on this PC.
        </div>
      </div>`;
  }

  function addMessage(role, content, streaming = false) {
    const empty = els.thread.querySelector(".empty");
    if (empty) empty.remove();
    const inner = ensureInner();
    const wrap = document.createElement("article");
    wrap.className = `msg ${role}` + (streaming ? " streaming" : "");
    wrap.innerHTML = `
      <div class="who">${role === "user" ? "You" : "SuperBot"}</div>
      <div class="bubble"></div>`;
    const bubble = wrap.querySelector(".bubble");
    bubble.innerHTML = formatContent(content || "");
    inner.appendChild(wrap);
    els.thread.scrollTop = els.thread.scrollHeight;
    return { wrap, bubble };
  }

  function renderMessages(list) {
    if (!list.length) {
      renderEmpty();
      return;
    }
    els.thread.innerHTML = `<div class="thread-inner"></div>`;
    for (const m of list) {
      if (m.role === "system") continue;
      addMessage(m.role, m.content, false);
    }
  }

  function resizeInput() {
    els.input.style.height = "auto";
    els.input.style.height = Math.min(els.input.scrollHeight, 180) + "px";
    els.send.disabled = busy || !els.input.value.trim();
  }

  function setModelOptions(names) {
    els.model.innerHTML = "";
    for (const name of names) {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      els.model.appendChild(opt);
    }
    els.model.value = names[0] || DEFAULT_MODEL;
  }

  async function api(path, opts = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
      ...opts,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }

  function formatWhen(iso) {
    if (!iso) return "";
    try {
      const d = new Date(iso);
      return d.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return "";
    }
  }

  async function refreshList(q = "") {
    const query = q ? `?q=${encodeURIComponent(q)}` : "";
    const data = await api(`/api/conversations${query}`);
    const items = data.conversations || [];
    els.chatList.innerHTML = "";
    if (!items.length) {
      els.chatList.innerHTML = `<div class="chat-item"><span class="title" style="font-weight:500;color:var(--muted)">No chats yet</span></div>`;
      return;
    }
    for (const c of items) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "chat-item" + (c.id === conversationId ? " active" : "");
      btn.innerHTML = `<span class="title"></span><span class="meta"></span>`;
      btn.querySelector(".title").textContent = c.title || "New chat";
      btn.querySelector(".meta").textContent = formatWhen(c.updated_at);
      btn.addEventListener("click", () => openConversation(c.id));
      els.chatList.appendChild(btn);
    }
  }

  async function createConversation(title = "New chat") {
    const conv = await api("/api/conversations", {
      method: "POST",
      body: JSON.stringify({ title }),
    });
    conversationId = conv.id;
    messages = [{ role: "system", content: SYSTEM }];
    setTitle(conv.title);
    setChatActionsEnabled(true);
    renderEmpty();
    await refreshList(els.search.value.trim());
    return conv;
  }

  async function openConversation(id) {
    if (busy) return;
    const conv = await api(`/api/conversations/${id}`);
    conversationId = conv.id;
    setTitle(conv.title);
    setChatActionsEnabled(true);
    const history = (conv.messages || []).filter((m) => m.role !== "system");
    messages = [{ role: "system", content: SYSTEM }].concat(
      history.map((m) => ({ role: m.role, content: m.content }))
    );
    renderMessages(history);
    await refreshList(els.search.value.trim());
    els.sidebar.classList.remove("open");
    els.input.focus();
  }

  async function ensureConversation() {
    if (conversationId) return conversationId;
    const conv = await createConversation("New chat");
    return conv.id;
  }

  async function saveMessage(role, content) {
    const id = await ensureConversation();
    await api(`/api/conversations/${id}/messages`, {
      method: "POST",
      body: JSON.stringify({ role, content }),
    });
    await refreshList(els.search.value.trim());
    const conv = await api(`/api/conversations/${id}`);
    setTitle(conv.title);
  }

  async function loadModels() {
    const res = await fetch("/api/tags");
    if (!res.ok) throw new Error("GUI server not reachable");
    const data = await res.json();
    const names = (data.models || []).map((m) => m.name);
    setModelOptions(names.length ? names : [DEFAULT_MODEL]);

    const health = await fetch("/api/health");
    const h = await health.json().catch(() => ({ ok: false }));
    if (!h.db_ok && h.db_ok !== undefined) {
      setStatus("Database error", "bad");
    }
    if (!h.ok) {
      setStatus("Start llama.cpp on :8080", "bad");
      throw new Error("llama.cpp not running on 127.0.0.1:8080");
    }
    setStatus("Ready · offline", "ok");
  }

  function extractDelta(obj) {
    const choice = obj.choices && obj.choices[0];
    if (choice?.delta?.content) return choice.delta.content;
    if (choice?.message?.content) return choice.message.content;
    if (obj.message?.content) return obj.message.content;
    return "";
  }

  async function sendMessage(text) {
    if (busy || !text.trim()) return;
    busy = true;
    els.send.disabled = true;

    try {
      await ensureConversation();
      messages.push({ role: "user", content: text });
      addMessage("user", text);
      await saveMessage("user", text);

      const { wrap, bubble } = addMessage("assistant", "", true);
      let reply = "";
      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            model: els.model.value || DEFAULT_MODEL,
            messages,
            stream: true,
            temperature: 0.2,
          }),
        });
        if (!res.ok || !res.body) throw new Error("Chat failed");

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n");
          buffer = parts.pop() || "";
          for (const line of parts) {
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith(":")) continue;
            const data = trimmed.startsWith("data:")
              ? trimmed.slice(5).trim()
              : trimmed;
            if (!data || data === "[DONE]") continue;
            let obj;
            try {
              obj = JSON.parse(data);
            } catch {
              continue;
            }
            const piece = extractDelta(obj);
            if (piece) {
              reply += piece;
              bubble.innerHTML = formatContent(reply);
              els.thread.scrollTop = els.thread.scrollHeight;
            }
          }
        }
        const finalText = reply || "(no reply)";
        messages.push({ role: "assistant", content: finalText });
        if (!reply) bubble.textContent = "(no reply)";
        await saveMessage("assistant", finalText);
        setStatus("Ready · offline", "ok");
      } catch (err) {
        bubble.textContent =
          "Could not reach llama.cpp. Run scripts\\start_llama.ps1 then retry.";
        setStatus("Offline / error", "bad");
        messages.pop();
      } finally {
        wrap.classList.remove("streaming");
      }
    } finally {
      busy = false;
      resizeInput();
      els.input.focus();
    }
  }

  els.form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = els.input.value.trim();
    if (!text) return;
    els.input.value = "";
    resizeInput();
    sendMessage(text);
  });

  els.input.addEventListener("input", resizeInput);
  els.input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      els.form.requestSubmit();
    }
  });

  els.newChat.addEventListener("click", async () => {
    if (busy) return;
    await createConversation("New chat");
    els.input.focus();
  });

  els.search.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      refreshList(els.search.value.trim()).catch((err) =>
        setStatus(String(err.message || err), "bad")
      );
    }, 200);
  });

  els.deleteChat.addEventListener("click", async () => {
    if (!conversationId || busy) return;
    if (!confirm("Delete this chat permanently?")) return;
    try {
      await api(`/api/conversations/${conversationId}`, { method: "DELETE" });
      conversationId = null;
      messages = [{ role: "system", content: SYSTEM }];
      setTitle("New chat");
      setChatActionsEnabled(false);
      renderEmpty();
      await refreshList(els.search.value.trim());
    } catch (err) {
      alert(err.message || String(err));
    }
  });

  els.toggleSidebar.addEventListener("click", () => {
    els.sidebar.classList.toggle("open");
  });

  async function boot() {
    renderEmpty();
    setChatActionsEnabled(false);
    resizeInput();
    await loadModels();
    await refreshList();
    // Conversation is created on first send or New chat click
    conversationId = null;
    setTitle("New chat");
  }

  boot().catch((err) => {
    setStatus(String(err.message || err), "bad");
  });
})();

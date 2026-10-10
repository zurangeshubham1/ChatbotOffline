(() => {
  const SYSTEM =
    "You are a helpful offline coding assistant. Prefer clear, correct code with short explanations. Support Python, Java, JavaScript, SQL, and algorithms.";

  const DEFAULT_MODEL = "qwen2.5-coder-1.5b-instruct-q4_k_m";

  const els = {
    status: document.getElementById("status"),
    model: document.getElementById("model"),
    clear: document.getElementById("clear"),
    thread: document.getElementById("thread"),
    form: document.getElementById("form"),
    input: document.getElementById("input"),
    send: document.getElementById("send"),
  };

  /** @type {{role: string, content: string}[]} */
  let messages = [{ role: "system", content: SYSTEM }];
  let busy = false;

  function setStatus(text, kind = "") {
    els.status.textContent = text;
    els.status.className = "status" + (kind ? " " + kind : "");
  }

  function renderEmpty() {
    els.thread.innerHTML = `
      <div class="empty">
        <div>
          <strong>Ask anything about code</strong>
          Write a function, fix a bug, or explain an error — answers stay on this PC via llama.cpp.
        </div>
      </div>`;
  }

  function escapeHtml(text) {
    return text
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

  function addMessage(role, content, streaming = false) {
    const empty = els.thread.querySelector(".empty");
    if (empty) empty.remove();

    const wrap = document.createElement("article");
    wrap.className = `msg ${role}` + (streaming ? " streaming" : "");
    wrap.innerHTML = `
      <div class="who">${role === "user" ? "You" : "CodeLocal"}</div>
      <div class="bubble"></div>`;
    const bubble = wrap.querySelector(".bubble");
    bubble.innerHTML = formatContent(content || "");
    els.thread.appendChild(wrap);
    els.thread.scrollTop = els.thread.scrollHeight;
    return { wrap, bubble };
  }

  function resizeInput() {
    els.input.style.height = "auto";
    els.input.style.height = Math.min(els.input.scrollHeight, 160) + "px";
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

  async function loadModels() {
    const res = await fetch("/api/tags");
    if (!res.ok) throw new Error("GUI server not reachable");
    const data = await res.json();
    const names = (data.models || []).map((m) => m.name);
    setModelOptions(names.length ? names : [DEFAULT_MODEL]);

    const health = await fetch("/api/health");
    const h = await health.json().catch(() => ({ ok: false }));
    if (!h.ok) {
      setStatus("Start llama.cpp on :8080", "bad");
      throw new Error("llama.cpp not running on 127.0.0.1:8080");
    }
    setStatus("Ready · llama.cpp · offline", "ok");
  }

  function extractDelta(obj) {
    // OpenAI SSE chunk
    const choice = obj.choices && obj.choices[0];
    if (choice?.delta?.content) return choice.delta.content;
    if (choice?.message?.content) return choice.message.content;
    // Fallback if anything Ollama-like slips through
    if (obj.message?.content) return obj.message.content;
    return "";
  }

  async function sendMessage(text) {
    if (busy || !text.trim()) return;
    busy = true;
    els.send.disabled = true;

    messages.push({ role: "user", content: text });
    addMessage("user", text);
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
      messages.push({ role: "assistant", content: reply || "(no reply)" });
      if (!reply) bubble.textContent = "(no reply)";
      setStatus("Ready · llama.cpp · offline", "ok");
    } catch (err) {
      bubble.textContent =
        "Could not reach llama.cpp. Run scripts\\start_llama.ps1 then retry.";
      setStatus("Offline / error", "bad");
      messages.pop();
    } finally {
      wrap.classList.remove("streaming");
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

  els.clear.addEventListener("click", () => {
    if (busy) return;
    messages = [{ role: "system", content: SYSTEM }];
    renderEmpty();
    els.input.focus();
  });

  renderEmpty();
  resizeInput();
  loadModels().catch((err) => {
    setStatus(String(err.message || err), "bad");
  });
})();

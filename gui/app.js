(() => {
  const SYSTEM =
    "You are a helpful offline coding assistant. Prefer clear, correct code with short explanations. Support Python, Java, JavaScript, SQL, and algorithms.";

  const preferred = [
    "coding-bot:latest",
    "coding-bot",
    "qwen2.5-coder:1.5b",
    "qwen2.5:1.5b-instruct",
  ];

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
          Write a function, fix a bug, or explain an error — answers stay on this PC.
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

  async function loadModels() {
    const res = await fetch("/api/tags");
    if (!res.ok) throw new Error("Ollama not reachable");
    const data = await res.json();
    const names = (data.models || []).map((m) => m.name);
    els.model.innerHTML = "";
    for (const name of names) {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      els.model.appendChild(opt);
    }
    const pick =
      preferred.find((p) => names.includes(p)) ||
      names.find((n) => n.startsWith("coding-bot") || n.includes("coder")) ||
      names[0];
    if (pick) els.model.value = pick;
    if (!names.length) throw new Error("No models installed");
    setStatus("Ready · offline", "ok");
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
          model: els.model.value,
          messages,
          stream: true,
          options: { temperature: 0.2 },
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
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          const obj = JSON.parse(trimmed);
          const piece = obj.message?.content || "";
          if (piece) {
            reply += piece;
            bubble.innerHTML = formatContent(reply);
            els.thread.scrollTop = els.thread.scrollHeight;
          }
        }
      }
      messages.push({ role: "assistant", content: reply || "(no reply)" });
      if (!reply) bubble.textContent = "(no reply)";
    } catch (err) {
      bubble.textContent = "Could not reach the local model. Is Ollama running?";
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

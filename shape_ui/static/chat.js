/* Shape UI – chat page behaviour (CSP-safe, no inline scripts). */
(function () {
  "use strict";

  // ── Ctrl+Enter submits the chat form ──────────────────────
  document.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      var form = document.getElementById("chat-form");
      if (form && document.activeElement && form.contains(document.activeElement)) {
        htmx.trigger(form, "submit");
      }
    }
  });

  // ── Auto-resize textarea ──────────────────────────────────
  var ta = document.getElementById("chat-input");
  if (ta) {
    ta.addEventListener("input", function () {
      this.style.height = "44px";
      this.style.height = Math.min(this.scrollHeight, 160) + "px";
    });
  }

  // ── Clear input + show thinking bubble when request starts ─
  document.body.addEventListener("htmx:beforeRequest", function (evt) {
    var form = document.getElementById("chat-form");
    if (form && evt.detail.elt === form) {
      form.reset();
      var textarea = form.querySelector(".chat-textarea");
      if (textarea) textarea.style.height = "44px";

      // Append a "thinking" bubble in the messages area (remove stale one first)
      var msgs = document.getElementById("messages");
      var existing = document.getElementById("thinking-bubble");
      if (existing) existing.remove();
      if (msgs) {
        var bubble = document.createElement("div");
        bubble.className = "msg-wrap msg-assistant";
        bubble.id = "thinking-bubble";
        bubble.innerHTML =
          '<div class="msg-bubble msg-bubble-assistant" style="display:flex;align-items:center;gap:0.5rem">' +
            '<div class="spinner"></div>' +
            '<span style="color:var(--text-muted);font-size:0.85rem">Thinking\u2026</span>' +
          '</div>';
        msgs.appendChild(bubble);
        msgs.scrollTop = msgs.scrollHeight;
      }
    }
  });

  // ── Force-swap error responses so the error partial is shown ─
  document.body.addEventListener("htmx:beforeOnLoad", function (evt) {
    var form = document.getElementById("chat-form");
    if (form && evt.detail.elt === form && evt.detail.xhr.status >= 400) {
      evt.detail.shouldSwap = true;
      evt.detail.isError = false;
    }
  });

  // ── Remove thinking bubble when any response arrives ───────
  document.body.addEventListener("htmx:afterRequest", function (evt) {
    var form = document.getElementById("chat-form");
    if (form && evt.detail.elt === form) {
      var thinking = document.getElementById("thinking-bubble");
      if (thinking) thinking.remove();
    }
  });

  // ── Scroll messages after swap (success or error) ─────────
  document.body.addEventListener("htmx:afterSwap", function (evt) {
    var msgs = document.getElementById("messages");
    if (msgs && evt.detail.target === msgs) {
      msgs.scrollTop = msgs.scrollHeight;
    }
  });

  // ── Scroll to bottom on initial load (when history exists) ─
  var msgs = document.getElementById("messages");
  if (msgs && msgs.querySelector(".msg-wrap")) {
    msgs.scrollTop = msgs.scrollHeight;
  }

  // ── Reset-draft confirmation (replaces inline onsubmit) ───
  var resetForm = document.getElementById("reset-form");
  if (resetForm) {
    resetForm.addEventListener("submit", function (e) {
      if (!confirm("Reset the draft survey and vocabulary? Your conversation history will be kept.")) {
        e.preventDefault();
      }
    });
  }
})();

/* Shape UI – export page behaviour (CSP-safe, no inline scripts). */
(function () {
  "use strict";

  // ── Platform selection ────────────────────────────────────
  function selectPlatform(btn) {
    document.querySelectorAll(".platform-card").forEach(function (c) {
      c.classList.remove("selected");
      c.setAttribute("aria-pressed", "false");
    });
    btn.classList.add("selected");
    btn.setAttribute("aria-pressed", "true");
    document.getElementById("fmt-input").value = btn.dataset.fmt;
    var toggle = document.getElementById("action-toggle");
    if (toggle) toggle.style.display = btn.dataset.push === "true" ? "" : "none";
    setAction("download");
  }

  document.querySelectorAll(".platform-card").forEach(function (card) {
    card.addEventListener("click", function () {
      selectPlatform(this);
    });
  });

  // Show action toggle if the pre-selected platform supports push
  (function () {
    var selected = document.querySelector(".platform-card.selected");
    if (selected && selected.dataset.push === "true") {
      var toggle = document.getElementById("action-toggle");
      if (toggle) toggle.style.display = "";
    }
  })();

  // ── Download / Push toggle ────────────────────────────────
  function setAction(action) {
    document.getElementById("action-input").value = action;
    var panel = document.getElementById("credential-panel");
    var btnDl = document.getElementById("toggle-download");
    var btnPush = document.getElementById("toggle-push");
    var label = document.getElementById("export-btn-label");
    if (action === "push") {
      if (panel) panel.classList.add("visible");
      if (btnDl) btnDl.className = "btn btn-sm btn-ghost";
      if (btnPush) btnPush.className = "btn btn-sm btn-primary";
      if (label) label.textContent = "Push to platform";
    } else {
      if (panel) panel.classList.remove("visible");
      if (btnDl) btnDl.className = "btn btn-sm btn-primary";
      if (btnPush) btnPush.className = "btn btn-sm btn-ghost";
      if (label) label.textContent = "Download";
    }
  }

  var btnDl = document.getElementById("toggle-download");
  var btnPush = document.getElementById("toggle-push");
  if (btnDl) btnDl.addEventListener("click", function () { setAction("download"); });
  if (btnPush) btnPush.addEventListener("click", function () { setAction("push"); });

  // ── Helpers for HTMX-loaded export result partials ────────

  function initExportResult(container) {
    // Blob download link
    var ta = container.querySelector("#export-content");
    var link = container.querySelector("#download-link");
    if (ta && link) {
      var blob = new Blob([ta.value], { type: "text/plain" });
      link.href = URL.createObjectURL(blob);
    }

    // Copy button
    var copyBtn = container.querySelector("#copy-btn");
    if (copyBtn) {
      copyBtn.addEventListener("click", function () {
        var content = document.getElementById("export-content");
        if (!content) return;
        navigator.clipboard.writeText(content.value).then(function () {
          copyBtn.textContent = "Copied!";
          setTimeout(function () {
            copyBtn.innerHTML =
              '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copy';
          }, 2000);
        });
      });
    }

    // Cleanup modal
    var modal = container.querySelector("#cleanup-modal");
    if (modal) {
      // "Keep session" button
      var keepBtn = modal.querySelector("[data-action='close-modal']");
      if (keepBtn) {
        keepBtn.addEventListener("click", function () { modal.close(); });
      }
      // "Delete session data" button
      var deleteBtn = modal.querySelector("[data-action='delete-session']");
      if (deleteBtn) {
        deleteBtn.addEventListener("click", function () {
          var sid = modal.dataset.sessionId || "";
          fetch("/session/" + encodeURIComponent(sid), {
            method: "DELETE",
            credentials: "same-origin",
          })
            .then(function (resp) {
              if (resp.ok) {
                window.location.href = "/";
              } else {
                var err = document.getElementById("cleanup-error");
                if (err) err.hidden = false;
              }
            })
            .catch(function () {
              var err = document.getElementById("cleanup-error");
              if (err) err.hidden = false;
            });
        });
      }

      // Auto-open modal for push results (immediate) or download (after link click)
      if (link) {
        link.addEventListener("click", function () {
          setTimeout(function () { modal.showModal(); }, 400);
        });
      } else {
        // Push result — show modal immediately
        modal.showModal();
      }
    }
  }

  // Run on HTMX swap into #export-result
  document.body.addEventListener("htmx:afterSwap", function (evt) {
    if (evt.detail.target && evt.detail.target.id === "export-result") {
      initExportResult(evt.detail.target);
    }
  });
})();

/**
 * web.js — Add-web-source panel.
 *
 * Handles: per-session consent toggle, URL preview fetch, inline preview
 * rendering, and ingest confirm/discard. Reuses window.refreshSessionStats
 * (exposed by review.js) so the docs list updates after a successful ingest.
 */

document.addEventListener("DOMContentLoaded", function () {
  var panel = document.getElementById("web-source-panel");
  if (!panel) return;

  var sessionId = panel.dataset.sessionId;
  var consentToggle = document.getElementById("web-consent-toggle");
  var form = document.getElementById("web-url-form");
  var input = document.getElementById("web-url-input");
  var previewBtn = document.getElementById("web-url-preview-btn");
  var statusEl = document.getElementById("web-url-status");
  var previewContainer = document.getElementById("web-preview-container");

  function setStatus(msg, kind) {
    if (!statusEl) return;
    statusEl.textContent = msg || "";
    statusEl.style.color =
      kind === "error" ? "var(--danger, #c0392b)" : "var(--text-muted)";
  }

  function setInputsEnabled(enabled) {
    if (input) input.disabled = !enabled;
    if (previewBtn) previewBtn.disabled = !enabled;
  }

  function escapeHtml(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function clearPreview() {
    if (!previewContainer) return;
    previewContainer.innerHTML = "";
    previewContainer.hidden = true;
  }

  function renderPreview(payload) {
    if (!previewContainer) return;
    var warnings = (payload.warnings || []).slice();
    var hasJsWarning = warnings.indexOf("likely_js_rendered") !== -1;
    var titleHtml = payload.title
      ? "<strong>" + escapeHtml(payload.title) + "</strong>"
      : "<em>(no title)</em>";
    var hostnameHtml = escapeHtml(payload.hostname || "");
    var preview = escapeHtml(payload.preview_text || "");
    var ingestNotice = payload.already_ingested_at
      ? '<div class="alert alert-warning" style="font-size:0.8rem; margin:0.4rem 0;">' +
        "You ingested this URL on " +
        escapeHtml(payload.already_ingested_at) +
        ". Confirming will replace the previous version.</div>"
      : "";
    var jsNotice = hasJsWarning
      ? '<div class="alert alert-warning" style="font-size:0.8rem; margin:0.4rem 0;">' +
        "This page may require a browser to render. Only " +
        payload.extracted_chars +
        " characters were extracted. Saving as PDF and uploading is a reliable workaround.</div>"
      : "";
    previewContainer.innerHTML =
      '<div style="border:1px solid var(--border); border-radius:var(--radius); padding:0.6rem; font-size:0.85rem;">' +
      '<div style="margin-bottom:0.35rem;">' +
      titleHtml +
      '<div style="font-size:0.75rem; color:var(--text-muted); word-break:break-all;">' +
      '<a href="' +
      escapeHtml(payload.final_url || "") +
      '" target="_blank" rel="noopener noreferrer">' +
      escapeHtml(payload.final_url || "") +
      "</a>" +
      "</div>" +
      '<div style="font-size:0.75rem; color:var(--text-muted);">' +
      hostnameHtml +
      " · " +
      escapeHtml(payload.content_type || "") +
      " · " +
      payload.extracted_chars +
      " chars</div>" +
      "</div>" +
      ingestNotice +
      jsNotice +
      '<details style="margin:0.3rem 0;">' +
      '<summary style="cursor:pointer; font-size:0.75rem; color:var(--text-muted);">Preview (first 500 chars)</summary>' +
      '<pre style="white-space:pre-wrap; font-size:0.8rem; margin:0.35rem 0 0;">' +
      preview +
      "</pre>" +
      "</details>" +
      '<div style="display:flex; gap:0.4rem; justify-content:flex-end; margin-top:0.4rem;">' +
      '<button type="button" class="btn btn-ghost" data-action="web-discard" style="font-size:0.8rem;">Discard</button>' +
      '<button type="button" class="btn btn-primary" data-action="web-ingest" data-url="' +
      escapeHtml(payload.initial_url || "") +
      '" style="font-size:0.8rem;">Add as source</button>' +
      "</div>" +
      "</div>";
    previewContainer.hidden = false;
  }

  if (consentToggle) {
    consentToggle.addEventListener("change", function () {
      var enabled = consentToggle.checked;
      consentToggle.disabled = true;
      fetch("/session/" + sessionId + "/web-consent", {
        method: "PUT",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: enabled }),
      })
        .then(function (resp) {
          if (!resp.ok) throw new Error("HTTP " + resp.status);
          return resp.json();
        })
        .then(function (data) {
          var on = !!data.web_consent;
          consentToggle.checked = on;
          setInputsEnabled(on);
          setStatus(on ? "" : "Web sources disabled.");
          if (!on) clearPreview();
        })
        .catch(function () {
          consentToggle.checked = !enabled;
          setStatus("Could not update consent. Please try again.", "error");
        })
        .finally(function () {
          consentToggle.disabled = false;
        });
    });
  }

  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var url = (input && input.value || "").trim();
      if (!url) {
        setStatus("Enter a URL first.", "error");
        return;
      }
      setStatus("Fetching preview…");
      clearPreview();
      previewBtn.disabled = true;
      fetch("/session/" + sessionId + "/web/preview", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url }),
      })
        .then(function (resp) {
          return resp.json().then(function (data) {
            return { ok: resp.ok, status: resp.status, data: data };
          });
        })
        .then(function (result) {
          if (!result.ok) {
            var detail = (result.data && result.data.detail) || "Preview failed.";
            setStatus(detail, "error");
            return;
          }
          setStatus("");
          renderPreview(result.data);
        })
        .catch(function () {
          setStatus("Network error during preview.", "error");
        })
        .finally(function () {
          previewBtn.disabled = false;
        });
    });
  }

  if (previewContainer) {
    previewContainer.addEventListener("click", function (e) {
      var discardBtn = e.target.closest("[data-action='web-discard']");
      if (discardBtn) {
        clearPreview();
        setStatus("");
        return;
      }
      var ingestBtn = e.target.closest("[data-action='web-ingest']");
      if (!ingestBtn) return;
      var url = ingestBtn.dataset.url;
      if (!url) return;
      ingestBtn.disabled = true;
      var discard = previewContainer.querySelector("[data-action='web-discard']");
      if (discard) discard.disabled = true;
      setStatus("Adding source…");
      fetch("/session/" + sessionId + "/web/ingest", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url }),
      })
        .then(function (resp) {
          return resp.json().then(function (data) {
            return { ok: resp.ok, status: resp.status, data: data };
          });
        })
        .then(function (result) {
          if (!result.ok) {
            var detail = (result.data && result.data.detail) || "Ingest failed.";
            setStatus(detail, "error");
            ingestBtn.disabled = false;
            if (discard) discard.disabled = false;
            return;
          }
          setStatus("Source added.");
          clearPreview();
          if (input) input.value = "";
          if (typeof window.refreshSessionStats === "function") {
            window.refreshSessionStats();
          }
        })
        .catch(function () {
          setStatus("Network error during ingest.", "error");
          ingestBtn.disabled = false;
          if (discard) discard.disabled = false;
        });
    });
  }
});

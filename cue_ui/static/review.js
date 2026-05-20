/**
 * review.js — Survey review page logic.
 *
 * Handles accept/dismiss via event delegation (no inline onclick),
 * SSE stream lifecycle, and ReviewState restore on OOB swaps.
 */

document.addEventListener("DOMContentLoaded", function () {
  var formEl = document.getElementById("survey-form");
  var sessionId = formEl ? formEl.dataset.sessionId : "";
  var reviewState = new ReviewState(sessionId);

  var serverStateEl = document.getElementById("server-review-state");
  if (serverStateEl) {
    try {
      var serverState = JSON.parse(serverStateEl.textContent);
      if (serverState && Object.keys(serverState).length > 0) {
        reviewState.loadWithServer(serverState);
      }
    } catch (e) {}
  }

  reviewState.restoreAll();

  // ---------------------------------------------------------------
  // Accept / Dismiss via event delegation
  // ---------------------------------------------------------------

  document.addEventListener("click", function (e) {
    var acceptBtn = e.target.closest("[data-action='accept']");
    if (acceptBtn) {
      var block = acceptBtn.closest(".suggestion-block");
      var questionId = block.dataset.questionId;
      var value = block.dataset.suggestion;
      var selectedId = block.dataset.selectedId;

      var textarea = document.getElementById("input-" + questionId);
      if (textarea) {
        textarea.value = value;
      } else if (selectedId) {
        var radio = document.getElementById("opt-" + questionId + "-" + selectedId);
        if (radio) radio.checked = true;
      }

      block.style.border = "1px solid #16a34a";
      block.style.background = "#f0fdf4";
      reviewState.save(questionId, { state: "accepted", value: value, selected_id: selectedId });
      return;
    }

    var dismissBtn = e.target.closest("[data-action='dismiss']");
    if (dismissBtn) {
      var block = dismissBtn.closest(".suggestion-block");
      var questionId = block.dataset.questionId;
      block.style.display = "none";
      reviewState.save(questionId, { state: "dismissed" });
      return;
    }
  });

  // ---------------------------------------------------------------
  // Restore state whenever a suggestion block arrives via SSE OOB
  // ---------------------------------------------------------------

  document.body.addEventListener("htmx:oobAfterSwap", function () {
    reviewState.restoreAll();
  });

  // ---------------------------------------------------------------
  // SSE stream lifecycle
  // ---------------------------------------------------------------

  function clearRemainingSpinners(message) {
    document.querySelectorAll(".suggestion-loading").forEach(function (el) {
      el.closest(".suggestion-zone").innerHTML =
        '<p style="color:var(--text-muted);font-size:0.875rem;">' + message + "</p>";
    });
  }

  var container = document.getElementById("suggestions-container");
  if (container) {
    container.addEventListener("htmx:sseMessage", function (e) {
      if (e.detail.type === "error") {
        container.removeAttribute("sse-connect");
        var detail = "Suggestion stream failed.";
        try { detail = JSON.parse(e.detail.data).detail || detail; } catch (_) { /* use default */ }
        var banner = document.getElementById("stream-error-banner");
        banner.textContent = "Could not load suggestions: " + detail;
        banner.style.display = "";
        clearRemainingSpinners("Suggestion unavailable.");
      } else if (e.detail.type === "done") {
        container.removeAttribute("sse-connect");
        clearRemainingSpinners("No suggestion available.");
        enableAcceptAllIfReady();
      }
    });

    // Stop reconnection on EventSource connection errors (e.g., session deleted)
    container.addEventListener("htmx:sseError", function () {
      container.removeAttribute("sse-connect");
    });
  }

  // ---------------------------------------------------------------
  // Accept all suggestions
  // ---------------------------------------------------------------

  function enableAcceptAllIfReady() {
    var btn = document.getElementById("accept-all-btn");
    if (!btn) return;
    var hasAcceptable = document.querySelectorAll("[data-action='accept']").length > 0;
    btn.disabled = !hasAcceptable;
  }

  // If some suggestions are already rendered from cache, try enabling immediately
  if (document.querySelectorAll(".suggestion-block").length > 0) {
    enableAcceptAllIfReady();
  }

  // Also enable after each OOB swap (suggestion arrived)
  document.body.addEventListener("htmx:oobAfterSwap", enableAcceptAllIfReady);

  var acceptAllBtn = document.getElementById("accept-all-btn");
  if (acceptAllBtn) {
    acceptAllBtn.addEventListener("click", function () {
      document.querySelectorAll("[data-action='accept']").forEach(function (btn) {
        var block = btn.closest(".suggestion-block");
        if (!block || block.style.display === "none") return;
        var questionId = block.dataset.questionId;
        var value = block.dataset.suggestion;
        var selectedId = block.dataset.selectedId;

        var textarea = document.getElementById("input-" + questionId);
        if (textarea) {
          textarea.value = value;
        } else if (selectedId) {
          var radio = document.getElementById("opt-" + questionId + "-" + selectedId);
          if (radio) radio.checked = true;
        }

        block.style.border = "1px solid #16a34a";
        block.style.background = "#f0fdf4";
        reviewState.save(questionId, { state: "accepted", value: value, selected_id: selectedId });
      });
    });
  }

  // ---------------------------------------------------------------
  // Late-document-uploads: mid-review upload + regenerate buttons
  //
  // Staleness rule: a cached suggestion with `data-generated-at` set
  // is "stale" if its timestamp predates `lastUploadAt`. Missing
  // timestamps are treated as "never stale" (legacy entries from
  // before this feature shipped).
  // ---------------------------------------------------------------

  var lastUploadAt = null;
  var luaEl = document.getElementById("server-last-upload-at");
  if (luaEl) {
    try { lastUploadAt = JSON.parse(luaEl.textContent); } catch (_) { /* keep null */ }
  }

  function isStale(block) {
    var ts = block.dataset.generatedAt;
    return !!(ts && lastUploadAt && ts < lastUploadAt);
  }

  function recomputeRegenerateVisibility() {
    var staleUntouchedIds = [];
    var emptyUntouchedIds = [];
    document.querySelectorAll("[data-suggestion-block]").forEach(function (block) {
      var qid = block.dataset.questionId;
      var btn = block.querySelector("[data-action='regenerate']");
      var stale = isStale(block);
      var untouched = !reviewState.get(qid);
      var hasNoAnswer = !(block.dataset.suggestion || block.dataset.selectedId);
      if (btn) btn.hidden = !stale;
      if (stale && untouched) staleUntouchedIds.push(qid);
      if (hasNoAnswer && untouched) emptyUntouchedIds.push(qid);
    });

    var bulkBtn = document.getElementById("regenerate-untouched-btn");
    if (bulkBtn) {
      bulkBtn.hidden = staleUntouchedIds.length === 0;
      var countEl = bulkBtn.querySelector("[data-count]");
      if (countEl) countEl.textContent = staleUntouchedIds.length;
      bulkBtn.dataset.targetIds = staleUntouchedIds.join(",");
    }

    var emptyBtn = document.getElementById("regenerate-empty-btn");
    if (emptyBtn) {
      emptyBtn.hidden = emptyUntouchedIds.length === 0;
      var emptyCountEl = emptyBtn.querySelector("[data-count]");
      if (emptyCountEl) emptyCountEl.textContent = emptyUntouchedIds.length;
      emptyBtn.dataset.targetIds = emptyUntouchedIds.join(",");
    }
  }

  var knownDocsList = new Set();
  // Seed from server-rendered rows so the first refresh doesn't flash everything.
  (function () {
    var listEl = document.getElementById("docs-list");
    if (!listEl) return;
    listEl.querySelectorAll("tr").forEach(function (row) {
      var nameEl = row.querySelector("td .source-name") || row.querySelector("td");
      if (nameEl) knownDocsList.add(nameEl.textContent.trim());
    });
  })();

  function iconForKind(kind) {
    if (kind === "web") return "🌐";
    if (kind === "text") return "✍";
    return "📄";
  }

  function renderDocsList(documents) {
    var listEl = document.getElementById("docs-list");
    var countEl = document.getElementById("docs-count");
    if (!listEl) return;
    if (countEl) countEl.textContent = documents.length;
    if (documents.length === 0) {
      knownDocsList = new Set();
      listEl.innerHTML = '<p style="margin:0; color:var(--text-muted); font-style:italic; font-size:0.75rem;">No sources yet.</p>';
      return;
    }
    var rows = documents.map(function (d) {
      var chunks = d.chunk_count;
      var label = chunks + " chunk" + (chunks === 1 ? "" : "s");
      var name = (d.name || "").replace(/[<>&]/g, function (c) {
        return { "<": "&lt;", ">": "&gt;", "&": "&amp;" }[c];
      });
      var rowClass = knownDocsList.has(d.name) ? "" : "source-row-new";
      return (
        '<tr class="' + rowClass + '"><td style="padding:0.3rem 0.5rem 0.3rem 0;">' +
        iconForKind(d.source_kind) + ' <span class="source-name">' + name + '</span>' +
        '</td><td style="padding:0.3rem 0; text-align:right; color:var(--text-muted); white-space:nowrap;">' +
        label +
        '</td><td style="padding:0.3rem 0 0.3rem 0.5rem; text-align:right;">' +
        '<button type="button" class="source-remove-btn" data-source-name="' + name + '" ' +
        'aria-label="Remove ' + name + '" title="Remove" ' +
        'style="background:none; border:0; cursor:pointer; color:var(--text-muted); font-size:0.85rem; padding:0 0.25rem;">' +
        '✕</button></td></tr>'
      );
    });
    listEl.innerHTML =
      '<table style="width:100%; border-collapse:collapse;">' +
      rows.join("") +
      "</table>";
    knownDocsList = new Set(documents.map(function (d) { return d.name; }));
  }

  function setAddedStatus(statusEl) {
    if (!statusEl) return;
    statusEl.innerHTML = '<span style="color:var(--success, #16a34a);">✓ Added</span>';
  }

  function refreshSessionStats() {
    return fetch("/session/" + sessionId + "/stats", { credentials: "same-origin" })
      .then(function (resp) {
        if (!resp.ok) return null;
        return resp.json();
      })
      .then(function (data) {
        if (!data) return null;
        if (data.last_upload_at) lastUploadAt = data.last_upload_at;
        renderDocsList(data.documents || []);
        recomputeRegenerateVisibility();
        return data;
      })
      .catch(function () { /* best-effort */ return null; });
  }

  recomputeRegenerateVisibility();
  document.body.addEventListener("htmx:oobAfterSwap", recomputeRegenerateVisibility);

  window.refreshSessionStats = refreshSessionStats;

  // ---- Per-row source remove ----
  document.addEventListener("click", function (e) {
    var btn = e.target.closest(".source-remove-btn");
    if (!btn) return;
    e.preventDefault();
    var name = btn.dataset.sourceName;
    if (!name) return;
    if (!window.confirm("Remove «" + name + "» from your sources?")) return;
    btn.disabled = true;
    fetch("/session/" + sessionId + "/documents/" + encodeURIComponent(name), {
      method: "DELETE",
      credentials: "same-origin",
    })
      .then(function (resp) {
        if (resp.ok || resp.status === 404) {
          refreshSessionStats();
        } else {
          btn.disabled = false;
          alert("Could not remove source (HTTP " + resp.status + ")");
        }
      })
      .catch(function () {
        btn.disabled = false;
        alert("Network error while removing source");
      });
  });

  // ---- Mid-review upload forms (files + text, parallel) ----

  var baseUrl = "/session/" + sessionId;

  var fileForm = document.getElementById("late-file-form");
  if (fileForm) {
    fileForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var statusEl = document.getElementById("late-file-status");
      var fileInput = document.getElementById("late-upload-files");
      var submitBtn = fileForm.querySelector("button[type='submit']");
      var files = fileInput ? Array.from(fileInput.files) : [];
      if (files.length === 0) {
        statusEl.textContent = "Choose a file first.";
        return;
      }
      submitBtn.disabled = true;
      statusEl.textContent = "Uploading…";
      var errors = [];

      function uploadFile(i) {
        if (i >= files.length) return Promise.resolve();
        var f = files[i];
        var fd = new FormData();
        fd.append("file", f);
        return fetch(baseUrl + "/upload-doc", { method: "POST", body: fd, credentials: "same-origin" })
          .then(function (resp) {
            if (!resp.ok) {
              return resp.json().then(function (data) {
                errors.push(f.name + ": " + (data.error || "Upload failed"));
              }, function () { errors.push(f.name + ": Upload failed"); });
            }
          })
          .catch(function () { errors.push(f.name + ": Upload failed (network error)"); })
          .then(function () { return uploadFile(i + 1); });
      }

      uploadFile(0).then(function () {
        var anySuccess = errors.length < files.length;
        var done = anySuccess ? refreshSessionStats() : Promise.resolve(null);
        return done.then(function () {
          if (anySuccess && fileInput) fileInput.value = "";
          if (errors.length) {
            statusEl.textContent = errors.join("; ");
          } else {
            setAddedStatus(statusEl);
          }
          submitBtn.disabled = false;
        });
      });
    });
  }

  var textForm = document.getElementById("late-text-form");
  if (textForm) {
    textForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var statusEl = document.getElementById("late-text-status");
      var textArea = document.getElementById("late-upload-text");
      var labelInput = document.getElementById("late-upload-label");
      var submitBtn = textForm.querySelector("button[type='submit']");
      var text = textArea ? textArea.value.trim() : "";
      var label = labelInput ? labelInput.value.trim() : "";
      if (!text) {
        statusEl.textContent = "Paste some text first.";
        return;
      }
      submitBtn.disabled = true;
      statusEl.textContent = "Uploading…";

      fetch(baseUrl + "/upload-text-snippet", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text, label: label || null }),
        credentials: "same-origin"
      })
        .then(function (resp) {
          if (resp.ok) {
            if (textArea) textArea.value = "";
            if (labelInput) labelInput.value = "";
            return refreshSessionStats().then(function () {
              setAddedStatus(statusEl);
            });
          }
          return resp.json().then(function (data) {
            statusEl.textContent = (label || "pasted text") + ": " + (data.error || "Upload failed");
          }, function () {
            statusEl.textContent = (label || "pasted text") + ": Upload failed";
          });
        })
        .catch(function () {
          statusEl.textContent = (label || "pasted text") + ": Upload failed (network error)";
        })
        .finally(function () {
          submitBtn.disabled = false;
        });
    });
  }

  // ---- Regenerate buttons (per-question + bulk) ----
  //
  // While a regenerate stream is in flight, each affected block hides its
  // Regenerate button and shows an inline spinner. On `suggestion` arrival the
  // whole block is replaced (the new partial's spinner is hidden by default).
  // On close, any leftover spinners (ids that didn't get a response) are
  // cleared, and `recomputeRegenerateVisibility()` re-evaluates which buttons
  // should be visible.

  function setRegeneratePending(ids, pending) {
    (ids || []).forEach(function (id) {
      var block = document.getElementById("sug-" + id);
      if (!block) return;
      var btn = block.querySelector("[data-action='regenerate']");
      var spinner = block.querySelector("[data-role='regenerate-spinner']");
      if (pending) {
        if (btn) btn.hidden = true;
        if (spinner) spinner.hidden = false;
      } else {
        if (spinner) spinner.hidden = true;
      }
    });
  }

  function openRegenerateStream(ids, onComplete) {
    var idList = Array.isArray(ids) ? ids.slice() : (ids ? [ids] : []);
    var url = "/session/" + sessionId + "/regenerate-stream";
    if (idList.length) url += "?ids=" + encodeURIComponent(idList.join(","));
    var pending = new Set(idList);
    setRegeneratePending(idList, true);
    var src = new EventSource(url);
    function close() {
      try { src.close(); } catch (_) {}
      setRegeneratePending(Array.from(pending), false);
      recomputeRegenerateVisibility();
      if (onComplete) onComplete();
    }
    src.addEventListener("done", close);
    src.addEventListener("error", close);
    src.addEventListener("suggestion", function (e) {
      var html = e.data;
      var tmp = document.createElement("div");
      tmp.innerHTML = html;
      var fresh = tmp.firstElementChild;
      if (!fresh || !fresh.id) return;
      var existing = document.getElementById(fresh.id);
      if (existing) existing.replaceWith(fresh);
      pending.delete(fresh.id.replace(/^sug-/, ""));
      reviewState.restoreAll();
      recomputeRegenerateVisibility();
      enableAcceptAllIfReady();
    });
    return src;
  }

  document.addEventListener("click", function (e) {
    var regenBtn = e.target.closest("[data-action='regenerate']");
    if (!regenBtn) return;
    var block = regenBtn.closest("[data-suggestion-block]");
    if (!block) return;
    openRegenerateStream([block.dataset.questionId]);
  });

  function wireBulkButton(btn, confirmTemplate) {
    if (!btn) return;
    btn.addEventListener("click", function () {
      var idsCsv = btn.dataset.targetIds || "";
      var idList = idsCsv ? idsCsv.split(",") : [];
      if (idList.length === 0) return;
      var n = idList.length;
      var msg = confirmTemplate
        .replace("{n}", n)
        .replace("{s}", n === 1 ? "" : "s");
      if (!window.confirm(msg)) return;
      btn.disabled = true;
      openRegenerateStream(idList, function () { btn.disabled = false; });
    });
  }

  wireBulkButton(
    document.getElementById("regenerate-untouched-btn"),
    "Regenerate {n} suggestion{s}? This may take a while."
  );
  wireBulkButton(
    document.getElementById("regenerate-empty-btn"),
    "Re-try {n} empty answer{s}? This may take a while."
  );
});

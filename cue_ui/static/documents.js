/**
 * documents.js — Document upload page logic (in-card ingest).
 *
 * Three independent cards (files, web, paste text) each ingest immediately
 * via fetch. A shared in-flight counter disables the Continue button while
 * any upload is in progress. The sources list (card 4) refreshes after each
 * successful add via window.refreshSessionStats, which web.js also reuses.
 */

document.addEventListener("DOMContentLoaded", function () {
  var firstCard = document.querySelector(".card[data-session-id]");
  if (!firstCard) return;
  var sessionId = firstCard.dataset.sessionId;
  var baseUrl = "/session/" + sessionId;

  var continueBtn = document.getElementById("continue-btn");
  var continueHint = document.getElementById("continue-hint");
  var docsList = document.getElementById("docs-list");
  var docsCount = document.getElementById("docs-count");
  var errorsContainer = document.getElementById("add-source-errors");

  var inFlight = 0;
  var knownSourceNames = new Set();

  // Seed knownSourceNames from the server-rendered list so the first refresh
  // doesn't flash everything as "new".
  if (docsList) {
    docsList.querySelectorAll("tr").forEach(function (row) {
      var first = row.querySelector("td");
      if (first) knownSourceNames.add(first.textContent.trim());
    });
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

  function setBusy(busy) {
    if (!continueBtn) return;
    if (busy) {
      continueBtn.classList.add("disabled");
      continueBtn.setAttribute("aria-disabled", "true");
      continueBtn.style.pointerEvents = "none";
      continueBtn.style.opacity = "0.5";
      if (continueHint) continueHint.hidden = false;
    } else {
      continueBtn.classList.remove("disabled");
      continueBtn.removeAttribute("aria-disabled");
      continueBtn.style.pointerEvents = "";
      continueBtn.style.opacity = "";
      if (continueHint) continueHint.hidden = true;
    }
  }

  function beginRequest() {
    inFlight++;
    setBusy(true);
  }

  function endRequest() {
    if (inFlight > 0) inFlight--;
    if (inFlight === 0) setBusy(false);
  }

  function renderDocs(documents) {
    if (docsCount) docsCount.textContent = documents.length;
    if (!docsList) return;
    if (documents.length === 0) {
      knownSourceNames = new Set();
      docsList.innerHTML =
        '<p style="margin:0; color:var(--text-muted); font-size:0.9rem; font-style:italic;">' +
        "No sources yet. Add files, a URL, or paste text above — or continue without any.</p>";
      return;
    }
    var rows = documents
      .map(function (doc) {
        var chunkLabel = (doc.chunk_count || 0) + " chunk" + (doc.chunk_count === 1 ? "" : "s");
        var isNew = !knownSourceNames.has(doc.name);
        var rowClass = isNew ? "source-row-new" : "";
        return (
          '<tr class="' + rowClass + '">' +
          '<td style="padding:0.4rem 0.5rem 0.4rem 0;">' +
          escapeHtml(doc.name) +
          "</td>" +
          '<td style="padding:0.4rem 0; text-align:right; color:var(--text-muted); white-space:nowrap;">' +
          escapeHtml(chunkLabel) +
          "</td>" +
          "</tr>"
        );
      })
      .join("");
    docsList.innerHTML =
      '<table style="width:100%; border-collapse:collapse; font-size:0.9rem;">' + rows + "</table>";
    knownSourceNames = new Set(documents.map(function (d) { return d.name; }));
  }

  function refreshSessionStats() {
    return fetch(baseUrl + "/stats", { credentials: "same-origin" })
      .then(function (resp) {
        if (!resp.ok) return null;
        return resp.json();
      })
      .then(function (data) {
        if (!data) return null;
        renderDocs(data.documents || []);
        return data;
      })
      .catch(function () {
        /* best-effort */
        return null;
      });
  }
  window.refreshSessionStats = refreshSessionStats;

  function setAddedStatus(statusEl) {
    if (!statusEl) return;
    statusEl.innerHTML =
      '<span style="color:var(--success, #16a34a);">✓ Added</span> &mdash; ' +
      '<a href="#sources-card" data-action="jump-to-sources" style="text-decoration:underline;">[↓ View list]</a>';
  }

  document.addEventListener("click", function (e) {
    var link = e.target.closest("[data-action='jump-to-sources']");
    if (!link) return;
    e.preventDefault();
    var card = document.getElementById("sources-card");
    if (card) card.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  function showError(message) {
    if (!errorsContainer) return;
    errorsContainer.hidden = false;
    var existing = errorsContainer.querySelector(".alert");
    if (!existing) {
      errorsContainer.innerHTML =
        '<div class="alert alert-error" style="margin-bottom:1rem;"><strong>Some sources could not be added:</strong><ul style="margin-top:0.5rem; padding-left:1.25rem;"></ul></div>';
    }
    var list = errorsContainer.querySelector("ul");
    if (!list) return;
    var li = document.createElement("li");
    li.textContent = message;
    list.appendChild(li);
  }

  function clearErrors() {
    if (!errorsContainer) return;
    errorsContainer.innerHTML = "";
    errorsContainer.hidden = true;
  }

  // ---- File card ----

  var fileForm = document.getElementById("file-card-form");
  if (fileForm) {
    fileForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var fileInput = document.getElementById("files");
      var btn = document.getElementById("file-add-btn");
      var statusEl = document.getElementById("file-add-status");
      var files = fileInput ? Array.from(fileInput.files) : [];
      if (files.length === 0) {
        if (statusEl) statusEl.textContent = "Choose at least one file.";
        return;
      }
      btn.disabled = true;
      var total = files.length;
      var index = 0;
      var hadSuccess = false;

      function uploadNext() {
        if (index >= total) {
          fileInput.value = "";
          btn.disabled = false;
          endRequest();
          if (hadSuccess) {
            refreshSessionStats().then(function () {
              setAddedStatus(statusEl);
            });
          } else if (statusEl) {
            statusEl.textContent = "";
          }
          return;
        }
        var file = files[index];
        index++;
        if (statusEl) {
          statusEl.textContent = "Adding " + index + " of " + total + " (" + file.name + ")…";
        }
        var formData = new FormData();
        formData.append("file", file);
        fetch(baseUrl + "/upload-doc", {
          method: "POST",
          body: formData,
          credentials: "same-origin",
        })
          .then(function (resp) {
            if (resp.ok) {
              hadSuccess = true;
              return;
            }
            return resp
              .json()
              .catch(function () {
                return {};
              })
              .then(function (data) {
                showError(file.name + ": " + (data.error || "Upload failed"));
              });
          })
          .catch(function () {
            showError(file.name + ": Upload failed (network error)");
          })
          .then(uploadNext);
      }

      clearErrors();
      beginRequest();
      uploadNext();
    });
  }

  // ---- Paste text card ----

  var textForm = document.getElementById("text-card-form");
  if (textForm) {
    textForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var textArea = document.getElementById("text-snippet");
      var labelInput = document.getElementById("text-label");
      var btn = document.getElementById("text-add-btn");
      var statusEl = document.getElementById("text-add-status");
      var text = textArea ? textArea.value.trim() : "";
      var label = labelInput ? labelInput.value.trim() : "";
      if (!text) {
        if (statusEl) statusEl.textContent = "Paste some text first.";
        return;
      }
      btn.disabled = true;
      if (statusEl) statusEl.textContent = "Adding…";
      clearErrors();
      beginRequest();
      fetch(baseUrl + "/upload-text-snippet", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text, label: label || null }),
        credentials: "same-origin",
      })
        .then(function (resp) {
          if (resp.ok) {
            if (textArea) textArea.value = "";
            if (labelInput) labelInput.value = "";
            return refreshSessionStats().then(function () {
              setAddedStatus(statusEl);
            });
          }
          return resp
            .json()
            .catch(function () {
              return {};
            })
            .then(function (data) {
              showError((label || "pasted text") + ": " + (data.error || "Upload failed"));
              if (statusEl) statusEl.textContent = "";
            });
        })
        .catch(function () {
          showError((label || "pasted text") + ": Upload failed (network error)");
          if (statusEl) statusEl.textContent = "";
        })
        .finally(function () {
          btn.disabled = false;
          endRequest();
        });
    });
  }

  // web.js emits custom events around its ingest call so the Continue button
  // stays disabled until the server has actually committed the chunks.
  document.addEventListener("web-ingest-start", beginRequest);
  document.addEventListener("web-ingest-end", endRequest);
});

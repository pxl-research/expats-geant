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
      }
    });
  }
});

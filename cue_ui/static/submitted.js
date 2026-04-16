/**
 * submitted.js — Post-submission page logic.
 *
 * Clears localStorage review state and auto-opens the cleanup modal.
 */

document.addEventListener("DOMContentLoaded", function () {
  // Clear review state for this session (session ID is on the data attribute)
  var el = document.querySelector("[data-session-id]");
  if (el) {
    try { localStorage.removeItem("review-" + el.dataset.sessionId); } catch (_) {}
  }

  // Auto-open cleanup modal
  var modal = document.getElementById("cleanup-modal");
  if (modal) { modal.showModal(); }
});

/**
 * session-cleanup.js — Session cleanup modal logic.
 *
 * Used on the review page and submitted page to delete session data.
 */

document.addEventListener("DOMContentLoaded", function () {
  var modal = document.getElementById("cleanup-modal");
  if (!modal) return;

  // "Start over" / open trigger
  var openBtn = document.getElementById("cleanup-open-btn");
  if (openBtn) {
    openBtn.addEventListener("click", function () { modal.showModal(); });
  }

  // "Keep session" close button
  var keepBtn = document.getElementById("cleanup-keep-btn");
  if (keepBtn) {
    keepBtn.addEventListener("click", function () { modal.close(); });
  }

  // "Delete session data" button
  var deleteBtn = document.getElementById("cleanup-delete-btn");
  if (deleteBtn) {
    deleteBtn.addEventListener("click", function () {
      var idEl = document.querySelector("[data-session-id]");
      var sessionId = idEl ? idEl.dataset.sessionId : "";
      var url = sessionId ? "/session/" + encodeURIComponent(sessionId) : "/session";
      fetch(url, { method: "DELETE", credentials: "same-origin" })
        .then(function (resp) {
          if (resp.ok) {
            // Clear all review state from localStorage
            try {
              Object.keys(localStorage)
                .filter(function (k) { return k.startsWith("review-"); })
                .forEach(function (k) { localStorage.removeItem(k); });
            } catch (_) {}
            window.location.href = "/";
          } else {
            document.getElementById("cleanup-error").hidden = false;
          }
        })
        .catch(function () {
          document.getElementById("cleanup-error").hidden = false;
        });
    });
  }
});

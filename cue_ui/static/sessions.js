/**
 * sessions.js — Sessions overview page logic.
 *
 * Wires the per-row Delete button to /session/{id} (DELETE) with a confirm
 * dialog. Cookie rotation happens server-side via Set-Cookie on the proxy
 * response when the deleted session was the JWT-bound one.
 */

document.addEventListener("DOMContentLoaded", function () {
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-action='delete-session']");
    if (!btn) return;
    var sessionId = btn.dataset.sessionId;
    if (!sessionId) return;
    if (!window.confirm("Delete this session and all its data? This cannot be undone.")) return;
    btn.disabled = true;
    fetch("/session/" + encodeURIComponent(sessionId), {
      method: "DELETE",
      credentials: "same-origin",
    })
      .then(function (resp) {
        if (resp.ok) {
          window.location.reload();
        } else {
          btn.disabled = false;
          window.alert("Could not delete session. Please try again.");
        }
      })
      .catch(function () {
        btn.disabled = false;
        window.alert("Could not delete session. Please try again.");
      });
  });
});

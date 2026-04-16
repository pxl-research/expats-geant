/**
 * error.js — Error page logic.
 *
 * Clears expired session state from localStorage.
 */

document.addEventListener("DOMContentLoaded", function () {
  var isExpired = document.querySelector("[data-session-expired]");
  if (isExpired) {
    try {
      Object.keys(localStorage)
        .filter(function (k) { return k.startsWith("review-"); })
        .forEach(function (k) { localStorage.removeItem(k); });
    } catch (_) {}
  }
});

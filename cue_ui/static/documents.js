/**
 * documents.js — Document upload page logic.
 *
 * Shows progress indicator and disables the submit button while the
 * upload is in flight.
 */

document.addEventListener("DOMContentLoaded", function () {
  var form = document.querySelector("form");
  if (!form) return;

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var btn = document.getElementById("upload-btn");
    var fileInput = document.getElementById("files");
    var count = fileInput ? fileInput.files.length : 0;
    btn.disabled = true;
    var progress = document.getElementById("upload-progress");
    progress.textContent = count > 0
      ? "Uploading " + count + " document" + (count > 1 ? "s" : "") + "\u2026"
      : "Uploading and indexing\u2026";
    progress.style.display = "inline";
    requestAnimationFrame(function () { form.submit(); });
  });
});

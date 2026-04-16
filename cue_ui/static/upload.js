/**
 * upload.js — Survey file upload page logic.
 *
 * Handles format auto-detection from file extension, submit progress
 * indicators, and API import field toggling.
 */

document.addEventListener("DOMContentLoaded", function () {
  // Auto-select format from file extension
  var fileInput = document.getElementById("file");
  if (fileInput) {
    fileInput.addEventListener("change", function () {
      var ext = this.value.split(".").pop().toLowerCase();
      var map = { qsf: "qsf", lss: "lss", xml: "qti", qti: "qti" };
      var fmt = map[ext];
      if (fmt) {
        document.getElementById("format").value = fmt;
      }
    });
  }

  // Show progress on file upload submit
  var fileForm = document.getElementById("file-upload-form");
  if (fileForm) {
    fileForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var btn = document.getElementById("submit-btn");
      btn.disabled = true;
      btn.textContent = "Importing\u2026";
      requestAnimationFrame(function () { fileForm.submit(); });
    });
  }

  // Toggle API import fields based on platform selection
  var apiFmt = document.getElementById("api-format");
  var lsFields = document.getElementById("ls-fields");
  var qsfFields = document.getElementById("qsf-fields");
  if (apiFmt && lsFields && qsfFields) {
    function updateFields() {
      lsFields.style.display = apiFmt.value === "lss" ? "" : "none";
      qsfFields.style.display = apiFmt.value === "qsf" ? "" : "none";
    }
    apiFmt.addEventListener("change", updateFields);
    updateFields();
  }

  // Show progress on API import submit
  var apiForm = document.getElementById("api-import-form");
  if (apiForm) {
    apiForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var btn = document.getElementById("api-import-btn");
      btn.disabled = true;
      btn.textContent = "Importing\u2026";
      requestAnimationFrame(function () { apiForm.submit(); });
    });
  }
});

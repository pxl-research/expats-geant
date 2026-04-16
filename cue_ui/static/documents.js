/**
 * documents.js — Document upload page logic.
 *
 * Uploads files one at a time via fetch so the progress indicator
 * can update between each file ("Processing document 1 of 3…").
 */

document.addEventListener("DOMContentLoaded", function () {
  var form = document.querySelector("form[data-session-id]");
  if (!form) return;

  var sessionId = form.dataset.sessionId;
  var baseUrl = "/session/" + sessionId;

  form.addEventListener("submit", function (e) {
    e.preventDefault();

    var btn = document.getElementById("upload-btn");
    var progress = document.getElementById("upload-progress");
    var fileInput = document.getElementById("files");
    var textArea = document.getElementById("text-snippet");
    var labelInput = document.getElementById("text-label");

    var files = fileInput ? Array.from(fileInput.files) : [];
    var text = textArea ? textArea.value.trim() : "";
    var label = labelInput ? labelInput.value.trim() : "";

    if (files.length === 0 && !text) {
      window.location.href = baseUrl + "/review";
      return;
    }

    btn.disabled = true;
    progress.style.display = "inline";

    var totalSteps = files.length + (text ? 1 : 0);
    var currentStep = 0;
    var errors = [];

    function updateProgress(message) {
      progress.textContent = message;
    }

    function uploadNextFile() {
      if (currentStep < files.length) {
        var file = files[currentStep];
        currentStep++;
        updateProgress("Processing document " + currentStep + " of " + totalSteps + " (" + file.name + ")\u2026");

        var formData = new FormData();
        formData.append("file", file);

        fetch(baseUrl + "/upload-doc", {
          method: "POST",
          body: formData,
          credentials: "same-origin"
        })
          .then(function (resp) {
            if (!resp.ok) {
              return resp.json().then(function (data) {
                errors.push(file.name + ": " + (data.error || "Upload failed"));
              });
            }
          })
          .catch(function () {
            errors.push(file.name + ": Upload failed (network error)");
          })
          .then(uploadNextFile);
      } else if (text) {
        currentStep++;
        updateProgress("Processing text snippet (" + currentStep + " of " + totalSteps + ")\u2026");

        fetch(baseUrl + "/upload-text-snippet", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: text, label: label || null }),
          credentials: "same-origin"
        })
          .then(function (resp) {
            if (!resp.ok) {
              return resp.json().then(function (data) {
                errors.push((label || "pasted text") + ": " + (data.error || "Upload failed"));
              });
            }
          })
          .catch(function () {
            errors.push((label || "pasted text") + ": Upload failed (network error)");
          })
          .then(finish);
      } else {
        finish();
      }
    }

    function finish() {
      if (errors.length > 0) {
        updateProgress("");
        progress.style.display = "none";
        btn.disabled = false;

        var existing = document.getElementById("upload-errors");
        if (existing) existing.remove();

        var errorDiv = document.createElement("div");
        errorDiv.id = "upload-errors";
        errorDiv.className = "alert alert-error";
        errorDiv.innerHTML = "<strong>Some files could not be uploaded:</strong><ul style='margin-top:0.5rem;padding-left:1.25rem;'>" +
          errors.map(function (err) { return "<li>" + err + "</li>"; }).join("") +
          "</ul>";
        form.parentElement.insertBefore(errorDiv, form);
      }

      if (errors.length < totalSteps) {
        window.location.href = baseUrl + "/review";
      }
    }

    uploadNextFile();
  });
});

/* Shape UI – global handlers (CSP-safe). Loaded on every page via base.html. */
(function () {
  "use strict";

  // Generic back-button handler for any element with id="btn-back"
  var back = document.getElementById("btn-back");
  if (back) {
    back.addEventListener("click", function () {
      history.back();
    });
  }
})();

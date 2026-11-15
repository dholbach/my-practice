/**
 * Checklist page: the complete button unlocks once every required (non-paused)
 * item is ticked, and a hint shows the progress.
 *
 * The two hint texts come from data-* attributes on this file's own <script> tag
 * (see checklist.html); "%1" and "%2" in data-progress stand for done and total.
 */

(function () {
    "use strict";

    const tag = document.getElementById("checklist-js");
    if (!tag) return;
    const text = tag.dataset;

    const REQUIRED = '.checklist-checkbox[data-required="true"]';
    const checkboxes = document.querySelectorAll(REQUIRED);
    const button = document.getElementById("complete-btn");
    const hint = document.getElementById("progress-hint");
    const total = checkboxes.length;

    function updateProgress() {
        const checked = document.querySelectorAll(REQUIRED + ":checked").length;
        if (button) button.disabled = !(total === 0 || checked === total);
        if (hint) {
            hint.textContent =
                total === 0
                    ? text.allPaused
                    : text.progress.replace("%1", checked).replace("%2", total);
        }
    }

    checkboxes.forEach(function (checkbox) {
        checkbox.addEventListener("change", function () {
            const row = this.closest(".checklist-row");
            const label = row ? row.querySelector(".checklist-label") : null;
            if (label) label.classList.toggle("checklist-label--done", this.checked);
            updateProgress();
        });
    });

    updateProgress();
})();

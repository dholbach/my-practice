/**
 * Tax year summary: save the allocation note without leaving the page.
 *
 * The save URL, the year and the status messages come from data-* attributes on
 * the .tax-note-widget element (see tax_year_summary.html), so the strings stay
 * inside the template surface the i18n coverage guardrail scans. The note goes out
 * through MPHttp.postForm (post_json.js), which adds the CSRF token; the view reads
 * a form-encoded POST.
 */

(function () {
    "use strict";

    const widget = document.querySelector(".tax-note-widget");
    if (!widget) return;
    const button = document.getElementById("tax-note-save-btn");
    const status = document.getElementById("tax-note-status");
    const textarea = document.getElementById("tax-note-textarea");
    const text = widget.dataset;

    button.addEventListener("click", function () {
        button.disabled = true;
        status.textContent = text.saving;

        MPHttp.postForm(text.saveUrl, { year: text.year, note: textarea.value })
            .then((response) => response.json())
            .then((data) => {
                status.textContent = data.saved ? text.savedPrefix + data.updated_at : text.saveError;
            })
            .catch(() => {
                status.textContent = text.networkError;
            })
            .finally(() => {
                button.disabled = false;
            });
    });
})();

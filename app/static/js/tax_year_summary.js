/**
 * Tax year summary: save the allocation note without leaving the page.
 *
 * The save URL, the year and the status messages come from data-* attributes on
 * the .tax-note-widget element (see tax_year_summary.html), so the strings stay
 * inside the template surface the i18n coverage guardrail scans. The CSRF token
 * comes from <body data-csrf-token>; the view reads a form-encoded POST.
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
        const body = new URLSearchParams();
        body.append("year", text.year);
        body.append("note", textarea.value);
        body.append("csrfmiddlewaretoken", document.body.dataset.csrfToken);

        button.disabled = true;
        status.textContent = text.saving;

        fetch(text.saveUrl, { method: "POST", body: body })
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

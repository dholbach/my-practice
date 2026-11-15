/**
 * Inquiry form: fill the date that belongs to a status when it is chosen, and
 * suggest free client codes while the name is typed.
 *
 * The suggestion URL and label come from data-* attributes on this file's own
 * <script> tag (see inquiry_form.html); code_suggestions.js is loaded before it.
 */

(function () {
    "use strict";

    const tag = document.getElementById("inquiry-form-js");
    if (!tag) return;
    const text = tag.dataset;

    // A status that has a date field of its own stamps today's date when picked
    const STATUS_DATE_FIELD = {
        contacted: "id_contacted_date",
        intro_meeting: "id_intro_date",
        in_intake: "id_decision_date",
        declined: "id_decision_date",
        not_suitable: "id_decision_date",
        unreachable: "id_decision_date",
    };

    const statusEl = document.getElementById("id_status");
    if (statusEl) {
        statusEl.addEventListener("change", function () {
            const dateEl = document.getElementById(STATUS_DATE_FIELD[this.value]);
            if (dateEl && !dateEl.value) dateEl.value = new Date().toISOString().slice(0, 10);
        });
    }

    const nameEl = document.getElementById("id_full_name");
    const strip = document.getElementById("inquiry-code-suggestions");
    if (!nameEl || !strip) return;

    let debounce;
    nameEl.addEventListener("input", function () {
        clearTimeout(debounce);
        const name = this.value.trim();
        if (!name) {
            strip.replaceChildren();
            return;
        }
        debounce = setTimeout(function () {
            MPCodeSuggestions.load(text.suggestUrl, name).then(function (codes) {
                MPCodeSuggestions.render(strip, { label: text.label, codes: codes });
            });
        }, 400);
    });
})();

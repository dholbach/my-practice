/**
 * Inquiry conversion page: suggest free client codes for the inquiry's name,
 * click one to use it, and offer them again when the code field is cleared.
 *
 * The URL, strings and the inquiry name come from data-* attributes on this
 * file's own <script> tag (see inquiry_convert_confirm.html); code_suggestions.js
 * is loaded before it.
 */

(function () {
    "use strict";

    const tag = document.getElementById("inquiry-convert-js");
    const codeEl = document.getElementById("id_client_code");
    const strip = document.getElementById("convert-code-suggestions");
    if (!tag || !codeEl || !strip) return;
    const text = tag.dataset;

    function show(codes) {
        MPCodeSuggestions.render(strip, {
            label: text.label,
            codes: codes,
            pickTitle: text.pickTitle,
            onPick: function (code) {
                codeEl.value = code;
                show([]);
            },
        });
    }

    function suggest() {
        MPCodeSuggestions.load(text.suggestUrl, text.inquiryName).then(show);
    }

    // Pre-load suggestions for the inquiry name on page load
    if (text.inquiryName) suggest();

    // Offer them again once the code field is cleared
    let debounce;
    codeEl.addEventListener("input", function () {
        if (this.value.trim()) {
            strip.replaceChildren();
            return;
        }
        clearTimeout(debounce);
        debounce = setTimeout(suggest, 200);
    });
})();

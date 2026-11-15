/* Client-code suggestions: ask the server which codes are free for a name and
 * draw them as chips in a strip.
 *
 *   MPCodeSuggestions.load(url, name).then(function (codes) {
 *       MPCodeSuggestions.render(strip, { label: "Available codes:", codes: codes });
 *   });
 *
 * render() takes options.onPick (makes the chips clickable) and options.pickTitle
 * (their tooltip). Chips are built with DOM calls and textContent: the codes are
 * derived from a user-entered name. A page that uses this loads it before its own
 * script; the page's strings and URL come from data-* attributes on its tag.
 */
(function (root) {
    "use strict";

    function load(url, name) {
        return fetch(url + "?name=" + encodeURIComponent(name))
            .then(function (response) {
                return response.json();
            })
            .then(function (data) {
                return data.suggestions || [];
            });
    }

    function render(strip, options) {
        strip.replaceChildren();
        if (!options.codes.length) return;
        const label = document.createElement("span");
        label.className = "hint-label";
        label.textContent = options.label;
        strip.appendChild(label);
        options.codes.forEach(function (code) {
            const chip = document.createElement("span");
            chip.className = "code-chip";
            chip.textContent = code;
            if (options.onPick) {
                chip.classList.add("clickable");
                chip.title = options.pickTitle || "";
                chip.addEventListener("click", function () {
                    options.onPick(code);
                });
            }
            strip.appendChild(chip);
        });
    }

    root.MPCodeSuggestions = { load, render };
})(typeof window !== "undefined" ? window : globalThis);

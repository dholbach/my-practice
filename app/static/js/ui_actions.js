/* Small declarative page behaviours, wired by data-* attributes.
 *
 * These used to be inline Alpine expressions (x-on:click="confirm(...) ||
 * $event.preventDefault()", window.print(), navigator.clipboard...). The CSP
 * build of Alpine — needed so script-src can drop 'unsafe-eval' — refuses
 * globals in expressions. A refused confirm() throws before preventDefault(),
 * so a delete or write-off would go through unconfirmed; doing it here, in one
 * listener per event type, keeps that from depending on expression syntax.
 *
 *   <form data-confirm="Really delete?">           confirm before submitting
 *   <a|button data-confirm="Really delete?">       confirm before following / submitting
 *   <button data-print>                             window.print()
 *   <a href="/x/" data-post-link>                   follow the link as a POST (with the
 *                                                   CSRF token from <body data-csrf-token>),
 *                                                   for card-shaped links to POST-only views
 *   <select data-navigate="/reports/?year=">       go to that URL + the chosen value
 *   <select data-submit-on-change>                  submit the enclosing form
 *   <button data-copy="text" data-copied-label="✓ Copied">
 *   <button data-copy-previous data-copied-label="✓ Copied">
 *                                                   copy the attribute, or the previous
 *                                                   sibling's text, and confirm briefly
 */
(function () {
    "use strict";

    const COPIED_MS = 1800;

    function copyText(button) {
        if (button.dataset.copy !== undefined) return button.dataset.copy;
        const source = button.previousElementSibling;
        return source ? source.textContent : "";
    }

    function submitAsPost(url) {
        const form = document.createElement("form");
        form.method = "post";
        form.action = url;
        const token = document.createElement("input");
        token.type = "hidden";
        token.name = "csrfmiddlewaretoken";
        token.value = document.body.dataset.csrfToken;
        form.appendChild(token);
        document.body.appendChild(form);
        form.submit();
    }

    function flashCopied(button) {
        const label = button.textContent;
        button.textContent = button.dataset.copiedLabel || "✓";
        setTimeout(function () {
            button.textContent = label;
        }, COPIED_MS);
    }

    // Capture phase: runs before any other handler can act on the submit.
    document.addEventListener(
        "submit",
        function (event) {
            const form = event.target.closest("form[data-confirm]");
            if (form && !window.confirm(form.dataset.confirm)) {
                event.preventDefault();
                event.stopImmediatePropagation();
            }
        },
        true
    );

    document.addEventListener(
        "click",
        function (event) {
            const guarded = event.target.closest("[data-confirm]:not(form)");
            if (guarded && !window.confirm(guarded.dataset.confirm)) {
                event.preventDefault();
                event.stopImmediatePropagation();
                return;
            }
            const postLink = event.target.closest("a[data-post-link]");
            if (postLink) {
                event.preventDefault();
                submitAsPost(postLink.getAttribute("href"));
                return;
            }
            if (event.target.closest("[data-print]")) {
                window.print();
                return;
            }
            const copy = event.target.closest("[data-copy], [data-copy-previous]");
            if (copy && navigator.clipboard) {
                navigator.clipboard.writeText(copyText(copy)).then(function () {
                    flashCopied(copy);
                });
            }
        },
        true
    );

    document.addEventListener("change", function (event) {
        const select = event.target;
        if (select.matches("[data-navigate]")) {
            window.location.href = select.dataset.navigate + encodeURIComponent(select.value);
        } else if (select.matches("[data-submit-on-change]") && select.form) {
            select.form.submit();
        }
    });
})();

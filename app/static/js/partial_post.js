/* POST a small action and swap the returned HTML into the page.
 *
 * Replaces htmx, which this app used for exactly this and nothing else. The
 * server sees an "X-Partial: 1" header (utils/view_helpers.is_partial_request)
 * and answers with the fragment instead of a redirect.
 *
 *   <button data-post="/url/"                      POST on click (a checkbox: on change)
 *           data-post-vals='{"days": "1"}'          optional form fields, as JSON
 *           data-post-target="#focus-queue-content" element to replace; or
 *           data-post-closest=".todo-item"          the nearest ancestor matching this
 *           data-post-swap="outer">                 "outer" (default) or "inner"
 *
 * The CSRF token comes from <body data-csrf-token>. A data-confirm on the same
 * element is asked first (ui_actions.js listens in the capture phase).
 */
(function () {
    "use strict";

    function targetOf(el) {
        if (el.dataset.postClosest) return el.closest(el.dataset.postClosest);
        if (el.dataset.postTarget) return document.querySelector(el.dataset.postTarget);
        return el;
    }

    function send(el) {
        const target = targetOf(el);
        if (!target || el.classList.contains("is-pending")) return;
        const body = new URLSearchParams(el.dataset.postVals ? JSON.parse(el.dataset.postVals) : {});
        el.classList.add("is-pending");
        fetch(el.dataset.post, {
            method: "POST",
            credentials: "same-origin",
            headers: { "X-CSRFToken": document.body.dataset.csrfToken, "X-Partial": "1" },
            body: body,
        })
            .then(function (response) {
                if (!response.ok) throw new Error(response.status);
                return response.text();
            })
            .then(function (html) {
                if (el.dataset.postSwap === "inner") {
                    target.innerHTML = html;
                } else {
                    target.outerHTML = html;
                }
                el.classList.remove("is-pending");
            })
            .catch(function () {
                // Nothing changed on the server as far as we know: undo the
                // checkbox the browser already toggled, and let a reload show truth.
                if (el.type === "checkbox") el.checked = !el.checked;
                el.classList.remove("is-pending");
            });
    }

    document.addEventListener("click", function (event) {
        const el = event.target.closest("[data-post]");
        if (!el || el.matches("input")) return;
        event.preventDefault();
        send(el);
    });

    document.addEventListener("change", function (event) {
        if (event.target.matches("input[data-post]")) send(event.target);
    });
})();

/* POST a JSON body to a same-site URL with the page's CSRF token.
 *
 *   const response = await MPHttp.postJson(url, { event_ids: [1, 2] });
 *   const data = await response.json();
 *
 * Returns the fetch() promise untouched, so the caller decides what an error
 * status or a network failure means. The token comes from <body data-csrf-token>.
 * Leave the body out for a bodyless POST. Not for form posts: partial_post.js and
 * ui_actions.js send those. base.html loads this at the end of the body, after page
 * scripts, so call it from handlers, not while the page script is loading.
 */
(function (root) {
    "use strict";

    function postJson(url, body) {
        const options = {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "X-CSRFToken": document.body.dataset.csrfToken,
                "Content-Type": "application/json",
            },
        };
        if (body !== undefined) options.body = JSON.stringify(body);
        return fetch(url, options);
    }

    root.MPHttp = { postJson };
})(typeof window !== "undefined" ? window : globalThis);

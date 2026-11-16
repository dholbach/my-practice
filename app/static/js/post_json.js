/* Same-site POSTs with the page's CSRF token: MPHttp.
 *
 *   MPHttp.csrfToken()                      the token, from <body data-csrf-token>
 *   MPHttp.postJson(url, { ids: [1, 2] })   a JSON body
 *   MPHttp.postForm(url, { year: 2025 })    a form-encoded body (what request.POST reads)
 *   MPHttp.postForm(url, formData)          a FormData (file uploads) as it is
 *   MPHttp.postForm(url, fields, { headers: { "X-Partial": "1" } })   extra headers
 *
 * Both post functions return the fetch() promise untouched, so the caller decides
 * what an error status or a network failure means and what to tell the user. The
 * token travels in the X-CSRFToken header, never in the body. Leave the body out
 * for a bodyless POST. This is the only script that reads the token from the page
 * (test_js_csrf_single_source.py keeps it so); a DOM form that has to carry it as
 * a hidden input, as ui_actions.js does, asks csrfToken().
 *
 * base.html loads this at the end of the body, after the page scripts, so call it
 * from handlers, not while a page script is loading.
 */
(function (root) {
    "use strict";

    function csrfToken() {
        return document.body.dataset.csrfToken;
    }

    function postJson(url, body) {
        const options = {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "X-CSRFToken": csrfToken(),
                "Content-Type": "application/json",
            },
        };
        if (body !== undefined) options.body = JSON.stringify(body);
        return fetch(url, options);
    }

    function postForm(url, fields, options) {
        const isFormData = typeof FormData !== "undefined" && fields instanceof FormData;
        return fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: Object.assign({ "X-CSRFToken": csrfToken() }, (options || {}).headers),
            body: isFormData ? fields : new URLSearchParams(fields || {}),
        });
    }

    root.MPHttp = { csrfToken, postJson, postForm };
})(typeof window !== "undefined" ? window : globalThis);

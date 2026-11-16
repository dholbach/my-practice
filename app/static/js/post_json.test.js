/**
 * Tests for post_json.js — MPHttp.csrfToken, postJson and postForm.
 * Run with: node post_json.test.js
 *
 * Loads the real source into a vm context with a stub document and fetch, then
 * inspects the request it made (plain `node <file>`, see dev.py cmd_test_js).
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "post_json.js"), "utf8");

let failures = 0;
function check(name, condition) {
    if (condition) {
        console.log(`  ok   ${name}`);
    } else {
        failures += 1;
        console.log(`  FAIL ${name}`);
    }
}

const calls = [];
const response = { ok: true };
const sandbox = {
    document: { body: { dataset: { csrfToken: "tok123" } } },
    fetch: async (url, options) => {
        calls.push({ url, options });
        return response;
    },
    JSON,
    URLSearchParams,
    FormData,
};
vm.createContext(sandbox);
vm.runInContext(SOURCE, sandbox);

(async () => {
    console.log("post_json.js");

    const result = await sandbox.MPHttp.postJson("/api/x/", { ids: [1, 2] });
    const first = calls[0];
    check("posts to the given URL", first.url === "/api/x/" && first.options.method === "POST");
    check("sends the CSRF token from <body>", first.options.headers["X-CSRFToken"] === "tok123");
    check("declares and encodes JSON", first.options.headers["Content-Type"] === "application/json" && first.options.body === '{"ids":[1,2]}');
    check("sends cookies to the same site", first.options.credentials === "same-origin");
    check("returns the fetch response untouched", result === response);

    await sandbox.MPHttp.postJson("/api/y/");
    check("no body argument sends no body", !("body" in calls[1].options));

    await sandbox.MPHttp.postJson("/api/z/", {});
    check("an empty object is still sent", calls[2].options.body === "{}");

    check("csrfToken reads the token from <body>", sandbox.MPHttp.csrfToken() === "tok123");

    calls.length = 0;
    const formResult = await sandbox.MPHttp.postForm("/api/form/", { year: 2025, note: "a & b" });
    const form = calls[0];
    check("postForm posts to the URL with the token in the header", form.url === "/api/form/" && form.options.method === "POST" && form.options.headers["X-CSRFToken"] === "tok123");
    check("postForm encodes the fields form-style", form.options.body.toString() === "year=2025&note=a+%26+b");
    check("postForm sets no Content-Type of its own (fetch derives it)", !("Content-Type" in form.options.headers));
    check("postForm sends cookies to the same site and returns the response untouched", form.options.credentials === "same-origin" && formResult === response);

    await sandbox.MPHttp.postForm("/api/bare/");
    check("postForm without fields sends an empty form body", calls[1].options.body.toString() === "");

    const upload = new FormData();
    upload.append("file", "x");
    await sandbox.MPHttp.postForm("/api/upload/", upload);
    check("a FormData goes out as it is", calls[2].options.body === upload);
    check("a FormData upload carries the token in the header too", calls[2].options.headers["X-CSRFToken"] === "tok123");

    await sandbox.MPHttp.postForm("/api/partial/", { a: "1" }, { headers: { "X-Partial": "1" } });
    check("extra headers are added next to the token", calls[3].options.headers["X-Partial"] === "1" && calls[3].options.headers["X-CSRFToken"] === "tok123");

    if (failures > 0) {
        console.log(`\n${failures} check(s) failed`);
        process.exit(1);
    }
    console.log("\nAll checks passed");
})();

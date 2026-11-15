/**
 * Tests for post_json.js — MPHttp.postJson.
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

    if (failures > 0) {
        console.log(`\n${failures} check(s) failed`);
        process.exit(1);
    }
    console.log("\nAll checks passed");
})();

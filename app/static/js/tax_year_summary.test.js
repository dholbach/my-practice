/**
 * Tests for tax_year_summary.js — saving the allocation note.
 * Run with: node tax_year_summary.test.js
 *
 * Browser IIFE wired on load: a throwaway DOM stub and fetch, with the real source
 * loaded via `vm` (plain `node <file>`, see dev.py cmd_test_js). Pinned: the
 * form-encoded body the view reads (year, note) with the CSRF token as a header, the status
 * messages for saved / refused / unreachable, and that the button comes back.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "tax_year_summary.js"), "utf8");
const POST_JSON = fs.readFileSync(path.join(__dirname, "post_json.js"), "utf8");

let failures = 0;
function check(name, condition) {
    if (condition) {
        console.log(`  ok   ${name}`);
    } else {
        failures += 1;
        console.log(`  FAIL ${name}`);
    }
}

const DATA = { saveUrl: "/tax/note/", year: "2025", saving: "Saving…", savedPrefix: "Saved: ", saveError: "Error saving.", networkError: "Network error." };

function load(fetchImpl) {
    const click = {};
    const nodes = {
        "tax-note-save-btn": { disabled: false, addEventListener: (type, fn) => (click[type] = fn) },
        "tax-note-status": { textContent: "" },
        "tax-note-textarea": { value: "split 95/5" },
    };
    const widget = { dataset: DATA };
    const calls = [];
    const sandbox = {
        document: {
            body: { dataset: { csrfToken: "tok123" } },
            querySelector: (selector) => (selector === ".tax-note-widget" ? widget : null),
            getElementById: (id) => nodes[id],
        },
        fetch: (url, options) => {
            calls.push({ url, options });
            return fetchImpl();
        },
        URLSearchParams,
    };
    vm.createContext(sandbox);
    vm.runInContext(POST_JSON, sandbox);
    vm.runInContext(SOURCE, sandbox);
    return { nodes, click: click.click, calls };
}

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

(async () => {
    console.log("tax_year_summary.js");

    {
        const { nodes, click, calls } = load(() => Promise.resolve({ json: () => Promise.resolve({ saved: true, updated_at: "15.11.2026 10:00" }) }));
        click();
        check("the button is disabled and the status says saving", nodes["tax-note-save-btn"].disabled && nodes["tax-note-status"].textContent === "Saving…");
        await flush();
        const body = calls[0].options.body;
        check("it posts to the widget's URL", calls[0].url === "/tax/note/" && calls[0].options.method === "POST");
        check("the body is form-encoded with year and note", body.get("year") === "2025" && body.get("note") === "split 95/5");
        check("the CSRF token goes in the header, not the body", calls[0].options.headers["X-CSRFToken"] === "tok123" && !body.has("csrfmiddlewaretoken"));
        check("a saved note shows the prefix and the time", nodes["tax-note-status"].textContent === "Saved: 15.11.2026 10:00");
        check("the button is enabled again", !nodes["tax-note-save-btn"].disabled);
    }
    {
        const { nodes, click } = load(() => Promise.resolve({ json: () => Promise.resolve({ saved: false }) }));
        click();
        await flush();
        check("a refused save shows the error", nodes["tax-note-status"].textContent === "Error saving.");
    }
    {
        const { nodes, click } = load(() => Promise.reject(new Error("offline")));
        click();
        await flush();
        check("a network failure shows the network error and re-enables the button", nodes["tax-note-status"].textContent === "Network error." && !nodes["tax-note-save-btn"].disabled);
    }

    if (failures > 0) {
        console.log(`\n${failures} check(s) failed`);
        process.exit(1);
    }
    console.log("\nAll checks passed");
})();

/**
 * Tests for invoice_detail.js — changing an invoice's status from the dropdown.
 * Run with: node invoice_detail.test.js
 *
 * Browser IIFE wired on load: a throwaway DOM stub and fetch with the real source
 * loaded via `vm` (plain `node <file>`, see dev.py cmd_test_js). Pinned: the
 * form-encoded request, the badge / paid-date / toast updates, that server text
 * only goes in as textContent, and the failure paths.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "invoice_detail.js"), "utf8");

let failures = 0;
function check(name, condition) {
    if (condition) {
        console.log(`  ok   ${name}`);
    } else {
        failures += 1;
        console.log(`  FAIL ${name}`);
    }
}

class FakeNode {
    constructor() {
        this.children = [];
        this.className = "";
        this.textContent = "";
        this.style = {};
        this.value = "";
        this.removed = false;
    }
    appendChild(child) {
        this.children.push(child);
    }
    replaceChildren(...nodes) {
        this.children = nodes;
        this.textContent = "";
    }
    remove() {
        this.removed = true;
    }
}

function load({ response, throws = false }) {
    const select = new FakeNode();
    select._listeners = {};
    select.addEventListener = (type, fn) => (select._listeners[type] = fn);
    select.value = "paid";
    const ids = {
        "invoice-detail-js": { dataset: { updateUrl: "/invoices/5/status/", statusChanged: "Status changed to:", error: "Error changing status" } },
        "status-select": select,
        "status-badge": new FakeNode(),
        "paid-date-value": new FakeNode(),
    };
    const body = new FakeNode();
    body.dataset = { csrfToken: "tok123" };
    const alerts = [];
    const calls = [];
    const timers = [];
    const sandbox = {
        document: { body, getElementById: (id) => ids[id] || null, createElement: () => new FakeNode() },
        fetch: async (url, options) => {
            calls.push({ url, options });
            if (throws) throw new Error("offline");
            return response;
        },
        alert: (message) => alerts.push(message),
        setTimeout: (fn, ms) => timers.push({ fn, ms }),
        console: { error: () => {} },
        encodeURIComponent,
    };
    vm.createContext(sandbox);
    vm.runInContext(SOURCE, sandbox);
    return { select, ids, body, alerts, calls, timers };
}

const ok = (data) => ({ ok: true, json: async () => data });

(async () => {
    console.log("invoice_detail.js");

    {
        const page = load({ response: ok({ status: "paid", display: "Paid <b>", paid_date: "15.11.2026" }) });
        await page.select._listeners.change.call(page.select);
        check("posts form-encoded to the configured URL with the token", page.calls[0].url === "/invoices/5/status/" && page.calls[0].options.body === "status=paid" && page.calls[0].options.headers["X-CSRFToken"] === "tok123" && page.calls[0].options.headers["Content-Type"] === "application/x-www-form-urlencoded");
        check("the badge gets the new class and text", page.ids["status-badge"].className === "status-badge paid" && page.ids["status-badge"].textContent === "Paid <b>");
        check("the dropdown resets", page.select.value === "");
        check("the paid date is shown", page.ids["paid-date-value"].textContent === "15.11.2026");
        const toast = page.body.children[0];
        check("a toast names the new status, as text", toast.className === "alert-box success" && toast.children[0].textContent === "Status changed to: Paid <b>");
        page.timers[0].fn();
        check("the toast goes after 3 s", page.timers[0].ms === 3000 && toast.removed);
    }
    {
        const page = load({ response: ok({ status: "sent", display: "Sent", paid_date: null }) });
        await page.select._listeners.change.call(page.select);
        const dash = page.ids["paid-date-value"].children[0];
        check("no paid date shows a dash", dash.className === "text-muted" && dash.textContent === "-");
    }
    {
        const page = load({ response: ok({}) });
        page.select.value = "";
        await page.select._listeners.change.call(page.select);
        check("the empty option does nothing", page.calls.length === 0);
    }
    {
        const page = load({ response: { ok: false } });
        await page.select._listeners.change.call(page.select);
        check("a refused change leaves the page as it was", page.body.children.length === 0 && page.alerts.length === 0);
    }
    {
        const page = load({ throws: true });
        await page.select._listeners.change.call(page.select);
        check("a network failure alerts", page.alerts[0] === "Error changing status");
    }

    if (failures > 0) {
        console.log(`\n${failures} check(s) failed`);
        process.exit(1);
    }
    console.log("\nAll checks passed");
})();

/**
 * Tests for calendar_approval_queue.js — skip duplicates, skip one event and
 * import a group on the calendar approval queue page.
 * Run with: node calendar_approval_queue.test.js
 *
 * The script is a browser IIFE with no exports, so each test builds a throwaway
 * DOM stub keyed by the exact selectors the script asks for, loads the real
 * source into it via `vm`, then drives the buttons and awaits the handlers.
 * Hand-rolled instead of jsdom for the same reason as bank_review.test.js: the
 * repo runs JS tests as plain `node <file>` (see dev.py cmd_test_js).
 *
 * What is pinned: the request bodies (invoice_id "new" / integer / absent, the
 * integer event ids), that only imported rows leave the page, that the toast
 * puts server-supplied error text in via textContent, and that buttons recover
 * after an error.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "calendar_approval_queue.js"), "utf8");

const I18N = {
    skipDuplicatesUrl: "/calendar/queue/skip-duplicates/",
    importUrl: "/calendar/queue/import/",
    skipping: "Skipping…",
    skipError: "Error while skipping.",
    skipEventError: "Error while skipping the event.",
    networkError: "Network error.",
    importNetworkError: "Network error while importing.",
    selectOne: "Please select at least one appointment.",
    importing: "Importing…",
    error: "Error",
    unknownError: "Unknown error",
    skipped: "skipped",
    eventImported: "event imported",
    eventsImported: "events imported",
};

let failures = 0;
function check(name, condition, detail) {
    if (condition) {
        console.log(`  ok   ${name}`);
    } else {
        failures += 1;
        console.log(`  FAIL ${name}${detail ? ` — ${detail}` : ""}`);
    }
}

class FakeNode {
    constructor(tagName = "div") {
        this.tagName = tagName.toUpperCase();
        this.children = [];
        this.dataset = {};
        this.style = {};
        this.textContent = "";
        this.className = "";
        this.disabled = false;
        this.removed = false;
        this._listeners = {};
    }
    addEventListener(type, fn) {
        (this._listeners[type] = this._listeners[type] || []).push(fn);
    }
    async click() {
        await Promise.all((this._listeners.click || []).map((fn) => fn.call(this)));
    }
    append(...nodes) {
        this.children.push(...nodes);
    }
    appendChild(node) {
        this.children.push(node);
        return node;
    }
    remove() {
        this.removed = true;
    }
    querySelectorAll() {
        return this.rows || [];
    }
}

/**
 * Build the page. `queries` maps an exact selector to a node or a node list.
 * Returns the handles plus the recorded alerts, fetch calls and timers.
 */
function setupPage({ queries = {}, ids = {}, fetchImpl, i18n = I18N } = {}) {
    const alerts = [];
    const fetchCalls = [];
    const timers = [];
    const body = new FakeNode("body");
    body.dataset.csrfToken = "tok123";
    const tag = new FakeNode("script");
    Object.assign(tag.dataset, i18n);
    ids["calendar-approval-queue-js"] = tag;

    const document = {
        body,
        getElementById: (id) => ids[id] || null,
        querySelector: (selector) => {
            const hit = queries[selector];
            return Array.isArray(hit) ? hit[0] || null : hit || null;
        },
        querySelectorAll: (selector) => {
            const hit = queries[selector];
            return Array.isArray(hit) ? hit : hit ? [hit] : [];
        },
        createElement: (tagName) => new FakeNode(tagName),
    };
    const sandbox = {
        document,
        alert: (message) => alerts.push(message),
        fetch: async (url, options) => {
            fetchCalls.push({ url, options });
            return fetchImpl(url, options);
        },
        setTimeout: (fn, ms) => timers.push({ fn, ms }),
        location: { reload: () => (sandbox.reloaded = true) },
        parseInt,
        JSON,
        Array,
    };
    vm.createContext(sandbox);
    vm.runInContext(SOURCE, sandbox);
    return { alerts, fetchCalls, timers, body, sandbox };
}

function jsonResponse(data, ok = true) {
    return { ok, json: async () => data };
}

function checkbox(value, checked = true) {
    const cb = new FakeNode("input");
    cb.value = String(value);
    cb.checked = checked;
    return cb;
}

function groupPage({ invoiceValue = "", response, ids = {}, remaining = 0 }) {
    const button = new FakeNode("button");
    button.dataset = { group: "1", client: "7", month: "2026-03" };
    button.textContent = "📥 Import";
    const row11 = new FakeNode("tr");
    const row12 = new FakeNode("tr");
    const group = new FakeNode("div");
    group.rows = Array.from({ length: remaining }, () => new FakeNode("tr"));
    const select = new FakeNode("select");
    select.value = invoiceValue;
    const queries = {
        ".import-group-btn": [button],
        ".invoice-select-7-2026-03": select,
        ".event-checkbox-group-1:checked": [checkbox(11), checkbox(12)],
        'tr[data-event-id="11"]': row11,
        'tr[data-event-id="12"]': row12,
    };
    ids["group-1"] = group;
    const page = setupPage({ queries, ids, fetchImpl: async () => response });
    return { ...page, button, row11, row12, group };
}

(async () => {
    console.log("calendar_approval_queue.js");

    // --- import: request body -------------------------------------------------
    {
        const page = groupPage({
            invoiceValue: "new",
            response: jsonResponse({ success: true, imported_ids: [11, 12], created: 2, skipped: 0, errors: [] }),
        });
        await page.button.click();
        const sent = JSON.parse(page.fetchCalls[0].options.body);
        check("import posts to the configured URL", page.fetchCalls[0].url === I18N.importUrl);
        check("import sends the CSRF token from <body>", page.fetchCalls[0].options.headers["X-CSRFToken"] === "tok123");
        check("import sends integer event ids", JSON.stringify(sent.event_ids) === "[11,12]");
        check('invoice "new" is sent as the string', sent.invoice_id === "new");
    }
    {
        const page = groupPage({
            invoiceValue: "42",
            response: jsonResponse({ success: true, imported_ids: [11], created: 1, skipped: 0, errors: [] }),
        });
        await page.button.click();
        check("an invoice id is sent as an integer", JSON.parse(page.fetchCalls[0].options.body).invoice_id === 42);
    }
    {
        const page = groupPage({
            invoiceValue: "",
            response: jsonResponse({ success: true, imported_ids: [], created: 0, skipped: 0, errors: [] }),
        });
        await page.button.click();
        check("no invoice selected sends no invoice_id", !("invoice_id" in JSON.parse(page.fetchCalls[0].options.body)));
    }

    // --- import: DOM effects --------------------------------------------------
    {
        const page = groupPage({
            remaining: 1,
            response: jsonResponse({ success: true, imported_ids: [11], created: 1, skipped: 1, errors: ["<b>Boom</b>"] }),
        });
        await page.button.click();
        check("only imported rows are removed", page.row11.removed && !page.row12.removed);
        check("a non-empty group stays", !page.group.removed);
        const toast = page.body.children[0];
        check("toast singular label for one event", toast.children[0].textContent === "✅ 1 event imported");
        const texts = toast.children.map((c) => c.textContent);
        check("toast shows the skipped count", texts.includes("1 skipped"));
        check("server error text goes in as textContent", texts.includes("<b>Boom</b>") && toast.innerHTML === undefined);
        check("toast with errors lingers 10 s", page.timers[0].ms === 10000);
        check("button recovers when some events failed", !page.button.disabled && page.button.textContent === "📥 Import");
    }
    {
        const page = groupPage({
            response: jsonResponse({ success: true, imported_ids: [11, 12], created: 2, skipped: 0, errors: [] }),
        });
        await page.button.click();
        check("plural label", page.body.children[0].children[0].textContent === "✅ 2 events imported");
        check("clean toast lasts 4 s", page.timers[0].ms === 4000);
        check("button stays disabled after a clean import", page.button.disabled);
        check("an emptied group is removed", page.group.removed);
    }

    // --- import: nothing selected, server error, network error ---------------
    {
        const page = groupPage({ response: jsonResponse({}) });
        page.sandbox.document.querySelectorAll = () => [];
        await page.button.click();
        check("nothing selected alerts and sends nothing", page.alerts[0] === I18N.selectOne && page.fetchCalls.length === 0);
    }
    {
        const page = groupPage({ response: jsonResponse({ success: false, error: "No client" }) });
        await page.button.click();
        check("server error alerts with its message", page.alerts[0] === "Error: No client");
        check("button recovers after a server error", !page.button.disabled && page.button.textContent === "📥 Import");
    }
    {
        const page = groupPage({ response: null });
        page.sandbox.fetch = async () => {
            throw new Error("offline");
        };
        await page.button.click();
        check("network error alerts and restores the button", page.alerts[0] === I18N.importNetworkError && !page.button.disabled);
    }

    // --- skip one event --------------------------------------------------------
    {
        const button = new FakeNode("button");
        button.dataset = { eventId: "5", skipUrl: "/calendar/events/5/skip/" };
        const row = new FakeNode("tr");
        const page = setupPage({
            queries: { ".skip-event-btn": [button], 'tr[data-event-id="5"]': row },
            fetchImpl: async () => ({ ok: true }),
        });
        await button.click();
        check("skip posts to the button's own URL", page.fetchCalls[0].url === "/calendar/events/5/skip/");
        check("skipped row fades, then goes", row.style.opacity === "0.35" && !row.removed);
        page.timers[0].fn();
        check("row removed after the fade", row.removed);
    }

    // --- skip all duplicates ---------------------------------------------------
    {
        const button = new FakeNode("button");
        button.textContent = "🚫 Skip all duplicates";
        const page = setupPage({
            ids: { "skip-duplicates-btn": button },
            fetchImpl: async () => jsonResponse({ success: false }),
        });
        await button.click();
        check("skip-duplicates posts to the configured URL", page.fetchCalls[0].url === I18N.skipDuplicatesUrl);
        check("failure alerts and restores the label", page.alerts[0] === I18N.skipError && button.textContent === "🚫 Skip all duplicates" && !button.disabled);
    }
    {
        const button = new FakeNode("button");
        button.textContent = "🚫 Skip all duplicates";
        const page = setupPage({
            ids: { "skip-duplicates-btn": button },
            fetchImpl: async () => jsonResponse({ success: true }),
        });
        await button.click();
        check("success reloads the page", page.sandbox.reloaded === true);
    }

    // --- select all ------------------------------------------------------------
    {
        const selectAll = new FakeNode("input");
        selectAll.className = "form-check select-all-3";
        const boxes = [checkbox(1, false), checkbox(2, false)];
        setupPage({
            queries: { '[class^="select-all-"]': [selectAll], ".event-checkbox-group-3": boxes },
            fetchImpl: async () => jsonResponse({}),
        });
        selectAll.checked = true;
        selectAll._listeners.change[0].call(selectAll);
        check("select-all ticks its group's boxes", boxes.every((b) => b.checked));
    }

    // --- without the script tag it does nothing ---------------------------------
    {
        const page = setupPage({ fetchImpl: async () => jsonResponse({}) });
        check("loads cleanly without a skip-duplicates button", page.fetchCalls.length === 0);
    }

    if (failures > 0) {
        console.log(`\n${failures} check(s) failed`);
        process.exit(1);
    }
    console.log("\nAll checks passed");
})();

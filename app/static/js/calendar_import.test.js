/**
 * Tests for calendar_import.js — event selection and the bulk import on the
 * manual calendar import page.
 * Run with: node calendar_import.test.js
 *
 * The script is a browser IIFE with no exports and starts on DOMContentLoaded.
 * Each test builds a throwaway DOM stub, loads the real source via `vm`, fires
 * DOMContentLoaded and drives the buttons. Hand-rolled instead of jsdom for the
 * same reason as bank_review.test.js (plain `node <file>`, see dev.py cmd_test_js).
 *
 * Pinned: ready events start selected, the selection count and bulk bar follow
 * the checkboxes, skip removes an event from the selection, import sends only
 * events that have a client and a service type (ids as integers), the summary
 * lists errors, and the button recovers whatever happens.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { FakeClassList } = require("./test_dom.js");

const SOURCE = fs.readFileSync(path.join(__dirname, "calendar_import.js"), "utf8");
const POST_JSON = fs.readFileSync(path.join(__dirname, "post_json.js"), "utf8");

const I18N = {
    importUrl: "/calendar/import/events/",
    showDuplicates: "Show duplicates",
    hideDuplicates: "Hide duplicates",
    selected: "selected",
    selectOne: "Please select at least one event.",
    selectClientAndService: "Please select a client and service type for all events.",
    importing: "Importing…",
    success: "Success!",
    eventsImported: "events imported",
    skipped: "skipped",
    errors: "errors",
    error: "Error",
    importError: "Error during import",
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
    constructor() {
        this.dataset = {};
        this.style = {};
        this.classList = new FakeClassList();
        this.textContent = "";
        this.checked = false;
        this.disabled = false;
        this.value = "";
        this._listeners = {};
    }
    addEventListener(type, fn) {
        (this._listeners[type] = this._listeners[type] || []).push(fn);
    }
    async fire(type) {
        await Promise.all((this._listeners[type] || []).map((fn) => fn.call(this)));
    }
}

/** An event row with its checkbox, client and service selects. */
function makeRow(id, { ready = true, client = "3", service = "9" } = {}) {
    const row = new FakeNode();
    row.dataset.eventId = String(id);
    row.dataset.isReady = ready ? "true" : "false";
    row.checkbox = new FakeNode();
    row.checkbox.closest = () => row;
    row.clientSelect = Object.assign(new FakeNode(), { value: client });
    row.serviceSelect = Object.assign(new FakeNode(), { value: service });
    row.querySelector = (selector) =>
        ({
            ".event-checkbox": row.checkbox,
            ".client-select": row.clientSelect,
            ".service-select": row.serviceSelect,
        })[selector] || null;
    row.skipButton = Object.assign(new FakeNode(), { dataset: { eventId: String(id) } });
    return row;
}

async function setupPage({ rows, fetchImpl }) {
    const alerts = [];
    const fetchCalls = [];
    const ids = {};
    ids["calendar-import-js"] = Object.assign(new FakeNode(), { dataset: { ...I18N } });
    for (const row of rows) ids[`event-${row.dataset.eventId}`] = row;
    for (const id of ["bulkActions", "selectedCount", "selectAll", "toggleDuplicates", "toggleDuplicatesTop", "js-import-top", "js-clear-selection"]) {
        ids[id] = new FakeNode();
    }
    const duplicateRow = new FakeNode();
    const body = new FakeNode();
    body.dataset.csrfToken = "tok123";

    const checkboxes = rows.map((r) => r.checkbox);
    const document = {
        body,
        getElementById: (id) => ids[id] || null,
        querySelectorAll: (selector) => {
            switch (selector) {
                case '.event-row[data-is-ready="true"]':
                    return rows.filter((r) => r.dataset.isReady === "true");
                case ".event-checkbox:checked":
                    return checkboxes.filter((c) => c.checked);
                case ".event-checkbox:not(:checked)":
                    return checkboxes.filter((c) => !c.checked);
                case ".event-checkbox:not([disabled])":
                    return checkboxes.filter((c) => !c.disabled);
                case ".event-checkbox":
                    return checkboxes;
                case ".event-duplicate":
                    return [duplicateRow];
                case "button[data-event-id]":
                    return rows.map((r) => r.skipButton);
                default:
                    throw new Error(`unhandled selector: ${selector}`);
            }
        },
        addEventListener: (type, fn) => {
            document._ready = fn;
        },
    };
    const sandbox = {
        document,
        alert: (message) => alerts.push(message),
        fetch: async (url, options) => {
            fetchCalls.push({ url, options });
            return fetchImpl(url, options);
        },
        window: { location: { reload: () => (sandbox.reloaded = true) } },
        parseInt,
        JSON,
        Array,
        Set,
    };
    vm.createContext(sandbox);
    // The page script calls the shared helper, so load it into the same page first.
    vm.runInContext(POST_JSON, sandbox);
    sandbox.MPHttp = sandbox.MPHttp || (sandbox.window && sandbox.window.MPHttp);
    vm.runInContext(SOURCE, sandbox);
    document._ready();
    return { alerts, fetchCalls, ids, rows, duplicateRow, sandbox };
}

const json = (data) => ({ json: async () => data });

(async () => {
    console.log("calendar_import.js");

    // --- initial state ---------------------------------------------------------
    {
        const rows = [makeRow(1), makeRow(2, { ready: false })];
        const page = await setupPage({ rows, fetchImpl: async () => json({}) });
        check("ready events start selected", rows[0].checkbox.checked && !rows[1].checkbox.checked);
        check("selected row is highlighted", rows[0].classList.contains("selected") && !rows[1].classList.contains("selected"));
        check("bulk bar is shown with the count", page.ids.bulkActions.classList.contains("visible") && page.ids.selectedCount.textContent === "1 selected");
    }
    {
        const rows = [makeRow(1, { ready: false })];
        const page = await setupPage({ rows, fetchImpl: async () => json({}) });
        check("nothing ready hides the bulk bar", !page.ids.bulkActions.classList.contains("visible"));
    }

    // --- selection -------------------------------------------------------------
    {
        const rows = [makeRow(1), makeRow(2)];
        const page = await setupPage({ rows, fetchImpl: async () => json({}) });
        rows[1].checkbox.checked = true;
        await rows[1].checkbox.fire("change");
        check("ticking a row updates the count", page.ids.selectedCount.textContent === "2 selected");
        page.ids.selectAll.checked = false;
        await page.ids.selectAll.fire("change");
        check("select-all off clears every row", rows.every((r) => !r.checkbox.checked) && !page.ids.bulkActions.classList.contains("visible"));
        page.ids.selectAll.checked = true;
        await page.ids.selectAll.fire("change");
        check("select-all on ticks every enabled row", rows.every((r) => r.checkbox.checked));
        await page.ids["js-clear-selection"].fire("click");
        check("clear selection unticks rows and select-all", rows.every((r) => !r.checkbox.checked) && !page.ids.selectAll.checked);
    }

    // --- skip ------------------------------------------------------------------
    {
        const rows = [makeRow(1), makeRow(2)];
        const page = await setupPage({ rows, fetchImpl: async () => json({}) });
        await rows[0].skipButton.fire("click");
        check("skipped row is marked, unticked and disabled", rows[0].classList.contains("skipped") && !rows[0].checkbox.checked && rows[0].checkbox.disabled);
        check("skipped row leaves the selection", page.ids.selectedCount.textContent === "1 selected");
    }

    // --- duplicates toggle -----------------------------------------------------
    {
        const page = await setupPage({ rows: [makeRow(1)], fetchImpl: async () => json({}) });
        await page.ids.toggleDuplicatesTop.fire("click");
        check("duplicates are hidden", page.duplicateRow.style.display === "none");
        check("both toggle buttons say show", page.ids.toggleDuplicates.textContent === "🔄 Show duplicates" && page.ids.toggleDuplicatesTop.textContent === "🔄 Show duplicates");
        await page.ids.toggleDuplicates.fire("click");
        check("second click shows them again", page.duplicateRow.style.display === "" && page.ids.toggleDuplicates.textContent === "🚫 Hide duplicates");
    }

    // --- import ----------------------------------------------------------------
    {
        const rows = [makeRow(1), makeRow(2, { client: "" }), makeRow(3, { service: "" })];
        rows.forEach((r) => (r.checkbox.checked = true));
        const page = await setupPage({
            rows,
            fetchImpl: async () => json({ success: true, created: 1, skipped: 2, errors: ["Bad event", "Worse event"] }),
        });
        rows.forEach((r) => (r.checkbox.checked = true));
        await rows[0].checkbox.fire("change");
        page.ids["js-import-top"].textContent = "✅ Import selected";
        await page.ids["js-import-top"].fire("click");
        const sent = JSON.parse(page.fetchCalls[0].options.body);
        check("import posts to the configured URL with the CSRF token", page.fetchCalls[0].url === I18N.importUrl && page.fetchCalls[0].options.headers["X-CSRFToken"] === "tok123");
        check("only rows with client and service are sent", sent.events.length === 1 && sent.events[0].id === "1");
        check("ids are integers and the action is import", sent.events[0].client_id === 3 && sent.events[0].service_type_id === 9 && sent.events[0].action === "import");
        const summary = page.alerts[0];
        check("summary has counts", summary.includes("1 events imported") && summary.includes("2 skipped"));
        check("summary numbers the errors", summary.includes("2 errors") && summary.includes("1. Bad event") && summary.includes("2. Worse event"));
        check("created events reload the page", page.sandbox.reloaded === true);
        const button = page.ids["js-import-top"];
        check("button is restored afterwards", !button.disabled && button.textContent === "✅ Import selected");
    }
    {
        const rows = [makeRow(1)];
        const page = await setupPage({ rows, fetchImpl: async () => json({ success: true, created: 0, skipped: 1, errors: [] }) });
        await page.ids["js-import-top"].fire("click");
        check("nothing created: no reload", page.sandbox.reloaded !== true);
    }
    {
        const rows = [makeRow(1, { client: "" })];
        const page = await setupPage({ rows, fetchImpl: async () => json({}) });
        await page.ids["js-import-top"].fire("click");
        check("missing client alerts and sends nothing", page.alerts[0] === I18N.selectClientAndService && page.fetchCalls.length === 0);
        check("button is usable again", !page.ids["js-import-top"].disabled);
    }
    {
        const rows = [makeRow(1, { ready: false })];
        const page = await setupPage({ rows, fetchImpl: async () => json({}) });
        await page.ids["js-import-top"].fire("click");
        check("empty selection alerts", page.alerts[0] === I18N.selectOne && page.fetchCalls.length === 0);
    }
    {
        const rows = [makeRow(1)];
        const page = await setupPage({ rows, fetchImpl: async () => json({ success: false, error: "No access" }) });
        await page.ids["js-import-top"].fire("click");
        check("server error is shown", page.alerts[0] === "❌ Error: No access");
    }
    {
        const rows = [makeRow(1)];
        const page = await setupPage({
            rows,
            fetchImpl: async () => {
                throw new Error("offline");
            },
        });
        await page.ids["js-import-top"].fire("click");
        check("network error is shown and the button recovers", page.alerts[0] === "❌ Error during import: offline" && !page.ids["js-import-top"].disabled);
    }

    if (failures > 0) {
        console.log(`\n${failures} check(s) failed`);
        process.exit(1);
    }
    console.log("\nAll checks passed");
})();

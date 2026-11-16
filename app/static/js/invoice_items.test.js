/**
 * Tests for invoice_items.js — the invoice create/edit line items.
 * Run with: node invoice_items.test.js
 *
 * DOM stub plus the real source via `vm`. Pinned: duration and rate per service
 * type, the draft invoice date following the latest session, the edit page's
 * deleted-row marking, and what "add item" does to the clone and the counter.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "invoice_items.js"), "utf8");

let failures = 0;
function check(name, condition) {
    if (condition) {
        console.log(`  ok   ${name}`);
    } else {
        failures += 1;
        console.log(`  FAIL ${name}`);
    }
}

const RATES = { 1: { code: "XX-1", rate_60: 100, rate_90: 150 } };

function classList() {
    const names = new Set();
    return { add: (n) => names.add(n), remove: (n) => names.delete(n), has: (n) => names.has(n), toggle(n, on) { on ? names.add(n) : names.delete(n); } };
}

function field(name, extra = {}) {
    return Object.assign({ name, value: "", type: "text", listeners: {}, classList: classList(), addEventListener(t, f) { this.listeners[t] = f; }, matches: () => false }, extra);
}

function select(options, index) {
    return field("items-0-service_type", { options, selectedIndex: index, value: "", matches: (sel) => sel === "[data-item-service]", closest: () => null, dispatchEvent() {} });
}

function load({ mode = "new", clientId = "1", status = "draft", invoiceDate = "" } = {}) {
    const clientSelect = field("client", { value: clientId, dispatchEvent(e) { (this.listeners[e.type] || (() => {}))(); } });
    const invoiceNumber = field("invoice_number");
    const invoiceDateField = field("invoice_date", { value: invoiceDate });
    const statusField = field("status", { value: status });
    const addButton = field("add", { dataset: { mode, itemLabel: "Item", nextNumberUrl: "/next/" } });
    const row = { rate: field("rate"), duration: field("items-0-duration"), classList: classList() };
    row.querySelector = (sel) => (sel === "[data-item-rate]" ? row.rate : sel === 'input[name*="duration"]' ? row.duration : null);
    const service = select([{ text: "60-Min session" }, { text: "90-Min session" }, { text: "Cancellation" }, { text: "Other" }], 0);
    service.closest = () => row;
    const sessionDates = [field("items-0-session_date", { value: "2026-03-01", matches: (sel) => sel.includes("session_date") }), field("items-1-session_date", { value: "2026-03-09", matches: (sel) => sel.includes("session_date") })];
    const docListeners = {};
    const document = {
        addEventListener: (t, f) => (docListeners[t] = f),
        getElementById: (id) => ({ "add-item": addButton, id_client: clientSelect, id_invoice_number: invoiceNumber, "client-rates-data": { textContent: JSON.stringify(RATES) } })[id] || null,
        querySelector: (sel) => (sel === 'input[name="invoice_date"]' ? invoiceDateField : sel === 'select[name="status"]' ? statusField : null),
        querySelectorAll: (sel) => (sel === 'input[name*="session_date"]' ? sessionDates : []),
    };
    vm.runInNewContext(SOURCE, { document, fetch: () => Promise.resolve({ ok: false }), console, Event: class { constructor(type) { this.type = type; } }, Date, Array, RegExp, parseInt, JSON });
    return { change: (target) => docListeners.change({ target }), service, row, invoiceDateField, sessionDates, statusField, clientSelect, addButton };
}

console.log("invoice_items.js");

(function () {
    for (const [index, duration, rate, name] of [[0, "60", 100, "60 minutes"], [1, "90", 150, "90 minutes"], [2, "0", 100, "cancellation"], [3, "60", 100, "other services"]]) {
        const page = load();
        page.service.selectedIndex = index;
        page.change(page.service);
        check(`${name}: duration ${duration}, rate ${rate}`, page.row.duration.value === duration && page.row.rate.value === rate);
    }
})();

(function () {
    const page = load();
    page.service.selectedIndex = 1;
    page.clientSelect.value = "";
    page.change(page.service);
    check("without a client the duration is set but the rate is left alone", page.row.duration.value === "90" && page.row.rate.value === "");
})();

(function () {
    const page = load({ invoiceDate: "2026-02-01" });
    page.change(page.sessionDates[1]);
    check("a draft's invoice date follows the latest session date", page.invoiceDateField.value === "2026-03-09");
    const issued = load({ status: "sent", invoiceDate: "2026-02-01" });
    issued.change(issued.sessionDates[1]);
    check("an issued invoice keeps its date", issued.invoiceDateField.value === "2026-02-01");
    check("an empty invoice date defaults to today", load().invoiceDateField.value === new Date().toISOString().split("T")[0]);
})();

(function () {
    const page = load({ mode: "edit" });
    const item = { classList: classList() };
    const box = field("items-0-DELETE", { type: "checkbox", checked: true, closest: () => item, matches: () => false });
    page.change(box);
    check("edit: ticking delete marks the row", item.classList.has("deleted"));
    box.checked = false;
    page.change(box);
    check("edit: unticking clears the mark", !item.classList.has("deleted"));
})();

(function () {
    // add-item: a template row with TOTAL_FORMS 2, cloned into a fresh row
    const fields = [field("items-0-duration"), field("items-0-note", { value: "x" }), field("items-0-DELETE", { type: "checkbox", checked: true })];
    const strong = { textContent: "" };
    const clone = { html: "", classList: classList(), attrs: {}, removedLabel: false };
    Object.defineProperty(clone, "innerHTML", { get() { return this.html; }, set(v) { this.html = v; } });
    clone.html = 'name="items-1-note"';
    clone.setAttribute = (k, v) => (clone.attrs[k] = v);
    clone.querySelectorAll = () => fields;
    clone.querySelector = (sel) => (sel === "strong" ? strong : sel === ".delete-label" ? { remove: () => (clone.removedLabel = true) } : null);
    const template = { cloneNode: () => clone };
    const totalForms = { value: "2" };
    const container = { appended: null, querySelector: () => template, appendChild(n) { this.appended = n; } };
    const page = load({ mode: "edit" });
    // reload with a document that knows the container
    const sourceDocument = {
        addEventListener() {},
        getElementById: (id) => ({ "add-item": page.addButton, id_client: page.clientSelect, "client-rates-data": { textContent: "{}" }, "items-container": container })[id] || null,
        querySelector: (sel) => (sel === "#id_items-TOTAL_FORMS" ? totalForms : null),
        querySelectorAll: () => [],
    };
    vm.runInNewContext(SOURCE, { document: sourceDocument, console, Event: class {}, Date, Array, RegExp, parseInt, JSON });
    page.addButton.listeners.click();
    check("add item renumbers the clone's fields", clone.html === 'name="items-2-note"' && clone.attrs["data-form-index"] === 2);
    check("add item clears values and resets the duration to 60", fields[1].value === "" && fields[0].value === "60" && fields[2].checked === false);
    check("add item labels it with the next number", strong.textContent === "Item 3");
    check("edit: the clone has no delete label and is appended", clone.removedLabel && container.appended === clone);
    check("add item bumps TOTAL_FORMS", totalForms.value === 3);
})();

process.exit(failures ? 1 : 0);

/**
 * Tests for analytics_page.js — period filter, tabs and dormant-client toggle.
 * Run with: node analytics_page.test.js
 *
 * A throwaway DOM stub plus the real source loaded via `vm`. Pinned: the custom
 * date range only shows for "custom", the tab comes from ?tab= (default revenue)
 * and a click writes it back to the URL and the filter form, dormant rows follow
 * the checkbox.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "analytics_page.js"), "utf8");

let failures = 0;
function check(name, condition) {
    if (condition) {
        console.log(`  ok   ${name}`);
    } else {
        failures += 1;
        console.log(`  FAIL ${name}`);
    }
}

function classList() {
    const names = new Set();
    return { add: (n) => names.add(n), remove: (n) => names.delete(n), has: (n) => names.has(n) };
}

function load({ search = "" } = {}) {
    const tabs = {};
    const buttons = {};
    for (const name of ["revenue", "clients", "capacity", "expenses"]) {
        tabs[name] = { classList: classList() };
        buttons[name] = { dataset: { tab: name }, classList: classList(), listeners: {}, addEventListener(t, f) { this.listeners[t] = f; } };
    }
    const period = { value: "all", listeners: {}, addEventListener(t, f) { this.listeners[t] = f; } };
    const customDates = { style: {} };
    const dormant = { checked: false, listeners: {}, addEventListener(t, f) { this.listeners[t] = f; } };
    const rows = [{ dataset: { clientStatus: "dormant" }, style: {} }, { dataset: { clientStatus: "active" }, style: {} }];
    const tabInput = { value: "revenue" };
    const pushed = [];
    const ready = [];
    const document = {
        addEventListener: (type, fn) => ready.push(fn),
        getElementById: (id) => {
            if (id === "period") return period;
            if (id === "customDates") return customDates;
            if (id === "toggle-dormant") return dormant;
            const m = id.match(/^(\w+)-tab$/);
            return m ? tabs[m[1]] || null : null;
        },
        querySelector: (sel) => {
            if (sel === 'input[name="tab"]') return tabInput;
            const m = sel.match(/data-tab="(\w+)"/);
            return m ? buttons[m[1]] || null : null;
        },
        querySelectorAll: (sel) => {
            if (sel === ".tab-content") return Object.values(tabs);
            if (sel === ".tab-button") return Object.values(buttons);
            if (sel === ".tab-button[data-tab]") return Object.values(buttons);
            if (sel === "table.client-table tbody tr") return rows;
            return [];
        },
    };
    const window = {
        location: { href: "https://x.test/analytics/" + search, search },
        history: { pushState: (s, t, url) => pushed.push(String(url)) },
    };
    vm.runInNewContext(SOURCE, { document, window, URL, URLSearchParams, Array });
    ready.forEach((fn) => fn());
    return { tabs, buttons, period, customDates, dormant, rows, tabInput, pushed };
}

console.log("analytics_page.js");

(function () {
    const page = load();
    check("revenue tab is active by default", page.tabs.revenue.classList.has("active") && page.buttons.revenue.classList.has("active"));
    check("custom dates hidden for a preset period", page.customDates.style.display === "none");
    page.period.value = "custom";
    page.period.listeners.change();
    check("custom dates shown for 'custom'", page.customDates.style.display === "flex");
})();

(function () {
    const page = load({ search: "?tab=capacity" });
    check("?tab= picks the tab", page.tabs.capacity.classList.has("active") && !page.tabs.revenue.classList.has("active"));
})();

(function () {
    const page = load();
    page.buttons.expenses.listeners.click();
    check("clicking a tab shows it and hides the others", page.tabs.expenses.classList.has("active") && !page.tabs.revenue.classList.has("active") && page.buttons.expenses.classList.has("active"));
    check("clicking a tab updates the URL and the form's tab input", page.pushed[0].endsWith("?tab=expenses") && page.tabInput.value === "expenses");
})();

(function () {
    const page = load();
    check("dormant rows hidden while unchecked", page.rows[0].style.display === "none" && page.rows[1].style.display === undefined);
    page.dormant.checked = true;
    page.dormant.listeners.change();
    check("dormant rows shown when checked", page.rows[0].style.display === "");
})();

process.exit(failures ? 1 : 0);

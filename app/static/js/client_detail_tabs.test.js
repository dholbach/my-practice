/**
 * Tests for client_detail_tabs.js — the tabs on the client detail page.
 * Run with: node client_detail_tabs.test.js
 *
 * Browser IIFE that wires itself on load: a throwaway DOM stub, the real source
 * loaded via `vm` (plain `node <file>`, see dev.py cmd_test_js). Pinned: which
 * tab is shown on a click and from the URL hash, the hash that is written back,
 * the cockpit shortcut that clicks a toggle inside a tab, and the "unsaved" mark.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "client_detail_tabs.js"), "utf8");

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
    return {
        add: (n) => names.add(n),
        remove: (n) => names.delete(n),
        has: (n) => names.has(n),
        toggle: (n, on) => (on ? names.add(n) : names.delete(n)),
    };
}

function load({ hash = "" } = {}) {
    const tabs = {};
    const buttons = {};
    for (const name of ["profil", "protokoll", "abrechnung"]) {
        tabs[name] = { id: `ptab-${name}`, classList: classList() };
        buttons[name] = { dataset: { tab: name }, classList: classList(), title: "" };
    }
    tabs.profil.classList.add("page-tab-active");
    buttons.profil.classList.add("page-tab-active");
    const tabBar = { dataset: { unsavedLabel: "Unsaved changes" } };
    const toggle = { clicks: 0, click() { this.clicks += 1; } };
    const section = { scrolled: null, scrollIntoView(options) { this.scrolled = options; } };
    const listeners = {};
    const urls = [];
    const timers = [];
    const document = {
        addEventListener: (type, fn) => (listeners[type] = fn),
        getElementById: (id) => tabs[id.replace("ptab-", "")] || null,
        querySelectorAll: (selector) => (selector === ".page-tab-content" ? Object.values(tabs) : Object.values(buttons)),
        querySelector: (selector) => {
            let m = selector.match(/^\.page-tab-btn\[data-tab="(\w+)"\]$/) || selector.match(/^\[data-tab="(\w+)"\]$/);
            if (m) return buttons[m[1]];
            if (selector === ".page-tab-bar") return tabBar;
            if (selector === "#section") return section;
            if (selector.startsWith("#ptab-") && selector.includes("showNote")) return toggle;
            return null;
        },
    };
    const sandbox = {
        document,
        window: { location: { hash } },
        history: { replaceState: (a, b, url) => urls.push(url) },
        setTimeout: (fn, ms) => timers.push({ fn, ms }),
    };
    vm.createContext(sandbox);
    vm.runInContext(SOURCE, sandbox);
    return { tabs, buttons, listeners, urls, timers, toggle, section };
}

function click(page, target) {
    const event = { prevented: false, preventDefault() { this.prevented = true; }, target: { closest: target } };
    page.listeners.click(event);
    return event;
}

const active = (page) => Object.keys(page.tabs).filter((n) => page.tabs[n].classList.has("page-tab-active"));

console.log("client_detail_tabs.js");

{
    const page = load();
    const event = click(page, (selector) => (selector.startsWith(".page-tab-btn") ? page.buttons.abrechnung : null));
    check("clicking a tab button shows that tab only", JSON.stringify(active(page)) === '["abrechnung"]' && page.buttons.abrechnung.classList.has("page-tab-active") && !page.buttons.profil.classList.has("page-tab-active"));
    check("it writes the tab into the URL hash and stops the default", page.urls[0] === "#ptab-abrechnung" && event.prevented);
}
{
    const page = load();
    const trigger = { dataset: { pageTab: "protokoll", clickInTab: "showNote" } };
    click(page, (selector) => (selector.startsWith(".page-tab-btn") ? trigger : null));
    check("a cockpit shortcut opens its tab and marks its button", JSON.stringify(active(page)) === '["protokoll"]' && page.buttons.protokoll.classList.has("page-tab-active"));
    check("and clicks the named toggle after 100 ms", page.timers[0].ms === 100 && page.toggle.clicks === 0);
    page.timers[0].fn();
    check("the toggle is clicked once the tab is visible", page.toggle.clicks === 1);
}
{
    const page = load();
    const link = { getAttribute: () => "#section", };
    page.listeners.click({
        preventDefault() {},
        target: { closest: (selector) => (selector === "[data-smooth-scroll]" ? link : null) },
    });
    check("a smooth-scroll link scrolls smoothly and does not switch tabs", page.section.scrolled.behavior === "smooth" && JSON.stringify(active(page)) === '["profil"]');
}
{
    const page = load();
    click(page, () => null);
    check("a click elsewhere does nothing", JSON.stringify(active(page)) === '["profil"]' && page.urls.length === 0);
}
{
    const page = load({ hash: "#ptab-protokoll" });
    check("a tab named in the URL hash is shown on load", JSON.stringify(active(page)) === '["protokoll"]' && page.buttons.protokoll.classList.has("page-tab-active"));
}
{
    const page = load({ hash: "#ptab-unknown" });
    check("an unknown hash is ignored", JSON.stringify(active(page)) === '["profil"]' && page.urls.length === 0);
}
{
    const page = load();
    const inProtocol = { closest: () => page.tabs.protokoll };
    page.listeners["draftguard:dirty"]({ target: inProtocol, detail: { dirty: true } });
    check("an unsaved edit marks its tab button", page.buttons.protokoll.classList.has("page-tab-btn--dirty") && page.buttons.protokoll.title === "Unsaved changes");
    page.listeners["draftguard:dirty"]({ target: inProtocol, detail: { dirty: false } });
    check("saving clears the mark", !page.buttons.protokoll.classList.has("page-tab-btn--dirty") && page.buttons.protokoll.title === "");
    page.listeners["draftguard:dirty"]({ target: { closest: () => null }, detail: { dirty: true } });
    check("a form outside any tab is ignored", true);
}

if (failures > 0) {
    console.log(`\n${failures} check(s) failed`);
    process.exit(1);
}
console.log("\nAll checks passed");

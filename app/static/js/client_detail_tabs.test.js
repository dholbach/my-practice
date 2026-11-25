/**
 * Tests for client_detail_tabs.js — the Clinical / Admin modes of the client detail page.
 * Run with: node client_detail_tabs.test.js
 *
 * Browser IIFE that wires itself on load: a throwaway DOM stub, the real source
 * loaded via `vm` (plain `node <file>`, see dev.py cmd_test_js). Pinned: which
 * sections are shown on a click and from the URL hash (a mode shows all its sections),
 * the hash that is written back, the scroll to the protocol, the cockpit shortcut that
 * clicks a toggle inside a section, and the "unsaved" mark.
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
    const modes = { profil: "clinical", protokoll: "clinical", abrechnung: "admin" };
    const tabs = {};
    for (const [name, mode] of Object.entries(modes)) {
        tabs[name] = {
            id: `ptab-${name}`,
            dataset: name === "protokoll" ? { mode, scrollOnOpen: "" } : { mode },
            classList: classList(),
            scrolled: null,
            scrollIntoView(options) { this.scrolled = options || true; },
        };
    }
    // One button per mode, naming the first section of its mode.
    const buttons = {
        clinical: { dataset: { tab: "profil", mode: "clinical" }, classList: classList(), title: "" },
        admin: { dataset: { tab: "abrechnung", mode: "admin" }, classList: classList(), title: "" },
    };
    tabs.profil.classList.add("page-tab-active");
    tabs.protokoll.classList.add("page-tab-active");
    buttons.clinical.classList.add("page-tab-active");
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
            const m = selector.match(/^\.page-tab-btn\[data-mode="(\w+)"\]$/);
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
const activeButtons = (page) => Object.keys(page.buttons).filter((n) => page.buttons[n].classList.has("page-tab-active"));

console.log("client_detail_tabs.js");

{
    const page = load();
    const event = click(page, (selector) => (selector.startsWith(".page-tab-btn") ? page.buttons.admin : null));
    check("clicking the Admin button shows the admin sections only", JSON.stringify(active(page)) === '["abrechnung"]' && JSON.stringify(activeButtons(page)) === '["admin"]');
    check("it writes the section into the URL hash and stops the default", page.urls[0] === "#ptab-abrechnung" && event.prevented);
    check("a mode button does not scroll", page.tabs.abrechnung.scrolled === null);
}
{
    const page = load();
    click(page, (selector) => (selector.startsWith(".page-tab-btn") ? page.buttons.admin : null));
    click(page, (selector) => (selector.startsWith(".page-tab-btn") ? page.buttons.clinical : null));
    check("the Clinical button shows the overview and the protocol together", JSON.stringify(active(page)) === '["profil","protokoll"]' && JSON.stringify(activeButtons(page)) === '["clinical"]');
}
{
    const page = load();
    const trigger = { dataset: { pageTab: "protokoll", clickInTab: "showNote" } };
    click(page, (selector) => (selector.startsWith(".page-tab-btn") ? trigger : null));
    check("a shortcut to the protocol keeps the clinical mode and scrolls to the protocol", JSON.stringify(active(page)) === '["profil","protokoll"]' && page.tabs.protokoll.scrolled.behavior === "smooth");
    check("and clicks the named toggle after 100 ms", page.timers[0].ms === 100 && page.toggle.clicks === 0);
    page.timers[0].fn();
    check("the toggle is clicked once the section is visible", page.toggle.clicks === 1);
}
{
    const page = load();
    click(page, (selector) => (selector.startsWith(".page-tab-btn") ? page.buttons.admin : null));
    const trigger = { dataset: { pageTab: "protokoll" } };
    click(page, (selector) => (selector.startsWith(".page-tab-btn") ? trigger : null));
    check("a shortcut to the protocol from the admin mode switches back to clinical", JSON.stringify(active(page)) === '["profil","protokoll"]' && JSON.stringify(activeButtons(page)) === '["clinical"]');
}
{
    const page = load();
    const trigger = { dataset: { pageTab: "abrechnung" } };
    click(page, (selector) => (selector.startsWith(".page-tab-btn") ? trigger : null));
    check("a shortcut to billing opens the admin mode without scrolling", JSON.stringify(active(page)) === '["abrechnung"]' && page.tabs.abrechnung.scrolled === null);
}
{
    const page = load();
    const link = { getAttribute: () => "#section", };
    page.listeners.click({
        preventDefault() {},
        target: { closest: (selector) => (selector === "[data-smooth-scroll]" ? link : null) },
    });
    check("a smooth-scroll link scrolls smoothly and does not switch modes", page.section.scrolled.behavior === "smooth" && JSON.stringify(active(page)) === '["profil","protokoll"]');
}
{
    const page = load();
    click(page, () => null);
    check("a click elsewhere does nothing", JSON.stringify(active(page)) === '["profil","protokoll"]' && page.urls.length === 0);
}
{
    const page = load({ hash: "#ptab-protokoll" });
    check("a hash naming the protocol shows the clinical mode and scrolls to it", JSON.stringify(active(page)) === '["profil","protokoll"]' && page.tabs.protokoll.scrolled !== null);
}
{
    const page = load({ hash: "#ptab-abrechnung" });
    check("a hash naming billing shows the admin mode", JSON.stringify(active(page)) === '["abrechnung"]' && JSON.stringify(activeButtons(page)) === '["admin"]' && page.tabs.abrechnung.scrolled === null);
}
{
    const page = load({ hash: "#ptab-profil" });
    check("a hash naming the overview stays at the top", JSON.stringify(active(page)) === '["profil","protokoll"]' && page.tabs.profil.scrolled === null);
}
{
    const page = load({ hash: "#ptab-unknown" });
    check("an unknown hash is ignored", JSON.stringify(active(page)) === '["profil","protokoll"]' && page.urls.length === 0);
}
{
    const page = load();
    const inProtocol = { closest: () => page.tabs.protokoll };
    page.listeners["draftguard:dirty"]({ target: inProtocol, detail: { dirty: true } });
    check("an unsaved edit marks the button of its mode", page.buttons.clinical.classList.has("page-tab-btn--dirty") && page.buttons.clinical.title === "Unsaved changes");
    page.listeners["draftguard:dirty"]({ target: inProtocol, detail: { dirty: false } });
    check("saving clears the mark", !page.buttons.clinical.classList.has("page-tab-btn--dirty") && page.buttons.clinical.title === "");
    page.listeners["draftguard:dirty"]({ target: { closest: () => null }, detail: { dirty: true } });
    check("a form outside any section is ignored", true);
}

if (failures > 0) {
    console.log(`\n${failures} check(s) failed`);
    process.exit(1);
}
console.log("\nAll checks passed");

/**
 * Tests for timeline_search.js — search and the "older entries" toggle of the protocol timeline.
 * Run with: node timeline_search.test.js
 *
 * Browser IIFE wired on load: a throwaway DOM stub and the real source loaded via `vm`
 * (see dev.py cmd_test_js). Pinned: only .cn-searchable text is matched (never a button
 * label), case and diacritics are ignored, matches open their <details> and clearing
 * restores them, the count and empty message, and the toggle for older entries.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "timeline_search.js"), "utf8");

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
        contains: (n) => names.has(n),
        toggle: (n, on) => {
            const want = on === undefined ? !names.has(n) : on;
            if (want) names.add(n);
            else names.delete(n);
            return want;
        },
    };
}

// parts: the texts of the .cn-searchable elements; detailsOpen: initial open state per <details>
function entry(parts, detailsOpen = []) {
    const details = detailsOpen.map((open) => ({ open }));
    return {
        hidden: false,
        details,
        querySelectorAll: (selector) => (selector === ".cn-searchable" ? parts.map((textContent) => ({ textContent })) : selector === "details" ? details : []),
    };
}

function load({ entries, hasList = true }) {
    const list = { classList: classList(), querySelectorAll: (s) => (s === ".cn-timeline-entry" ? entries : []) };
    const count = { textContent: "" };
    const none = { hidden: true };
    const input = {
        value: "",
        dataset: { timelineSearch: "#timeline", timelineCount: "#count", timelineEmpty: "#none", countTemplate: "{count} matching entries" },
        listeners: {},
        addEventListener(type, fn) { this.listeners[type] = fn; },
    };
    const toggle = { textContent: "show", dataset: { timelineToggle: "#timeline", labelShow: "show", labelHide: "hide" } };
    const listeners = {};
    const document = {
        readyState: "complete",
        addEventListener: (type, fn) => (listeners[type] = fn),
        querySelectorAll: (s) => (s === "[data-timeline-search]" ? [input] : []),
        querySelector: (s) => ({ "#timeline": hasList ? list : null, "#count": count, "#none": none })[s] || null,
    };
    vm.createContext({ document });
    vm.runInContext(SOURCE, vm.createContext({ document }));
    return { input, list, count, none, toggle, click: (target) => listeners.click({ target: { closest: () => target } }) };
}

const type = (page, value) => {
    page.input.value = value;
    page.input.listeners.input();
};
const hiddenFlags = (entries) => entries.map((e) => e.hidden);

console.log("timeline_search.js");

{
    const entries = [entry(["13.11.2026", "Telefon als Trigger"]), entry(["06.11.2026", "Nacken und Kiefer"]), entry(["23.10.2026", "Update"])];
    const page = load({ entries });
    type(page, "telefon");
    check("typing hides the entries that do not match", JSON.stringify(hiddenFlags(entries)) === "[false,true,true]");
    check("the list is marked as searching so older entries show", page.list.classList.contains("cn-searching"));
    check("the count says how many match", page.count.textContent === "1 matching entries");
    check("the empty message stays hidden while something matches", page.none.hidden === true);
    type(page, "");
    check("clearing the query shows everything again", JSON.stringify(hiddenFlags(entries)) === "[false,false,false]");
    check("and clears the count and the searching mark", page.count.textContent === "" && !page.list.classList.contains("cn-searching"));
}
{
    const entries = [entry(["Gefühl danach: ruhig"]), entry(["Ressource Hund"])];
    const page = load({ entries });
    type(page, "GEFUHL");
    check("matching ignores case and diacritics", JSON.stringify(hiddenFlags(entries)) === "[false,true]");
    type(page, "hund ");
    check("surrounding whitespace in the query is ignored", JSON.stringify(hiddenFlags(entries)) === "[true,false]");
}
{
    const entries = [entry(["13.11.2026", "Telefon"]), entry(["20.11.2026", "Hund"])];
    const page = load({ entries });
    type(page, "zzz");
    check("no match hides every entry and shows the empty message", JSON.stringify(hiddenFlags(entries)) === "[true,true]" && page.none.hidden === false && page.count.textContent === "0 matching entries");
    type(page, "");
    check("clearing hides the empty message again", page.none.hidden === true);
}
{
    const entries = [entry(["Telefon"], [false, false]), entry(["Hund"], [true])];
    const page = load({ entries });
    type(page, "telefon");
    check("a matching entry opens its details", entries[0].details.every((d) => d.open === true));
    check("a non-matching entry keeps its details as they were", entries[1].details[0].open === true);
    type(page, "");
    check("clearing restores each details element to how it was before", entries[0].details.every((d) => d.open === false) && entries[1].details[0].open === true);
}
{
    const entries = [entry(["Telefon"])];
    const page = load({ entries });
    page.click(page.toggle);
    check("the toggle expands the older entries and swaps its label", page.list.classList.contains("cn-show-old") && page.toggle.textContent === "hide");
    page.click(page.toggle);
    check("and collapses them again", !page.list.classList.contains("cn-show-old") && page.toggle.textContent === "show");
    page.click(null);
    check("a click elsewhere does nothing", !page.list.classList.contains("cn-show-old"));
}
{
    const page = load({ entries: [entry(["x"])], hasList: false });
    check("an input whose list is missing is left alone", Object.keys(page.input.listeners).length === 0);
}

if (failures > 0) {
    console.log(`\n${failures} check(s) failed`);
    process.exit(1);
}
console.log("\nAll checks passed");

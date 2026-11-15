/**
 * Tests for inquiry_form.js — status date stamping and client-code suggestions
 * on the inquiry form. Run with: node inquiry_form.test.js
 *
 * The script is a browser IIFE that wires itself on load: a throwaway DOM stub,
 * a stand-in MPCodeSuggestions that records its calls, and fake timers, with the
 * real source loaded via `vm` (plain `node <file>`, see dev.py cmd_test_js).
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "inquiry_form.js"), "utf8");

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
    constructor(value = "") {
        this.value = value;
        this.dataset = {};
        this._listeners = {};
        this.children = [1];
    }
    addEventListener(type, fn) {
        this._listeners[type] = fn;
    }
    replaceChildren() {
        this.children = [];
    }
}

function load({ withStrip = true } = {}) {
    const ids = {
        "inquiry-form-js": Object.assign(new FakeNode(), { dataset: { suggestUrl: "/suggest/", label: "Available codes:" } }),
        id_status: new FakeNode(),
        id_contacted_date: new FakeNode(),
        id_intro_date: new FakeNode(),
        id_decision_date: new FakeNode("2026-01-02"),
        id_full_name: new FakeNode(),
    };
    if (withStrip) ids["inquiry-code-suggestions"] = new FakeNode();
    const timers = [];
    const loads = [];
    const renders = [];
    const sandbox = {
        document: { getElementById: (id) => ids[id] || null },
        setTimeout: (fn, ms) => timers.push({ fn, ms }) && timers.length,
        clearTimeout: (n) => {
            if (n) timers[n - 1].cancelled = true;
        },
        Date,
        MPCodeSuggestions: {
            load: (url, name) => {
                loads.push({ url, name });
                return Promise.resolve(["AB-1"]);
            },
            render: (strip, options) => renders.push(options),
        },
    };
    vm.createContext(sandbox);
    vm.runInContext(SOURCE, sandbox);
    return { ids, timers, loads, renders };
}

(async () => {
    console.log("inquiry_form.js");
    const today = new Date().toISOString().slice(0, 10);

    {
        const { ids } = load();
        ids.id_status.value = "contacted";
        ids.id_status._listeners.change.call(ids.id_status);
        check("a status stamps its date field with today", ids.id_contacted_date.value === today);
        ids.id_status.value = "declined";
        ids.id_status._listeners.change.call(ids.id_status);
        check("an already-filled date is kept", ids.id_decision_date.value === "2026-01-02");
        ids.id_status.value = "new";
        ids.id_status._listeners.change.call(ids.id_status);
        check("a status without a date field does nothing", ids.id_intro_date.value === "");
    }
    {
        const { ids, timers, loads, renders } = load();
        ids.id_full_name.value = "  Max Mustermann ";
        ids.id_full_name._listeners.input.call(ids.id_full_name);
        check("typing waits 400 ms before asking", timers.length === 1 && timers[0].ms === 400 && loads.length === 0);
        ids.id_full_name.value = "Max Mustermann";
        ids.id_full_name._listeners.input.call(ids.id_full_name);
        check("typing again cancels the earlier wait", timers[0].cancelled === true);
        timers[1].fn();
        await Promise.resolve();
        await Promise.resolve();
        check("it asks for the trimmed name at the configured URL", loads[0].url === "/suggest/" && loads[0].name === "Max Mustermann");
        check("it renders the codes with the label", renders[0].label === "Available codes:" && renders[0].codes[0] === "AB-1");
    }
    {
        const { ids, timers } = load();
        ids["inquiry-code-suggestions"].children = [1, 2];
        ids.id_full_name.value = "   ";
        ids.id_full_name._listeners.input.call(ids.id_full_name);
        check("an empty name clears the strip without asking", ids["inquiry-code-suggestions"].children.length === 0 && timers.length === 0);
    }
    {
        const { ids } = load({ withStrip: false });
        check("without a suggestion strip only the status dates are wired", !ids.id_full_name._listeners.input && !!ids.id_status._listeners.change);
    }

    if (failures > 0) {
        console.log(`\n${failures} check(s) failed`);
        process.exit(1);
    }
    console.log("\nAll checks passed");
})();

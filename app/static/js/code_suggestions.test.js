/**
 * Tests for code_suggestions.js — MPCodeSuggestions.load and .render.
 * Run with: node code_suggestions.test.js
 *
 * Plain `node <file>` with a hand-rolled DOM stub and the real source loaded via
 * `vm` (see dev.py cmd_test_js). The point of render() is that codes, which are
 * derived from a user-entered name, only ever go in as textContent.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "code_suggestions.js"), "utf8");

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
        this.title = "";
        this._listeners = {};
        const names = new Set();
        this.classList = { add: (n) => names.add(n), has: (n) => names.has(n) };
    }
    appendChild(child) {
        this.children.push(child);
    }
    replaceChildren() {
        this.children = [];
    }
    addEventListener(type, fn) {
        this._listeners[type] = fn;
    }
}

const calls = [];
const sandbox = {
    document: { createElement: () => new FakeNode() },
    fetch: async (url) => {
        calls.push(url);
        return { json: async () => ({ suggestions: ["AB-1", "AB-2"] }) };
    },
    encodeURIComponent,
};
vm.createContext(sandbox);
vm.runInContext(SOURCE, sandbox);
const { load, render } = sandbox.MPCodeSuggestions;

(async () => {
    console.log("code_suggestions.js");

    const codes = await load("/clients/suggest-code/", "Max Müller&x");
    check("load asks for the encoded name", calls[0] === "/clients/suggest-code/?name=Max%20M%C3%BCller%26x");
    check("load resolves to the suggestions", JSON.stringify(codes) === '["AB-1","AB-2"]');

    sandbox.fetch = async () => ({ json: async () => ({}) });
    check("load tolerates a missing suggestions key", (await load("/x/", "a")).length === 0);

    const strip = new FakeNode();
    render(strip, { label: "Available codes:", codes: ["AB-1", "<b>x</b>"] });
    check("a label and one chip per code", strip.children.length === 3 && strip.children[0].className === "hint-label");
    check("the label text is set", strip.children[0].textContent === "Available codes:");
    check("codes go in as text", strip.children[2].textContent === "<b>x</b>");
    check("plain chips are not clickable", !strip.children[1].classList.has("clickable") && !strip.children[1]._listeners.click);

    render(strip, { label: "L", codes: [] });
    check("no codes empties the strip", strip.children.length === 0);

    let picked = null;
    render(strip, { label: "L", codes: ["CD-3"], pickTitle: "Click to use", onPick: (code) => (picked = code) });
    const chip = strip.children[1];
    check("clickable chips get the class and the tooltip", chip.classList.has("clickable") && chip.title === "Click to use");
    chip._listeners.click();
    check("clicking a chip hands its code to onPick", picked === "CD-3");

    if (failures > 0) {
        console.log(`\n${failures} check(s) failed`);
        process.exit(1);
    }
    console.log("\nAll checks passed");
})();

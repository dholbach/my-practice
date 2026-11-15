/**
 * Tests for checklist.js — the progress hint and the complete button.
 * Run with: node checklist.test.js
 *
 * Browser IIFE wired on load: a throwaway DOM stub with the real source loaded via
 * `vm` (plain `node <file>`, see dev.py cmd_test_js).
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "checklist.js"), "utf8");
const REQUIRED = '.checklist-checkbox[data-required="true"]';

let failures = 0;
function check(name, condition) {
    if (condition) {
        console.log(`  ok   ${name}`);
    } else {
        failures += 1;
        console.log(`  FAIL ${name}`);
    }
}

function box(checked = false) {
    const label = { toggled: null, classList: { toggle: (name, on) => (label.toggled = [name, on]) } };
    const row = { querySelector: (s) => (s === ".checklist-label" ? label : null) };
    const node = { checked, label, _listeners: {} };
    node.addEventListener = (type, fn) => (node._listeners[type] = fn);
    node.closest = (s) => (s === ".checklist-row" ? row : null);
    node.change = () => node._listeners.change.call(node);
    return node;
}

function load(boxes) {
    const button = { disabled: false };
    const hint = { textContent: "" };
    const ids = {
        "checklist-js": { dataset: { allPaused: "All items paused", progress: "%1 of %2 completed" } },
        "complete-btn": button,
        "progress-hint": hint,
    };
    const document = {
        getElementById: (id) => ids[id] || null,
        querySelectorAll: (selector) => {
            if (selector === REQUIRED) return boxes;
            if (selector === REQUIRED + ":checked") return boxes.filter((b) => b.checked);
            throw new Error(`unhandled: ${selector}`);
        },
    };
    vm.runInContext(SOURCE, vm.createContext({ document }));
    return { button, hint };
}

console.log("checklist.js");

{
    const boxes = [box(), box(), box()];
    const { button, hint } = load(boxes);
    check("starts locked with 0 of 3", button.disabled === true && hint.textContent === "0 of 3 completed");
    boxes[0].checked = true;
    boxes[0].change();
    check("ticking one updates the hint", hint.textContent === "1 of 3 completed" && button.disabled === true);
    check("ticking marks the label done", boxes[0].label.toggled[0] === "checklist-label--done" && boxes[0].label.toggled[1] === true);
    boxes[1].checked = true;
    boxes[1].change();
    boxes[2].checked = true;
    boxes[2].change();
    check("all ticked unlocks the button", button.disabled === false && hint.textContent === "3 of 3 completed");
    boxes[2].checked = false;
    boxes[2].change();
    check("unticking locks it again", button.disabled === true);
}
{
    const { button, hint } = load([]);
    check("with every item paused the button is unlocked and the hint says so", button.disabled === false && hint.textContent === "All items paused");
}

if (failures > 0) {
    console.log(`\n${failures} check(s) failed`);
    process.exit(1);
}
console.log("\nAll checks passed");

/**
 * Tests for time_off_notice_form.js — the select-all checkbox over the recipients.
 * Run with: node time_off_notice_form.test.js
 *
 * The script is a browser IIFE that wires itself on load, so each test builds a
 * throwaway DOM stub and loads the real source via `vm` (plain `node <file>`,
 * see dev.py cmd_test_js).
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "time_off_notice_form.js"), "utf8");

let failures = 0;
function check(name, condition) {
    if (condition) {
        console.log(`  ok   ${name}`);
    } else {
        failures += 1;
        console.log(`  FAIL ${name}`);
    }
}

function checkbox(checked) {
    const node = { checked, _listeners: {} };
    node.addEventListener = (type, fn) => (node._listeners[type] = fn);
    node.change = () => node._listeners.change.call(node);
    return node;
}

function load({ withSelectAll = true, states = [true, true, true] } = {}) {
    const selectAll = withSelectAll ? checkbox(true) : null;
    const boxes = states.map(checkbox);
    const document = {
        getElementById: (id) => (id === "recipients-select-all" ? selectAll : null),
        querySelectorAll: (selector) => {
            if (selector !== ".recipient-checkbox") throw new Error(`unhandled: ${selector}`);
            return boxes;
        },
    };
    const sandbox = { document, Array };
    vm.createContext(sandbox);
    vm.runInContext(SOURCE, sandbox);
    return { selectAll, boxes };
}

console.log("time_off_notice_form.js");

{
    const { selectAll, boxes } = load();
    selectAll.checked = false;
    selectAll.change();
    check("select-all off unticks every recipient", boxes.every((b) => !b.checked));
    selectAll.checked = true;
    selectAll.change();
    check("select-all on ticks every recipient", boxes.every((b) => b.checked));
}
{
    const { selectAll, boxes } = load();
    boxes[1].checked = false;
    boxes[1].change();
    check("unticking a recipient unticks select-all", selectAll.checked === false);
    boxes[1].checked = true;
    boxes[1].change();
    check("ticking the last one ticks select-all again", selectAll.checked === true);
}
{
    const { boxes } = load({ withSelectAll: false });
    boxes[0].checked = false;
    boxes[0].change();
    check("works without a select-all checkbox", true);
}

if (failures > 0) {
    console.log(`\n${failures} check(s) failed`);
    process.exit(1);
}
console.log("\nAll checks passed");

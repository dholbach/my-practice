/**
 * Tests for typing_target.js — MPTyping.isTyping, shared by the command palette
 * and the keyboard shortcuts.
 * Run with: node typing_target.test.js
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "typing_target.js"), "utf8");

let failures = 0;
function check(name, condition) {
    if (condition) {
        console.log(`  ok   ${name}`);
    } else {
        failures += 1;
        console.log(`  FAIL ${name}`);
    }
}

const window_ = {};
vm.runInNewContext(SOURCE, { window: window_ });
const { isTyping } = window_.MPTyping;

function el(tagName, extra = {}) {
    return Object.assign({ tagName, isContentEditable: false, contentEditable: "inherit", parentElement: null }, extra);
}

console.log("typing_target.js");
check("input, textarea and select are typing", ["INPUT", "TEXTAREA", "SELECT"].every((tag) => isTyping(el(tag))));
check("a button or the body is not typing", !isTyping(el("BUTTON")) && !isTyping(el("BODY")));
check("a contenteditable element is typing", isTyping(el("DIV", { isContentEditable: true })) && isTyping(el("DIV", { contentEditable: "true" })));
check("an element inside a contenteditable parent is typing", isTyping(el("SPAN", { parentElement: el("DIV", { isContentEditable: true }) })));
check("no target is not typing", !isTyping(null) && !isTyping({}));
process.exit(failures ? 1 : 0);

/**
 * Tests for ui_actions.js
 * Run with: node ui_actions.test.js
 *
 * ui_actions.js is a browser IIFE wired to document events, so — like
 * form_draft_guard.test.js — each test loads the real source into a vm
 * context with a hand-rolled DOM stub and drives it through events.
 * data-confirm is the one that matters most: if it stops cancelling, a delete
 * or write-off goes through without the question being asked.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "ui_actions.js"), "utf8");

class FakeElement {
    constructor(tagName, attrs = {}, parent = null) {
        this.tagName = tagName.toUpperCase();
        this.attrs = attrs;
        this.dataset = {};
        for (const [name, value] of Object.entries(attrs)) {
            if (name.startsWith("data-")) {
                const key = name.slice(5).replace(/-([a-z])/g, (_m, c) => c.toUpperCase());
                this.dataset[key] = value;
            }
        }
        this.parentElement = parent;
        this.previousElementSibling = null;
        this.textContent = "";
        this.value = "";
        this.form = null;
    }
    matches(selector) {
        return selector.split(",").some((part) => this._matchesOne(part.trim()));
    }
    _matchesOne(selector) {
        const not = selector.match(/:not\(([a-z]+)\)$/);
        if (not) {
            if (this.tagName === not[1].toUpperCase()) return false;
            selector = selector.replace(not[0], "");
        }
        const match = selector.match(/^([a-z]*)((?:\[[a-z-]+\])*)$/);
        if (!match) throw new Error(`unsupported selector ${selector}`);
        if (match[1] && this.tagName !== match[1].toUpperCase()) return false;
        const attrs = match[2].match(/[a-z-]+/g) || [];
        return attrs.every((name) => name in this.attrs);
    }
    closest(selector) {
        for (let el = this; el; el = el.parentElement) {
            if (el.matches(selector)) return el;
        }
        return null;
    }
}

function load({ confirmAnswer = true } = {}) {
    const listeners = {};
    const calls = { confirm: [], print: 0, clipboard: [], href: null, submitted: 0 };
    const timers = [];
    const context = {
        document: {
            addEventListener(type, fn) {
                (listeners[type] = listeners[type] || []).push(fn);
            },
        },
        window: {
            confirm(message) {
                calls.confirm.push(message);
                return confirmAnswer;
            },
            print() {
                calls.print += 1;
            },
            location: {
                set href(value) {
                    calls.href = value;
                },
            },
        },
        navigator: {
            clipboard: {
                writeText(text) {
                    calls.clipboard.push(text);
                    return { then: (fn) => fn() };
                },
            },
        },
        setTimeout: (fn) => timers.push(fn),
        encodeURIComponent,
    };
    vm.runInNewContext(SOURCE, context);
    function fire(type, target) {
        const event = {
            type,
            target,
            defaultPrevented: false,
            stopped: false,
            preventDefault() {
                this.defaultPrevented = true;
            },
            stopImmediatePropagation() {
                this.stopped = true;
            },
        };
        for (const fn of listeners[type] || []) fn(event);
        return event;
    }
    return { fire, calls, timers };
}

let failures = 0;
function test(name, fn) {
    try {
        fn();
        console.log(`✓ ${name}`);
    } catch (err) {
        failures += 1;
        console.log(`✗ ${name}\n  ${err.message}`);
    }
}
function assertEqual(actual, expected, label) {
    if (actual !== expected) throw new Error(`${label}: expected ${expected}, got ${actual}`);
}

test("declined confirm on a form cancels the submit", () => {
    const { fire, calls } = load({ confirmAnswer: false });
    const form = new FakeElement("form", { "data-confirm": "Really delete?" });
    const event = fire("submit", form);
    assertEqual(calls.confirm[0], "Really delete?", "message");
    assertEqual(event.defaultPrevented, true, "prevented");
    assertEqual(event.stopped, true, "other handlers stopped");
});

test("accepted confirm lets the submit through", () => {
    const { fire } = load({ confirmAnswer: true });
    const event = fire("submit", new FakeElement("form", { "data-confirm": "Sure?" }));
    assertEqual(event.defaultPrevented, false, "prevented");
});

test("declined confirm on a link inside it cancels the click", () => {
    const { fire } = load({ confirmAnswer: false });
    const link = new FakeElement("a", { "data-confirm": "Delete invoice?" });
    const icon = new FakeElement("span", {}, link);
    assertEqual(fire("click", icon).defaultPrevented, true, "prevented");
});

test("a form's data-confirm is asked once, on submit — not on clicks inside it", () => {
    const { fire, calls } = load({ confirmAnswer: false });
    const form = new FakeElement("form", { "data-confirm": "Sure?" });
    const button = new FakeElement("button", {}, form);
    fire("click", button);
    assertEqual(calls.confirm.length, 0, "confirm calls on click");
});

test("forms without data-confirm submit untouched", () => {
    const { fire, calls } = load({ confirmAnswer: false });
    const event = fire("submit", new FakeElement("form"));
    assertEqual(event.defaultPrevented, false, "prevented");
    assertEqual(calls.confirm.length, 0, "confirm calls");
});

test("data-print prints", () => {
    const { fire, calls } = load();
    fire("click", new FakeElement("button", { "data-print": "" }));
    assertEqual(calls.print, 1, "print calls");
});

test("data-navigate goes to the prefix plus the encoded value", () => {
    const { fire, calls } = load();
    const select = new FakeElement("select", { "data-navigate": "/reports/revenue/?year=" });
    select.value = "2025";
    fire("change", select);
    assertEqual(calls.href, "/reports/revenue/?year=2025", "href");
});

test("data-submit-on-change submits the enclosing form", () => {
    const { fire, calls } = load();
    const select = new FakeElement("select", { "data-submit-on-change": "" });
    select.form = { submit: () => (calls.submitted += 1) };
    fire("change", select);
    assertEqual(calls.submitted, 1, "submits");
});

test("data-copy copies the attribute and flashes, then restores the label", () => {
    const { fire, calls, timers } = load();
    const button = new FakeElement("button", { "data-copy": "Subject line", "data-copied-label": "✓ Copied" });
    button.textContent = "Copy";
    fire("click", button);
    assertEqual(calls.clipboard[0], "Subject line", "copied text");
    assertEqual(button.textContent, "✓ Copied", "flash");
    timers.forEach((fn) => fn());
    assertEqual(button.textContent, "Copy", "restored");
});

test("data-copy-previous copies the previous sibling's text", () => {
    const { fire, calls } = load();
    const button = new FakeElement("button", { "data-copy-previous": "" });
    button.previousElementSibling = { textContent: "Email body" };
    fire("click", button);
    assertEqual(calls.clipboard[0], "Email body", "copied text");
});

if (failures) {
    console.log(`\n${failures} test(s) failed`);
    process.exit(1);
}
console.log("\nAll ui_actions tests passed");

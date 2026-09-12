/**
 * Tests for command_palette.js (P-047)
 * Run with: node command_palette.test.js
 *
 * Same approach as form_draft_guard.test.js and global-search.test.js: the
 * script is a browser IIFE with no exports, so each test builds a throwaway DOM
 * stub, loads the real source into it via `vm`, and drives it through events.
 * Stubs are hand-rolled rather than jsdom because the repo runs JS tests as
 * plain `node <file>` with no framework or devDependencies (see dev.py
 * cmd_test_js), and a DOM dependency would have to exist in the Docker image.
 *
 * The stub's selector matching covers exactly the selectors command_palette.js
 * uses — class, [attr], [attr="value"], and the one compound form
 * `.cmd-palette__item:not([hidden])`. It is not a general engine; a new selector
 * in the source needs a matching case here.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "command_palette.js"), "utf8");

// ---------------------------------------------------------------------------
// Minimal DOM stub
// ---------------------------------------------------------------------------

class FakeEvent {
    constructor(type, options = {}) {
        this.type = type;
        this.key = options.key || "";
        this.metaKey = Boolean(options.metaKey);
        this.ctrlKey = Boolean(options.ctrlKey);
        this.altKey = Boolean(options.altKey);
        this.target = options.target || null;
        this.defaultPrevented = false;
    }
    preventDefault() {
        this.defaultPrevented = true;
    }
}

class FakeNode {
    constructor(tagName = "div") {
        this.tagName = tagName.toUpperCase();
        this.children = [];
        this.parentNode = null;
        this.dataset = {};
        this.attributes = {};
        this.id = "";
        this.hidden = false;
        this.value = "";
        this.focused = false;
        this.scrolledIntoView = false;
        this._classes = new Set();
        this._listeners = {};
        this._text = "";

        const node = this;
        this.classList = {
            add: (name) => node._classes.add(name),
            remove: (name) => node._classes.delete(name),
            contains: (name) => node._classes.has(name),
        };
    }

    get className() {
        return Array.from(this._classes).join(" ");
    }
    set className(value) {
        this._classes = new Set(String(value).split(/\s+/).filter(Boolean));
    }

    // Own text plus descendants', matching how the source filters on textContent.
    get textContent() {
        return this._text + this.children.map((c) => c.textContent).join("");
    }
    set textContent(value) {
        this._text = String(value);
        this.children = [];
    }

    setAttribute(name, value) {
        this.attributes[name] = String(value);
    }
    getAttribute(name) {
        return Object.prototype.hasOwnProperty.call(this.attributes, name)
            ? this.attributes[name]
            : null;
    }
    removeAttribute(name) {
        delete this.attributes[name];
    }

    addEventListener(type, fn) {
        (this._listeners[type] = this._listeners[type] || []).push(fn);
    }
    dispatch(type, options = {}) {
        const event = new FakeEvent(type, Object.assign({ target: this }, options));
        for (const fn of this._listeners[type] || []) fn.call(this, event);
        return event;
    }

    appendChild(child) {
        child.parentNode = this;
        this.children.push(child);
        return child;
    }

    focus() {
        this.focused = true;
        if (this.ownerDocument) this.ownerDocument.activeElement = this;
    }
    scrollIntoView() {
        this.scrolledIntoView = true;
    }

    _descendants() {
        return this.children.flatMap((c) => [c, ...c._descendants()]);
    }

    _matches(selector) {
        // `.a:not([hidden])`
        const notHidden = selector.match(/^(.+):not\(\[hidden\]\)$/);
        if (notHidden) return this._matches(notHidden[1]) && !this.hidden;

        // `[attr="value"]` / `[attr]`
        const attr = selector.match(/^\[([\w-]+)(?:="([^"]*)")?\]$/);
        if (attr) {
            const [, name, value] = attr;
            const key = name.startsWith("data-")
                ? name.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())
                : null;
            const actual = key !== null ? this.dataset[key] : this.getAttribute(name);
            if (actual === undefined || actual === null) return false;
            return value === undefined || actual === value;
        }

        // `.class`
        if (selector.startsWith(".")) return this._classes.has(selector.slice(1));

        throw new Error(`stub selector not supported: ${selector}`);
    }

    querySelectorAll(selector) {
        return this._descendants().filter((n) => n._matches(selector));
    }
    querySelector(selector) {
        return this.querySelectorAll(selector)[0] || null;
    }
}

/**
 * Builds the subset of includes/command_palette.html the script touches:
 * two groups with the given item labels, plus input, backdrop, empty message
 * and the two platform <kbd> variants.
 */
function buildPalette({ jumpTo, actions }) {
    const document = new FakeNode("document");
    document.readyState = "complete";
    document.activeElement = null;

    const body = new FakeNode("body");
    document.body = body;
    document.appendChild(body);

    const palette = new FakeNode("div");
    palette.id = "command-palette";
    palette.hidden = true;
    body.appendChild(palette);

    const backdrop = new FakeNode("div");
    backdrop.className = "cmd-palette__backdrop";
    backdrop.dataset.cmdkDismiss = "";
    palette.appendChild(backdrop);

    const dialog = palette.appendChild(new FakeNode("div"));

    const input = new FakeNode("input");
    input.id = "cmd-palette-input";
    dialog.appendChild(input);

    const makeGroup = (labels) => {
        const group = new FakeNode("section");
        group.className = "cmd-palette__group";
        dialog.appendChild(group);
        return labels.map(([label, href]) => {
            const item = new FakeNode("a");
            item.className = "cmd-palette__item";
            item.textContent = label;
            item.setAttribute("href", href);
            return group.appendChild(item);
        });
    };
    makeGroup(jumpTo);
    makeGroup(actions);

    const empty = new FakeNode("p");
    empty.id = "cmd-palette-empty";
    empty.hidden = true;
    dialog.appendChild(empty);

    const trigger = new FakeNode("button");
    trigger.id = "cmd-palette-trigger";
    body.appendChild(trigger);

    const kbdMac = new FakeNode("kbd");
    kbdMac.dataset.cmdkKey = "mac";
    kbdMac.hidden = true;
    trigger.appendChild(kbdMac);
    const kbdOther = new FakeNode("kbd");
    kbdOther.dataset.cmdkKey = "other";
    trigger.appendChild(kbdOther);

    // Tag every node so focus() can report back through document.activeElement.
    for (const node of [document, ...document._descendants()]) node.ownerDocument = document;

    const byId = {};
    for (const node of document._descendants()) if (node.id) byId[node.id] = node;
    document.getElementById = (id) => byId[id] || null;

    return { document, palette, input, backdrop, empty, trigger, kbdMac, kbdOther };
}

function load(dom, { platform = "Linux x86_64" } = {}) {
    const { document } = dom;
    const location = { href: "/dashboard/" };
    const context = {
        document,
        navigator: { platform, userAgent: platform },
        window: { location },
        location,
        console,
    };
    context.globalThis = context;
    vm.createContext(context);
    vm.runInContext(SOURCE, context);
    return { location };
}

// ---------------------------------------------------------------------------
// Assertions + runner
// ---------------------------------------------------------------------------

let failures = 0;

function assert(condition, message) {
    if (!condition) {
        failures += 1;
        console.error(`  ✗ ${message}`);
    }
}

// FakeNode has parentNode/children cycles, so JSON.stringify is not an option
// for the failure message when a test compares elements (focus handoff does).
function describe(value) {
    if (value instanceof FakeNode) return `<${value.tagName.toLowerCase()}#${value.id || "?"}>`;
    return JSON.stringify(value);
}

function assertEqual(actual, expected, message) {
    assert(
        actual === expected,
        `${message} (expected ${describe(expected)}, got ${describe(actual)})`
    );
}

function test(name, fn) {
    const before = failures;
    try {
        fn();
    } catch (error) {
        failures += 1;
        console.error(`  ✗ ${name} threw: ${error.stack}`);
    }
    console.log(`${failures === before ? "✓" : "✗"} ${name}`);
}

// ---------------------------------------------------------------------------
// Fixture
// ---------------------------------------------------------------------------

const JUMP_TO = [
    ["📬 Inquiries", "/inquiries/"],
    ["🏦 Bank import", "/bank/import/"],
    ["🏦 Bank expenses", "/bank/expenses/"],
    ["📊 Analytics", "/analytics/"],
];
const ACTIONS = [
    ["➕ New invoice", "/invoices/new/"],
    ["➕ New client", "/clients/new/"],
];

function setup(options) {
    const dom = buildPalette({ jumpTo: JUMP_TO, actions: ACTIONS });
    const env = load(dom, options);
    return Object.assign({}, dom, env);
}

const visibleLabels = (dom) =>
    dom.palette.querySelectorAll(".cmd-palette__item").filter((i) => !i.hidden).map((i) => i.textContent);

const selectedLabel = (dom) => {
    const hit = dom.palette
        .querySelectorAll(".cmd-palette__item")
        .filter((i) => i.classList.contains("cmd-palette__item--selected"));
    return hit.length === 1 ? hit[0].textContent : null;
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test("starts closed and opens on Ctrl+K", () => {
    const dom = setup();
    assertEqual(dom.palette.hidden, true, "palette hidden before Ctrl+K");

    const event = dom.document.dispatch("keydown", { key: "k", ctrlKey: true });
    assertEqual(dom.palette.hidden, false, "palette visible after Ctrl+K");
    assert(event.defaultPrevented, "Ctrl+K must preventDefault — it is the browser's own shortcut");
    assert(dom.input.focused, "input focused on open");
    assert(dom.document.body.classList.contains("cmd-palette-open"), "body scroll-lock class set");
});

test("opens on ⌘K and toggles closed on a second press", () => {
    const dom = setup({ platform: "MacIntel" });
    dom.document.dispatch("keydown", { key: "K", metaKey: true });
    assertEqual(dom.palette.hidden, false, "⌘K opens (capital K, as Shift-less macOS reports it)");

    dom.document.dispatch("keydown", { key: "k", metaKey: true });
    assertEqual(dom.palette.hidden, true, "second ⌘K closes");
    assert(!dom.document.body.classList.contains("cmd-palette-open"), "scroll-lock class cleared");
});

test("ignores Ctrl+Alt+K so it cannot shadow an OS/browser combo", () => {
    const dom = setup();
    const event = dom.document.dispatch("keydown", { key: "k", ctrlKey: true, altKey: true });
    assertEqual(dom.palette.hidden, true, "palette stays closed");
    assert(!event.defaultPrevented, "the event is left alone");
});

test("trigger button opens the palette", () => {
    const dom = setup();
    dom.trigger.dispatch("click");
    assertEqual(dom.palette.hidden, false, "click on the header trigger opens");
});

test("Escape closes and returns focus to where it was", () => {
    const dom = setup();
    const opener = dom.trigger;
    opener.focus();

    dom.document.dispatch("keydown", { key: "k", ctrlKey: true });
    assertEqual(dom.document.activeElement, dom.input, "focus moved into the palette");

    dom.input.dispatch("keydown", { key: "Escape" });
    assertEqual(dom.palette.hidden, true, "palette closed");
    assertEqual(dom.document.activeElement, opener, "focus handed back to the opener");
});

test("backdrop click closes", () => {
    const dom = setup();
    dom.document.dispatch("keydown", { key: "k", ctrlKey: true });
    dom.backdrop.dispatch("click");
    assertEqual(dom.palette.hidden, true, "clicking the scrim closes the palette");
});

test("typing filters items and hides groups that emptied out", () => {
    const dom = setup();
    dom.document.dispatch("keydown", { key: "k", ctrlKey: true });

    dom.input.value = "bank";
    dom.input.dispatch("input");

    assertEqual(visibleLabels(dom).join(" | "), "🏦 Bank import | 🏦 Bank expenses", "only Bank items visible");
    const groups = dom.palette.querySelectorAll(".cmd-palette__group");
    assertEqual(groups[0].hidden, false, "Jump-to group still shown");
    assertEqual(groups[1].hidden, true, "Actions group hidden — nothing in it matched");
    assertEqual(dom.empty.hidden, true, "no empty message while there are matches");
});

test("filtering is case-insensitive and matches mid-label", () => {
    const dom = setup();
    dom.document.dispatch("keydown", { key: "k", ctrlKey: true });
    dom.input.value = "INVOICE";
    dom.input.dispatch("input");
    assertEqual(visibleLabels(dom).join(" | "), "➕ New invoice", "case-insensitive substring match");
});

test("no matches shows the empty message and leaves nothing selected", () => {
    const dom = setup();
    dom.document.dispatch("keydown", { key: "k", ctrlKey: true });
    dom.input.value = "zzz";
    dom.input.dispatch("input");

    assertEqual(visibleLabels(dom).length, 0, "no items visible");
    assertEqual(dom.empty.hidden, false, "empty message shown");
    assertEqual(selectedLabel(dom), null, "nothing selected");

    // Enter on an empty list must be inert, not navigate to a stale item.
    const before = dom.location.href;
    dom.input.dispatch("keydown", { key: "Enter" });
    assertEqual(dom.location.href, before, "Enter does nothing with no matches");
});

test("first match is pre-selected so Enter works without pressing ArrowDown", () => {
    const dom = setup();
    dom.document.dispatch("keydown", { key: "k", ctrlKey: true });
    assertEqual(selectedLabel(dom), "📬 Inquiries", "first item selected on open");

    dom.input.value = "bank ex";
    dom.input.dispatch("input");
    assertEqual(selectedLabel(dom), "🏦 Bank expenses", "selection follows the filter");

    const event = dom.input.dispatch("keydown", { key: "Enter" });
    assertEqual(dom.location.href, "/bank/expenses/", "Enter navigates to the selected item");
    assert(event.defaultPrevented, "Enter is consumed so the form/page does not also act");
});

test("arrow keys move the selection over visible items only, and wrap", () => {
    const dom = setup();
    dom.document.dispatch("keydown", { key: "k", ctrlKey: true });
    dom.input.value = "bank";
    dom.input.dispatch("input");

    dom.input.dispatch("keydown", { key: "ArrowDown" });
    assertEqual(selectedLabel(dom), "🏦 Bank expenses", "ArrowDown → second match");

    dom.input.dispatch("keydown", { key: "ArrowDown" });
    assertEqual(selectedLabel(dom), "🏦 Bank import", "ArrowDown past the end wraps to the top");

    dom.input.dispatch("keydown", { key: "ArrowUp" });
    assertEqual(selectedLabel(dom), "🏦 Bank expenses", "ArrowUp past the top wraps to the end");
});

test("hover moves the selection so Enter opens what is highlighted", () => {
    const dom = setup();
    dom.document.dispatch("keydown", { key: "k", ctrlKey: true });

    const analytics = dom.palette
        .querySelectorAll(".cmd-palette__item")
        .find((i) => i.textContent.includes("Analytics"));
    analytics.dispatch("mouseenter");
    assertEqual(selectedLabel(dom), "📊 Analytics", "hovered item becomes the selection");

    dom.input.dispatch("keydown", { key: "Enter" });
    assertEqual(dom.location.href, "/analytics/", "Enter follows the hovered item");
});

test("reopening clears the previous query", () => {
    const dom = setup();
    dom.document.dispatch("keydown", { key: "k", ctrlKey: true });
    dom.input.value = "bank";
    dom.input.dispatch("input");
    dom.input.dispatch("keydown", { key: "Escape" });

    dom.document.dispatch("keydown", { key: "k", ctrlKey: true });
    assertEqual(dom.input.value, "", "input reset");
    assertEqual(visibleLabels(dom).length, JUMP_TO.length + ACTIONS.length, "all items visible again");
});

test("shortcut hint matches the platform", () => {
    const linux = setup();
    assertEqual(linux.kbdMac.hidden, true, "⌘K hint hidden off macOS");
    assertEqual(linux.kbdOther.hidden, false, "Ctrl K hint shown off macOS");

    const mac = setup({ platform: "MacIntel" });
    assertEqual(mac.kbdMac.hidden, false, "⌘K hint shown on macOS");
    assertEqual(mac.kbdOther.hidden, true, "Ctrl K hint hidden on macOS");
});

// ---------------------------------------------------------------------------

if (failures > 0) {
    console.error(`\n${failures} assertion(s) failed`);
    process.exit(1);
}
console.log("\nAll command_palette.js tests passed");

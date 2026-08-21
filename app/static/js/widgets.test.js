/**
 * Tests for widgets.js — collapsible dashboard widgets with localStorage state.
 * Run with: node widgets.test.js
 *
 * Unlike the other scripts here, widgets.js is not wrapped in an IIFE: it
 * declares initializeWidgets/toggleWidget/WIDGET_STATE_PREFIX at top level and
 * self-initialises on load. The tests still drive it through the DOM rather
 * than calling those globals, since the click wiring is the actual contract.
 *
 * Hand-rolled DOM stub for the same reason as the sibling suites: the repo runs
 * JS tests as plain `node <file>` with no framework (see dev.py cmd_test_js).
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "widgets.js"), "utf8");

const PREFIX = "widget_state_";

// ---------------------------------------------------------------------------
// Minimal DOM stub
// ---------------------------------------------------------------------------

class FakeEvent {
    constructor(type, options = {}) {
        this.type = type;
        this.detail = options.detail;
        this.target = null;
    }
}

class FakeClassList {
    constructor() {
        this._set = new Set();
    }
    add(name) {
        this._set.add(name);
    }
    remove(name) {
        this._set.delete(name);
    }
    contains(name) {
        return this._set.has(name);
    }
    /** Returns the resulting state, which toggleWidget persists. */
    toggle(name) {
        if (this._set.has(name)) {
            this._set.delete(name);
            return false;
        }
        this._set.add(name);
        return true;
    }
}

class FakeNode {
    constructor(tagName = "div") {
        this.tagName = tagName.toUpperCase();
        this.children = [];
        this.parentNode = null;
        this.dataset = {};
        this.className = "";
        this.classList = new FakeClassList();
        this._listeners = {};
    }

    addEventListener(type, fn) {
        (this._listeners[type] = this._listeners[type] || []).push(fn);
    }

    dispatchEvent(event) {
        if (!event.target) event.target = this;
        for (const fn of this._listeners[event.type] || []) fn.call(this, event);
        return true;
    }

    appendChild(child) {
        child.parentNode = this;
        this.children.push(child);
        return child;
    }

    closest(selector) {
        const wanted = selector.slice(1);
        let node = this;
        while (node) {
            if (node.className.split(/\s+/).includes(wanted)) return node;
            node = node.parentNode;
        }
        return null;
    }
}

/**
 * Build a dashboard with the given widgets and load the script.
 *
 * @param options.widgets  [{ id, defaultCollapsed }]
 * @param options.storage  pre-existing localStorage entries
 */
function setupPage(options = {}) {
    const { widgets = [], storage = {}, readyState = "loading", skipId = false } = options;

    const document_ = new FakeNode("#document");
    document_.readyState = readyState;

    const nodes = new Map();
    for (const spec of widgets) {
        const widget = new FakeNode("section");
        widget.className = "dashboard-widget";
        if (!skipId) widget.dataset.widgetId = spec.id;
        if (spec.defaultCollapsed) widget.dataset.defaultCollapsed = "true";

        const header = new FakeNode("div");
        header.className = "widget-header";
        widget.appendChild(header);

        document_.appendChild(widget);
        nodes.set(spec.id, { widget, header });
    }

    const all = () => [...nodes.values()];
    document_.querySelectorAll = (selector) => {
        if (selector === ".dashboard-widget") return all().map((n) => n.widget);
        if (selector === ".widget-header") return all().map((n) => n.header);
        return [];
    };
    document_.querySelector = (selector) => {
        const match = selector.match(/\[data-widget-id="(.*)"\]/);
        if (!match) return null;
        const found = nodes.get(match[1]);
        return found ? found.widget : null;
    };

    const store = new Map(Object.entries(storage));
    const toggles = [];

    const sandbox = {
        document: document_,
        console,
        CustomEvent: FakeEvent,
        localStorage: {
            getItem: (k) => (store.has(k) ? store.get(k) : null),
            setItem: (k, v) => store.set(k, String(v)),
            removeItem: (k) => store.delete(k),
        },
    };

    vm.runInNewContext(SOURCE, sandbox);
    if (readyState === "loading") document_.dispatchEvent(new FakeEvent("DOMContentLoaded"));

    // Listen after init so only user-driven toggles are recorded.
    for (const { widget } of all()) {
        widget.addEventListener("widgetToggle", (e) => toggles.push(e.detail));
    }

    return {
        document: document_,
        store,
        toggles,
        widget: (id) => nodes.get(id).widget,
        header: (id) => nodes.get(id).header,
        collapsed: (id) => nodes.get(id).widget.classList.contains("collapsed"),
        click: (id) => nodes.get(id).header.dispatchEvent(new FakeEvent("click")),
        saved: (id) => store.get(PREFIX + id) ?? null,
    };
}

// ---------------------------------------------------------------------------
// Test framework
// ---------------------------------------------------------------------------

let failures = 0;

function test(name, fn) {
    try {
        fn();
        console.log(`✓ ${name}`);
    } catch (error) {
        failures++;
        console.error(`✗ ${name}`);
        console.error(`  ${error.message}`);
    }
}

function assertEquals(actual, expected, message) {
    const a = JSON.stringify(actual);
    const b = JSON.stringify(expected);
    if (a !== b) throw new Error(`${message}\n  Expected: ${b}\n  Actual: ${a}`);
}

function assertTrue(value, message) {
    if (!value) throw new Error(message);
}

console.log("\n🧩 Running widgets Tests\n");

// --- restoring state on load ------------------------------------------------

test("a widget with no saved state and no default starts expanded", () => {
    const page = setupPage({ widgets: [{ id: "revenue" }] });
    assertTrue(!page.collapsed("revenue"), "expanded by default");
});

test("data-default-collapsed collapses a widget with no saved state", () => {
    const page = setupPage({ widgets: [{ id: "revenue", defaultCollapsed: true }] });
    assertTrue(page.collapsed("revenue"), "default honoured");
});

test("a saved 'collapsed' state wins over no default", () => {
    const page = setupPage({
        widgets: [{ id: "revenue" }],
        storage: { [PREFIX + "revenue"]: "collapsed" },
    });
    assertTrue(page.collapsed("revenue"), "restored from storage");
});

test("a saved 'expanded' state overrides data-default-collapsed", () => {
    // The documented precedence is LocalStorage > default > expanded, so a
    // widget the user deliberately opened must not re-collapse on every load.
    const page = setupPage({
        widgets: [{ id: "revenue", defaultCollapsed: true }],
        storage: { [PREFIX + "revenue"]: "expanded" },
    });
    assertTrue(!page.collapsed("revenue"), "the user's choice wins over the default");
});

test("a widget without a data-widget-id is skipped entirely", () => {
    // The id guard runs before the default-collapsed check, so an id-less
    // widget stays expanded even when it asks to start collapsed — there would
    // be no key to persist the user's choice under.
    const page = setupPage({ widgets: [{ id: "orphan", defaultCollapsed: true }] });
    assertTrue(page.collapsed("orphan"), "sanity: the default applies with an id");

    const bare = setupPage({ widgets: [{ id: "orphan", defaultCollapsed: true }], skipId: true });
    assertTrue(!bare.collapsed("orphan"), "no id means the default is not applied");
});

test("each widget restores independently", () => {
    const page = setupPage({
        widgets: [{ id: "a" }, { id: "b" }],
        storage: { [PREFIX + "a"]: "collapsed" },
    });
    assertTrue(page.collapsed("a"), "a restored collapsed");
    assertTrue(!page.collapsed("b"), "b untouched");
});

test("initialises immediately when the document is already loaded", () => {
    const page = setupPage({
        widgets: [{ id: "revenue" }],
        storage: { [PREFIX + "revenue"]: "collapsed" },
        readyState: "complete",
    });
    assertTrue(page.collapsed("revenue"), "no DOMContentLoaded needed");
});

// --- toggling ---------------------------------------------------------------

test("clicking the header collapses an expanded widget", () => {
    const page = setupPage({ widgets: [{ id: "revenue" }] });
    page.click("revenue");
    assertTrue(page.collapsed("revenue"), "collapsed after one click");
});

test("clicking again expands it", () => {
    const page = setupPage({ widgets: [{ id: "revenue" }] });
    page.click("revenue");
    page.click("revenue");
    assertTrue(!page.collapsed("revenue"), "back to expanded");
});

test("collapsing persists to localStorage", () => {
    const page = setupPage({ widgets: [{ id: "revenue" }] });
    page.click("revenue");
    assertEquals(page.saved("revenue"), "collapsed", "state written under the prefixed key");
});

test("expanding persists too, rather than clearing the key", () => {
    const page = setupPage({
        widgets: [{ id: "revenue" }],
        storage: { [PREFIX + "revenue"]: "collapsed" },
    });
    page.click("revenue");
    assertEquals(page.saved("revenue"), "expanded", "explicit expanded state recorded");
});

test("clicking one widget leaves the others alone", () => {
    const page = setupPage({ widgets: [{ id: "a" }, { id: "b" }] });
    page.click("a");
    assertTrue(page.collapsed("a"), "a collapsed");
    assertTrue(!page.collapsed("b"), "b unaffected");
    assertEquals(page.saved("b"), null, "and nothing written for b");
});

test("a click inside the header still finds the owning widget", () => {
    // The handler walks up with closest('.dashboard-widget'), so clicks on the
    // title or the chevron inside the header have to work too.
    const page = setupPage({ widgets: [{ id: "revenue" }] });
    const inner = new FakeNode("span");
    page.header("revenue").appendChild(inner);
    page.header("revenue").dispatchEvent(new FakeEvent("click"));
    assertTrue(page.collapsed("revenue"), "toggled via the header");
});

// --- the widgetToggle event -------------------------------------------------

test("toggling emits widgetToggle with the id and the new state", () => {
    const page = setupPage({ widgets: [{ id: "revenue" }] });
    page.click("revenue");
    assertEquals(page.toggles, [{ widgetId: "revenue", collapsed: true }], "collapse event");
    page.click("revenue");
    assertEquals(
        page.toggles[1],
        { widgetId: "revenue", collapsed: false },
        "expand event reports the new state"
    );
});

test("restoring state on load does not emit widgetToggle", () => {
    // The event is for analytics, so it must mean "the user did something",
    // not "the page loaded".
    const page = setupPage({
        widgets: [{ id: "revenue" }],
        storage: { [PREFIX + "revenue"]: "collapsed" },
    });
    assertEquals(page.toggles, [], "no event from restoration");
});

// ---------------------------------------------------------------------------

if (failures > 0) {
    console.error(`\n❌ ${failures} test(s) failed\n`);
    process.exit(1);
}
console.log("\n✅ All tests passed!\n");

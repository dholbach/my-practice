/**
 * Tests for keyboard-nav.js — the help overlay and context-aware shortcuts.
 * Run with: node keyboard-nav.test.js
 *
 * Same approach as the sibling suites: the script is a browser IIFE with no
 * exports, so the test builds a throwaway DOM stub, loads the real source into
 * it via `vm`, and drives it through keydown events. Hand-rolled rather than
 * jsdom because the repo runs JS tests as plain `node <file>` with no framework
 * or devDependencies (see dev.py cmd_test_js).
 *
 * The URL paths asserted here are the real ones from my_practice/urls.py —
 * `clients/<int:pk>/detail/`, `invoices/<int:pk>/`. The context detection is
 * regex-matched against window.location.pathname, so a URL rename silently
 * kills a whole group of shortcuts; these tests are what would catch that.
 *
 * P-047 Phase 3 retired the single-letter global navigation keys (c/i/d/a/p),
 * the title hints on nav links and the auto-fading corner toast; the command
 * palette covers all three. What is left is the ? overlay and the contextual
 * n/e keys, which act on the record already on screen.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "keyboard-nav.js"), "utf8");

// Mirrors the data-kbd-* attributes base.html puts on <body>.
const I18N = {
    kbdHelp: "Help",
    kbdCommandPalette: "Open command palette",
    kbdNewClient: "New client",
    kbdNewInvoice: "New invoice",
    kbdEditClient: "Edit client",
    kbdEditInvoice: "Edit invoice",
    kbdHelpTitle: "Keyboard Shortcuts",
    kbdHelpIntro: "These shortcuts work everywhere.",
    kbdGlobalNav: "Global Navigation",
    kbdOnThisPage: "On This Page",
    kbdPress: "Press",
    kbdOr: "or",
    kbdToClose: "to close",
};

// ---------------------------------------------------------------------------
// Minimal DOM stub
// ---------------------------------------------------------------------------

class FakeEvent {
    constructor(type, options = {}) {
        this.type = type;
        this.key = options.key;
        this.target = options.target || null;
        this.ctrlKey = Boolean(options.ctrlKey);
        this.altKey = Boolean(options.altKey);
        this.metaKey = Boolean(options.metaKey);
        this.defaultPrevented = false;
    }
    preventDefault() {
        this.defaultPrevented = true;
    }
}

class FakeNode {
    constructor(tagName = "div", registry = null) {
        this.tagName = tagName.toUpperCase();
        this.children = [];
        this.parentNode = null;
        this.dataset = {};
        this.className = "";
        this._id = "";
        this._html = "";
        this._listeners = {};
        this._registry = registry;
        this.isContentEditable = false;
    }

    set id(value) {
        this._id = value;
        if (this._registry) this._registry.set(value, this);
    }
    get id() {
        return this._id;
    }

    addEventListener(type, fn) {
        (this._listeners[type] = this._listeners[type] || []).push(fn);
    }

    dispatchEvent(event) {
        if (!event.target) event.target = this;
        for (const fn of this._listeners[event.type] || []) fn.call(this, event);
        return !event.defaultPrevented;
    }

    appendChild(child) {
        child.parentNode = this;
        this.children.push(child);
        return child;
    }

    remove() {
        if (this._registry && this._id) this._registry.delete(this._id);
        if (!this.parentNode) return;
        const siblings = this.parentNode.children;
        const index = siblings.indexOf(this);
        if (index >= 0) siblings.splice(index, 1);
        this.parentNode = null;
    }

    get parentElement() {
        return this.parentNode && this.parentNode.tagName !== "#DOCUMENT"
            ? this.parentNode
            : null;
    }

    set innerHTML(value) {
        this._html = value;
    }
    get innerHTML() {
        return this._html;
    }
}

/**
 * Load the script against a page at the given path.
 *
 * @param options.pathname  window.location.pathname, driving getPageContext()
 */
function setupPage(options = {}) {
    const { pathname = "/dashboard/", i18n = I18N } = options;

    const registry = new Map();
    const make = (tag) => new FakeNode(tag, registry);

    const document_ = make("#document");
    const body = make("body");
    body.dataset = Object.assign({}, i18n);
    document_.body = body;
    document_.children.push(body);

    document_.createElement = (tag) => make(tag);
    document_.getElementById = (id) => registry.get(id) || null;

    const navigations = [];
    const window_ = make("#window");
    window_.location = {
        pathname,
        set href(value) {
            navigations.push(value);
        },
        get href() {
            return navigations[navigations.length - 1];
        },
    };

    vm.runInNewContext(SOURCE, { document: document_, window: window_, console });

    return {
        document: document_,
        body,
        navigations,
        overlay: () => registry.get("keyboard-help-overlay") || null,
        press(key, options = {}) {
            const target = options.target || body;
            const event = new FakeEvent("keydown", Object.assign({ key, target }, options));
            document_.dispatchEvent(event);
            return event;
        },
        overlayHtml() {
            const overlay = registry.get("keyboard-help-overlay");
            return overlay ? overlay.innerHTML : "";
        },
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

function assertContains(haystack, needle, message) {
    if (!String(haystack).includes(needle)) {
        throw new Error(`${message}\n  Expected to contain: ${needle}\n  Actual: ${haystack}`);
    }
}

console.log("\n⌨️  Running keyboard-nav Tests\n");

// --- retired global shortcuts -----------------------------------------------

test("the retired single-letter nav keys no longer navigate", () => {
    // c/i/d/a/p used to jump to Clients/Invoices/Dashboard/Analytics/Practice
    // Analysis from anywhere outside an input. The palette covers all five, and
    // a bare letter that navigates away on a stray keypress is a bad trade.
    for (const key of ["c", "i", "d", "a", "p"]) {
        const page = setupPage({ pathname: "/" });
        const event = page.press(key);
        assertEquals(page.navigations, [], `"${key}" no longer navigates`);
        assertTrue(!event.defaultPrevented, `"${key}" is left for the page`);
    }
});

test("an unmapped key is left alone", () => {
    const page = setupPage({ pathname: "/" });
    const event = page.press("z");
    assertEquals(page.navigations, [], "no navigation");
    assertTrue(!event.defaultPrevented, "and the key is not swallowed");
});

// --- typing guards ----------------------------------------------------------

test("shortcuts are inert while typing in a field", () => {
    for (const tag of ["input", "textarea", "select"]) {
        const page = setupPage({ pathname: "/clients/" });
        const field = new FakeNode(tag);
        page.press("n", { target: field });
        assertEquals(page.navigations, [], `typing "n" in <${tag}> must not navigate`);
    }
});

test("shortcuts are inert inside a contenteditable element", () => {
    const page = setupPage({ pathname: "/clients/" });
    const editor = new FakeNode("div");
    editor.isContentEditable = true;
    page.press("n", { target: editor });
    assertEquals(page.navigations, [], "contenteditable is a typing context");
});

test("shortcuts are inert inside a contenteditable parent", () => {
    const page = setupPage({ pathname: "/clients/" });
    const editor = new FakeNode("div");
    editor.isContentEditable = true;
    const inner = new FakeNode("span");
    inner.parentNode = editor;
    page.press("n", { target: inner });
    assertEquals(page.navigations, [], "the guard walks up the tree");
});

test("modifier combinations are left to the browser", () => {
    // ⌘K/Ctrl+K reaches command_palette.js precisely because this file bails on
    // any modifier — the two listeners share the document.
    for (const modifier of ["ctrlKey", "altKey", "metaKey"]) {
        const page = setupPage({ pathname: "/clients/" });
        page.press("n", { [modifier]: true });
        assertEquals(page.navigations, [], `${modifier}+n belongs to the browser`);
    }
});

// --- page context -----------------------------------------------------------

test("n on the client list opens the new-client form", () => {
    const page = setupPage({ pathname: "/clients/" });
    page.press("n");
    assertEquals(page.navigations, ["/clients/new/"], "contextual new");
});

test("n on a client detail page pre-fills a new invoice for that client", () => {
    const page = setupPage({ pathname: "/clients/42/detail/" });
    page.press("n");
    assertEquals(page.navigations, ["/invoices/new/?client=42"], "client id carried over");
});

test("e on a client detail page edits that client", () => {
    const page = setupPage({ pathname: "/clients/42/detail/" });
    page.press("e");
    assertEquals(page.navigations, ["/clients/42/edit/"], "client id carried over");
});

test("n on the invoice list opens the new-invoice form", () => {
    const page = setupPage({ pathname: "/invoices/" });
    page.press("n");
    assertEquals(page.navigations, ["/invoices/new/"], "contextual new");
});

test("e on an invoice detail page edits that invoice", () => {
    const page = setupPage({ pathname: "/invoices/7/" });
    page.press("e");
    assertEquals(page.navigations, ["/invoices/7/edit/"], "invoice id carried over");
});

test("e does nothing on the client list", () => {
    const page = setupPage({ pathname: "/clients/" });
    page.press("e");
    assertEquals(page.navigations, [], "no contextual e on the client list");
});

test("e does nothing on a page with no edit context", () => {
    const page = setupPage({ pathname: "/dashboard/" });
    page.press("e");
    assertEquals(page.navigations, [], "no edit target");
});

// --- help overlay -----------------------------------------------------------

test("? opens the help overlay", () => {
    const page = setupPage({ pathname: "/" });
    page.press("?");
    assertTrue(page.overlay() !== null, "overlay created");
});

test("? again closes it", () => {
    const page = setupPage({ pathname: "/" });
    page.press("?");
    page.press("?");
    assertEquals(page.overlay(), null, "overlay toggles off");
});

test("Escape closes the overlay and is swallowed", () => {
    const page = setupPage({ pathname: "/" });
    page.press("?");
    const event = page.press("Escape");
    assertEquals(page.overlay(), null, "overlay closed");
    assertTrue(event.defaultPrevented, "Escape consumed while the overlay is open");
});

test("Escape without an overlay is left alone", () => {
    const page = setupPage({ pathname: "/" });
    const event = page.press("Escape");
    assertTrue(!event.defaultPrevented, "Escape stays available to the page");
});

test("the overlay documents the palette, not the retired nav keys", () => {
    const page = setupPage({
        pathname: "/",
        i18n: Object.assign({}, I18N, { kbdCommandPalette: "PALETTE", kbdHelp: "HELPROW" }),
    });
    page.press("?");
    const html = page.overlayHtml();

    assertContains(html, "⌘K", "the palette shortcut is listed");
    assertContains(html, "PALETTE", "with its translated name from the dataset");
    assertContains(html, "HELPROW", "and ? documents itself now that it is a global key");
    for (const gone of ["Clients", "Dashboard", "Practice Analysis"]) {
        assertTrue(!html.includes(gone), `${gone} is no longer a global shortcut row`);
    }
});

test("the overlay uses CSS classes, not inline styles", () => {
    // P-047 Phase 3 moved the overlay's appearance into tailwind.css; a literal
    // colour or px here would be invisible to the CSS-token guardrail, which
    // only scans the stylesheet.
    const page = setupPage({ pathname: "/" });
    page.press("?");
    assertEquals(page.overlay().className, "kbd-help", "overlay carries the component class");
    assertTrue(!page.overlayHtml().includes("style="), "no inline style attributes");
});

test("the overlay adds a context section on a client detail page", () => {
    const page = setupPage({ pathname: "/clients/42/detail/" });
    page.press("?");
    const html = page.overlayHtml();
    assertContains(html, I18N.kbdOnThisPage, "context heading present");
    assertContains(html, I18N.kbdNewInvoice, "contextual n listed");
    assertContains(html, I18N.kbdEditClient, "contextual e listed");
});

test("the overlay omits the context section where there is none", () => {
    const page = setupPage({ pathname: "/dashboard/" });
    page.press("?");
    assertTrue(!page.overlayHtml().includes(I18N.kbdOnThisPage), "no empty context table");
});

// ---------------------------------------------------------------------------

if (failures > 0) {
    console.error(`\n❌ ${failures} test(s) failed\n`);
    process.exit(1);
}
console.log("\n✅ All tests passed!\n");

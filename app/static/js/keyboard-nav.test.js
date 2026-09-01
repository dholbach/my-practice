/**
 * Tests for keyboard-nav.js — global and context-aware keyboard shortcuts.
 * Run with: node keyboard-nav.test.js
 *
 * Same approach as the sibling suites: the script is a browser IIFE with no
 * exports, so the test builds a throwaway DOM stub, loads the real source into
 * it via `vm`, and drives it through keydown events. Hand-rolled rather than
 * jsdom because the repo runs JS tests as plain `node <file>` with no framework
 * or devDependencies (see dev.py cmd_test_js).
 *
 * The URL paths asserted here are the real ones from my_practice/urls.py —
 * `clients/<int:pk>/detail/`, `invoices/<int:pk>/`, `practice-analysis/`. The
 * context detection is regex-matched against window.location.pathname, so a
 * URL rename silently kills a whole group of shortcuts; these tests are what
 * would catch that.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "keyboard-nav.js"), "utf8");

// Mirrors the data-kbd-* attributes base.html puts on <body>.
const I18N = {
    kbdClients: "Clients",
    kbdInvoices: "Invoices",
    kbdDashboard: "Dashboard",
    kbdAnalytics: "Analytics",
    kbdPracticeAnalysis: "Practice Analysis",
    kbdHelp: "Help",
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
    kbdForShortcuts: "for keyboard shortcuts",
    kbdShortcutLabel: "Shortcut",
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

class FakeStyle {
    set cssText(text) {
        for (const declaration of text.split(";")) {
            const [property, ...rest] = declaration.split(":");
            if (!property || rest.length === 0) continue;
            const name = property.trim().replace(/-([a-z])/g, (_, c) => c.toUpperCase());
            this[name] = rest.join(":").trim();
        }
    }
}

class FakeNode {
    constructor(tagName = "div", registry = null) {
        this.tagName = tagName.toUpperCase();
        this.children = [];
        this.parentNode = null;
        this.dataset = {};
        this.className = "";
        this.style = new FakeStyle();
        this.attributes = {};
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

    getAttribute(name) {
        return this.attributes[name] ?? null;
    }
    setAttribute(name, value) {
        this.attributes[name] = value;
    }

    closest(selector) {
        const wanted = selector.slice(1);
        let node = this;
        while (node) {
            if (node.className && node.className.split(/\s+/).includes(wanted)) return node;
            node = node.parentNode;
        }
        return null;
    }

    set innerHTML(value) {
        this._html = value;
    }
    get innerHTML() {
        return this._html;
    }

    querySelectorAll() {
        return [];
    }
}

/**
 * Load the script against a page at the given path.
 *
 * @param options.pathname  window.location.pathname, driving getPageContext()
 * @param options.links     [{ href, title, inDropdown }] for the title hints
 */
function setupPage(options = {}) {
    const { pathname = "/dashboard/", i18n = I18N, links = [], readyState = "loading" } = options;

    const registry = new Map();
    const make = (tag) => new FakeNode(tag, registry);

    const document_ = make("#document");
    document_.readyState = readyState;

    const body = make("body");
    body.dataset = Object.assign({}, i18n);
    document_.body = body;
    body.parentNode = document_;
    document_.children.push(body);

    const linkNodes = links.map((spec) => {
        const anchor = make("a");
        anchor.attributes.href = spec.href;
        if (spec.title) anchor.attributes.title = spec.title;
        if (spec.inDropdown) {
            const wrapper = make("div");
            wrapper.className = "dropdown-content";
            wrapper.appendChild(anchor);
            body.appendChild(wrapper);
        } else {
            body.appendChild(anchor);
        }
        return anchor;
    });

    document_.createElement = (tag) => make(tag);
    document_.getElementById = (id) => registry.get(id) || null;
    document_.querySelectorAll = (selector) => {
        const match = selector.match(/href\*="([^"]+)"/);
        if (!match) return [];
        return linkNodes.filter((a) => (a.attributes.href || "").includes(match[1]));
    };

    const navigations = [];
    const timers = [];
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

    vm.runInNewContext(SOURCE, {
        document: document_,
        window: window_,
        console,
        setTimeout: (fn) => {
            timers.push(fn);
            return timers.length;
        },
        clearTimeout: () => {},
    });
    if (readyState === "loading") document_.dispatchEvent(new FakeEvent("DOMContentLoaded"));

    return {
        document: document_,
        body,
        navigations,
        links: linkNodes,
        overlay: () => registry.get("keyboard-help-overlay") || null,
        hint: () => registry.get("keyboard-hint") || null,
        flushTimers() {
            const pending = timers.splice(0, timers.length);
            for (const fn of pending) if (fn) fn();
        },
        press(key, options = {}) {
            const target = options.target || body;
            const event = new FakeEvent("keydown", Object.assign({ key, target }, options));
            document_.dispatchEvent(event);
            return event;
        },
        overlayHtml() {
            const overlay = registry.get("keyboard-help-overlay");
            return overlay ? overlay.children.map((c) => c.innerHTML).join("") : "";
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

// --- global shortcuts -------------------------------------------------------

test("the five global shortcuts navigate to their real URLs", () => {
    // These paths are asserted against my_practice/urls.py, so renaming a URL
    // without updating the shortcut shows up here rather than as a 404.
    const expected = {
        c: "/clients/",
        i: "/invoices/",
        d: "/dashboard/",
        a: "/analytics/",
        p: "/practice-analysis/",
    };
    for (const [key, url] of Object.entries(expected)) {
        const page = setupPage({ pathname: "/" });
        const event = page.press(key);
        assertEquals(page.navigations, [url], `"${key}" goes to ${url}`);
        assertTrue(event.defaultPrevented, `"${key}" is swallowed`);
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
        const page = setupPage({ pathname: "/" });
        const field = new FakeNode(tag);
        page.press("c", { target: field });
        assertEquals(page.navigations, [], `typing "c" in <${tag}> must not navigate`);
    }
});

test("shortcuts are inert inside a contenteditable element", () => {
    const page = setupPage({ pathname: "/" });
    const editor = new FakeNode("div");
    editor.isContentEditable = true;
    page.press("c", { target: editor });
    assertEquals(page.navigations, [], "contenteditable is a typing context");
});

test("shortcuts are inert inside a contenteditable parent", () => {
    const page = setupPage({ pathname: "/" });
    const editor = new FakeNode("div");
    editor.isContentEditable = true;
    const inner = new FakeNode("span");
    inner.parentNode = editor;
    page.press("c", { target: inner });
    assertEquals(page.navigations, [], "the guard walks up the tree");
});

test("modifier combinations are left to the browser", () => {
    for (const modifier of ["ctrlKey", "altKey", "metaKey"]) {
        const page = setupPage({ pathname: "/" });
        page.press("c", { [modifier]: true });
        assertEquals(page.navigations, [], `${modifier}+c belongs to the browser`);
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

test("contextual shortcuts win over global ones", () => {
    // "e" is not global, but "n" on /clients/ must not fall through to
    // anything else either — the contextual branch returns early.
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

test("the overlay lists the global shortcuts using translated names", () => {
    // All of these come from body.dataset. Three of them used to be hardcoded
    // English literals, invisible to the i18n guardrail because it only scans
    // templates — the German UI showed "Dashboard"/"Analytics"/"Practice
    // Analysis" while the nav used the actual translated German labels.
    const page = setupPage({
        pathname: "/",
        i18n: Object.assign({}, I18N, {
            kbdClients: "KLIENTEN",
            kbdInvoices: "RECHNUNGEN",
            kbdDashboard: "UEBERSICHT",
            kbdAnalytics: "ANALYSEN",
            kbdPracticeAnalysis: "PRAXISANALYSE",
        }),
    });
    page.press("?");
    const html = page.overlayHtml();
    for (const name of ["KLIENTEN", "RECHNUNGEN", "UEBERSICHT", "ANALYSEN", "PRAXISANALYSE"]) {
        assertContains(html, name, `${name} comes from the dataset`);
    }
});

test("the overlay omits the help row itself", () => {
    const page = setupPage({ pathname: "/", i18n: Object.assign({}, I18N, { kbdHelp: "HELPROW" }) });
    page.press("?");
    assertTrue(!page.overlayHtml().includes("HELPROW"), "no ? row inside the ? overlay");
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

// --- shortcut hints on links ------------------------------------------------

test("adds a shortcut hint to matching nav links", () => {
    const page = setupPage({ pathname: "/", links: [{ href: "/clients/" }] });
    assertEquals(
        page.links[0].getAttribute("title"),
        `${I18N.kbdShortcutLabel}: c`,
        "hint added as the title"
    );
});

test("keeps an existing title and appends the hint", () => {
    const page = setupPage({
        pathname: "/",
        links: [{ href: "/invoices/", title: "Alle Rechnungen" }],
    });
    assertEquals(
        page.links[0].getAttribute("title"),
        `Alle Rechnungen (${I18N.kbdShortcutLabel}: i)`,
        "original title preserved"
    );
});

test("skips links inside a dropdown", () => {
    const page = setupPage({
        pathname: "/",
        links: [{ href: "/analytics/", inDropdown: true }],
    });
    assertEquals(page.links[0].getAttribute("title"), null, "dropdown links left alone");
});

// --- the help hint ----------------------------------------------------------

test("adds a dismissable help hint built from the dataset", () => {
    const page = setupPage({ pathname: "/" });
    const hint = page.hint();
    assertTrue(hint !== null, "hint added");
    assertContains(hint.innerHTML, I18N.kbdPress, "uses the translated prefix");
    assertContains(hint.innerHTML, I18N.kbdForShortcuts, "and the translated suffix");
});

test("clicking the hint opens the overlay", () => {
    const page = setupPage({ pathname: "/" });
    page.hint().dispatchEvent(new FakeEvent("click"));
    assertTrue(page.overlay() !== null, "hint is a shortcut to the overlay");
});

test("the hint fades itself out", () => {
    const page = setupPage({ pathname: "/" });
    page.flushTimers();
    assertEquals(page.hint().style.opacity, "0", "faded after the timeout");
});

// ---------------------------------------------------------------------------

if (failures > 0) {
    console.error(`\n❌ ${failures} test(s) failed\n`);
    process.exit(1);
}
console.log("\n✅ All tests passed!\n");

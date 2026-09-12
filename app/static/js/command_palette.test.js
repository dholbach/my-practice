/**
 * Tests for command_palette.js (P-047)
 * Run with: node command_palette.test.js
 *
 * Same approach as form_draft_guard.test.js and the global-search.test.js this
 * replaced: the script is a browser IIFE with no exports, so each test builds a
 * throwaway DOM stub, loads the real source into it via `vm`, and drives it
 * through events. Stubs are hand-rolled rather than jsdom because the repo runs
 * JS tests as plain `node <file>` with no framework or devDependencies (see
 * dev.py cmd_test_js), and a DOM dependency would have to exist in the Docker
 * image too.
 *
 * Two things this file has to fake:
 *   - setTimeout is a manual map, so the 300ms search debounce can be flushed
 *     synchronously instead of slept through.
 *   - fetch hands back a deferred, so a test can land two responses in either
 *     order and check the stale one is dropped. Tests are therefore async and
 *     run sequentially.
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
    // Assigning "" is also how the source empties the results container.
    set textContent(value) {
        this._text = String(value);
        for (const child of this.children) child.parentNode = null;
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
        child.ownerDocument = this.ownerDocument;
        this.children.push(child);
        return child;
    }

    focus() {
        this.focused = true;
        if (this.ownerDocument) this.ownerDocument.activeElement = this;
    }
    scrollIntoView() {}

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
 * Builds the subset of includes/command_palette.html the script touches: the
 * results group, two static groups with the given item labels, the three status
 * lines, and the two platform <kbd> variants on the header trigger.
 */
function buildPalette({ jumpTo, actions }) {
    const document = new FakeNode("document");
    document.ownerDocument = document;
    document.readyState = "complete";
    document.activeElement = null;
    document.createElement = (tag) => {
        const node = new FakeNode(tag);
        node.ownerDocument = document;
        return node;
    };
    document.createTextNode = (text) => {
        const node = new FakeNode("#text");
        node.ownerDocument = document;
        node.textContent = text;
        return node;
    };

    const body = document.appendChild(new FakeNode("body"));
    document.body = body;

    const palette = body.appendChild(new FakeNode("div"));
    palette.id = "command-palette";
    palette.hidden = true;

    const backdrop = palette.appendChild(new FakeNode("div"));
    backdrop.className = "cmd-palette__backdrop";
    backdrop.dataset.cmdkDismiss = "";

    const dialog = palette.appendChild(new FakeNode("div"));
    const input = dialog.appendChild(new FakeNode("input"));
    input.id = "cmd-palette-input";

    const resultsGroup = dialog.appendChild(new FakeNode("section"));
    resultsGroup.className = "cmd-palette__group";
    resultsGroup.id = "cmd-palette-results-group";
    resultsGroup.hidden = true;
    const resultsContainer = resultsGroup.appendChild(new FakeNode("div"));
    resultsContainer.id = "cmd-palette-results";

    const makeGroup = (labels) => {
        const group = dialog.appendChild(new FakeNode("section"));
        group.className = "cmd-palette__group";
        for (const [label, href] of labels) {
            const item = group.appendChild(new FakeNode("a"));
            item.className = "cmd-palette__item";
            item.textContent = label;
            item.setAttribute("href", href);
        }
    };
    makeGroup(jumpTo);
    makeGroup(actions);

    const status = (id) => {
        const el = dialog.appendChild(new FakeNode("p"));
        el.id = id;
        el.hidden = true;
        return el;
    };
    const loading = status("cmd-palette-loading");
    const error = status("cmd-palette-error");
    const empty = status("cmd-palette-empty");

    const trigger = body.appendChild(new FakeNode("button"));
    trigger.id = "cmd-palette-trigger";
    const kbdMac = trigger.appendChild(new FakeNode("kbd"));
    kbdMac.dataset.cmdkKey = "mac";
    kbdMac.hidden = true;
    const kbdOther = trigger.appendChild(new FakeNode("kbd"));
    kbdOther.dataset.cmdkKey = "other";

    const byId = {};
    for (const node of document._descendants()) if (node.id) byId[node.id] = node;
    document.getElementById = (id) => byId[id] || null;

    return {
        document, palette, input, backdrop, resultsGroup, resultsContainer,
        loading, error, empty, trigger, kbdMac, kbdOther,
    };
}

/** fetch stub: each call records a deferred the test resolves or rejects itself. */
function makeFetch() {
    const calls = [];
    const fetchImpl = (url) => {
        const call = { url };
        call.promise = new Promise((resolve, reject) => {
            call.respond = (results) =>
                resolve({ json: () => Promise.resolve({ results }) });
            call.fail = () => reject(new Error("network down"));
        });
        calls.push(call);
        return call.promise;
    };
    return { fetchImpl, calls };
}

function load(dom, { platform = "Linux x86_64" } = {}) {
    const { document } = dom;
    const location = { href: "/dashboard/" };
    const { fetchImpl, calls } = makeFetch();

    const timers = new Map();
    let nextTimerId = 1;
    const errors = [];

    const context = {
        document,
        navigator: { platform, userAgent: platform },
        window: { location },
        location,
        console: { error: (...args) => errors.push(args.join(" ")) },
        fetch: fetchImpl,
        setTimeout: (fn) => {
            const id = nextTimerId++;
            timers.set(id, fn);
            return id;
        },
        clearTimeout: (id) => timers.delete(id),
        Promise,
    };
    context.globalThis = context;
    vm.createContext(context);
    vm.runInContext(SOURCE, context);

    return {
        location,
        fetchCalls: calls,
        errors,
        pendingTimers: () => timers.size,
        flushTimers: () => {
            const fns = Array.from(timers.values());
            timers.clear();
            for (const fn of fns) fn();
        },
    };
}

// Lets queued promise callbacks (fetch → .json() → render) run before asserting.
const settle = () => new Promise((resolve) => setImmediate(resolve));

// ---------------------------------------------------------------------------
// Assertions + runner
// ---------------------------------------------------------------------------

let failures = 0;
const tests = [];

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
    tests.push({ name, fn });
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
    return Object.assign({}, dom, load(dom, options));
}

function openPalette(dom) {
    dom.document.dispatch("keydown", { key: "k", ctrlKey: true });
}

function type(dom, text) {
    dom.input.value = text;
    dom.input.dispatch("input");
}

const items = (dom) => dom.palette.querySelectorAll(".cmd-palette__item");
const visibleLabels = (dom) => items(dom).filter((i) => !i.hidden).map((i) => i.textContent);

const selectedLabel = (dom) => {
    const hit = items(dom).filter((i) => i.classList.contains("cmd-palette__item--selected"));
    return hit.length === 1 ? hit[0].textContent : null;
};

// ---------------------------------------------------------------------------
// Open / close
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

test('"/" opens the palette, inheriting the old search box shortcut', () => {
    const dom = setup();
    const event = dom.document.dispatch("keydown", { key: "/" });
    assertEqual(dom.palette.hidden, false, '"/" opens');
    assert(event.defaultPrevented, '"/" is consumed so it does not land in the page');
});

test('"/" typed into a field is left alone', () => {
    const dom = setup();
    const field = new FakeNode("textarea");
    const event = dom.document.dispatch("keydown", { key: "/", target: field });
    assertEqual(dom.palette.hidden, true, "palette stays closed while typing");
    assert(!event.defaultPrevented, "the slash reaches the field");
});

test("trigger button opens the palette", () => {
    const dom = setup();
    dom.trigger.dispatch("click");
    assertEqual(dom.palette.hidden, false, "click on the header trigger opens");
});

test("Escape closes and returns focus to where it was", () => {
    const dom = setup();
    dom.trigger.focus();
    openPalette(dom);
    assertEqual(dom.document.activeElement, dom.input, "focus moved into the palette");

    dom.input.dispatch("keydown", { key: "Escape" });
    assertEqual(dom.palette.hidden, true, "palette closed");
    assertEqual(dom.document.activeElement, dom.trigger, "focus handed back to the opener");
});

test("backdrop click closes", () => {
    const dom = setup();
    openPalette(dom);
    dom.backdrop.dispatch("click");
    assertEqual(dom.palette.hidden, true, "clicking the scrim closes the palette");
});

// ---------------------------------------------------------------------------
// Static filtering
// ---------------------------------------------------------------------------

test("typing filters items and hides groups that emptied out", () => {
    const dom = setup();
    openPalette(dom);
    type(dom, "bank");

    assertEqual(visibleLabels(dom).join(" | "), "🏦 Bank import | 🏦 Bank expenses", "only Bank items visible");
    const groups = dom.palette.querySelectorAll(".cmd-palette__group");
    assertEqual(groups[1].hidden, false, "Jump-to group still shown");
    assertEqual(groups[2].hidden, true, "Actions group hidden — nothing in it matched");
    assertEqual(dom.empty.hidden, true, "no empty message while there are matches");
});

test("filtering is case-insensitive and matches mid-label", () => {
    const dom = setup();
    openPalette(dom);
    type(dom, "INVOICE");
    assertEqual(visibleLabels(dom).join(" | "), "➕ New invoice", "case-insensitive substring match");
});

test("first match is pre-selected so Enter works without pressing ArrowDown", () => {
    const dom = setup();
    openPalette(dom);
    assertEqual(selectedLabel(dom), "📬 Inquiries", "first item selected on open");

    type(dom, "bank ex");
    assertEqual(selectedLabel(dom), "🏦 Bank expenses", "selection follows the filter");

    const event = dom.input.dispatch("keydown", { key: "Enter" });
    assertEqual(dom.location.href, "/bank/expenses/", "Enter navigates to the selected item");
    assert(event.defaultPrevented, "Enter is consumed so the form/page does not also act");
});

test("arrow keys move the selection over visible items only, and wrap", () => {
    const dom = setup();
    openPalette(dom);
    type(dom, "bank");

    dom.input.dispatch("keydown", { key: "ArrowDown" });
    assertEqual(selectedLabel(dom), "🏦 Bank expenses", "ArrowDown → second match");

    dom.input.dispatch("keydown", { key: "ArrowDown" });
    assertEqual(selectedLabel(dom), "🏦 Bank import", "ArrowDown past the end wraps to the top");

    dom.input.dispatch("keydown", { key: "ArrowUp" });
    assertEqual(selectedLabel(dom), "🏦 Bank expenses", "ArrowUp past the top wraps to the end");
});

test("hover moves the selection so Enter opens what is highlighted", () => {
    const dom = setup();
    openPalette(dom);

    const analytics = items(dom).find((i) => i.textContent.includes("Analytics"));
    analytics.dispatch("mouseenter");
    assertEqual(selectedLabel(dom), "📊 Analytics", "hovered item becomes the selection");

    dom.input.dispatch("keydown", { key: "Enter" });
    assertEqual(dom.location.href, "/analytics/", "Enter follows the hovered item");
});

test("reopening clears the previous query", () => {
    const dom = setup();
    openPalette(dom);
    type(dom, "bank");
    dom.input.dispatch("keydown", { key: "Escape" });

    openPalette(dom);
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
// Search (/api/search/)
// ---------------------------------------------------------------------------

test("the search request is debounced, not fired per keystroke", async () => {
    const dom = setup();
    openPalette(dom);

    type(dom, "sch");
    type(dom, "schm");
    type(dom, "schmidt");
    assertEqual(dom.fetchCalls.length, 0, "nothing requested before the debounce elapses");
    assertEqual(dom.pendingTimers(), 1, "only the newest keystroke has a timer — earlier ones cleared");

    dom.flushTimers();
    assertEqual(dom.fetchCalls.length, 1, "one request for the final text");
    assertEqual(dom.fetchCalls[0].url, "/api/search/?q=schmidt", "query sent url-encoded");
    assertEqual(dom.loading.hidden, false, "loading line shown while in flight");

    dom.fetchCalls[0].respond([]);
    await settle();
    assertEqual(dom.loading.hidden, true, "loading line cleared when the response lands");
});

test("results render above the static entries and are Enter-able", async () => {
    const dom = setup();
    openPalette(dom);
    type(dom, "MU");
    dom.flushTimers();
    dom.fetchCalls[0].respond([
        { type: "client", url: "/clients/7/detail/", prefix: "👤 MU-1 — ", name: "Max Mustermann", suffix: "" },
        { type: "invoice", url: "/invoices/3/", prefix: "📄 INV-001 — MU-1", name: "", suffix: "" },
    ]);
    await settle();

    assertEqual(dom.resultsGroup.hidden, false, "results group revealed");
    assertEqual(
        visibleLabels(dom).join(" | "),
        "👤 MU-1 — Max Mustermann | 📄 INV-001 — MU-1",
        "results listed first; no static entry contains \"MU\""
    );
    assertEqual(selectedLabel(dom), "👤 MU-1 — Max Mustermann", "top result pre-selected");

    dom.input.dispatch("keydown", { key: "ArrowDown" });
    dom.input.dispatch("keydown", { key: "Enter" });
    assertEqual(dom.location.href, "/invoices/3/", "Enter opens the selected result");
});

test("result labels with & and < survive verbatim", async () => {
    const dom = setup();
    openPalette(dom);
    type(dom, "ka");
    dom.flushTimers();
    dom.fetchCalls[0].respond([
        { type: "client", url: "/clients/9/detail/", prefix: "👤 KA-1 — ", name: "Karl <Kalle> & Co", suffix: "" },
    ]);
    await settle();

    assertEqual(
        visibleLabels(dom).join(""),
        "👤 KA-1 — Karl <Kalle> & Co",
        "built as a text node, so no escaping round-trip to get wrong"
    );
});

test("results and matching static entries appear together", async () => {
    const dom = setup();
    openPalette(dom);
    type(dom, "bank");
    dom.flushTimers();
    dom.fetchCalls[0].respond([
        { type: "client", url: "/clients/4/detail/", prefix: "👤 BA-1 — ", name: "Banks", suffix: "" },
    ]);
    await settle();

    assertEqual(
        visibleLabels(dom).join(" | "),
        "👤 BA-1 — Banks | 🏦 Bank import | 🏦 Bank expenses",
        "one search hit followed by the two static matches"
    );
});

test("a superseded response is dropped even if it lands last", async () => {
    const dom = setup();
    openPalette(dom);

    type(dom, "sch");
    dom.flushTimers();
    type(dom, "schmidt");
    dom.flushTimers();
    assertEqual(dom.fetchCalls.length, 2, "two requests in flight");

    // Newest answers first, then the slower earlier one — the race the
    // latestRequestId guard exists for.
    dom.fetchCalls[1].respond([{ type: "client", url: "/clients/2/detail/", prefix: "👤 SC-1 — ", name: "Schmidt", suffix: "" }]);
    await settle();
    dom.fetchCalls[0].respond([{ type: "client", url: "/clients/99/detail/", prefix: "👤 XX-9 — ", name: "Stale", suffix: "" }]);
    await settle();

    assertEqual(visibleLabels(dom).join(""), "👤 SC-1 — Schmidt", "stale response ignored");
    dom.input.dispatch("keydown", { key: "Enter" });
    assertEqual(dom.location.href, "/clients/2/detail/", "Enter cannot navigate to a stale result");
});

test("clearing the input drops the results and any in-flight response", async () => {
    const dom = setup();
    openPalette(dom);
    type(dom, "MU");
    dom.flushTimers();

    type(dom, "");
    dom.fetchCalls[0].respond([{ type: "client", url: "/clients/7/detail/", prefix: "👤 MU-1 — ", name: "Max", suffix: "" }]);
    await settle();

    assertEqual(dom.resultsGroup.hidden, true, "results group hidden again");
    assertEqual(visibleLabels(dom).length, JUMP_TO.length + ACTIONS.length, "back to the full static list");
    assertEqual(dom.loading.hidden, true, "loading line cleared");
});

test("a failed search shows the error line and clears stale rows", async () => {
    const dom = setup();
    openPalette(dom);
    type(dom, "MU");
    dom.flushTimers();
    dom.fetchCalls[0].respond([{ type: "client", url: "/clients/7/detail/", prefix: "👤 MU-1 — ", name: "Max", suffix: "" }]);
    await settle();

    type(dom, "MUS");
    dom.flushTimers();
    dom.fetchCalls[1].fail();
    await settle();

    assertEqual(dom.error.hidden, false, "error line shown");
    assertEqual(dom.loading.hidden, true, "loading line cleared");
    assertEqual(dom.empty.hidden, true, "no 'No results' piled on top of the error");
    assertEqual(visibleLabels(dom).length, 0, "the previous query's rows are gone");
    assert(dom.errors.length === 1, "the failure is logged for the console");

    const before = dom.location.href;
    dom.input.dispatch("keydown", { key: "Enter" });
    assertEqual(dom.location.href, before, "Enter cannot navigate after a failure");
});

test("no static match and no search hit shows the empty message", async () => {
    const dom = setup();
    openPalette(dom);
    type(dom, "zzz");
    assertEqual(dom.empty.hidden, false, "empty message already shown before the search returns");

    dom.flushTimers();
    assertEqual(dom.empty.hidden, true, "suppressed while the search is in flight");

    dom.fetchCalls[0].respond([]);
    await settle();
    assertEqual(dom.empty.hidden, false, "shown again once the search comes back empty");
    assertEqual(selectedLabel(dom), null, "nothing selected");

    const before = dom.location.href;
    dom.input.dispatch("keydown", { key: "Enter" });
    assertEqual(dom.location.href, before, "Enter does nothing with no matches");
});

// --- privacy mode ------------------------------------------------------------

// Names are rendered as initial + <span class="sensitive-data pn-rest">rest</span>,
// which body.privacy-mode blurs. These assert the markup, since whether the blur
// actually paints is CSS's job (tailwind.css .sensitive-data / .pn-rest).
const sensitiveText = (item) =>
    item.children
        .filter((c) => c.classList.contains("sensitive-data"))
        .map((c) => c.textContent)
        .join("|");

const plainText = (item) =>
    item.children
        .filter((c) => !c.classList.contains("sensitive-data"))
        .map((c) => c.textContent)
        .join("");

test("a client result blurs the name but keeps the code and initials legible", async () => {
    const dom = setup();
    openPalette(dom);
    type(dom, "MU");
    dom.flushTimers();
    dom.fetchCalls[0].respond([
        { type: "client", url: "/clients/7/detail/", prefix: "👤 MU-1 — ", name: "Max Mustermann", suffix: "" },
    ]);
    await settle();

    const [item] = dom.resultsContainer.children;
    assertEqual(item.textContent, "👤 MU-1 — Max Mustermann", "reads normally with privacy mode off");
    assertEqual(sensitiveText(item), "ax|ustermann", "only the tail of each word is sensitive");
    assertEqual(plainText(item), "👤 MU-1 — M M", "code and both initials stay in the clear");
});

test("an inquiry result blurs the name — it is the only identifier there", async () => {
    const dom = setup();
    openPalette(dom);
    type(dom, "an");
    dom.flushTimers();
    dom.fetchCalls[0].respond([
        { type: "inquiry", url: "/inquiries/3/edit/", prefix: "📬 ", name: "Anna Schmidt", suffix: " (Neu)" },
    ]);
    await settle();

    const [item] = dom.resultsContainer.children;
    assertEqual(sensitiveText(item), "nna|chmidt", "name tails sensitive");
    assertEqual(plainText(item), "📬 A S (Neu)", "initials and status stay legible");
});

test("an invoice result has nothing sensitive — it carries a code, not a name", async () => {
    const dom = setup();
    openPalette(dom);
    type(dom, "MU");
    dom.flushTimers();
    dom.fetchCalls[0].respond([
        { type: "invoice", url: "/invoices/3/", prefix: "📄 MU-1 - MU (12.09.2026)", name: "", suffix: "" },
    ]);
    await settle();

    const [item] = dom.resultsContainer.children;
    assertEqual(sensitiveText(item), "", "no blurred span at all");
    assertEqual(item.textContent, "📄 MU-1 - MU (12.09.2026)", "row reads in full");
});

test("a single-character name part is left whole rather than emptied", async () => {
    const dom = setup();
    openPalette(dom);
    type(dom, "x");
    dom.flushTimers();
    dom.fetchCalls[0].respond([
        { type: "client", url: "/clients/8/detail/", prefix: "👤 XY-1 — ", name: "X Yolo", suffix: "" },
    ]);
    await settle();

    const [item] = dom.resultsContainer.children;
    assertEqual(item.textContent, "👤 XY-1 — X Yolo", "spacing survives a one-letter word");
    assertEqual(sensitiveText(item), "olo", "nothing to blur in a lone initial");
});

test("static entries carry nothing sensitive", () => {
    const dom = setup();
    openPalette(dom);
    for (const item of items(dom)) {
        assertEqual(
            item.querySelectorAll(".sensitive-data").length,
            0,
            `${item.textContent} is a destination, not personal data`
        );
    }
});

test("closing cancels a pending search", () => {
    const dom = setup();
    openPalette(dom);
    type(dom, "MU");
    assertEqual(dom.pendingTimers(), 1, "search queued");

    dom.input.dispatch("keydown", { key: "Escape" });
    assertEqual(dom.pendingTimers(), 0, "timer cleared on close");
    dom.flushTimers();
    assertEqual(dom.fetchCalls.length, 0, "no request fired for a palette the user dismissed");
});

// ---------------------------------------------------------------------------

(async () => {
    for (const { name, fn } of tests) {
        const before = failures;
        try {
            await fn();
        } catch (error) {
            failures += 1;
            console.error(`  ✗ ${name} threw: ${error.stack}`);
        }
        console.log(`${failures === before ? "✓" : "✗"} ${name}`);
    }

    if (failures > 0) {
        console.error(`\n${failures} assertion(s) failed`);
        process.exit(1);
    }
    console.log("\nAll command_palette.js tests passed");
})();

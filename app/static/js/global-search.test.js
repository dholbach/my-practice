/**
 * Tests for global-search.js — the header search box.
 * Run with: node global-search.test.js
 *
 * Same approach as form_draft_guard.test.js and bank_review.test.js: the script
 * is a browser IIFE with no exports, so each test builds a throwaway DOM stub,
 * loads the real source into it via `vm`, and drives it through events. Stubs
 * are hand-rolled rather than jsdom because the repo runs JS tests as plain
 * `node <file>` with no framework or devDependencies (see dev.py cmd_test_js).
 *
 * Two things this file has to fake that the others didn't:
 *   - setTimeout is a manual queue, so the 300ms input debounce can be flushed
 *     synchronously instead of slept through.
 *   - fetch returns a real Promise, so tests await a microtask flush after
 *     triggering a search. Tests are therefore async and run sequentially.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "global-search.js"), "utf8");

// Mirrors the data-* attributes base.html puts on <body>.
const I18N = {
    searchPlaceholder: "Search…",
    searchLoading: "Searching…",
    searchNoResults: "No results",
    searchError: "Search failed",
    kbdPress: "Press",
    kbdForSearch: "to search",
    kbdOr: "or",
    kbdForShortcuts: "for shortcuts",
};

// ---------------------------------------------------------------------------
// Minimal DOM stub
// ---------------------------------------------------------------------------

class FakeEvent {
    constructor(type, options = {}) {
        this.type = type;
        this.key = options.key;
        this.target = options.target || null;
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
        this._id = "";
        this._html = "";
        this._listeners = {};
        this._registry = registry;
        this.focused = false;
        this.blurred = false;
        this.scrolledIntoView = false;
        this.attributes = {};
    }

    // Registering on assignment is what makes document.getElementById work for
    // the elements the script creates itself (#global-search-results et al).
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
        child.remove();
        child.parentNode = this;
        this.children.push(child);
        return child;
    }

    insertBefore(child, reference) {
        child.remove();
        child.parentNode = this;
        const index = this.children.indexOf(reference);
        this.children.splice(index < 0 ? this.children.length : index, 0, child);
        return child;
    }

    remove() {
        if (!this.parentNode) return;
        const siblings = this.parentNode.children;
        const index = siblings.indexOf(this);
        if (index >= 0) siblings.splice(index, 1);
        this.parentNode = null;
    }

    get firstChild() {
        return this.children[0] || null;
    }

    getAttribute(name) {
        return this.attributes[name] ?? null;
    }

    focus() {
        this.focused = true;
    }
    blur() {
        this.blurred = true;
    }
    scrollIntoView() {
        this.scrolledIntoView = true;
    }

    /**
     * Parse the anchors displayResults() writes, so the rendered markup itself
     * is what the assertions read — href and label come back out of the HTML
     * rather than from the input data.
     */
    set innerHTML(html) {
        this._html = html;
        this.children = [];
        for (const match of html.matchAll(/<a href="([^"]*)"[\s\S]*?class="([^"]*)"[\s\S]*?>([\s\S]*?)<\/a>/g)) {
            const anchor = new FakeNode("a");
            anchor.attributes.href = match[1];
            anchor.className = match[2];
            anchor.textContent = match[3].trim();
            anchor.parentNode = this;
            this.children.push(anchor);
        }
    }
    get innerHTML() {
        return this._html;
    }

    querySelector(selector) {
        return this.querySelectorAll(selector)[0] || null;
    }

    querySelectorAll(selector) {
        const matches = (node) =>
            selector.startsWith(".")
                ? node.className.split(/\s+/).includes(selector.slice(1))
                : node.tagName === selector.toUpperCase();
        const found = [];
        const walk = (node) => {
            for (const child of node.children) {
                if (matches(child)) found.push(child);
                walk(child);
            }
        };
        walk(this);
        return found;
    }
}

/**
 * Build a page with a header + nav, load the script, and return handles.
 *
 * @param options.header    false to omit the .header element entirely
 * @param options.nav       false to omit the <nav> inside the header
 * @param options.toggles   ids to pre-create as existing header controls
 * @param options.results   payload for the next fetch
 * @param options.fetchFails reject the next fetch instead of resolving
 * @param options.deferFetches park each fetch in `pending` for manual settling
 */
function setupPage(options = {}) {
    const {
        header = true,
        nav = true,
        toggles = [],
        keyboardHint = false,
        readyState = "loading",
        i18n = I18N,
    } = options;

    const registry = new Map();
    const make = (tag) => new FakeNode(tag, registry);

    const document_ = make("#document");
    document_.readyState = readyState;

    const body = make("body");
    body.dataset = Object.assign({}, i18n);
    document_.body = body;
    body.parentNode = document_;
    document_.children.push(body);

    if (header) {
        const headerNode = make("header");
        headerNode.className = "header";
        body.appendChild(headerNode);
        if (nav) headerNode.appendChild(make("nav"));
        for (const id of toggles) {
            const toggle = make("button");
            toggle.id = id;
            headerNode.appendChild(toggle);
        }
        if (keyboardHint) {
            const hint = make("div");
            hint.id = "keyboard-hint";
            headerNode.appendChild(hint);
        }
    }

    document_.createElement = (tag) => make(tag);
    document_.getElementById = (id) => registry.get(id) || null;

    // Handles are monotonic and never reused, as in a browser. The earlier
    // array-index stub recycled them after a flush, so a type/flush/type
    // sequence handed out the same id twice and the second clearTimeout could
    // cancel a live timer instead of the dead one it was aimed at.
    let nextTimerId = 1;
    const timers = new Map();
    const fetches = [];
    const navigations = [];
    const pending = [];

    const state = {
        results: options.results || [],
        fetchFails: Boolean(options.fetchFails),
        deferFetches: Boolean(options.deferFetches),
    };

    const window_ = make("#window");
    Object.defineProperty(window_, "location", {
        value: {
            set href(value) {
                navigations.push(value);
            },
            get href() {
                return navigations[navigations.length - 1];
            },
        },
    });

    const sandbox = {
        document: document_,
        window: window_,
        console: { error() {}, log() {} },
        // Ids are 1-based: the HTML spec requires a timer handle "greater than
        // zero", and handleSearchInput leans on that with `if (searchTimeout)`.
        // A 0-based stub would make the first timer falsy and fake a debounce
        // failure that no browser can produce.
        setTimeout: (fn, delay) => {
            const id = nextTimerId++;
            timers.set(id, { fn, delay });
            return id;
        },
        clearTimeout: (id) => {
            timers.delete(id);
        },
        // With deferFetches the promise is parked in `pending` instead of
        // settling, so a test can land two overlapping responses in whatever
        // order it likes — the only way to reproduce a race that in a browser
        // depends on which request the network happens to finish first.
        fetch: (url) => {
            fetches.push(url);
            if (state.deferFetches) {
                return new Promise((resolve, reject) => {
                    pending.push({
                        url,
                        resolveWith: (results) =>
                            resolve({ json: () => Promise.resolve({ results }) }),
                        rejectWith: () => reject(new Error("network")),
                    });
                });
            }
            return state.fetchFails
                ? Promise.reject(new Error("network"))
                : Promise.resolve({ json: () => Promise.resolve({ results: state.results }) });
        },
    };
    sandbox.window.location = window_.location;

    vm.runInNewContext(SOURCE, sandbox);
    if (readyState === "loading") document_.dispatchEvent(new FakeEvent("DOMContentLoaded"));

    return {
        document: document_,
        body,
        state,
        fetches,
        navigations,
        input: () => registry.get("global-search-input") || null,
        dropdown: () => registry.get("global-search-results") || null,
        controls: () => registry.get("header-controls") || null,
        hint: () => registry.get("keyboard-hint") || null,
        registry,
        /** Run every pending timer callback (the 300ms debounce, the blur delay). */
        flushTimers() {
            const due = [...timers.values()];
            timers.clear();
            for (const timer of due) timer.fn();
        },
        /** Parked fetches, oldest first, when deferFetches is on. */
        pending,
        /** Let the fetch promise chain settle. */
        flushAsync() {
            return new Promise((resolve) => setImmediate(resolve));
        },
        type(value) {
            const input = registry.get("global-search-input");
            input.value = value;
            input.dispatchEvent(new FakeEvent("input", { target: input }));
        },
        press(key, target) {
            const input = registry.get("global-search-input");
            const event = new FakeEvent("keydown", { key, target: target || input });
            (target || input).dispatchEvent(event);
            return event;
        },
        pressGlobal(key, target) {
            const event = new FakeEvent("keydown", { key, target });
            document_.dispatchEvent(event);
            return event;
        },
        /** Type, flush the debounce, and let the fetch resolve. */
        async search(query) {
            this.type(query);
            this.flushTimers();
            await this.flushAsync();
        },
    };
}

// ---------------------------------------------------------------------------
// Test framework (async variant of form_draft_guard.test.js)
// ---------------------------------------------------------------------------

let failures = 0;
const queue = [];

function test(name, fn) {
    queue.push({ name, fn });
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

function assertNotContains(haystack, needle, message) {
    if (String(haystack).includes(needle)) {
        throw new Error(`${message}\n  Expected NOT to contain: ${needle}\n  Actual: ${haystack}`);
    }
}

const RESULTS = [
    { label: "👤 XX-1 — Max Mustermann", url: "/clients/1/" },
    { label: "📄 XX-2 - YY (15.01.2026)", url: "/invoices/2/" },
    { label: "📬 Anna Schmidt (Neu)", url: "/inquiries/3/" },
];

// --- initialisation ---------------------------------------------------------

test("does nothing when the page has no header", () => {
    const page = setupPage({ header: false });
    assertEquals(page.input(), null, "no header means no search box");
});

test("does nothing when the header has no nav", () => {
    const page = setupPage({ nav: false });
    assertEquals(page.input(), null, "no nav means no search box");
});

test("builds the search box and a controls wrapper", () => {
    const page = setupPage();
    assertTrue(page.input() !== null, "search input exists");
    assertTrue(page.controls() !== null, "controls wrapper exists");
});

test("moves the existing header toggles into the controls wrapper", () => {
    const page = setupPage({ toggles: ["langToggle", "privacyToggle", "themeToggle"] });
    const ids = page.controls().children.map((c) => c.id);
    for (const id of ["langToggle", "privacyToggle", "themeToggle"]) {
        assertContains(ids.join(","), id, `${id} moved into the wrapper`);
    }
});

test("puts the search box before the toggles", () => {
    const page = setupPage({ toggles: ["themeToggle"] });
    assertEquals(
        page.controls().firstChild.id,
        "global-search-container",
        "search comes first in the controls row"
    );
});

test("initialises immediately when the document is already loaded", () => {
    const page = setupPage({ readyState: "complete" });
    assertTrue(page.input() !== null, "no DOMContentLoaded needed when readyState is complete");
});

// --- i18n plumbing ----------------------------------------------------------

test("placeholder comes from the body dataset, not the source", () => {
    const page = setupPage({ i18n: Object.assign({}, I18N, { searchPlaceholder: "SUCHEN" }) });
    assertEquals(page.input().placeholder, "SUCHEN", "placeholder is translated via data-*");
});

test("the keyboard hint is rebuilt from the body dataset", () => {
    const page = setupPage({ keyboardHint: true });
    const html = page.hint().innerHTML;
    for (const key of ["kbdPress", "kbdForSearch", "kbdOr", "kbdForShortcuts"]) {
        assertContains(html, I18N[key], `hint uses the ${key} string from data-*`);
    }
});

test("a missing keyboard hint is tolerated", () => {
    const page = setupPage();
    assertEquals(page.hint(), null, "no hint element, and init did not throw");
});

// --- debounce and querying --------------------------------------------------

test("debounces input into a single request", async () => {
    const page = setupPage({ results: RESULTS });
    page.type("Ma");
    page.type("Max");
    page.type("Maxi");
    page.flushTimers();
    await page.flushAsync();
    assertEquals(page.fetches.length, 1, "three keystrokes produce one request");
    assertContains(page.fetches[0], "q=Maxi", "the last query wins");
});

test("an empty query clears results without querying", async () => {
    const page = setupPage({ results: RESULTS });
    await page.search("Max");
    page.type("");
    page.flushTimers();
    await page.flushAsync();
    assertEquals(page.fetches.length, 1, "clearing must not fire a request");
    assertEquals(page.dropdown().style.display, "none", "dropdown hides when cleared");
});

test("the query is URL-encoded", async () => {
    const page = setupPage({ results: [] });
    await page.search("c:Müller & Co");
    assertContains(page.fetches[0], encodeURIComponent("c:Müller & Co"), "query is encoded");
});

test("shows the loading state while the request is in flight", () => {
    const page = setupPage({ results: RESULTS });
    page.type("Max");
    page.flushTimers();
    assertContains(page.dropdown().innerHTML, I18N.searchLoading, "loading label shown");
});

// --- rendering --------------------------------------------------------------

test("renders one link per result, with its url", async () => {
    const page = setupPage({ results: RESULTS });
    await page.search("Max");
    const items = page.dropdown().querySelectorAll(".search-result-item");
    assertEquals(items.length, 3, "three results render three links");
    assertEquals(items[0].getAttribute("href"), "/clients/1/", "first href");
    assertEquals(items[2].getAttribute("href"), "/inquiries/3/", "third href");
});

test("escapes HTML in result labels", async () => {
    // A client legitimately named with an ampersand or angle brackets must not
    // break the markup — search_views.py builds the label from full_name.
    const page = setupPage({
        results: [{ label: "👤 XX-1 — Müller & Co <GmbH>", url: "/clients/1/" }],
    });
    await page.search("Mueller");
    const html = page.dropdown().innerHTML;
    assertContains(html, "&amp;", "ampersand escaped");
    assertContains(html, "&lt;GmbH&gt;", "angle brackets escaped");
    assertNotContains(html, "<GmbH>", "raw markup must not reach the DOM");
});

test("escapes HTML in result urls too", async () => {
    // The href is written into markup, so an & in a query string has to be
    // encoded as &amp; to be a well-formed attribute. (The stub reads the raw
    // attribute text rather than decoding it, so this asserts on the markup.)
    const page = setupPage({
        results: [{ label: "👤 XX-1", url: "/clients/?tag=a&status=b" }],
    });
    await page.search("x");
    assertContains(page.dropdown().innerHTML, "tag=a&amp;status=b", "url escaped in the href");
});

test("escapes a script tag smuggled through a label", async () => {
    const page = setupPage({
        results: [{ label: "<script>window.pwned=1</script>", url: "/clients/1/" }],
    });
    await page.search("x");
    assertNotContains(page.dropdown().innerHTML, "<script>", "no raw script tag");
});

test("shows the no-results label for an empty payload", async () => {
    const page = setupPage({ results: [] });
    await page.search("zzz");
    assertContains(page.dropdown().innerHTML, I18N.searchNoResults, "no-results label shown");
});

test("shows the error label when the request fails", async () => {
    const page = setupPage({ fetchFails: true });
    await page.search("Max");
    assertContains(page.dropdown().innerHTML, I18N.searchError, "error label shown");
});

test("a failed request drops the previous results", async () => {
    // Without this, Enter still navigates to whatever was showing before the
    // failure — a stale row from a query the user has already replaced.
    const page = setupPage({ results: RESULTS });
    await page.search("Max");
    page.press("ArrowDown");
    page.state.fetchFails = true;
    await page.search("zzz");
    page.press("Enter");
    assertEquals(page.navigations.length, 0, "no navigation to a stale result after an error");
});

// --- overlapping requests ---------------------------------------------------
//
// The 300ms debounce spaces requests out but does not serialise them: pause
// mid-word and two searches are in flight at once. fetch settles in completion
// order, not call order, so whichever request the network finishes last is the
// one that writes the dropdown. These drive both responses by hand.

const OLD_RESULTS = [{ label: "stale hit", url: "/clients/9/" }];
const NEW_RESULTS = [{ label: "fresh hit", url: "/clients/1/" }];

/** Type two queries, leaving both requests parked and unsettled. */
async function twoInFlight() {
    const page = setupPage({ deferFetches: true });
    await page.search("sch");
    await page.search("schmidt");
    assertEquals(page.fetches.length, 2, "sanity: both requests were actually issued");
    return page;
}

test("a slow response for an earlier query cannot overwrite a newer one", async () => {
    const page = await twoInFlight();
    page.pending[1].resolveWith(NEW_RESULTS);
    await page.flushAsync();
    page.pending[0].resolveWith(OLD_RESULTS);
    await page.flushAsync();

    assertContains(page.dropdown().innerHTML, "fresh hit", "the newest query's results stand");
    assertNotContains(page.dropdown().innerHTML, "stale hit", "the superseded response is dropped");
});

test("Enter after a superseded response goes to the newer result", async () => {
    // The visible symptom of the same bug: currentResults is what Enter reads,
    // so a stale overwrite sends the user to a row for a query they replaced.
    const page = await twoInFlight();
    page.pending[1].resolveWith(NEW_RESULTS);
    await page.flushAsync();
    page.pending[0].resolveWith(OLD_RESULTS);
    await page.flushAsync();

    page.press("ArrowDown");
    page.press("Enter");
    assertEquals(page.navigations, ["/clients/1/"], "navigates to the fresh result");
});

test("a superseded response does not reset the selection", async () => {
    // The stale branch would set selectedIndex = -1, so a user who had already
    // arrowed onto a row would find Enter doing nothing.
    const page = await twoInFlight();
    page.pending[1].resolveWith(NEW_RESULTS);
    await page.flushAsync();
    page.press("ArrowDown");
    page.pending[0].resolveWith(OLD_RESULTS);
    await page.flushAsync();

    page.press("Enter");
    assertEquals(page.navigations, ["/clients/1/"], "the selection survived the late response");
});

test("a stale failure does not clear the newer query's results", async () => {
    const page = await twoInFlight();
    page.pending[1].resolveWith(NEW_RESULTS);
    await page.flushAsync();
    page.pending[0].rejectWith();
    await page.flushAsync();

    assertContains(page.dropdown().innerHTML, "fresh hit", "results survive the late failure");
    assertNotContains(page.dropdown().innerHTML, I18N.searchError, "and no error is shown");
    page.press("ArrowDown");
    page.press("Enter");
    assertEquals(page.navigations, ["/clients/1/"], "still navigable");
});

test("a stale success does not paper over the newer query's failure", async () => {
    // The mirror case: the newest request is the one that failed, so the error
    // must stay put and a late success must not offer rows to navigate to.
    const page = await twoInFlight();
    page.pending[1].rejectWith();
    await page.flushAsync();
    page.pending[0].resolveWith(OLD_RESULTS);
    await page.flushAsync();

    assertContains(page.dropdown().innerHTML, I18N.searchError, "the error stands");
    assertNotContains(page.dropdown().innerHTML, "stale hit", "no rows from the late success");
    page.press("ArrowDown");
    page.press("Enter");
    assertEquals(page.navigations.length, 0, "nothing to navigate to");
});

test("clearing the box retires the request still in flight", async () => {
    const page = setupPage({ deferFetches: true });
    await page.search("sch");
    page.type("");

    page.pending[0].resolveWith(OLD_RESULTS);
    await page.flushAsync();

    assertEquals(page.dropdown().style.display, "none", "the dropdown stays hidden");
    assertNotContains(page.dropdown().innerHTML, "stale hit", "and stays empty of stale rows");
    page.press("ArrowDown");
    page.press("Enter");
    assertEquals(page.navigations.length, 0, "nothing selectable behind the empty box");
});

test("responses that arrive in order still render the newest", async () => {
    // The guard must reject only what is actually superseded — if it were keyed
    // on anything but recency, the common in-order case would render nothing.
    const page = await twoInFlight();
    page.pending[0].resolveWith(OLD_RESULTS);
    await page.flushAsync();
    page.pending[1].resolveWith(NEW_RESULTS);
    await page.flushAsync();

    assertContains(page.dropdown().innerHTML, "fresh hit", "the last word wins as usual");
    assertNotContains(page.dropdown().innerHTML, "stale hit", "the earlier one is replaced");
});

test("a single request is unaffected by the guard", async () => {
    const page = setupPage({ deferFetches: true });
    await page.search("Max");
    page.pending[0].resolveWith(NEW_RESULTS);
    await page.flushAsync();
    assertContains(page.dropdown().innerHTML, "fresh hit", "the ordinary path still renders");
});

// --- keyboard navigation ----------------------------------------------------

test("ArrowDown moves the selection and stops at the last result", async () => {
    const page = setupPage({ results: RESULTS });
    await page.search("Max");
    for (let i = 0; i < 5; i++) page.press("ArrowDown");
    page.press("Enter");
    assertEquals(page.navigations, ["/inquiries/3/"], "selection clamps at the last result");
});

test("ArrowUp walks back and stops above the first result", async () => {
    const page = setupPage({ results: RESULTS });
    await page.search("Max");
    page.press("ArrowDown");
    page.press("ArrowDown");
    page.press("ArrowUp");
    page.press("Enter");
    assertEquals(page.navigations, ["/clients/1/"], "back to the first result");
});

test("ArrowUp cannot push the selection below the first result", async () => {
    // Without the clamp at -1, three ArrowUps leave the index at -4 and the
    // following ArrowDown lands on -3 — so the first result becomes
    // unreachable and Enter silently does nothing.
    const page = setupPage({ results: RESULTS });
    await page.search("Max");
    page.press("ArrowUp");
    page.press("ArrowUp");
    page.press("ArrowUp");
    page.press("ArrowDown");
    page.press("Enter");
    assertEquals(page.navigations, ["/clients/1/"], "one ArrowDown reaches the first result");
});

test("Enter does nothing while no result is selected", async () => {
    const page = setupPage({ results: RESULTS });
    await page.search("Max");
    page.press("Enter");
    assertEquals(page.navigations.length, 0, "Enter without a selection is inert");
});

test("arrow keys are inert before any results exist", () => {
    const page = setupPage({ results: RESULTS });
    const event = page.press("ArrowDown");
    assertTrue(!event.defaultPrevented, "no results means the key is not intercepted");
});

test("Escape hides the dropdown and blurs the input", async () => {
    const page = setupPage({ results: RESULTS });
    await page.search("Max");
    page.press("Escape");
    assertEquals(page.dropdown().style.display, "none", "dropdown hidden");
    assertTrue(page.input().blurred, "input blurred");
});

test("the selected row is highlighted and scrolled into view", async () => {
    const page = setupPage({ results: RESULTS });
    await page.search("Max");
    page.press("ArrowDown");
    const items = page.dropdown().querySelectorAll(".search-result-item");
    assertEquals(items[0].style.background, "var(--color-dropdown-hover)", "first row highlighted");
    assertEquals(items[1].style.background, "transparent", "others cleared");
    assertTrue(items[0].scrolledIntoView, "selected row scrolled into view");
});

// --- the "/" shortcut -------------------------------------------------------

test("slash focuses the search box", () => {
    const page = setupPage();
    const elsewhere = new FakeNode("div");
    const event = page.pressGlobal("/", elsewhere);
    assertTrue(page.input().focused, "search input focused");
    assertTrue(event.defaultPrevented, "the slash itself is swallowed");
});

test("slash is ignored while typing in a field", () => {
    for (const tag of ["input", "textarea", "select"]) {
        const page = setupPage();
        const field = new FakeNode(tag);
        page.pressGlobal("/", field);
        assertTrue(!page.input().focused, `slash inside <${tag}> must type normally`);
    }
});

// ---------------------------------------------------------------------------

(async () => {
    console.log("\n🔍 Running global-search Tests\n");
    for (const { name, fn } of queue) {
        try {
            await fn();
            console.log(`✓ ${name}`);
        } catch (error) {
            failures++;
            console.error(`✗ ${name}`);
            console.error(`  ${error.message}`);
        }
    }
    if (failures > 0) {
        console.error(`\n❌ ${failures} test(s) failed\n`);
        process.exit(1);
    }
    console.log("\n✅ All tests passed!\n");
})();

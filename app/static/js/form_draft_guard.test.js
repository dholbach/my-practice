/**
 * Tests for form_draft_guard.js (M-PAT-06)
 * Run with: node form_draft_guard.test.js
 *
 * form_draft_guard.js is a browser IIFE with no exports — it wires itself to
 * document/window/localStorage on load. So each test builds a throwaway DOM
 * stub, loads the real source into it via `vm`, and drives it through events.
 * The stub is deliberately hand-rolled rather than jsdom: the repo runs JS
 * tests as plain `node <file>` with no test framework or devDependencies
 * (see dev.py cmd_test_js), and a DOM dependency would have to exist inside
 * the Docker image too.
 *
 * setTimeout is stubbed as a manual queue so the 500ms input debounce can be
 * flushed synchronously instead of slept through.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "form_draft_guard.js"), "utf8");

// ---------------------------------------------------------------------------
// Minimal DOM stub
// ---------------------------------------------------------------------------

class FakeEvent {
    constructor(type, options = {}) {
        this.type = type;
        this.bubbles = Boolean(options.bubbles);
        this.detail = options.detail;
        this.target = null;
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
        this.id = "";
        this.className = "";
        this._listeners = {};
        this._html = "";
    }

    addEventListener(type, fn) {
        (this._listeners[type] = this._listeners[type] || []).push(fn);
    }

    // Walks up parentNode so bubbling events reach `document`, which is how
    // client_detail.html listens for draftguard:dirty.
    dispatchEvent(event) {
        if (!event.target) event.target = this;
        let node = this;
        while (node) {
            for (const fn of node._listeners[event.type] || []) fn.call(node, event);
            if (!event.bubbles) break;
            node = node.parentNode;
        }
        return !event.defaultPrevented;
    }

    appendChild(child) {
        child.parentNode = this;
        this.children.push(child);
        return child;
    }

    insertBefore(child, reference) {
        child.parentNode = this;
        const index = this.children.indexOf(reference);
        this.children.splice(index < 0 ? this.children.length : index, 0, child);
        return child;
    }

    remove() {
        if (!this.parentNode) return;
        const index = this.parentNode.children.indexOf(this);
        if (index >= 0) this.parentNode.children.splice(index, 1);
        this.parentNode = null;
    }

    // Only needs to be good enough for the restore banner: pull out the
    // data-action buttons the guard immediately queries back for.
    set innerHTML(html) {
        this._html = html;
        this.children = [];
        for (const match of html.matchAll(/data-action="([^"]+)"/g)) {
            const button = new FakeNode("button");
            button.dataset.action = match[1];
            this.appendChild(button);
        }
    }
    get innerHTML() {
        return this._html;
    }

    querySelector(selector) {
        const match = selector.match(/\[data-action="([^"]+)"\]/);
        if (!match) return null;
        return this.children.find((c) => c.dataset.action === match[1]) || null;
    }
}

function makeField(name, value, type = "text", checked = false) {
    const el = new FakeNode("input");
    el.name = name;
    el.value = value;
    el.type = type;
    el.checked = checked;
    return el;
}

/**
 * Build a page containing one or more guarded forms and load the guard into it.
 * Returns handles for driving and inspecting the result.
 */
function setupPage(options = {}) {
    const { forms = [], pathname = "/clients/1/", search = "" } = options;

    const document_ = new FakeNode("#document");
    const container = new FakeNode("div");
    container.parentNode = document_;

    const store = new Map(Object.entries(options.storage || {}));
    const timers = [];

    const formNodes = forms.map((spec) => {
        const form = new FakeNode("form");
        form.id = spec.id || "";
        form.elements = spec.fields || [];
        form.dataset = Object.assign(
            {
                draftGuard: "",
                draftMessage: "You have an unsaved draft.",
                draftRestoreLabel: "Restore draft",
                draftDiscardLabel: "Discard",
            },
            spec.dataset || {}
        );
        container.appendChild(form);
        return form;
    });

    document_.createElement = (tag) => new FakeNode(tag);
    document_.querySelectorAll = (selector) =>
        selector === "form[data-draft-guard]" ? formNodes : [];

    const window_ = new FakeNode("#window");
    window_.location = { pathname, search };

    const sandbox = {
        document: document_,
        window: window_,
        CustomEvent: FakeEvent,
        localStorage: {
            getItem: (k) => (store.has(k) ? store.get(k) : null),
            setItem: (k, v) => store.set(k, String(v)),
            removeItem: (k) => store.delete(k),
        },
        setTimeout: (fn) => {
            timers.push(fn);
            return timers.length - 1;
        },
        clearTimeout: (id) => {
            if (typeof id === "number") timers[id] = null;
        },
        console,
    };

    vm.runInNewContext(SOURCE, sandbox);
    document_.dispatchEvent(new FakeEvent("DOMContentLoaded"));

    // Record dirty events at document level — the bubbling path the real page uses.
    const dirtyEvents = [];
    document_.addEventListener("draftguard:dirty", (e) => dirtyEvents.push(e.detail.dirty));

    return {
        document: document_,
        container,
        window: window_,
        forms: formNodes,
        form: formNodes[0],
        store,
        dirtyEvents,
        flushTimers() {
            const pending = timers.splice(0, timers.length);
            for (const fn of pending) if (fn) fn();
        },
        banner() {
            return container.children.find((c) => c.className === "draft-restore-banner") || null;
        },
        beforeunload() {
            const event = new FakeEvent("beforeunload");
            window_.dispatchEvent(event);
            return event;
        },
    };
}

// ---------------------------------------------------------------------------
// Test framework (mirrors chart_utils.test.js, but tracks failures)
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

function assertNull(value, message) {
    if (value !== null && value !== undefined) {
        throw new Error(`${message}\n  Got: ${JSON.stringify(value)}`);
    }
}

const KEY = "form_draft:/clients/1/#notes-form";

function savedFields(page, key = KEY) {
    const raw = page.store.get(key);
    return raw ? JSON.parse(raw).fields : null;
}

function basicForm(fields) {
    return {
        id: "notes-form",
        fields: fields || [makeField("case_notes", "")],
    };
}

// The guard snapshots each field's value as a baseline when the page loads,
// then only treats a form as dirty once a field's value differs from that
// baseline. Tests simulate "the user typed something" by building the form
// with its pre-edit (often blank) value, then calling this to apply the
// post-edit value — exactly like a real browser mutates el.value before
// firing input/change.
function typeInto(field, value) {
    field.value = value;
}

console.log("\n📝 Running form_draft_guard Tests\n");

// --- dirty-state signalling (the draftguard:dirty contract) -----------------

test("draftguard:dirty fires on first input and bubbles to document", () => {
    const page = setupPage({ forms: [basicForm()] });
    typeInto(page.form.elements[0], "x");
    page.form.dispatchEvent(new FakeEvent("input", { bubbles: true }));
    assertEquals(page.dirtyEvents, [true], "should emit exactly one dirty=true");
});

test("draftguard:dirty is not re-emitted while already dirty", () => {
    const page = setupPage({ forms: [basicForm()] });
    typeInto(page.form.elements[0], "x");
    page.form.dispatchEvent(new FakeEvent("input", { bubbles: true }));
    page.form.dispatchEvent(new FakeEvent("input", { bubbles: true }));
    page.form.dispatchEvent(new FakeEvent("change", { bubbles: true }));
    assertEquals(page.dirtyEvents, [true], "repeat edits should not re-announce dirty");
});

test("draftguard:dirty emits dirty=false on submit", () => {
    const page = setupPage({ forms: [basicForm()] });
    typeInto(page.form.elements[0], "x");
    page.form.dispatchEvent(new FakeEvent("input", { bubbles: true }));
    page.form.dispatchEvent(new FakeEvent("submit", { bubbles: true }));
    assertEquals(page.dirtyEvents, [true, false], "should announce clean after submit");
});

test("submitting a never-edited form emits nothing", () => {
    const page = setupPage({ forms: [basicForm()] });
    page.form.dispatchEvent(new FakeEvent("submit", { bubbles: true }));
    assertEquals(page.dirtyEvents, [], "clean form should stay silent");
});

test("an input/change event with no actual value change stays clean", () => {
    // e.g. a field regaining focus, or a non-blank server-rendered default
    // (a boilerplate notes template) that the user never touched.
    const page = setupPage({ forms: [basicForm([makeField("case_notes", "template text")])] });
    page.form.dispatchEvent(new FakeEvent("change", { bubbles: true }));
    assertEquals(page.dirtyEvents, [], "unchanged value should not count as an edit");
    assertNull(page.store.get(KEY), "nothing should be saved");
});

test("editing a field back to its original value clears dirty state and any saved draft", () => {
    const field = makeField("case_notes", "original");
    const page = setupPage({ forms: [basicForm([field])] });
    typeInto(field, "typing...");
    page.form.dispatchEvent(new FakeEvent("change", { bubbles: true }));
    assertTrue(page.store.has(KEY), "draft exists mid-edit");
    typeInto(field, "original");
    page.form.dispatchEvent(new FakeEvent("change", { bubbles: true }));
    assertEquals(page.dirtyEvents, [true, false], "reverting should announce clean");
    assertNull(page.store.get(KEY), "reverted edit should not leave a stale draft");
});

test("dirty event carries the form as target, so the owning tab is identifiable", () => {
    const page = setupPage({ forms: [basicForm()] });
    let target = null;
    page.document.addEventListener("draftguard:dirty", (e) => {
        target = e.target;
    });
    typeInto(page.form.elements[0], "x");
    page.form.dispatchEvent(new FakeEvent("input", { bubbles: true }));
    assertTrue(target === page.form, "event target should be the guarded form");
});

// --- autosave --------------------------------------------------------------

test("input autosaves after the debounce flushes", () => {
    const field = makeField("case_notes", "");
    const page = setupPage({ forms: [basicForm([field])] });
    typeInto(field, "hello");
    page.form.dispatchEvent(new FakeEvent("input", { bubbles: true }));
    assertNull(page.store.get(KEY), "should not save before the debounce fires");
    page.flushTimers();
    assertEquals(savedFields(page), { case_notes: "hello" }, "should save after debounce");
});

test("change autosaves immediately, without waiting for the debounce", () => {
    const field = makeField("case_notes", "");
    const page = setupPage({ forms: [basicForm([field])] });
    typeInto(field, "picked");
    page.form.dispatchEvent(new FakeEvent("change", { bubbles: true }));
    assertEquals(savedFields(page), { case_notes: "picked" }, "change should save at once");
});

test("csrfmiddlewaretoken is never persisted", () => {
    const body = makeField("body", "");
    const page = setupPage({
        forms: [basicForm([makeField("csrfmiddlewaretoken", "secret-token"), body])],
    });
    typeInto(body, "text");
    page.form.dispatchEvent(new FakeEvent("change", { bubbles: true }));
    assertEquals(savedFields(page), { body: "text" }, "CSRF token must be excluded");
});

test("hidden, submit, button and file inputs are excluded", () => {
    const body = makeField("body", "");
    const page = setupPage({
        forms: [
            basicForm([
                body,
                makeField("next", "/somewhere/", "hidden"),
                makeField("go", "Save", "submit"),
                makeField("cancel", "Cancel", "button"),
                makeField("receipt", "C:\\fakepath\\x.pdf", "file"),
            ]),
        ],
    });
    typeInto(body, "text");
    page.form.dispatchEvent(new FakeEvent("change", { bubbles: true }));
    assertEquals(savedFields(page), { body: "text" }, "only real inputs should persist");
});

test("unnamed fields are ignored", () => {
    const body = makeField("body", "");
    const page = setupPage({ forms: [basicForm([makeField("", "orphan"), body])] });
    typeInto(body, "x");
    page.form.dispatchEvent(new FakeEvent("change", { bubbles: true }));
    assertEquals(savedFields(page), { body: "x" }, "fields without a name are skipped");
});

test("checkbox groups persist as a list of checked values only", () => {
    const calm = makeField("mood", "calm", "checkbox", true);
    const page = setupPage({
        forms: [
            basicForm([
                calm,
                makeField("mood", "tense", "checkbox", false),
                makeField("mood", "tired", "checkbox", true),
            ]),
        ],
    });
    calm.checked = false; // baseline had it unchecked; this is the "edit"
    page.form.dispatchEvent(new FakeEvent("change", { bubbles: true }));
    assertEquals(savedFields(page), { mood: ["tired"] }, "unchecked boxes are dropped");
});

test("radio groups persist the selected value", () => {
    const intake = makeField("session_type", "intake", "radio", false);
    const followup = makeField("session_type", "followup", "radio", false);
    const page = setupPage({ forms: [basicForm([intake, followup])] });
    followup.checked = true;
    page.form.dispatchEvent(new FakeEvent("change", { bubbles: true }));
    assertEquals(savedFields(page), { session_type: ["followup"] }, "selected radio persists");
});

// --- draft key scoping -----------------------------------------------------

test("draft key includes pathname, query string and form id", () => {
    const body = makeField("body", "");
    const page = setupPage({
        forms: [basicForm([body])],
        pathname: "/clients/7/",
        search: "?tab=protokoll",
    });
    typeInto(body, "x");
    page.form.dispatchEvent(new FakeEvent("change", { bubbles: true }));
    assertEquals(
        [...page.store.keys()],
        ["form_draft:/clients/7/?tab=protokoll#notes-form"],
        "key should scope by URL and form id"
    );
});

test("two guarded forms on one page keep separate drafts", () => {
    const first = makeField("body", "");
    const second = makeField("body", "");
    const page = setupPage({
        forms: [
            { id: "notes-form", fields: [first] },
            { id: "supervision-form", fields: [second] },
        ],
    });
    typeInto(first, "first");
    typeInto(second, "second");
    page.forms[0].dispatchEvent(new FakeEvent("change", { bubbles: true }));
    page.forms[1].dispatchEvent(new FakeEvent("change", { bubbles: true }));
    assertEquals(savedFields(page, KEY), { body: "first" }, "first form's draft");
    assertEquals(
        savedFields(page, "form_draft:/clients/1/#supervision-form"),
        { body: "second" },
        "second form's draft"
    );
});

// --- restore banner --------------------------------------------------------

test("stored draft with content shows the restore banner", () => {
    const page = setupPage({
        forms: [basicForm()],
        storage: { [KEY]: JSON.stringify({ fields: { case_notes: "recovered text" } }) },
    });
    assertTrue(page.banner() !== null, "banner should be inserted before the form");
});

test("stored draft that is entirely blank is discarded, not offered", () => {
    const page = setupPage({
        forms: [basicForm()],
        storage: { [KEY]: JSON.stringify({ fields: { case_notes: "   " } }) },
    });
    assertNull(page.banner(), "whitespace-only draft should not prompt");
    assertNull(page.store.get(KEY), "and should be cleared from storage");
});

test("malformed stored draft is cleared instead of throwing", () => {
    const page = setupPage({ forms: [basicForm()], storage: { [KEY]: "{not json" } });
    assertNull(page.banner(), "no banner for unparseable draft");
    assertNull(page.store.get(KEY), "corrupt entry should be cleared");
});

test("stored draft identical to a non-blank server-rendered default is discarded, not offered", () => {
    // e.g. a boilerplate notes template pre-filled server-side — the same
    // text sitting in localStorage isn't an edit worth restoring.
    const page = setupPage({
        forms: [basicForm([makeField("case_notes", "template text")])],
        storage: { [KEY]: JSON.stringify({ fields: { case_notes: "template text" } }) },
    });
    assertNull(page.banner(), "identical-to-baseline draft should not prompt");
    assertNull(page.store.get(KEY), "and should be cleared from storage");
});

test("restore applies the saved fields, marks dirty and dismisses the banner", () => {
    const field = makeField("case_notes", "");
    const page = setupPage({
        forms: [basicForm([field])],
        storage: { [KEY]: JSON.stringify({ fields: { case_notes: "recovered text" } }) },
    });
    page.banner().querySelector('[data-action="restore"]')._listeners.click[0]();
    assertEquals(field.value, "recovered text", "field should be repopulated");
    assertEquals(page.dirtyEvents, [true], "restored content counts as unsaved");
    assertNull(page.banner(), "banner should be removed after restoring");
});

test("discard clears the stored draft and leaves the field untouched", () => {
    const field = makeField("case_notes", "");
    const page = setupPage({
        forms: [basicForm([field])],
        storage: { [KEY]: JSON.stringify({ fields: { case_notes: "recovered text" } }) },
    });
    page.banner().querySelector('[data-action="discard"]')._listeners.click[0]();
    assertNull(page.store.get(KEY), "draft should be gone");
    assertEquals(field.value, "", "field should not be repopulated");
    assertNull(page.banner(), "banner should be removed after discarding");
});

test("checkbox state is restored, including unchecking boxes not in the draft", () => {
    const calm = makeField("mood", "calm", "checkbox", false);
    const tense = makeField("mood", "tense", "checkbox", true);
    const page = setupPage({
        forms: [basicForm([calm, tense])],
        storage: { [KEY]: JSON.stringify({ fields: { mood: ["calm"] } }) },
    });
    page.banner().querySelector('[data-action="restore"]')._listeners.click[0]();
    assertTrue(calm.checked, "checkbox in the draft should be checked");
    assertTrue(!tense.checked, "checkbox absent from the draft should be unchecked");
});

// --- submit and navigation guard -------------------------------------------

test("submit clears the stored draft", () => {
    const body = makeField("body", "");
    const page = setupPage({ forms: [basicForm([body])] });
    typeInto(body, "text");
    page.form.dispatchEvent(new FakeEvent("change", { bubbles: true }));
    assertTrue(page.store.has(KEY), "draft exists before submit");
    page.form.dispatchEvent(new FakeEvent("submit", { bubbles: true }));
    assertNull(page.store.get(KEY), "submitting should clear the draft");
});

test("beforeunload is blocked while a form is dirty", () => {
    const page = setupPage({ forms: [basicForm()] });
    assertTrue(!page.beforeunload().defaultPrevented, "clean page should navigate freely");
    typeInto(page.form.elements[0], "x");
    page.form.dispatchEvent(new FakeEvent("input", { bubbles: true }));
    assertTrue(page.beforeunload().defaultPrevented, "dirty page should warn");
});

test("beforeunload stops warning once the form is submitted", () => {
    const page = setupPage({ forms: [basicForm()] });
    typeInto(page.form.elements[0], "x");
    page.form.dispatchEvent(new FakeEvent("input", { bubbles: true }));
    page.form.dispatchEvent(new FakeEvent("submit", { bubbles: true }));
    assertTrue(!page.beforeunload().defaultPrevented, "submitted form should not warn");
});

// ---------------------------------------------------------------------------

if (failures > 0) {
    console.error(`\n❌ ${failures} test(s) failed\n`);
    process.exit(1);
}
console.log("\n✅ All tests passed!\n");

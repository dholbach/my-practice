/**
 * Tests for expense_form.js — the receipt drag-and-drop dropzone.
 * Run with: node expense_form.test.js
 *
 * Same approach as the other JS suites here: the script is a browser IIFE with
 * no exports, so the test builds a throwaway DOM stub, loads the real source
 * into it via `vm`, fires DOMContentLoaded, and drives it through events.
 * Hand-rolled rather than jsdom because the repo runs JS tests as plain
 * `node <file>` with no framework or devDependencies (see dev.py cmd_test_js).
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "expense_form.js"), "utf8");

// ---------------------------------------------------------------------------
// Minimal DOM stub
// ---------------------------------------------------------------------------

class FakeEvent {
    constructor(type, options = {}) {
        this.type = type;
        this.target = options.target || null;
        this.relatedTarget = options.relatedTarget || null;
        this.dataTransfer = options.dataTransfer || null;
        this.defaultPrevented = false;
    }
    preventDefault() {
        this.defaultPrevented = true;
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
}

class FakeNode {
    constructor(tagName = "div", registry = null) {
        this.tagName = tagName.toUpperCase();
        this.children = [];
        this.parentNode = null;
        this.classList = new FakeClassList();
        this.className = "";
        this.textContent = "";
        this._id = "";
        this._listeners = {};
        this._registry = registry;
        this.files = [];
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

    /** Used by the dragleave guard to tell "still inside" from "actually left". */
    contains(node) {
        if (node === this) return true;
        return this.children.some((child) => child.contains(node));
    }

    set innerHTML(value) {
        this._html = value;
        if (value === "") this.children = [];
    }
    get innerHTML() {
        return this._html || "";
    }

    querySelector(selector) {
        const matches = (node) =>
            selector.startsWith("#")
                ? node.id === selector.slice(1)
                : node.className.split(/\s+/).includes(selector.slice(1));
        const walk = (node) => {
            for (const child of node.children) {
                if (matches(child)) return child;
                const found = walk(child);
                if (found) return found;
            }
            return null;
        };
        return walk(this);
    }
}

function makeFile(name) {
    return { name };
}

/**
 * Build the dropzone markup expense_form.html renders, load the script, and
 * return handles. The nested children matter: they are what makes dragleave
 * fire while the pointer is still inside the zone.
 */
function setupPage(options = {}) {
    const { hasInvoiceChecked = false, withInput = true } = options;

    const registry = new Map();
    const make = (tag) => new FakeNode(tag, registry);

    const document_ = make("#document");
    const dropzone = make("div");
    dropzone.className = "receipt-dropzone";
    dropzone.id = "receipt-dropzone";

    let input = null;
    if (withInput) {
        input = make("input");
        input.className = "receipt-input";
        input.id = "id_receipts";
        dropzone.appendChild(input);
    }

    // .dropzone-content wraps three more children — the real nesting.
    const content = make("div");
    content.className = "dropzone-content";
    for (const cls of ["dropzone-icon", "dropzone-text", "dropzone-hint"]) {
        const child = make("div");
        child.className = cls;
        content.appendChild(child);
    }
    dropzone.appendChild(content);

    const filelist = make("div");
    filelist.className = "dropzone-filelist hidden";
    filelist.classList.add("hidden");
    filelist.id = "dropzone-filelist";
    dropzone.appendChild(filelist);

    const checkbox = make("input");
    checkbox.id = "id_has_invoice";
    checkbox.checked = hasInvoiceChecked;

    document_.children.push(dropzone, checkbox);
    document_.createElement = (tag) => make(tag);
    document_.getElementById = (id) => registry.get(id) || null;

    vm.runInNewContext(SOURCE, {
        document: document_,
        console,
        // The drop handler merges old + new selections through a DataTransfer.
        DataTransfer: class {
            constructor() {
                this._files = [];
                this.items = { add: (file) => this._files.push(file) };
            }
            get files() {
                return this._files;
            }
        },
    });
    document_.dispatchEvent(new FakeEvent("DOMContentLoaded"));

    return {
        document: document_,
        dropzone,
        input,
        filelist,
        checkbox,
        content,
        selectFiles(...names) {
            input.files = names.map(makeFile);
            input.dispatchEvent(new FakeEvent("change"));
        },
        drop(...names) {
            const event = new FakeEvent("drop", {
                dataTransfer: { files: names.map(makeFile) },
            });
            dropzone.dispatchEvent(event);
            return event;
        },
        dragOver() {
            const event = new FakeEvent("dragover");
            dropzone.dispatchEvent(event);
            return event;
        },
        dragLeave(relatedTarget) {
            dropzone.dispatchEvent(new FakeEvent("dragleave", { relatedTarget }));
        },
        filenames() {
            return filelist.children.map((child) => child.textContent);
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

console.log("\n📎 Running expense_form Tests\n");

// --- wiring -----------------------------------------------------------------

test("does nothing when the page has no dropzone", () => {
    const registry = new Map();
    const document_ = new FakeNode("#document", registry);
    document_.createElement = (tag) => new FakeNode(tag, registry);
    document_.getElementById = () => null;
    vm.runInNewContext(SOURCE, { document: document_, console, DataTransfer: class {} });
    document_.dispatchEvent(new FakeEvent("DOMContentLoaded"));
    assertTrue(true, "no dropzone must not throw");
});

test("bails out when the dropzone has no file input", () => {
    const page = setupPage({ withInput: false });
    // Without an input there is nothing to wire, so dragover must not highlight.
    page.dragOver();
    assertTrue(!page.dropzone.classList.contains("dragover"), "handlers not attached");
});

// --- selecting via the file input -------------------------------------------

test("lists the selected filenames", () => {
    const page = setupPage();
    page.selectFiles("beleg1.pdf", "beleg2.jpg");
    assertEquals(page.filenames(), ["✓ beleg1.pdf", "✓ beleg2.jpg"], "both files listed");
});

test("reveals the filelist once files are chosen", () => {
    const page = setupPage();
    assertTrue(page.filelist.classList.contains("hidden"), "starts hidden");
    page.selectFiles("beleg.pdf");
    assertTrue(!page.filelist.classList.contains("hidden"), "shown after choosing");
});

test("ticks the has-invoice checkbox automatically", () => {
    const page = setupPage();
    page.selectFiles("beleg.pdf");
    assertTrue(page.checkbox.checked, "attaching a receipt implies there is an invoice");
});

test("leaves an already-ticked checkbox alone", () => {
    const page = setupPage({ hasInvoiceChecked: true });
    page.selectFiles("beleg.pdf");
    assertTrue(page.checkbox.checked, "still ticked");
});

test("clearing the input leaves the previous list on screen", () => {
    // Documented, not endorsed: showFilelist returns early on an empty list, so
    // the filenames from the previous selection stay visible.
    const page = setupPage();
    page.selectFiles("beleg.pdf");
    page.selectFiles();
    assertEquals(page.filenames(), ["✓ beleg.pdf"], "stale list is current behaviour");
});

// --- dropping ---------------------------------------------------------------

test("dropped files are added and the drop is swallowed", () => {
    const page = setupPage();
    const event = page.drop("gedroppt.pdf");
    assertTrue(event.defaultPrevented, "the browser must not open the file");
    assertEquals(page.filenames(), ["✓ gedroppt.pdf"], "dropped file listed");
});

test("dropped files are merged with the existing selection", () => {
    const page = setupPage();
    page.selectFiles("erste.pdf");
    page.drop("zweite.pdf");
    assertEquals(
        page.filenames(),
        ["✓ erste.pdf", "✓ zweite.pdf"],
        "dropping appends rather than replacing"
    );
});

test("dropping the same file twice adds it twice", () => {
    // Documented, not endorsed: the DataTransfer merge does not de-duplicate.
    const page = setupPage();
    page.drop("beleg.pdf");
    page.drop("beleg.pdf");
    assertEquals(page.filenames().length, 2, "no de-duplication on merge");
});

test("an empty drop changes nothing", () => {
    const page = setupPage();
    page.selectFiles("beleg.pdf");
    page.drop();
    assertEquals(page.filenames(), ["✓ beleg.pdf"], "selection untouched");
});

test("dropping ticks the has-invoice checkbox too", () => {
    const page = setupPage();
    page.drop("beleg.pdf");
    assertTrue(page.checkbox.checked, "same rule as choosing via the input");
});

// --- the dragover highlight -------------------------------------------------

test("dragover highlights the zone and swallows the event", () => {
    const page = setupPage();
    const event = page.dragOver();
    assertTrue(page.dropzone.classList.contains("dragover"), "highlight applied");
    assertTrue(event.defaultPrevented, "preventDefault is required to allow a drop");
});

test("leaving the zone entirely clears the highlight", () => {
    const page = setupPage();
    page.dragOver();
    page.dragLeave(null);
    assertTrue(!page.dropzone.classList.contains("dragover"), "highlight cleared");
});

test("crossing into a child element keeps the highlight", () => {
    // dragleave bubbles from children, and this dropzone has four. Without a
    // containment guard the highlight is dropped mid-drag and re-added by the
    // next dragover, which reads as a flicker.
    const page = setupPage();
    page.dragOver();
    page.dragLeave(page.content);
    assertTrue(page.dropzone.classList.contains("dragover"), "still inside the zone");
});

test("crossing into a nested grandchild also keeps the highlight", () => {
    const page = setupPage();
    page.dragOver();
    page.dragLeave(page.content.children[0]);
    assertTrue(page.dropzone.classList.contains("dragover"), "containment is recursive");
});

test("dropping clears the highlight", () => {
    const page = setupPage();
    page.dragOver();
    page.drop("beleg.pdf");
    assertTrue(!page.dropzone.classList.contains("dragover"), "highlight cleared on drop");
});

// ---------------------------------------------------------------------------

if (failures > 0) {
    console.error(`\n❌ ${failures} test(s) failed\n`);
    process.exit(1);
}
console.log("\n✅ All tests passed!\n");

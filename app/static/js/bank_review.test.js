/**
 * Tests for bank_review.js — the live tally of selected invoice amounts.
 * Run with: node bank_review.test.js
 *
 * Like form_draft_guard.js, this is a browser IIFE with no exports: it wires
 * itself to document on load. So each test builds a throwaway DOM stub, loads
 * the real source into it via `vm`, fires DOMContentLoaded, then drives the
 * <select> through change events and inspects the tally element the script
 * inserts. The stub is hand-rolled rather than jsdom for the same reason as
 * form_draft_guard.test.js — the repo runs JS tests as plain `node <file>`
 * with no framework or devDependencies (see dev.py cmd_test_js), and a DOM
 * dependency would have to exist inside the Docker image too.
 *
 * Two contracts are pinned here that span the Python/JS boundary and are
 * invisible to both the i18n guardrail and any Django test:
 *
 *   1. Option text comes from TransactionMatchForm._invoice_label
 *      (import_forms.py), which formats "{total:,.2f}" and then replaces ","
 *      with " " — so thousands are space-separated and the decimal is a DOT.
 *   2. data-amount on the surrounding form must be a machine-readable dot
 *      decimal. Django localises template numbers, so under
 *      LANGUAGE_CODE="de-de" a bare {{ trans.amount }} renders "90,50" and
 *      parseFloat truncates it to 90 — see the |unlocalize in bank_review.html.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "bank_review.js"), "utf8");

// Mirrors the data-tally-* attributes on the <script> tag in bank_review.html.
const I18N = {
    tallyMatches: "matches the transaction",
    tallyDifference: "Difference:",
    tallyInvoice: "Invoice",
    tallyInvoices: "Invoices",
};

// ---------------------------------------------------------------------------
// Minimal DOM stub
// ---------------------------------------------------------------------------

class FakeEvent {
    constructor(type) {
        this.type = type;
        this.target = null;
    }
}

/**
 * Stand-in for CSSStyleDeclaration.
 *
 * The script sets the tally's base rules through `style.cssText` and then
 * overrides individual properties (`style.display`, `style.background`, ...).
 * A plain object would leave the cssText declarations unreadable, so this
 * expands them into camelCase properties the way a browser does — which is
 * what makes "starts hidden" a real assertion rather than a tautology.
 */
class FakeStyle {
    set cssText(text) {
        for (const declaration of text.split(";")) {
            const [property, ...rest] = declaration.split(":");
            if (!property || rest.length === 0) continue;
            const name = property
                .trim()
                .replace(/-([a-z])/g, (_, c) => c.toUpperCase());
            this[name] = rest.join(":").trim();
        }
    }
}

class FakeNode {
    constructor(tagName = "div") {
        this.tagName = tagName.toUpperCase();
        this.children = [];
        this.parentNode = null;
        this.dataset = {};
        this.id = "";
        this.style = new FakeStyle();
        this.innerHTML = "";
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

    // The script places the tally with insertAdjacentElement("afterend", ...),
    // so position relative to the <select> is part of what's under test.
    insertAdjacentElement(position, element) {
        if (position !== "afterend") throw new Error(`unhandled position: ${position}`);
        const siblings = this.parentNode.children;
        siblings.splice(siblings.indexOf(this) + 1, 0, element);
        element.parentNode = this.parentNode;
        return element;
    }

    // Only "form[data-amount]" is ever asked for.
    closest(selector) {
        if (selector !== "form[data-amount]") throw new Error(`unhandled: ${selector}`);
        let node = this.parentNode;
        while (node) {
            if (node.tagName === "FORM" && "amount" in node.dataset) return node;
            node = node.parentNode;
        }
        return null;
    }
}

function makeOption(text, selected = false) {
    const option = new FakeNode("option");
    option.text = text;
    option.selected = selected;
    return option;
}

/**
 * Build a page with one <select name="invoice"> inside a form, load the script,
 * and return handles for driving it.
 *
 * @param options.amount     data-amount on the form; null omits the attribute
 *                           entirely (and with it the whole form wrapper).
 * @param options.options    option label strings.
 * @param options.i18n       dataset for the #bank-review-js tag; null omits it.
 */
function setupPage(options = {}) {
    const { amount = "90.00", options: labels = [], i18n = I18N } = options;

    const document_ = new FakeNode("#document");
    const select = new FakeNode("select");
    select.name = "invoice";
    select.children = labels.map((text) => makeOption(text));
    Object.defineProperty(select, "selectedOptions", {
        get: () => select.children.filter((o) => o.selected),
    });

    let container = document_;
    if (amount !== null) {
        const form = new FakeNode("form");
        form.dataset.amount = amount;
        document_.appendChild(form);
        container = form;
    }
    container.appendChild(select);

    const scriptTag = i18n === null ? null : new FakeNode("script");
    if (scriptTag) {
        scriptTag.id = "bank-review-js";
        scriptTag.dataset = Object.assign({}, i18n);
    }

    document_.createElement = (tag) => new FakeNode(tag);
    document_.querySelectorAll = (selector) =>
        selector === 'select[name="invoice"]' ? [select] : [];
    document_.getElementById = (id) => (id === "bank-review-js" ? scriptTag : null);

    vm.runInNewContext(SOURCE, { document: document_, console });
    document_.dispatchEvent(new FakeEvent("DOMContentLoaded"));

    return {
        document: document_,
        select,
        container,
        tally() {
            return container.children[container.children.indexOf(select) + 1] || null;
        },
        /** Select the options at these indices and fire change. */
        choose(...indices) {
            select.children.forEach((o, i) => {
                o.selected = indices.includes(i);
            });
            select.dispatchEvent(new FakeEvent("change"));
            return this.tally();
        },
    };
}

// ---------------------------------------------------------------------------
// Test framework (mirrors form_draft_guard.test.js)
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

/** Invoice option label exactly as _invoice_label builds it. */
function label(number, date, amount) {
    return `${number} (${date}): ${amount} €`;
}

console.log("\n🏦 Running bank_review Tests\n");

// --- wiring ----------------------------------------------------------------

test("inserts a tally element directly after the select, hidden", () => {
    const page = setupPage({ options: [label("XX-1", "2026-01-15", "90.00")] });
    const tally = page.tally();
    assertTrue(tally !== null, "a tally element should be inserted");
    assertEquals(tally.style.display, "none", "tally starts hidden");
});

test("stays hidden while nothing is selected", () => {
    const page = setupPage({ options: [label("XX-1", "2026-01-15", "90.00")] });
    assertEquals(page.choose().style.display, "none", "no selection means no tally");
});

test("deselecting everything hides the tally again", () => {
    const page = setupPage({ options: [label("XX-1", "2026-01-15", "90.00")] });
    page.choose(0);
    assertEquals(page.choose().style.display, "none", "tally hides when cleared");
});

// --- amount parsing (the _invoice_label contract) --------------------------

test("parses a plain dot-decimal amount", () => {
    const page = setupPage({ options: [label("XX-1", "2026-01-15", "90.00")] });
    assertContains(page.choose(0).innerHTML, "90,00 €", "90.00 should tally as 90,00 €");
});

test("parses space-separated thousands, as _invoice_label emits them", () => {
    // "{:,.2f}" then "," -> " ", so 1234.56 reaches the DOM as "1 234.56".
    const page = setupPage({
        amount: "1234.56",
        options: [label("XX-1", "2026-01-15", "1 234.56")],
    });
    assertContains(page.choose(0).innerHTML, "1.234,56 €", "spaces are thousands separators");
});

test("sums multiple selected invoices", () => {
    const page = setupPage({
        amount: "150.50",
        options: [
            label("XX-1", "2026-01-15", "90.00"),
            label("XX-2", "2026-01-16", "60.50"),
        ],
    });
    assertContains(page.choose(0, 1).innerHTML, "150,50 €", "90.00 + 60.50 = 150,50");
});

test("hides the tally when an option label cannot be parsed", () => {
    const page = setupPage({ options: ["Something without an amount"] });
    assertEquals(page.choose(0).style.display, "none", "unparseable label hides the tally");
});

test("one unparseable option suppresses the whole tally", () => {
    const page = setupPage({
        options: [label("XX-1", "2026-01-15", "90.00"), "no amount here"],
    });
    assertEquals(page.choose(0, 1).style.display, "none", "a partial sum must not be shown");
});

// --- German number formatting ----------------------------------------------

test("formats thousands with a dot and decimals with a comma", () => {
    const page = setupPage({
        amount: "1000.00",
        options: [label("XX-1", "2026-01-15", "1 000.00")],
    });
    assertContains(page.choose(0).innerHTML, "1.000,00 €", "1000 formats as 1.000,00");
});

test("formats millions with both thousands separators", () => {
    const page = setupPage({
        amount: "1234567.89",
        options: [label("XX-1", "2026-01-15", "1 234 567.89")],
    });
    assertContains(page.choose(0).innerHTML, "1.234.567,89 €", "grouping repeats every 3 digits");
});

test("keeps two decimals on a whole-euro amount", () => {
    const page = setupPage({ amount: "7.00", options: [label("XX-1", "2026-01-15", "7.00")] });
    assertContains(page.choose(0).innerHTML, "7,00 €", "always two decimal places");
});

// --- match / mismatch against the transaction amount ------------------------

test("an exact match shows the success icon and label", () => {
    const page = setupPage({ amount: "90.00", options: [label("XX-1", "2026-01-15", "90.00")] });
    const tally = page.choose(0);
    assertContains(tally.innerHTML, "✅", "matching total gets the success icon");
    assertContains(tally.innerHTML, I18N.tallyMatches, "and the 'matches' label");
    assertEquals(tally.style.color, "var(--color-success)", "success colour");
});

test("a total over the transaction shows a + difference", () => {
    const page = setupPage({ amount: "90.00", options: [label("XX-1", "2026-01-15", "95.50")] });
    const tally = page.choose(0);
    assertContains(tally.innerHTML, "⚠️", "mismatch gets the warning icon");
    assertContains(tally.innerHTML, "+5,50 €", "over by 5,50");
    assertEquals(tally.style.color, "var(--color-warning)", "warning colour");
});

test("a total under the transaction shows a minus difference", () => {
    const page = setupPage({ amount: "90.00", options: [label("XX-1", "2026-01-15", "80.00")] });
    // U+2212 MINUS SIGN, not a hyphen.
    assertContains(page.choose(0).innerHTML, "−10,00 €", "under by 10,00");
});

test("cent-level differences are reported, not rounded away", () => {
    // The bug |unlocalize fixes: data-amount="90,50" parseFloats to 90, so a
    // genuinely matching pair used to render as a 0,50 € mismatch.
    const page = setupPage({ amount: "90.50", options: [label("XX-1", "2026-01-15", "90.50")] });
    assertContains(page.choose(0).innerHTML, "✅", "90.50 vs 90.50 matches exactly");
});

test("a comma-decimal data-amount is the regression this guards against", () => {
    // Documents *why* bank_review.html needs |unlocalize: if the attribute ever
    // renders localised again, parseFloat truncates and the tally lies.
    const page = setupPage({ amount: "90,50", options: [label("XX-1", "2026-01-15", "90.50")] });
    assertContains(
        page.choose(0).innerHTML,
        "⚠️",
        "a localised data-amount produces a false mismatch — keep |unlocalize"
    );
});

test("differences under half a cent count as a match", () => {
    const page = setupPage({ amount: "90.004", options: [label("XX-1", "2026-01-15", "90.00")] });
    assertContains(page.choose(0).innerHTML, "✅", "0.004 is inside the float tolerance");
});

test("differences at half a cent do not count as a match", () => {
    const page = setupPage({ amount: "90.01", options: [label("XX-1", "2026-01-15", "90.00")] });
    assertContains(page.choose(0).innerHTML, "⚠️", "0.01 is outside the float tolerance");
});

// --- pluralisation ----------------------------------------------------------

test("uses the singular noun for one invoice", () => {
    const page = setupPage({ options: [label("XX-1", "2026-01-15", "90.00")] });
    assertContains(page.choose(0).innerHTML, `1 ${I18N.tallyInvoice}`, "singular for one");
});

test("uses the plural noun for several invoices", () => {
    const page = setupPage({
        amount: "180.00",
        options: [
            label("XX-1", "2026-01-15", "90.00"),
            label("XX-2", "2026-01-16", "90.00"),
        ],
    });
    assertContains(page.choose(0, 1).innerHTML, `2 ${I18N.tallyInvoices}`, "plural for two");
});

// --- i18n plumbing ----------------------------------------------------------

test("all four labels come from the script tag's dataset, not the source", () => {
    // The guardrail only scans templates, so a German literal in this .js file
    // would be invisible to it. Swapping the dataset must swap the output.
    const page = setupPage({
        amount: "80.00",
        options: [label("XX-1", "2026-01-15", "90.00")],
        i18n: {
            tallyMatches: "MATCHES",
            tallyDifference: "DIFF",
            tallyInvoice: "INV",
            tallyInvoices: "INVS",
        },
    });
    const tally = page.choose(0);
    assertContains(tally.innerHTML, "DIFF", "difference label comes from the dataset");
    assertContains(tally.innerHTML, "INV", "noun comes from the dataset");
});

test("a missing script tag does not throw", () => {
    const page = setupPage({
        amount: "90.00",
        options: [label("XX-1", "2026-01-15", "90.00")],
        i18n: null,
    });
    const tally = page.choose(0);
    assertEquals(tally.style.display, "block", "tally still renders without the tag");
});

// ---------------------------------------------------------------------------

if (failures > 0) {
    console.error(`\n❌ ${failures} test(s) failed\n`);
    process.exit(1);
}
console.log("\n✅ All tests passed!\n");

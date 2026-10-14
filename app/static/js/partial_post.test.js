/**
 * Tests for partial_post.js
 * Run with: node partial_post.test.js
 *
 * Loads the real source into a vm context with a stub DOM and a fake fetch,
 * then drives it through click/change events.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "partial_post.js"), "utf8");

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
        this.type = attrs.type || "";
        this.checked = false;
        this.parentElement = parent;
        this.innerHTML = "";
        this.outerHTML = "";
        const classes = new Set((attrs.class || "").split(" ").filter(Boolean));
        this.classList = {
            add: (c) => classes.add(c),
            remove: (c) => classes.delete(c),
            contains: (c) => classes.has(c),
        };
    }
    matches(selector) {
        const match = selector.match(/^([a-z]*)((?:\[[a-z-]+\])*)(\.[a-z-]+)?$/);
        if (!match) throw new Error(`unsupported selector ${selector}`);
        if (match[1] && this.tagName !== match[1].toUpperCase()) return false;
        if (match[3] && !this.classList.contains(match[3].slice(1))) return false;
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

async function load({ ok = true, html = "<p>new</p>" } = {}) {
    const listeners = {};
    const requests = [];
    const byId = {};
    const context = {
        document: {
            body: { dataset: { csrfToken: "tok" } },
            addEventListener(type, fn) {
                (listeners[type] = listeners[type] || []).push(fn);
            },
            querySelector: (sel) => byId[sel] || null,
        },
        URLSearchParams,
        JSON,
        fetch(url, options) {
            requests.push({ url, options });
            return Promise.resolve({ ok, status: ok ? 200 : 500, text: () => Promise.resolve(html) });
        },
    };
    vm.runInNewContext(SOURCE, context);
    function fire(type, target) {
        const event = {
            target,
            defaultPrevented: false,
            preventDefault() {
                this.defaultPrevented = true;
            },
        };
        for (const fn of listeners[type] || []) fn(event);
        return event;
    }
    const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
    return { fire, requests, byId, settle };
}

let failures = 0;
async function test(name, fn) {
    try {
        await fn();
        console.log(`✓ ${name}`);
    } catch (err) {
        failures += 1;
        console.log(`✗ ${name}\n  ${err.message}`);
    }
}
function assertEqual(actual, expected, label) {
    if (actual !== expected) throw new Error(`${label}: expected ${expected}, got ${actual}`);
}

(async () => {
    await test("a click posts with CSRF, the partial header and the vals", async () => {
        const { fire, requests, byId, settle } = await load();
        byId["#queue"] = new FakeElement("div");
        const button = new FakeElement("button", {
            "data-post": "/snooze/",
            "data-post-vals": '{"days": "3"}',
            "data-post-target": "#queue",
        });
        const event = fire("click", button);
        await settle();
        assertEqual(event.defaultPrevented, true, "default prevented");
        assertEqual(requests[0].url, "/snooze/", "url");
        assertEqual(requests[0].options.method, "POST", "method");
        assertEqual(requests[0].options.headers["X-CSRFToken"], "tok", "csrf");
        assertEqual(requests[0].options.headers["X-Partial"], "1", "partial header");
        assertEqual(requests[0].options.body.get("days"), "3", "vals");
        assertEqual(byId["#queue"].outerHTML, "<p>new</p>", "outer swap");
    });

    await test("inner swap replaces the target's contents", async () => {
        const { fire, byId, settle } = await load({ html: "SENT" });
        byId["#cell"] = new FakeElement("td");
        fire(
            "click",
            new FakeElement("button", {
                "data-post": "/status/",
                "data-post-target": "#cell",
                "data-post-swap": "inner",
            })
        );
        await settle();
        assertEqual(byId["#cell"].innerHTML, "SENT", "inner swap");
    });

    await test("a checkbox posts on change and swaps its closest row", async () => {
        const { fire, requests, settle } = await load({ html: "<div>row</div>" });
        const row = new FakeElement("div", { class: "todo-item" });
        const box = new FakeElement(
            "input",
            { type: "checkbox", "data-post": "/done/", "data-post-closest": ".todo-item" },
            row
        );
        fire("click", box); // the browser's own toggle; must not post
        assertEqual(requests.length, 0, "no post on click");
        fire("change", box);
        await settle();
        assertEqual(requests.length, 1, "posted on change");
        assertEqual(row.outerHTML, "<div>row</div>", "row swapped");
    });

    await test("a failed request reverts the checkbox and leaves the page", async () => {
        const { fire, settle } = await load({ ok: false });
        const row = new FakeElement("div", { class: "todo-item" });
        const box = new FakeElement(
            "input",
            { type: "checkbox", "data-post": "/done/", "data-post-closest": ".todo-item" },
            row
        );
        box.checked = true; // toggled by the click that triggered change
        fire("change", box);
        await settle();
        assertEqual(box.checked, false, "reverted");
        assertEqual(row.outerHTML, "", "not swapped");
        assertEqual(box.classList.contains("is-pending"), false, "pending cleared");
    });

    await test("a second click while pending does not post twice", async () => {
        const { fire, requests, byId, settle } = await load();
        byId["#queue"] = new FakeElement("div");
        const button = new FakeElement("button", { "data-post": "/x/", "data-post-target": "#queue" });
        fire("click", button);
        fire("click", button);
        await settle();
        assertEqual(requests.length, 1, "one request");
    });

    await test("clicks elsewhere are ignored", async () => {
        const { fire, requests } = await load();
        const event = fire("click", new FakeElement("a", { href: "/elsewhere/" }));
        assertEqual(requests.length, 0, "no request");
        assertEqual(event.defaultPrevented, false, "default kept");
    });

    if (failures) {
        console.log(`\n${failures} test(s) failed`);
        process.exit(1);
    }
    console.log("\nAll partial_post tests passed");
})();

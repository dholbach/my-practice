/**
 * Tests for client_tags.js — adding and removing client tags.
 * Run with: node client_tags.test.js
 *
 * DOM stub plus the real source via `vm`; fetch is stubbed. Pinned: the request
 * URLs, bodies and CSRF header, the reload on success, the removed tag, and the
 * error texts coming from the container's data attributes.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "client_tags.js"), "utf8");

let failures = 0;
function check(name, condition) {
    if (condition) {
        console.log(`  ok   ${name}`);
    } else {
        failures += 1;
        console.log(`  FAIL ${name}`);
    }
}

function element(dataset = {}) {
    return { dataset, listeners: {}, addEventListener(t, f) { this.listeners[t] = f; }, classList: { toggle() {}, contains: () => false, remove() {} } };
}

async function load({ response = { success: true } } = {}) {
    const container = element({ clientId: "7", addError: "add failed", removeError: "remove failed" });
    const removeButton = element({ tagId: "3" });
    removed = false;
    removeButton.closest = () => ({ remove: () => (removed = true) });
    const item = element({ tagId: "5" });
    const addButton = element();
    const dropdown = element();
    dropdown.querySelector = () => addButton;
    dropdown.querySelectorAll = () => [item];
    container.querySelectorAll = () => [removeButton];
    const requests = [];
    const alerts = [];
    let reloaded = false;
    const context = {
        document: {
            body: { dataset: { csrfToken: "body-token" } },
            getElementById: (id) => (id === "tagDropdown7" ? dropdown : null),
            querySelector: () => null,
            querySelectorAll: () => [container],
        },
        fetch: (url, init) => { requests.push({ url, init }); return Promise.resolve({ json: () => Promise.resolve(response) }); },
        alert: (m) => alerts.push(m),
        location: { reload: () => (reloaded = true) },
        console, parseInt, setTimeout,
    };
    vm.runInNewContext(SOURCE, context);
    const settle = () => new Promise((r) => setImmediate(r));
    return { item, removeButton, requests, alerts, settle, reloaded: () => reloaded, removed: () => removed };
}
let removed = false;

console.log("client_tags.js");

(async function () {
    let page = await load();
    page.item.listeners.click();
    await page.settle();
    check("adding posts the tag id with the CSRF header", page.requests[0].url === "/api/clients/7/tags/add/" && page.requests[0].init.body === "tag_id=5" && page.requests[0].init.headers["X-CSRFToken"] === "body-token");
    check("a successful add reloads the page", page.reloaded());

    page = await load({ response: { success: false } });
    page.item.listeners.click();
    await page.settle();
    check("a failed add shows the add error", page.alerts[0] === "add failed" && !page.reloaded());

    page = await load();
    page.removeButton.listeners.click();
    await page.settle();
    check("removing posts to the remove URL", page.requests[0].url === "/api/clients/7/tags/3/remove/");
    check("a successful remove drops the tag", page.removed());

    page = await load({ response: { success: false } });
    page.removeButton.listeners.click();
    await page.settle();
    check("a failed remove shows the remove error", page.alerts[0] === "remove failed");
    process.exit(failures ? 1 : 0);
})();

/**
 * Tests for client_documents.js — document upload and delete in the client sidebar.
 * Run with: node client_documents.test.js
 *
 * DOM stub plus the real source via `vm`. Pinned: the fields pre-filled from a
 * filename, the upload request, the "onboarding step completed" reload, and the
 * delete confirmation.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "client_documents.js"), "utf8");
const POST_JSON = fs.readFileSync(path.join(__dirname, "post_json.js"), "utf8");

let failures = 0;
function check(name, condition) {
    if (condition) {
        console.log(`  ok   ${name}`);
    } else {
        failures += 1;
        console.log(`  FAIL ${name}`);
    }
}

function node(extra = {}) {
    const classes = new Set();
    return Object.assign(
        {
            value: "", style: {}, dataset: {}, files: [], listeners: {}, disabled: false,
            classList: { add: (c) => classes.add(c), remove: (c) => classes.delete(c), has: (c) => classes.has(c) },
            addEventListener(t, f) { this.listeners[t] = f; },
            click() { if (this.listeners.click) this.listeners.click(); },
        },
        extra
    );
}

function load({ response = { id: 9 }, confirmAnswer = true } = {}) {
    const dropLabel = { textContent: "", innerHTML: "" };
    const ids = {
        "client-documents": node({ dataset: { uploadUrl: "/up/", dropHint: "<b>hint</b>", uploadFailed: "up failed", deleteConfirm: "sure?", deleteFailed: "del failed" } }),
        docDropZone: node({ querySelector: () => dropLabel }),
        docFileInput: node(),
        docUploadForm: node(),
        docUploadBtn: node(),
        docCancelBtn: node(),
        docProgress: node(),
        docDate: node(),
        docTypeSelect: node(),
        docDescription: node(),
    };
    const requests = [];
    const alerts = [];
    let reloaded = false;
    const deleteButton = node({ dataset: { docId: "4" } });
    const row = { removed: false, remove() { this.removed = true; } };
    const context = {
        document: {
            body: { dataset: { csrfToken: "csrf-body" } },
            getElementById: (id) => (id === "doc-4" ? row : ids[id] || null),
            querySelector: () => null,
            querySelectorAll: () => [deleteButton],
        },
        FormData: class { constructor() { this.data = {}; } append(k, v) { this.data[k] = v; } },
        fetch: (url, init) => { requests.push({ url, init }); return Promise.resolve({ json: () => Promise.resolve(response) }); },
        alert: (m) => alerts.push(m),
        confirm: () => confirmAnswer,
        location: { reload: () => (reloaded = true) },
        Date, String, URLSearchParams,
    };
    vm.createContext(context);
    vm.runInContext(POST_JSON, context);
    vm.runInContext(SOURCE, context);
    const settle = () => new Promise((r) => setImmediate(r));
    return { ids, dropLabel, requests, alerts, deleteButton, row, settle, reloaded: () => reloaded };
}

console.log("client_documents.js");

(async function () {
    let page = load();
    page.ids.docFileInput.files = [{ name: "2026-01-09-Behandlungsvertrag-Max.pdf" }];
    page.ids.docFileInput.listeners.change();
    check("the filename fills date, type and description", page.ids.docDate.value === "2026-01-09" && page.ids.docTypeSelect.value === "contract" && page.ids.docDescription.value === "behandlungsvertrag max");
    check("the upload form opens and shows the file name", page.ids.docUploadForm.style.display === "block" && page.dropLabel.textContent === "2026-01-09-Behandlungsvertrag-Max.pdf");

    page.ids.docUploadBtn.click();
    check("upload posts the form data to the data-upload-url", page.requests[0].url === "/up/" && page.requests[0].init.body.data.document_type === "contract" && page.requests[0].init.body.data.file.name === "2026-01-09-Behandlungsvertrag-Max.pdf");
    check("the upload carries the CSRF token in the header, not in the form", page.requests[0].init.headers["X-CSRFToken"] === "csrf-body" && !("csrfmiddlewaretoken" in page.requests[0].init.body.data));
    check("the button is disabled while uploading", page.ids.docUploadBtn.disabled === true);

    page = load({ response: { id: 9, onboarding_step_completed: true } });
    page.ids.docFileInput.files = [{ name: "scan.pdf" }];
    page.ids.docFileInput.listeners.change();
    page.ids.docUploadBtn.click();
    await page.settle();
    check("a completed onboarding step reloads the page", page.reloaded());

    page = load({ response: { error: "too big" } });
    page.ids.docFileInput.files = [{ name: "scan.pdf" }];
    page.ids.docFileInput.listeners.change();
    page.ids.docUploadBtn.click();
    await page.settle();
    check("a server error is alerted and re-enables the button", page.alerts[0] === "too big" && page.ids.docUploadBtn.disabled === false);

    page = load({ response: { id: 9 } });
    page.ids.docFileInput.files = [{ name: "scan.pdf" }];
    page.ids.docFileInput.listeners.change();
    page.ids.docCancelBtn.click();
    check("cancel restores the drop hint", page.dropLabel.innerHTML === "<b>hint</b>" && page.ids.docUploadForm.style.display === "none");

    page = load({ response: { success: true } });
    page.deleteButton.click();
    await page.settle();
    check("delete asks first, then posts and removes the row", page.requests[0].url === "/documents/4/delete/" && page.requests[0].init.headers["X-CSRFToken"] === "csrf-body" && page.row.removed);

    page = load({ confirmAnswer: false });
    page.deleteButton.click();
    check("declining the confirmation sends nothing", page.requests.length === 0);
    process.exit(failures ? 1 : 0);
})();

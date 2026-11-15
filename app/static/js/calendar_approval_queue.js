/**
 * Calendar approval queue: skip duplicates, skip one event, import a group.
 *
 * Translated strings, URLs and the per-event skip URL come from data-* attributes
 * on this file's own <script> tag and on the skip buttons (see
 * calendar_approval_queue.html), so the strings stay inside the template surface
 * the i18n coverage guardrail scans. Requests go through MPHttp.postJson (post_json.js).
 */

(function () {
    "use strict";

    const tag = document.getElementById("calendar-approval-queue-js");
    if (!tag) return;
    const text = tag.dataset;

    function wireSkipDuplicates() {
        const button = document.getElementById("skip-duplicates-btn");
        if (!button) return;
        button.addEventListener("click", async function () {
            const label = this.textContent;
            const restore = () => {
                this.disabled = false;
                this.textContent = label;
            };
            this.disabled = true;
            this.textContent = text.skipping;
            try {
                const res = await MPHttp.postJson(text.skipDuplicatesUrl);
                const data = await res.json();
                if (data.success) {
                    location.reload();
                } else {
                    alert(text.skipError);
                    restore();
                }
            } catch (e) {
                alert(text.networkError);
                restore();
            }
        });
    }

    // Each group's "select all" checkbox carries class select-all-<n> and toggles
    // the event checkboxes of that group.
    function wireSelectAll() {
        document.querySelectorAll('[class^="select-all-"]').forEach((selectAll) => {
            const suffix = selectAll.className.split("-").pop();
            selectAll.addEventListener("change", function () {
                document.querySelectorAll(`.event-checkbox-group-${suffix}`).forEach((cb) => {
                    cb.checked = this.checked;
                });
            });
        });
    }

    function wireSkipEvent() {
        document.querySelectorAll(".skip-event-btn").forEach((button) => {
            button.addEventListener("click", async function () {
                const row = document.querySelector(`tr[data-event-id="${this.dataset.eventId}"]`);
                try {
                    const res = await MPHttp.postJson(this.dataset.skipUrl);
                    if (res.ok) {
                        row.style.opacity = "0.35";
                        row.style.transition = "opacity 0.3s";
                        setTimeout(() => row.remove(), 350);
                    }
                } catch (e) {
                    alert(text.skipEventError);
                }
            });
        });
    }

    // The summary in the error texts comes from the calendar: use textContent only.
    function showImportToast(data) {
        const importedLabel = data.created === 1 ? text.eventImported : text.eventsImported;
        const toast = document.createElement("div");
        toast.className = "alert-box success";
        toast.style.cssText = "position:fixed;top:20px;right:20px;z-index:1000;min-width:260px;";
        const heading = document.createElement("strong");
        heading.textContent = `✅ ${data.created} ${importedLabel}`;
        toast.appendChild(heading);
        if (data.skipped) {
            const skipped = document.createElement("small");
            skipped.textContent = `${data.skipped} ${text.skipped}`;
            toast.append(document.createElement("br"), skipped);
        }
        data.errors.forEach((message) => {
            const line = document.createElement("small");
            line.textContent = message;
            toast.append(document.createElement("br"), line);
        });
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), data.errors.length ? 10000 : 4000);
    }

    function wireImportGroup() {
        document.querySelectorAll(".import-group-btn").forEach((button) => {
            button.addEventListener("click", async function () {
                const groupNum = this.dataset.group;
                const invoiceSelect = document.querySelector(
                    `.invoice-select-${this.dataset.client}-${this.dataset.month}`
                );
                const invoiceId = invoiceSelect?.value || null;

                const checked = document.querySelectorAll(
                    `.event-checkbox-group-${groupNum}:checked`
                );
                if (checked.length === 0) {
                    alert(text.selectOne);
                    return;
                }

                const body = { event_ids: Array.from(checked).map((cb) => parseInt(cb.value)) };
                if (invoiceId === "new") {
                    body.invoice_id = "new";
                } else if (invoiceId) {
                    body.invoice_id = parseInt(invoiceId);
                }

                const label = this.textContent;
                const restore = () => {
                    this.disabled = false;
                    this.textContent = label;
                };
                this.disabled = true;
                this.textContent = text.importing;

                try {
                    const res = await MPHttp.postJson(text.importUrl, body);
                    const data = await res.json();
                    if (!data.success) {
                        alert(`${text.error}: ${data.error || text.unknownError}`);
                        restore();
                        return;
                    }
                    // Remove only the rows that were imported; failed ones stay for a retry or skip
                    data.imported_ids.forEach((id) => {
                        const row = document.querySelector(`tr[data-event-id="${id}"]`);
                        if (row) row.remove();
                    });
                    const groupEl = document.getElementById(`group-${groupNum}`);
                    if (groupEl.querySelectorAll("tbody tr").length === 0) groupEl.remove();
                    showImportToast(data);
                    if (data.errors.length) restore();
                } catch (e) {
                    alert(text.importNetworkError);
                    restore();
                }
            });
        });
    }

    wireSkipDuplicates();
    wireSelectAll();
    wireSkipEvent();
    wireImportGroup();
})();

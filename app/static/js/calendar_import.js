/**
 * Manual calendar import page: pick events, choose client and service type,
 * import the selection.
 *
 * Translated strings and the import URL come from data-* attributes on this
 * file's own <script> tag (see calendar_import.html), so the strings stay inside
 * the template surface the i18n coverage guardrail scans. Requests go
 * through MPHttp.postJson (post_json.js).
 */

(function () {
    "use strict";

    const tag = document.getElementById("calendar-import-js");
    if (!tag) return;
    const text = tag.dataset;

    const selectedEvents = new Set();
    let duplicatesHidden = false;

    function toggleDuplicates() {
        duplicatesHidden = !duplicatesHidden;
        document.querySelectorAll(".event-duplicate").forEach((row) => {
            row.style.display = duplicatesHidden ? "none" : "";
        });
        const label = duplicatesHidden ? `🔄 ${text.showDuplicates}` : `🚫 ${text.hideDuplicates}`;
        ["toggleDuplicates", "toggleDuplicatesTop"].forEach((id) => {
            const button = document.getElementById(id);
            if (button) button.textContent = label;
        });
    }

    function updateBulkActions() {
        selectedEvents.clear();
        document.querySelectorAll(".event-checkbox:checked").forEach((cb) => {
            const row = cb.closest(".event-row");
            selectedEvents.add(row.dataset.eventId);
            row.classList.add("selected");
        });
        document.querySelectorAll(".event-checkbox:not(:checked)").forEach((cb) => {
            cb.closest(".event-row").classList.remove("selected");
        });

        const bulkActions = document.getElementById("bulkActions");
        const count = selectedEvents.size;
        if (count > 0) {
            bulkActions.classList.add("visible");
            document.getElementById("selectedCount").textContent = `${count} ${text.selected}`;
        } else {
            bulkActions.classList.remove("visible");
        }
    }

    function toggleSelectAll(checkbox) {
        document.querySelectorAll(".event-checkbox:not([disabled])").forEach((cb) => {
            cb.checked = checkbox.checked;
        });
        updateBulkActions();
    }

    function clearSelection() {
        document.querySelectorAll(".event-checkbox").forEach((cb) => {
            cb.checked = false;
        });
        document.getElementById("selectAll").checked = false;
        updateBulkActions();
    }

    function skipEvent(eventId) {
        const row = document.getElementById(`event-${eventId}`);
        row.classList.add("skipped");
        const checkbox = row.querySelector(".event-checkbox");
        checkbox.checked = false;
        checkbox.disabled = true;
        updateBulkActions();
    }

    function importSummary(result) {
        let message = `✅ ${text.success}\n\n${result.created} ${text.eventsImported}\n${result.skipped} ${text.skipped}`;
        if (result.errors && result.errors.length > 0) {
            message += `\n\n❌ ${result.errors.length} ${text.errors}:\n\n`;
            result.errors.forEach((err, idx) => {
                message += `${idx + 1}. ${err}\n`;
            });
        }
        return message;
    }

    async function importSelected(button) {
        if (selectedEvents.size === 0) {
            alert(text.selectOne);
            return;
        }

        const label = button.textContent;
        button.disabled = true;
        button.textContent = `⏳ ${text.importing}`;

        const events = Array.from(selectedEvents)
            .map((eventId) => {
                const row = document.getElementById(`event-${eventId}`);
                const clientId = row.querySelector(".client-select").value;
                const serviceTypeId = row.querySelector(".service-select").value;
                if (!clientId || !serviceTypeId) return null;
                return {
                    id: eventId,
                    action: "import",
                    client_id: parseInt(clientId),
                    service_type_id: parseInt(serviceTypeId),
                };
            })
            .filter((event) => event !== null);

        if (events.length === 0) {
            alert(text.selectClientAndService);
            button.disabled = false;
            button.textContent = label;
            return;
        }

        try {
            const response = await MPHttp.postJson(text.importUrl, { events: events });
            const result = await response.json();
            if (result.success) {
                alert(importSummary(result));
                // Only reload if something was created
                if (result.created > 0) window.location.reload();
            } else {
                alert(`❌ ${text.error}: ${result.error}`);
            }
        } catch (error) {
            alert(`❌ ${text.importError}: ${error.message}`);
        } finally {
            button.disabled = false;
            button.textContent = label;
        }
    }

    function init() {
        // Ready events start selected
        document.querySelectorAll('.event-row[data-is-ready="true"]').forEach((row) => {
            const checkbox = row.querySelector(".event-checkbox");
            if (checkbox && !checkbox.disabled) checkbox.checked = true;
        });
        updateBulkActions();

        ["js-import-top", "js-import-bottom"].forEach((id) => {
            const button = document.getElementById(id);
            if (button) button.addEventListener("click", () => importSelected(button));
        });
        ["toggleDuplicatesTop", "toggleDuplicates"].forEach((id) => {
            const button = document.getElementById(id);
            if (button) button.addEventListener("click", toggleDuplicates);
        });
        const clearButton = document.getElementById("js-clear-selection");
        if (clearButton) clearButton.addEventListener("click", clearSelection);
        const selectAll = document.getElementById("selectAll");
        if (selectAll) selectAll.addEventListener("change", () => toggleSelectAll(selectAll));
        document.querySelectorAll(".event-checkbox").forEach((cb) => {
            cb.addEventListener("change", updateBulkActions);
        });
        document.querySelectorAll("button[data-event-id]").forEach((button) => {
            button.addEventListener("click", () => skipEvent(button.dataset.eventId));
        });
    }

    document.addEventListener("DOMContentLoaded", init);
})();

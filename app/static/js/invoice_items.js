/**
 * Invoice create and edit forms: line items.
 *
 * Both pages share the item behaviour (the rate and duration follow the service
 * type, "add item" clones a row); #add-item says which page this is with
 * data-mode="new" | "edit". The client hourly rates come from #client-rates-data
 * ({clientId: {code, rate_60, rate_90}}), the "Item" label from data-item-label
 * and the invoice-number suggestion URL from data-next-number-url.
 *
 * new:  the invoice date follows the latest session date of a draft, the invoice
 *       number is suggested when a client is picked, and a client change refreshes
 *       the rates.
 * edit: rows ticked for deletion are marked, and a cloned row has no delete box.
 */

(function () {
    "use strict";

    const addButton = document.getElementById("add-item");
    if (!addButton) return;
    const isEdit = addButton.dataset.mode === "edit";
    const clientRates = JSON.parse(document.getElementById("client-rates-data").textContent);

    const clientSelect = document.getElementById("id_client");
    const invoiceNumberField = document.getElementById("id_invoice_number");
    const invoiceDateField = document.querySelector('input[name="invoice_date"]');
    const statusField = document.querySelector('select[name="status"]');

    function today() {
        return new Date().toISOString().split("T")[0];
    }

    function ratesForClient() {
        const clientId = clientSelect.value;
        return clientId && clientRates[clientId] ? clientRates[clientId] : null;
    }

    // Auto-update the invoice date to the latest session date (drafts only)
    function updateInvoiceDateToLatest() {
        if (statusField && statusField.value !== "draft") return;

        let latestDate = null;
        document.querySelectorAll('input[name*="session_date"]').forEach(function (field) {
            if (field.value) {
                const date = new Date(field.value);
                if (!latestDate || date > latestDate) latestDate = date;
            }
        });

        if (latestDate && invoiceDateField) {
            const current = invoiceDateField.value ? new Date(invoiceDateField.value) : null;
            if (!current || latestDate > current) {
                invoiceDateField.value = latestDate.toISOString().split("T")[0];
            }
        }
    }

    function updateRateForItem(rateField, serviceSelect) {
        const rates = ratesForClient();
        if (!rates) return;
        const serviceText = serviceSelect?.options[serviceSelect.selectedIndex]?.text || "";
        rateField.value = serviceText.includes("90") ? rates.rate_90 : rates.rate_60;
    }

    function updateAllRates() {
        if (!ratesForClient()) return;
        document.querySelectorAll("[data-item-rate]").forEach(function (rateField) {
            const row = rateField.closest(".formset-item");
            if (row) updateRateForItem(rateField, row.querySelector("[data-item-service]"));
        });
    }

    async function suggestInvoiceNumber(clientId) {
        if (!clientId || invoiceNumberField.value) return;
        try {
            const response = await fetch(addButton.dataset.nextNumberUrl + "?client=" + clientId);
            if (response.ok) {
                const data = await response.json();
                if (data.suggested_number && !invoiceNumberField.value) {
                    invoiceNumberField.value = data.suggested_number;
                }
            }
        } catch (error) {
            console.log("Could not fetch next invoice number:", error);
        }
    }

    // Duration and rate follow the service type of a row
    function applyServiceType(select) {
        const row = select.closest(".formset-item");
        const rateField = row.querySelector("[data-item-rate]");
        const durationField = row.querySelector('input[name*="duration"]');
        const serviceText = select.options[select.selectedIndex]?.text;
        if (!serviceText) return;

        const rates = ratesForClient();
        let duration = "60";
        let rate = rates && rates.rate_60;
        if (serviceText.includes("60")) {
            duration = "60";
        } else if (serviceText.includes("90")) {
            duration = "90";
            rate = rates && rates.rate_90;
        } else if (serviceText.toLowerCase().includes("cancellation")) {
            duration = "0";
        }
        if (durationField) durationField.value = duration;
        if (rates && rateField) rateField.value = rate;
    }

    function addItem() {
        const container = document.getElementById("items-container");
        const totalForms = document.querySelector("#id_items-TOTAL_FORMS");
        const formNum = parseInt(totalForms.value);

        // The edit form clones the first row, the create form the last one
        const template = isEdit
            ? container.querySelector(".formset-item")
            : container.querySelector(".formset-item:last-child");
        if (!template) return;

        const newItem = template.cloneNode(true);
        newItem.classList.remove("deleted");
        newItem.innerHTML = newItem.innerHTML.replace(new RegExp("items-(\\d+)-", "g"), "items-" + formNum + "-");

        newItem.querySelectorAll("input, select, textarea").forEach(function (field) {
            if (field.type === "checkbox") {
                field.checked = false;
            } else if (!/TOTAL_FORMS|INITIAL_FORMS|MIN_NUM|MAX_NUM/.test(field.name)) {
                field.value = "";
            }
            if (field.name.includes("session_date") && field.type === "date") field.value = today();
            if (field.name.includes("duration")) field.value = "60";
        });

        // Default to the 60 minute service type; its change event fills duration and rate
        const serviceTypeSelect = newItem.querySelector('select[name*="service_type"]');
        if (serviceTypeSelect) {
            const therapy60 = Array.from(serviceTypeSelect.options).find((opt) => opt.text.includes("60"));
            if (therapy60) {
                serviceTypeSelect.value = therapy60.value;
                serviceTypeSelect.dispatchEvent(new Event("change", { bubbles: true }));
            }
        }

        newItem.querySelector("strong").textContent = addButton.dataset.itemLabel + " " + (formNum + 1);

        // A new row has nothing to delete yet
        if (isEdit) {
            const deleteLabel = newItem.querySelector(".delete-label");
            if (deleteLabel) deleteLabel.remove();
        }

        container.appendChild(newItem);
        totalForms.value = formNum + 1;

        const rates = ratesForClient();
        const rateField = newItem.querySelector("[data-item-rate]");
        if (rates && newItem.querySelector("[data-item-service]") && rateField) {
            rateField.value = rates.rate_60;
        }

        if (!isEdit) updateInvoiceDateToLatest();
    }

    document.addEventListener("change", function (e) {
        if (e.target.matches("[data-item-service]")) applyServiceType(e.target);
        if (!isEdit && e.target.matches('input[name*="session_date"]')) updateInvoiceDateToLatest();
        if (isEdit && e.target.type === "checkbox" && e.target.name.includes("DELETE")) {
            const item = e.target.closest(".formset-item");
            if (item) item.classList.toggle("deleted", e.target.checked);
        }
    });

    addButton.addEventListener("click", addItem);

    if (isEdit) {
        document.querySelectorAll('input[type="checkbox"][name*="DELETE"]:checked').forEach(function (checkbox) {
            const item = checkbox.closest(".formset-item");
            if (item) item.classList.add("deleted");
        });
    } else {
        clientSelect.addEventListener("change", function () {
            suggestInvoiceNumber(clientSelect.value);
            updateAllRates();
        });
        if (clientSelect.value) clientSelect.dispatchEvent(new Event("change"));
        if (invoiceDateField && !invoiceDateField.value) invoiceDateField.value = today();
    }
})();

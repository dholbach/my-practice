/**
 * Invoice detail page: change the invoice status from the dropdown without a
 * reload, then update the badge and the "Paid on" date and flash a toast.
 *
 * The update URL and the texts come from data-* attributes on this file's own
 * <script> tag (see invoice_detail.html), so the strings stay inside the template
 * surface the i18n coverage guardrail scans. The CSRF token comes from
 * <body data-csrf-token>; the view reads a form-encoded POST.
 */

(function () {
    "use strict";

    const tag = document.getElementById("invoice-detail-js");
    const select = document.getElementById("status-select");
    if (!tag || !select) return;
    const text = tag.dataset;

    function showPaidDate(paidDate) {
        const value = document.getElementById("paid-date-value");
        if (!value) return;
        if (paidDate) {
            value.textContent = paidDate;
        } else {
            const dash = document.createElement("span");
            dash.className = "text-muted";
            dash.textContent = "-";
            value.replaceChildren(dash);
        }
    }

    function showToast(display) {
        const toast = document.createElement("div");
        toast.className = "alert-box success";
        toast.style.cssText =
            "position: fixed; top: 20px; right: 20px; z-index: 1000; box-shadow: 0 4px 12px rgba(0,0,0,0.15);";
        const message = document.createElement("strong");
        message.textContent = `${text.statusChanged} ${display}`;
        toast.appendChild(message);
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }

    select.addEventListener("change", async function () {
        const newStatus = this.value;
        if (!newStatus) return;

        try {
            const response = await fetch(text.updateUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-CSRFToken": document.body.dataset.csrfToken,
                },
                body: `status=${encodeURIComponent(newStatus)}`,
            });
            if (!response.ok) return;

            const data = await response.json();
            const badge = document.getElementById("status-badge");
            badge.className = `status-badge ${data.status}`;
            badge.textContent = data.display;
            this.value = "";
            showPaidDate(data.paid_date);
            showToast(data.display);
        } catch (error) {
            console.error("Error:", error);
            alert(text.error);
        }
    });
})();

/**
 * Bank review page: live tally of selected invoice amounts.
 *
 * For each multi-invoice <select> in the manual-assignment forms,
 * shows the sum of selected invoices and highlights whether it matches
 * the transaction amount.
 *
 * Option label format (from TransactionMatchForm._invoice_label):
 *   "LI-3 (2025-12-15): 90.00 €"  (thousands separated by space, decimal by dot)
 */

(function () {
    "use strict";

    function parseOptionAmount(optionText) {
        // Extract the amount from "LI-3 (2025-12-15): 1 234.56 €"
        const match = optionText.match(/:\s*([\d\s]+\.?\d*)\s*€\s*$/);
        if (!match) return NaN;
        // Spaces are used as thousands separators – remove them before parsing
        return parseFloat(match[1].replace(/\s/g, ""));
    }

    function formatAmount(value) {
        // Simple German-style: 1234.56 → "1.234,56"
        return value
            .toFixed(2)
            .replace(".", ",")
            .replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    }

    function updateTally(select, tally, transactionAmount) {
        const selected = Array.from(select.selectedOptions);

        if (selected.length === 0) {
            tally.style.display = "none";
            return;
        }

        let total = 0;
        let parseError = false;
        selected.forEach(function (opt) {
            const amount = parseOptionAmount(opt.text);
            if (isNaN(amount)) {
                parseError = true;
            } else {
                total += amount;
            }
        });

        if (parseError) {
            tally.style.display = "none";
            return;
        }

        const formattedTotal = formatAmount(total);
        const diff = Math.abs(total - transactionAmount);
        const matches = diff < 0.005; // float tolerance

        let icon, extraInfo;
        if (!isNaN(transactionAmount)) {
            if (matches) {
                icon = "✅";
                extraInfo = " — passt zur Transaktion";
            } else {
                const diffFormatted = formatAmount(Math.abs(total - transactionAmount));
                const sign = total > transactionAmount ? "+" : "−";
                icon = "⚠️";
                extraInfo = ` — Differenz: ${sign}${diffFormatted} €`;
            }
        } else {
            icon = "📊";
            extraInfo = "";
        }

        const countLabel =
            selected.length === 1 ? "1 Rechnung" : `${selected.length} Rechnungen`;

        tally.innerHTML = `${icon} <strong>${countLabel}:</strong> ${formattedTotal} €<span style="font-size:0.8em;opacity:0.85;">${extraInfo}</span>`;
        tally.style.display = "block";

        if (matches) {
            tally.style.background = "var(--color-success-bg)";
            tally.style.color = "var(--color-success)";
            tally.style.borderLeftColor = "var(--color-success)";
        } else {
            tally.style.background = "var(--color-warning-bg)";
            tally.style.color = "var(--color-warning)";
            tally.style.borderLeftColor = "var(--color-warning)";
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll('select[name="invoice"]').forEach(function (select) {
            // Walk up to find the form element with data-amount
            const form = select.closest("form[data-amount]");
            const transactionAmount = form
                ? parseFloat(form.dataset.amount)
                : NaN;

            // Insert tally element directly after the <select>
            const tally = document.createElement("div");
            tally.style.cssText =
                "display:none; margin-top:0.5rem; padding:0.4rem 0.75rem; border-radius:6px;" +
                "border-left:3px solid; font-size:0.875rem; font-weight:600;";
            select.insertAdjacentElement("afterend", tally);

            select.addEventListener("change", function () {
                updateTally(select, tally, transactionAmount);
            });
        });
    });
})();

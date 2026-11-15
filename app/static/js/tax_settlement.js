/**
 * Tax quarter overview: the "Tax Assessment (Steuerbescheid)" card, an Alpine
 * component registered by name (the CSP build of Alpine, with no 'unsafe-eval' in
 * script-src, cannot call a global function from x-data).
 *
 * The element carrying x-data="taxSettlement" supplies everything through data-*
 * attributes (see tax_quarter_overview.html): year, save URL, the stored amount
 * and date, and the error texts, so the strings stay inside the template surface
 * the i18n coverage guardrail scans. The CSRF token comes from <body data-csrf-token>.
 */

document.addEventListener("alpine:init", function () {
    Alpine.data("taxSettlement", function () {
        return {
            editing: false,
            saving: false,
            error: "",
            amount: "",
            settlementDate: "",

            init() {
                this.amount = this.$el.dataset.amount;
                this.settlementDate = this.$el.dataset.settlementDate;
            },

            startEdit() {
                this.error = "";
                this.editing = true;
            },

            cancel() {
                this.editing = false;
                this.error = "";
            },

            async save() {
                const text = this.$el.dataset;
                this.saving = true;
                this.error = "";
                const data = new FormData();
                data.append("year", text.year);
                data.append("settlement_amount", this.amount);
                data.append("settlement_date", this.settlementDate);
                data.append("csrfmiddlewaretoken", document.body.dataset.csrfToken);
                try {
                    const response = await fetch(text.saveUrl, { method: "POST", body: data });
                    const json = await response.json();
                    if (json.saved) {
                        window.location.reload();
                    } else {
                        this.error = json.error || text.saveFailed;
                    }
                } catch {
                    this.error = text.networkError;
                } finally {
                    this.saving = false;
                }
            },

            async clear() {
                this.amount = "";
                this.settlementDate = "";
                await this.save();
            },
        };
    });
});

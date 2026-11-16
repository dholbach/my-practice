/**
 * Analytics page: the period filter's custom date range, the revenue / clients /
 * capacity / expenses tabs, and the "show dormant clients" toggle.
 *
 * Wired with listeners instead of inline handlers (CSP). The active tab is kept in
 * the ?tab= query parameter and in the filter form's hidden "tab" input, so a
 * period change keeps the tab the user is on.
 */

(function () {
    "use strict";

    function toggleCustomDates() {
        const period = document.getElementById("period");
        const customDates = document.getElementById("customDates");
        if (!period || !customDates) return;
        customDates.style.display = period.value === "custom" ? "flex" : "none";
    }

    function toggleDormantClients() {
        const checkbox = document.getElementById("toggle-dormant");
        if (!checkbox) return;
        document.querySelectorAll("table.client-table tbody tr").forEach(function (row) {
            if (row.dataset.clientStatus === "dormant") {
                row.style.display = checkbox.checked ? "" : "none";
            }
        });
    }

    function showTab(tabName) {
        document.querySelectorAll(".tab-content").forEach((tab) => tab.classList.remove("active"));
        document.querySelectorAll(".tab-button").forEach((btn) => btn.classList.remove("active"));
        const content = document.getElementById(tabName + "-tab");
        if (content) content.classList.add("active");
        const button = document.querySelector('.tab-button[data-tab="' + tabName + '"]');
        if (button) button.classList.add("active");
    }

    function switchTab(tabName) {
        const url = new URL(window.location.href);
        url.searchParams.set("tab", tabName);
        window.history.pushState({}, "", url);
        showTab(tabName);
        const tabInput = document.querySelector('input[name="tab"]');
        if (tabInput) tabInput.value = tabName;
    }

    document.addEventListener("DOMContentLoaded", function () {
        toggleCustomDates();
        const period = document.getElementById("period");
        if (period) period.addEventListener("change", toggleCustomDates);

        toggleDormantClients();
        const dormant = document.getElementById("toggle-dormant");
        if (dormant) dormant.addEventListener("change", toggleDormantClients);

        document.querySelectorAll(".tab-button[data-tab]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                switchTab(btn.dataset.tab);
            });
        });
        showTab(new URLSearchParams(window.location.search).get("tab") || "revenue");
    });
})();

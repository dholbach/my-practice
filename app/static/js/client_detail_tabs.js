/**
 * Client detail page: the Overview / Protocol / Billing tabs.
 *
 * Wired with a delegated click listener rather than inline onclick= attributes,
 * which the CSP (script-src without 'unsafe-inline') does not run. A trigger names
 * its tab with data-tab (the tab buttons) or data-page-tab (cockpit shortcuts), and
 * may name an Alpine toggle inside that tab to click once it is visible
 * (data-click-in-tab, e.g. "showNote"). The tab is kept in the URL hash (#ptab-<name>)
 * and restored on load; a tab holding a form_draft_guard'd unsaved edit is marked
 * on its button, since the browser's beforeunload dialog says nothing about where.
 */

(function () {
    "use strict";

    function pageTab(tabName, button) {
        document.querySelectorAll(".page-tab-content").forEach((el) => el.classList.remove("page-tab-active"));
        document.querySelectorAll(".page-tab-btn").forEach((el) => el.classList.remove("page-tab-active"));
        document.getElementById("ptab-" + tabName).classList.add("page-tab-active");
        if (button) button.classList.add("page-tab-active");
        if (history.replaceState) history.replaceState(null, "", "#ptab-" + tabName);
    }

    document.addEventListener("click", function (e) {
        const scrollLink = e.target.closest("[data-smooth-scroll]");
        if (scrollLink) {
            e.preventDefault();
            document.querySelector(scrollLink.getAttribute("href")).scrollIntoView({ behavior: "smooth" });
            return;
        }
        const trigger = e.target.closest(".page-tab-btn[data-tab], [data-page-tab]");
        if (!trigger) return;
        e.preventDefault();
        const tabName = trigger.dataset.pageTab || trigger.dataset.tab;
        pageTab(tabName, document.querySelector('.page-tab-btn[data-tab="' + tabName + '"]'));
        const toggle = trigger.dataset.clickInTab;
        if (toggle) {
            setTimeout(function () {
                const el = document.querySelector("#ptab-" + tabName + " [x-on\\:click*=" + toggle + "]");
                if (el) el.click();
            }, 100);
        }
    });

    // Restore the tab from the URL hash on load
    const hash = window.location.hash;
    if (hash.startsWith("#ptab-")) {
        const tabName = hash.replace("#ptab-", "");
        if (document.getElementById("ptab-" + tabName)) {
            pageTab(tabName, document.querySelector('[data-tab="' + tabName + '"]'));
        }
    }

    document.addEventListener("draftguard:dirty", function (e) {
        const tabContent = e.target.closest(".page-tab-content");
        if (!tabContent) return;
        const tabName = tabContent.id.replace("ptab-", "");
        const button = document.querySelector('.page-tab-btn[data-tab="' + tabName + '"]');
        if (!button) return;
        button.classList.toggle("page-tab-btn--dirty", e.detail.dirty);
        button.title = e.detail.dirty ? document.querySelector(".page-tab-bar").dataset.unsavedLabel : "";
    });
})();

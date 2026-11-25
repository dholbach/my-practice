/**
 * Client detail page: the Clinical / Admin modes.
 *
 * The page has two modes. Clinical shows the overview and the protocol one below the
 * other in a single scroll; Admin shows billing, contact and onboarding. Each section
 * (#ptab-<name>) carries data-mode, and the mode buttons carry the same, so one click
 * shows every section of a mode. The section names stay in the URL hash (#ptab-<name>)
 * and keep working from links elsewhere in the app: #ptab-protokoll opens the clinical
 * mode and scrolls to the protocol (the sections marked data-scroll-on-open), the
 * others just open their mode.
 *
 * Wired with a delegated click listener rather than inline onclick= attributes,
 * which the CSP (script-src without 'unsafe-inline') does not run. A trigger names
 * its section with data-tab (the mode buttons) or data-page-tab (shortcuts), and
 * may name an Alpine toggle inside that section to click once it is visible
 * (data-click-in-tab, e.g. "showNote"). A mode holding a form_draft_guard'd unsaved
 * edit is marked on its button, since the browser's beforeunload dialog says
 * nothing about where.
 */

(function () {
    "use strict";

    function showMode(mode) {
        document.querySelectorAll(".page-tab-content").forEach((el) => el.classList.toggle("page-tab-active", el.dataset.mode === mode));
        document.querySelectorAll(".page-tab-btn").forEach((el) => el.classList.toggle("page-tab-active", el.dataset.mode === mode));
    }

    // Opens the mode of a section and returns it, or null for a name the page does not have.
    function pageTab(tabName) {
        const section = document.getElementById("ptab-" + tabName);
        if (!section) return null;
        showMode(section.dataset.mode);
        if (history.replaceState) history.replaceState(null, "", "#ptab-" + tabName);
        return section;
    }

    function scrollsOnOpen(section) {
        return section.dataset.scrollOnOpen !== undefined;
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
        const section = pageTab(tabName);
        if (!section) return;
        // A shortcut to a section further down the page takes you there; a mode button does not.
        if (trigger.dataset.pageTab && scrollsOnOpen(section)) section.scrollIntoView({ behavior: "smooth" });
        const toggle = trigger.dataset.clickInTab;
        if (toggle) {
            setTimeout(function () {
                const el = document.querySelector("#ptab-" + tabName + " [x-on\\:click*=" + toggle + "]");
                if (el) el.click();
            }, 100);
        }
    });

    // Restore the section from the URL hash on load
    const hash = window.location.hash;
    if (hash.startsWith("#ptab-")) {
        const section = pageTab(hash.replace("#ptab-", ""));
        if (section && scrollsOnOpen(section)) section.scrollIntoView();
    }

    document.addEventListener("draftguard:dirty", function (e) {
        const content = e.target.closest(".page-tab-content");
        if (!content) return;
        const button = document.querySelector('.page-tab-btn[data-mode="' + content.dataset.mode + '"]');
        if (!button) return;
        button.classList.toggle("page-tab-btn--dirty", e.detail.dirty);
        button.title = e.detail.dirty ? document.querySelector(".page-tab-bar").dataset.unsavedLabel : "";
    });
})();

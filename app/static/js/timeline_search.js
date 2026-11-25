/**
 * Client detail page: search and "older entries" toggle for the protocol timeline.
 *
 * The timeline is rendered server-side with every entry (a client has at most a few
 * hundred), so searching needs no request: the text is already in the page, which is
 * also the only place it exists in the clear (the database holds it encrypted).
 *
 *   <input type="search" data-timeline-search="#timeline"      the list to filter
 *          data-timeline-count="#count"                         where "N matching entries" goes
 *          data-timeline-empty="#none"                          shown (un-hidden) when nothing matches
 *          data-count-template="{count} matching entries">      translated, {count} is replaced
 *   <div id="timeline"> <div class="cn-timeline-entry"> ...      one per entry; only the
 *                           <span class="cn-searchable">         .cn-searchable text is matched,
 *                                                                so button labels never match
 *   <button data-timeline-toggle="#timeline"                     expand / collapse the entries
 *           data-label-show="..." data-label-hide="...">         beyond the first ten
 *
 * Matching ignores case and diacritics ("cafe" finds "Café"). While a query is
 * typed the list gets .cn-searching, which shows older entries too, and the matching
 * entries' <details> are opened; clearing the query restores what was open before.
 */
(function () {
    "use strict";

    function fold(text) {
        return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLocaleLowerCase();
    }

    function slice(list) {
        return Array.prototype.slice.call(list);
    }

    function setup(input) {
        const list = document.querySelector(input.dataset.timelineSearch);
        if (!list) return;
        const count = document.querySelector(input.dataset.timelineCount);
        const none = document.querySelector(input.dataset.timelineEmpty);
        const entries = slice(list.querySelectorAll(".cn-timeline-entry")).map(function (entry) {
            return {
                el: entry,
                text: fold(slice(entry.querySelectorAll(".cn-searchable")).map(function (part) { return part.textContent; }).join(" ")),
                details: slice(entry.querySelectorAll("details")).map(function (d) { return { el: d, open: d.open }; }),
            };
        });

        function apply() {
            const query = fold(input.value.trim());
            list.classList.toggle("cn-searching", query !== "");
            let matches = 0;
            entries.forEach(function (entry) {
                const hit = query === "" || entry.text.indexOf(query) !== -1;
                entry.el.hidden = !hit;
                if (hit && query !== "") matches += 1;
                entry.details.forEach(function (d) { d.el.open = query !== "" && hit ? true : d.open; });
            });
            if (count) count.textContent = query === "" ? "" : input.dataset.countTemplate.replace("{count}", String(matches));
            if (none) none.hidden = query === "" || matches > 0;
        }

        input.addEventListener("input", apply);
    }

    document.addEventListener("click", function (e) {
        const toggle = e.target.closest("[data-timeline-toggle]");
        if (!toggle) return;
        const list = document.querySelector(toggle.dataset.timelineToggle);
        if (!list) return;
        const expanded = !list.classList.contains("cn-show-old");
        list.classList.toggle("cn-show-old", expanded);
        toggle.textContent = expanded ? toggle.dataset.labelHide : toggle.dataset.labelShow;
    });

    function init() {
        slice(document.querySelectorAll("[data-timeline-search]")).forEach(setup);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();

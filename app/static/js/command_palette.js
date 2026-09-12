/**
 * Command Palette (P-047) — ⌘K / Ctrl+K, or "/".
 *
 * The markup lives in templates/includes/command_palette.html and is rendered
 * server-side; this file only opens/closes it, filters the static entries,
 * queries /api/search/ and moves the selection. That split is deliberate:
 *   - every label stays inside {% trans %}, where the i18n guardrail can see it
 *     (a translated string hardcoded here would be invisible to it), and
 *   - every rule stays in tailwind.css under .cmd-palette* (M-PAT-04) rather
 *     than in style.cssText, the way the global-search.js this replaced did.
 *
 * Filtering reads each static item's own textContent, so no label is duplicated
 * into a data-* attribute and can't drift out of sync with what's rendered.
 *
 * Search rows are built with createElement + textContent rather than an
 * innerHTML string. global-search.js had to escape result labels on the way in
 * (client and inquiry names legitimately contain & and <, which rendered as
 * broken markup or vanished); building nodes removes that whole class of bug
 * instead of guarding against it.
 */

(function () {
    'use strict';

    const ITEM_SELECTOR = '.cmd-palette__item';
    const SEARCH_URL = '/api/search/';
    const SEARCH_DEBOUNCE_MS = 300;

    let palette = null;
    let input = null;
    let resultsGroup = null;
    let resultsContainer = null;
    let loading = null;
    let error = null;
    let empty = null;

    let groups = [];
    // Fixed at init; the server-rendered "Jump to" and "Actions" entries.
    let staticItems = [];
    // Rebuilt on every search response.
    let resultItems = [];
    // Visible items in DOM order — search results first, then static entries.
    let visible = [];
    let selectedIndex = -1;

    let searchState = 'idle'; // 'idle' | 'loading' | 'done' | 'error'
    let searchTimeout = null;

    /* Monotonic id for the newest search the user has asked for. Carried over
       from global-search.js, where it fixed a live bug: the debounce only spaces
       requests out, it does not stop two being in flight at once, and fetch
       resolves in completion order rather than call order. Type "sch", pause,
       then finish "schmidt": if the first request is the slower of the two, its
       results land last and the palette ends up showing matches for a query the
       box no longer contains — with Enter navigating to one of them. Each
       response checks it is still the newest before touching any state. */
    let latestRequestId = 0;

    // Element focused before the palette opened, so Esc can hand focus back
    // instead of dropping it on <body> and stranding keyboard users.
    let previouslyFocused = null;

    function normalize(text) {
        return text.toLowerCase().trim();
    }

    function isOpen() {
        return palette !== null && !palette.hidden;
    }

    function isTyping(target) {
        if (!target || !target.tagName) return false;
        const tag = target.tagName.toLowerCase();
        if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
        return Boolean(target.isContentEditable);
    }

    function clearSelection() {
        selectedIndex = -1;
        staticItems.concat(resultItems).forEach(function (item) {
            item.classList.remove('cmd-palette__item--selected');
            item.removeAttribute('aria-selected');
        });
    }

    function setSelected(index) {
        if (visible.length === 0) {
            clearSelection();
            return;
        }
        clearSelection();
        // Wrap around: ↓ past the end returns to the top, ↑ past the top to the
        // end — a long "Jump to" list is otherwise a dead end in both directions.
        selectedIndex = ((index % visible.length) + visible.length) % visible.length;

        const current = visible[selectedIndex];
        current.classList.add('cmd-palette__item--selected');
        current.setAttribute('aria-selected', 'true');
        current.scrollIntoView({ block: 'nearest' });
    }

    /**
     * Recomputes what is on screen: group visibility, the status lines, the
     * visible-item list and the selection. Called after anything that can change
     * the contents — a keystroke, or a search response landing later.
     */
    function refresh(keepSelection) {
        // Hide a group whose every item was filtered out, so its heading doesn't
        // sit above nothing.
        groups.forEach(function (group) {
            group.hidden = group.querySelector(ITEM_SELECTOR + ':not([hidden])') === null;
        });

        visible = resultItems
            .filter(function (item) { return !item.hidden; })
            .concat(staticItems.filter(function (item) { return !item.hidden; }));

        loading.hidden = searchState !== 'loading';
        error.hidden = searchState !== 'error';
        // While a search is in flight or has failed, that line is the message —
        // "No results" on top of it would be both noisy and premature.
        empty.hidden = visible.length > 0 || searchState === 'loading' || searchState === 'error';

        if (visible.length === 0) {
            clearSelection();
        } else if (keepSelection && selectedIndex >= 0 && selectedIndex < visible.length) {
            setSelected(selectedIndex);
        } else {
            // Pre-select the first match so ↵ works without pressing ↓ first.
            setSelected(0);
        }
    }

    function filterStaticItems(query) {
        const needle = normalize(query);
        staticItems.forEach(function (item) {
            item.hidden = needle !== '' && !normalize(item.textContent).includes(needle);
        });
    }

    function renderResults(results) {
        resultsContainer.textContent = '';
        resultItems = results.map(function (result) {
            const item = document.createElement('a');
            item.className = 'cmd-palette__item';
            item.setAttribute('role', 'option');
            item.setAttribute('href', result.url);
            // The API pre-bakes the icon into result.label ("👤 XX-1 — Name").
            item.textContent = result.label;
            item.addEventListener('mouseenter', function () {
                selectItem(item);
            });
            resultsContainer.appendChild(item);
            return item;
        });
        resultsGroup.hidden = resultItems.length === 0;
    }

    function discardResults() {
        resultsContainer.textContent = '';
        resultItems = [];
        resultsGroup.hidden = true;
    }

    function clearResults() {
        // Retire any in-flight request too, so a response for text the user has
        // already deleted cannot repopulate the list behind them.
        latestRequestId++;
        discardResults();
        searchState = 'idle';
    }

    function performSearch(query) {
        const requestId = ++latestRequestId;
        searchState = 'loading';
        refresh(true);

        fetch(SEARCH_URL + '?q=' + encodeURIComponent(query))
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (requestId !== latestRequestId) return;
                searchState = 'done';
                renderResults(data.results || []);
                refresh(false);
            })
            .catch(function (err) {
                console.error('Command palette search error:', err);
                // A stale failure must not clear the newer query's results
                // either, so this is checked after the log, not before it.
                if (requestId !== latestRequestId) return;
                searchState = 'error';
                // Drop the previous query's rows too: without this, Enter still
                // navigates to whatever was showing before the failure.
                discardResults();
                refresh(false);
            });
    }

    function handleInput() {
        const query = input.value.trim();

        if (searchTimeout) {
            clearTimeout(searchTimeout);
            searchTimeout = null;
        }

        // The static list filters on every keystroke; only the network call is
        // debounced, so the palette never feels like it lags behind typing.
        filterStaticItems(query);

        if (query === '') {
            clearResults();
            refresh(false);
            return;
        }

        refresh(false);
        searchTimeout = setTimeout(function () {
            performSearch(query);
        }, SEARCH_DEBOUNCE_MS);
    }

    function selectItem(item) {
        const index = visible.indexOf(item);
        if (index !== -1) setSelected(index);
    }

    function open() {
        if (!palette || isOpen()) return;
        previouslyFocused = document.activeElement;
        palette.hidden = false;
        document.body.classList.add('cmd-palette-open');
        input.value = '';
        filterStaticItems('');
        clearResults();
        refresh(false);
        input.focus();
    }

    function close() {
        if (!palette || !isOpen()) return;
        if (searchTimeout) {
            clearTimeout(searchTimeout);
            searchTimeout = null;
        }
        palette.hidden = true;
        document.body.classList.remove('cmd-palette-open');
        if (previouslyFocused && typeof previouslyFocused.focus === 'function') {
            previouslyFocused.focus();
        }
        previouslyFocused = null;
    }

    function handlePaletteKeydown(event) {
        if (event.key === 'Escape') {
            event.preventDefault();
            close();
        } else if (event.key === 'ArrowDown') {
            event.preventDefault();
            setSelected(selectedIndex + 1);
        } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            setSelected(selectedIndex - 1);
        } else if (event.key === 'Enter') {
            const current = visible[selectedIndex];
            if (current) {
                event.preventDefault();
                window.location.href = current.getAttribute('href');
            }
        }
    }

    function handleGlobalKeydown(event) {
        // ⌘K on macOS, Ctrl+K elsewhere. Both are the browser's own
        // search-bar shortcut, so preventDefault is not optional here.
        if ((event.metaKey || event.ctrlKey) && !event.altKey && event.key.toLowerCase() === 'k') {
            event.preventDefault();
            if (isOpen()) {
                close();
            } else {
                open();
            }
            return;
        }

        // "/" kept as an alias: it focused the old header search box, and that
        // is the muscle memory this palette inherits.
        if (event.key === '/' && !event.metaKey && !event.ctrlKey && !event.altKey) {
            if (isOpen() || isTyping(event.target)) return;
            event.preventDefault();
            open();
        }
    }

    function initialize() {
        palette = document.getElementById('command-palette');
        if (!palette) return;

        input = document.getElementById('cmd-palette-input');
        resultsGroup = document.getElementById('cmd-palette-results-group');
        resultsContainer = document.getElementById('cmd-palette-results');
        loading = document.getElementById('cmd-palette-loading');
        error = document.getElementById('cmd-palette-error');
        empty = document.getElementById('cmd-palette-empty');

        groups = Array.prototype.slice.call(palette.querySelectorAll('.cmd-palette__group'));
        staticItems = Array.prototype.slice.call(palette.querySelectorAll(ITEM_SELECTOR));

        input.addEventListener('input', handleInput);
        input.addEventListener('keydown', handlePaletteKeydown);

        palette.querySelectorAll('[data-cmdk-dismiss]').forEach(function (el) {
            el.addEventListener('click', close);
        });

        // Hover should track the keyboard selection, so ↵ always opens what is
        // highlighted regardless of which input the user reached for last.
        staticItems.forEach(function (item) {
            item.addEventListener('mouseenter', function () {
                selectItem(item);
            });
        });

        document.addEventListener('keydown', handleGlobalKeydown);

        // The header trigger is the discoverability and touch story — ⌘K alone
        // is invisible and unreachable on a phone.
        const trigger = document.getElementById('cmd-palette-trigger');
        if (trigger) {
            trigger.addEventListener('click', open);
        }

        // Show the shortcut in the form the user's own keyboard has. Both
        // variants are rendered so neither is a translatable string in here.
        const isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || '');
        document.querySelectorAll('[data-cmdk-key]').forEach(function (el) {
            el.hidden = el.dataset.cmdkKey !== (isMac ? 'mac' : 'other');
        });

        refresh(false);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize);
    } else {
        initialize();
    }
})();

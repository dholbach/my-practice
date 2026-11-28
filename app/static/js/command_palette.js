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
 * Quick capture: "note XX-1 ask about sleep" swaps the list for one row that
 * POSTs a "for next time" reminder instead of navigating. The row's wording
 * (data-label, data-failed) comes from the template; the server resolves the
 * client code and answers with the text to show, so nothing translatable lives
 * here either.
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
    // "note <client code> <text>": the capture command.
    const CAPTURE_PATTERN = /^note\s+(\S+)\s+(\S[\s\S]*)$/i;

    let palette = null;
    let input = null;
    let resultsGroup = null;
    let resultsContainer = null;
    let loading = null;
    let error = null;
    let empty = null;

    let groups = [];
    // The quick-capture row and its group; null where the template has none.
    let captureItem = null;
    let captureGroup = null;
    let captureCommand = null; // {code, text} while the row is offered
    let capturing = false;
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

    function clearSelection() {
        selectedIndex = -1;
        staticItems.concat(resultItems, captureItem ? [captureItem] : []).forEach(function (item) {
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
            .concat(staticItems.filter(function (item) { return !item.hidden; }))
            .concat(captureItem && !captureItem.hidden ? [captureItem] : []);

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

    /**
     * Append a personal name with its initials left legible and the rest marked
     * sensitive, so privacy mode blurs it to "K… K…" instead of hiding the row.
     * Full blur is what the rest of the app does to a name, but it only works
     * where a client code identifies the row too; here the name is often the
     * only thing telling two results apart (inquiries have no code at all), so
     * this mirrors the privacy_name template filter in payment_tags.py — keep
     * the two in step if either changes.
     */
    function appendName(target, name) {
        String(name).trim().split(/\s+/).forEach(function (word, index) {
            if (index > 0) target.appendChild(document.createTextNode(' '));
            if (word.length > 1) {
                target.appendChild(document.createTextNode(word.charAt(0)));
                const rest = document.createElement('span');
                rest.className = 'sensitive-data pn-rest';
                rest.textContent = word.slice(1);
                target.appendChild(rest);
            } else {
                target.appendChild(document.createTextNode(word));
            }
        });
    }

    function renderResults(results) {
        resultsContainer.textContent = '';
        resultItems = results.map(function (result) {
            const item = document.createElement('a');
            item.className = 'cmd-palette__item';
            item.setAttribute('role', 'option');
            item.setAttribute('href', result.url);

            // prefix/name/suffix rather than one string: only `name` is
            // personal, and it needs its own treatment (see appendName).
            // Built as nodes, never innerHTML — names contain & and <.
            item.appendChild(document.createTextNode(result.prefix || ''));
            if (result.name) appendName(item, result.name);
            item.appendChild(document.createTextNode(result.suffix || ''));

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

    function setCaptureRow(command) {
        captureCommand = command;
        captureItem.hidden = command === null;
        captureGroup.hidden = command === null;
        if (command !== null) {
            captureItem.textContent = captureItem.dataset.label
                .replace('{code}', command.code)
                .replace('{text}', command.text);
        }
    }

    function submitCapture() {
        if (!captureCommand || capturing) return;
        const command = captureCommand;
        capturing = true;
        MPHttp.postForm(captureItem.dataset.url, { code: command.code, text: command.text })
            .then(function (response) { return response.json(); })
            .then(function (data) {
                capturing = false;
                if (data.success) {
                    // Saved: empty the box and show the server's confirmation in
                    // place of the row; the next keystroke starts afresh.
                    input.value = '';
                    captureCommand = null;
                    captureItem.textContent = data.message;
                } else {
                    // Keep the input so a mistyped code can be fixed in place.
                    captureItem.textContent = data.error;
                }
            })
            .catch(function (err) {
                console.error('Command palette capture error:', err);
                capturing = false;
                captureItem.textContent = captureItem.dataset.failed;
            });
    }

    function handleInput() {
        const query = input.value.trim();

        if (captureItem) {
            const match = CAPTURE_PATTERN.exec(query);
            if (match) {
                // A command is not a search: hide the entries and drop any
                // results, so Enter can only mean "save this reminder".
                if (searchTimeout) {
                    clearTimeout(searchTimeout);
                    searchTimeout = null;
                }
                clearResults();
                staticItems.forEach(function (item) { item.hidden = true; });
                setCaptureRow({ code: match[1], text: match[2].trim() });
                refresh(false);
                return;
            }
            setCaptureRow(null);
        }

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
        if (captureItem) setCaptureRow(null);
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
            if (current && current === captureItem) {
                event.preventDefault();
                submitCapture();
            } else if (current) {
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
            if (isOpen() || window.MPTyping.isTyping(event.target)) return;
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
        captureItem = document.getElementById('cmd-palette-capture');
        captureGroup = document.getElementById('cmd-palette-capture-group');
        // The capture row is not a static entry: it must not be filtered by
        // its label or navigated to.
        staticItems = Array.prototype.slice.call(palette.querySelectorAll(ITEM_SELECTOR))
            .filter(function (item) { return item !== captureItem; });

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

        if (captureItem) {
            captureItem.addEventListener('click', function (event) {
                event.preventDefault();
                submitCapture();
            });
            captureItem.addEventListener('mouseenter', function () {
                selectItem(captureItem);
            });
        }

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

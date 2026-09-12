/**
 * Command Palette (P-047 Phase 1) — ⌘K / Ctrl+K.
 *
 * The markup lives in templates/includes/command_palette.html and is rendered
 * server-side; this file only opens/closes it, filters the items and moves the
 * selection. That split is deliberate:
 *   - every label stays inside {% trans %}, where the i18n guardrail can see it
 *     (a translated string hardcoded here would be invisible to it), and
 *   - every rule stays in tailwind.css under .cmd-palette* (M-PAT-04) rather
 *     than in style.cssText the way global-search.js and keyboard-nav.js
 *     predate the rule by doing.
 *
 * Filtering reads each item's own textContent, so no label is duplicated into a
 * data-* attribute and can't drift out of sync with what's rendered.
 */

(function () {
    'use strict';

    const ITEM_SELECTOR = '.cmd-palette__item';

    let palette = null;
    let input = null;
    let empty = null;
    let items = [];
    let visible = [];
    let selectedIndex = -1;
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
        items.forEach(function (item) {
            item.classList.remove('cmd-palette__item--selected');
            item.removeAttribute('aria-selected');
        });
    }

    function setSelected(index) {
        if (visible.length === 0) {
            clearSelection();
            return;
        }
        // Wrap around: ↓ past the end returns to the top, ↑ past the top to the
        // end — a long "Jump to" list is otherwise a dead end in both directions.
        clearSelection();
        selectedIndex = ((index % visible.length) + visible.length) % visible.length;

        const current = visible[selectedIndex];
        current.classList.add('cmd-palette__item--selected');
        current.setAttribute('aria-selected', 'true');
        current.scrollIntoView({ block: 'nearest' });
    }

    function applyFilter(query) {
        const needle = normalize(query);

        visible = items.filter(function (item) {
            const match = needle === '' || normalize(item.textContent).includes(needle);
            item.hidden = !match;
            return match;
        });

        // Hide a group whose every item was filtered out, so its heading doesn't
        // sit above nothing.
        palette.querySelectorAll('.cmd-palette__group').forEach(function (group) {
            const hasVisible = group.querySelector(ITEM_SELECTOR + ':not([hidden])') !== null;
            group.hidden = !hasVisible;
        });

        if (empty) {
            empty.hidden = visible.length > 0;
        }

        // Pre-select the first match so ↵ works without pressing ↓ first.
        if (visible.length > 0) {
            setSelected(0);
        } else {
            clearSelection();
        }
    }

    function open() {
        if (!palette || isOpen()) return;
        previouslyFocused = document.activeElement;
        palette.hidden = false;
        document.body.classList.add('cmd-palette-open');
        input.value = '';
        applyFilter('');
        input.focus();
    }

    function close() {
        if (!palette || !isOpen()) return;
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
        }
    }

    function initialize() {
        palette = document.getElementById('command-palette');
        if (!palette) return;

        input = document.getElementById('cmd-palette-input');
        empty = document.getElementById('cmd-palette-empty');
        items = Array.prototype.slice.call(palette.querySelectorAll(ITEM_SELECTOR));

        input.addEventListener('input', function () {
            applyFilter(input.value);
        });
        input.addEventListener('keydown', handlePaletteKeydown);

        palette.querySelectorAll('[data-cmdk-dismiss]').forEach(function (el) {
            el.addEventListener('click', close);
        });

        // Hover should track the keyboard selection, so ↵ always opens what is
        // highlighted regardless of which input the user reached for last.
        items.forEach(function (item) {
            item.addEventListener('mouseenter', function () {
                const index = visible.indexOf(item);
                if (index !== -1) setSelected(index);
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

        applyFilter('');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize);
    } else {
        initialize();
    }
})();

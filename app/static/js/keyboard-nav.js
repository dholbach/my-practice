/**
 * Keyboard Navigation for Therapy Practice App
 *
 * Global shortcuts:
 * - ⌘K / Ctrl+K, or /: command palette (command_palette.js owns these)
 * - ?: help overlay
 *
 * Context-aware shortcuts:
 * - n: New (client/invoice depending on page)
 * - e: Edit (on detail pages)
 *
 * The single-letter global navigation keys (c/i/d/a/p) were retired in P-047
 * Phase 3: every destination they covered is in the command palette, and a bare
 * letter that navigates away the moment it lands outside an input is a poor
 * trade for that. The context-aware keys stay — they act on the record you are
 * already looking at, which the palette has no way to express.
 */

(function() {
    'use strict';

    // Translated strings, provided by base.html via data-* attributes on <body>
    // (see P-039 Phase 5 — small enough surface that a full JavaScriptCatalog
    // wasn't worth wiring up).
    const i18n = document.body.dataset;

    // Helper: Check if user is typing in an input field
    function isTyping(event) {
        const target = event.target;
        const tagName = target.tagName.toLowerCase();

        // Exclude input fields, textareas, and contenteditable elements
        if (tagName === 'input' || tagName === 'textarea' || tagName === 'select') {
            return true;
        }

        if (target.isContentEditable || target.contentEditable === 'true') {
            return true;
        }

        // Check if inside a contenteditable parent
        let parent = target.parentElement;
        while (parent) {
            if (parent.isContentEditable || parent.contentEditable === 'true') {
                return true;
            }
            parent = parent.parentElement;
        }

        return false;
    }

    // Helper: Get current page context
    function getPageContext() {
        const path = window.location.pathname;

        if (path.includes('/clients/')) {
            if (path.match(/\/clients\/\d+\/detail/)) {
                return 'client-detail';
            }
            return 'clients';
        }

        if (path.includes('/invoices/')) {
            if (path.match(/\/invoices\/\d+\//)) {
                return 'invoice-detail';
            }
            return 'invoices';
        }

        return 'other';
    }

    // Keys the overlay documents but does not implement: the palette owns ⌘K
    // and /, and ? is handled below. Display order is the order listed here.
    const globalHints = [
        { keys: '⌘K · Ctrl+K', name: () => i18n.kbdCommandPalette },
        { keys: '/', name: () => i18n.kbdCommandPalette },
        { keys: '?', name: () => i18n.kbdHelp }
    ];

    const contextualShortcuts = {
        'clients': {
            'n': { url: '/clients/new/', name: () => i18n.kbdNewClient }
        },
        'client-detail': {
            'n': { action: 'createInvoice', name: () => i18n.kbdNewInvoice },
            'e': { action: 'editClient', name: () => i18n.kbdEditClient }
        },
        'invoices': {
            'n': { url: '/invoices/new/', name: () => i18n.kbdNewInvoice }
        },
        'invoice-detail': {
            'e': { action: 'editInvoice', name: () => i18n.kbdEditInvoice }
        }
    };

    // Handle contextual actions that require dynamic URLs
    function handleContextualAction(action) {
        const path = window.location.pathname;

        if (action === 'createInvoice') {
            // Extract client ID from URL like /clients/123/detail/
            const match = path.match(/\/clients\/(\d+)\/detail/);
            if (match) {
                window.location.href = `/invoices/new/?client=${match[1]}`;
            }
        } else if (action === 'editClient') {
            const match = path.match(/\/clients\/(\d+)\/detail/);
            if (match) {
                window.location.href = `/clients/${match[1]}/edit/`;
            }
        } else if (action === 'editInvoice') {
            const match = path.match(/\/invoices\/(\d+)\//);
            if (match) {
                window.location.href = `/invoices/${match[1]}/edit/`;
            }
        }
    }

    function shortcutRows(entries) {
        return entries.map(function(entry) {
            return `
                <tr class="kbd-help__row">
                    <td class="kbd-help__key"><kbd>${entry.keys}</kbd></td>
                    <td class="kbd-help__name">${entry.name()}</td>
                </tr>
            `;
        }).join('');
    }

    // Show help overlay
    function showHelpOverlay() {
        // Check if overlay already exists
        if (document.getElementById('keyboard-help-overlay')) {
            document.getElementById('keyboard-help-overlay').remove();
            return;
        }

        const contextual = contextualShortcuts[getPageContext()] || {};
        const contextEntries = Object.keys(contextual).map(function(key) {
            return { keys: key, name: contextual[key].name };
        });

        const overlay = document.createElement('div');
        overlay.id = 'keyboard-help-overlay';
        overlay.className = 'kbd-help';

        let html = `
            <div class="kbd-help__box">
                <h2 class="kbd-help__title">⌨️ ${i18n.kbdHelpTitle}</h2>
                <p class="kbd-help__intro">${i18n.kbdHelpIntro}</p>

                <h3 class="kbd-help__section">${i18n.kbdGlobalNav}</h3>
                <table class="kbd-help__table">${shortcutRows(globalHints)}</table>
        `;

        if (contextEntries.length > 0) {
            html += `
                <h3 class="kbd-help__section">${i18n.kbdOnThisPage}</h3>
                <table class="kbd-help__table">${shortcutRows(contextEntries)}</table>
            `;
        }

        html += `
                <p class="kbd-help__footer">
                    ${i18n.kbdPress} <kbd>?</kbd> ${i18n.kbdOr} <kbd>ESC</kbd> ${i18n.kbdToClose}
                </p>
            </div>
        `;

        overlay.innerHTML = html;
        document.body.appendChild(overlay);

        // Close on click outside
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) {
                overlay.remove();
            }
        });
    }

    // Main keyboard event handler
    document.addEventListener('keydown', function(event) {
        // Ignore if user is typing
        if (isTyping(event)) {
            return;
        }

        // Ignore if modifier keys are pressed (except Shift for ?)
        if (event.ctrlKey || event.altKey || event.metaKey) {
            return;
        }

        const key = event.key.toLowerCase();

        // Close help overlay with ESC
        if (key === 'escape') {
            const overlay = document.getElementById('keyboard-help-overlay');
            if (overlay) {
                overlay.remove();
                event.preventDefault();
                return;
            }
        }

        // Check for help shortcut (?)
        if (event.key === '?') {
            event.preventDefault();
            showHelpOverlay();
            return;
        }

        const contextual = contextualShortcuts[getPageContext()] || {};
        if (contextual[key]) {
            event.preventDefault();
            const shortcut = contextual[key];

            if (shortcut.action) {
                handleContextualAction(shortcut.action);
            } else if (shortcut.url) {
                window.location.href = shortcut.url;
            }
        }
    });
})();

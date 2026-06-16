/**
 * Keyboard Navigation for Therapy Practice App
 *
 * Global shortcuts:
 * - c: Clients
 * - i: Invoices
 * - d: Dashboard
 * - a: Analytics
 * - p: Practice Analysis
 * - ?: Help overlay
 *
 * Context-aware shortcuts:
 * - n: New (client/invoice depending on page)
 * - e: Edit (on detail pages)
 */

(function() {
    'use strict';

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

        if (path.includes('/dashboard')) return 'dashboard';
        if (path.includes('/analytics')) return 'analytics';
        if (path.includes('/practice-analysis')) return 'practice';

        return 'home';
    }

    // Keyboard shortcut mappings
    const shortcuts = {
        global: {
            'c': { url: '/clients/', name: 'Klienten' },
            'i': { url: '/invoices/', name: 'Rechnungen' },
            'd': { url: '/dashboard/', name: 'Dashboard' },
            'a': { url: '/analytics/', name: 'Analytics' },
            'p': { url: '/practice-analysis/', name: 'Practice Analysis' },
            '?': { action: 'showHelp', name: 'Hilfe' }
        },
        contextual: {
            'clients': {
                'n': { url: '/clients/new/', name: 'Neuer Klient' }
            },
            'client-detail': {
                'n': { action: 'createInvoice', name: 'Neue Rechnung' },
                'e': { action: 'editClient', name: 'Klient bearbeiten' }
            },
            'invoices': {
                'n': { url: '/invoices/new/', name: 'Neue Rechnung' }
            },
            'invoice-detail': {
                'e': { action: 'editInvoice', name: 'Rechnung bearbeiten' }
            }
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

    // Show help overlay
    function showHelpOverlay() {
        // Check if overlay already exists
        if (document.getElementById('keyboard-help-overlay')) {
            document.getElementById('keyboard-help-overlay').remove();
            return;
        }

        const context = getPageContext();
        const contextShortcuts = shortcuts.contextual[context] || {};

        const overlay = document.createElement('div');
        overlay.id = 'keyboard-help-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            z-index: 10000;
            display: flex;
            align-items: center;
            justify-content: center;
            backdrop-filter: blur(5px);
        `;

        const helpBox = document.createElement('div');
        helpBox.style.cssText = `
            background: var(--color-surface, white);
            padding: 2rem;
            border-radius: 12px;
            max-width: 600px;
            max-height: 80vh;
            overflow-y: auto;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
        `;

        let html = `
            <h2 style="margin-top: 0; color: var(--color-text-primary);">⌨️ Tastaturkürzel</h2>
            <p style="color: var(--color-text-secondary); margin-bottom: 1.5rem;">
                Diese Shortcuts funktionieren überall (außer in Eingabefeldern).
            </p>

            <h3 style="color: var(--color-text-primary); margin-top: 1.5rem;">Globale Navigation</h3>
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 1.5rem;">
        `;

        for (const [key, data] of Object.entries(shortcuts.global)) {
            if (data.action === 'showHelp') continue;
            html += `
                <tr style="border-bottom: 1px solid var(--color-border);">
                    <td style="padding: 0.5rem; font-weight: bold; font-family: monospace; color: var(--color-link);">${key}</td>
                    <td style="padding: 0.5rem; color: var(--color-text-primary);">${data.name}</td>
                </tr>
            `;
        }

        html += '</table>';

        // Context-specific shortcuts
        if (Object.keys(contextShortcuts).length > 0) {
            html += `
                <h3 style="color: var(--color-text-primary); margin-top: 1.5rem;">Auf dieser Seite</h3>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 1.5rem;">
            `;

            for (const [key, data] of Object.entries(contextShortcuts)) {
                html += `
                    <tr style="border-bottom: 1px solid var(--color-border);">
                        <td style="padding: 0.5rem; font-weight: bold; font-family: monospace; color: var(--color-link);">${key}</td>
                        <td style="padding: 0.5rem; color: var(--color-text-primary);">${data.name}</td>
                    </tr>
                `;
            }

            html += '</table>';
        }

        html += `
            <p style="color: var(--color-text-secondary); font-size: 0.9rem; margin-top: 1.5rem; text-align: center;">
                Drücke <kbd style="padding: 0.2rem 0.5rem; background: var(--color-bg-secondary); border-radius: 4px; font-family: monospace;">?</kbd>
                oder <kbd style="padding: 0.2rem 0.5rem; background: var(--color-bg-secondary); border-radius: 4px;">ESC</kbd>
                um zu schließen
            </p>
        `;

        helpBox.innerHTML = html;
        overlay.appendChild(helpBox);
        document.body.appendChild(overlay);

        // Close on click outside or ESC
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
        const context = getPageContext();

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

        // Check contextual shortcuts first
        const contextShortcuts = shortcuts.contextual[context] || {};
        if (contextShortcuts[key]) {
            event.preventDefault();
            const shortcut = contextShortcuts[key];

            if (shortcut.action) {
                handleContextualAction(shortcut.action);
            } else if (shortcut.url) {
                window.location.href = shortcut.url;
            }
            return;
        }

        // Check global shortcuts
        if (shortcuts.global[key]) {
            event.preventDefault();
            const shortcut = shortcuts.global[key];

            if (shortcut.action === 'showHelp') {
                showHelpOverlay();
            } else if (shortcut.url) {
                window.location.href = shortcut.url;
            }
        }
    });

    // Add visual indicator for shortcuts (optional tooltip)
    function addShortcutIndicators() {
        const indicators = [
            { selector: 'a[href*="/clients/"]', key: 'c', name: 'Clients' },
            { selector: 'a[href*="/invoices/"]', key: 'i', name: 'Invoices' },
            { selector: 'a[href*="/dashboard"]', key: 'd', name: 'Dashboard' },
            { selector: 'a[href*="/analytics"]', key: 'a', name: 'Analytics' },
            { selector: 'a[href*="/practice-analysis"]', key: 'p', name: 'Practice' }
        ];

        indicators.forEach(function(indicator) {
            const elements = document.querySelectorAll(indicator.selector);
            elements.forEach(function(el) {
                // Skip if it's inside a dropdown (those have specific paths)
                if (el.closest('.dropdown-content')) return;

                const originalTitle = el.getAttribute('title') || '';
                const shortcutHint = `Shortcut: ${indicator.key}`;
                const newTitle = originalTitle ? `${originalTitle} (${shortcutHint})` : shortcutHint;
                el.setAttribute('title', newTitle);
            });
        });
    }

    // Initialize on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', addShortcutIndicators);
    } else {
        addShortcutIndicators();
    }

    // Add small help hint to the page
    function addHelpHint() {
        // Only add if not already present
        if (document.getElementById('keyboard-hint')) return;

        const hint = document.createElement('div');
        hint.id = 'keyboard-hint';
        hint.style.cssText = `
            position: fixed;
            bottom: 1rem;
            right: 1rem;
            background: var(--color-surface);
            padding: 0.5rem 1rem;
            border-radius: 8px;
            box-shadow: 0 2px 8px var(--color-shadow);
            font-size: 0.85rem;
            color: var(--color-text-secondary);
            z-index: 1000;
            opacity: 0.7;
            transition: opacity 0.2s;
            cursor: pointer;
        `;
        hint.innerHTML = 'Drücke <kbd style="padding: 0.2rem 0.4rem; background: var(--color-bg-secondary); border-radius: 4px; font-family: monospace; color: var(--color-text-primary);">?</kbd> für Tastaturkürzel';

        hint.addEventListener('mouseenter', function() {
            hint.style.opacity = '1';
        });

        hint.addEventListener('mouseleave', function() {
            hint.style.opacity = '0.7';
        });

        hint.addEventListener('click', showHelpOverlay);

        document.body.appendChild(hint);

        // Auto-hide after 5 seconds if user hasn't interacted
        setTimeout(function() {
            hint.style.transition = 'opacity 1s';
            hint.style.opacity = '0';
        }, 5000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', addHelpHint);
    } else {
        addHelpHint();
    }
})();

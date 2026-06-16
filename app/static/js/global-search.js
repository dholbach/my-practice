/**
 * Global Search Component
 *
 * Unified search box for clients and invoices with prefix support:
 * - "c:XX" or "client:XX" -> search clients only
 * - "i:2024" or "in:2024" -> search invoices only
 * - "XX" -> search both
 */

(function() {
    'use strict';

    let searchTimeout = null;
    let currentResults = [];
    let selectedIndex = -1;

    function createSearchBox() {
        // Create search container
        const searchContainer = document.createElement('div');
        searchContainer.id = 'global-search-container';
        searchContainer.style.cssText = `
            position: relative;
            display: inline-block;
            margin-right: 0.5rem;
        `;

        // Create input field
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.id = 'global-search-input';
        searchInput.placeholder = 'Suche... (c:Klient/Anfrage, i:Rechnung)';
        searchInput.style.cssText = `
            padding: 0.5rem 1rem;
            border: 2px solid var(--color-border);
            border-radius: 8px;
            background: var(--color-surface);
            color: var(--color-text-primary);
            font-size: 0.9rem;
            width: 300px;
            transition: all 0.2s;
        `;

        // Create results dropdown
        const resultsDropdown = document.createElement('div');
        resultsDropdown.id = 'global-search-results';
        resultsDropdown.style.cssText = `
            display: none;
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: var(--color-dropdown-bg);
            border: 1px solid var(--color-border);
            border-radius: 8px;
            box-shadow: 0 4px 12px var(--color-shadow);
            margin-top: 0.5rem;
            max-height: 400px;
            overflow-y: auto;
            z-index: 1000;
        `;

        searchContainer.appendChild(searchInput);
        searchContainer.appendChild(resultsDropdown);

        // Event listeners
        searchInput.addEventListener('input', handleSearchInput);
        searchInput.addEventListener('keydown', handleKeyNavigation);
        searchInput.addEventListener('focus', function() {
            searchInput.style.borderColor = 'var(--color-link)';
            searchInput.style.outline = 'none';
            if (currentResults.length > 0) {
                resultsDropdown.style.display = 'block';
            }
        });
        searchInput.addEventListener('blur', function() {
            searchInput.style.borderColor = 'var(--color-border)';
            // Delay hiding to allow click on results
            setTimeout(function() {
                resultsDropdown.style.display = 'none';
                selectedIndex = -1;
            }, 200);
        });

        return searchContainer;
    }

    function handleSearchInput(event) {
        const query = event.target.value.trim();
        const resultsDropdown = document.getElementById('global-search-results');

        // Clear previous timeout
        if (searchTimeout) {
            clearTimeout(searchTimeout);
        }

        // Clear results if query is empty
        if (!query) {
            currentResults = [];
            selectedIndex = -1;
            resultsDropdown.style.display = 'none';
            return;
        }

        // Debounce search
        searchTimeout = setTimeout(function() {
            performSearch(query);
        }, 300);
    }

    function performSearch(query) {
        const resultsDropdown = document.getElementById('global-search-results');

        // Show loading state
        resultsDropdown.innerHTML = '<div style="padding: 1rem; color: var(--color-text-secondary); text-align: center;">Suche...</div>';
        resultsDropdown.style.display = 'block';

        // Perform AJAX request
        fetch(`/api/search/?q=${encodeURIComponent(query)}`)
            .then(response => response.json())
            .then(data => {
                currentResults = data.results || [];
                selectedIndex = -1;
                displayResults();
            })
            .catch(error => {
                console.error('Search error:', error);
                resultsDropdown.innerHTML = '<div style="padding: 1rem; color: var(--color-danger);">Fehler bei der Suche</div>';
            });
    }

    function displayResults() {
        const resultsDropdown = document.getElementById('global-search-results');

        if (currentResults.length === 0) {
            resultsDropdown.innerHTML = '<div style="padding: 1rem; color: var(--color-text-secondary); text-align: center;">Keine Ergebnisse</div>';
            resultsDropdown.style.display = 'block';
            return;
        }

        let html = '';
        currentResults.forEach(function(result, index) {
            const isSelected = index === selectedIndex;
            html += `
                <a href="${result.url}"
                   class="search-result-item"
                   data-index="${index}"
                   style="
                       display: block;
                       padding: 0.75rem 1rem;
                       color: var(--color-text-primary);
                       text-decoration: none;
                       border-bottom: 1px solid var(--color-border);
                       transition: background 0.2s;
                       ${isSelected ? 'background: var(--color-dropdown-hover);' : ''}
                   "
                   onmouseover="this.style.background = 'var(--color-dropdown-hover)'"
                   onmouseout="this.style.background = '${isSelected ? 'var(--color-dropdown-hover)' : 'transparent'}'"
                >
                    ${result.label}
                </a>
            `;
        });

        resultsDropdown.innerHTML = html;
        resultsDropdown.style.display = 'block';

        // Add click handlers
        const items = resultsDropdown.querySelectorAll('.search-result-item');
        items.forEach(function(item) {
            item.addEventListener('mousedown', function(e) {
                // Use mousedown instead of click to fire before blur
                e.preventDefault();
                window.location.href = item.getAttribute('href');
            });
        });
    }

    function handleKeyNavigation(event) {
        if (currentResults.length === 0) return;

        if (event.key === 'ArrowDown') {
            event.preventDefault();
            selectedIndex = Math.min(selectedIndex + 1, currentResults.length - 1);
            updateSelectedItem();
        } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            selectedIndex = Math.max(selectedIndex - 1, -1);
            updateSelectedItem();
        } else if (event.key === 'Enter') {
            event.preventDefault();
            if (selectedIndex >= 0 && currentResults[selectedIndex]) {
                window.location.href = currentResults[selectedIndex].url;
            }
        } else if (event.key === 'Escape') {
            const resultsDropdown = document.getElementById('global-search-results');
            resultsDropdown.style.display = 'none';
            event.target.blur();
        }
    }

    function updateSelectedItem() {
        const resultsDropdown = document.getElementById('global-search-results');
        const items = resultsDropdown.querySelectorAll('.search-result-item');

        items.forEach(function(item, index) {
            if (index === selectedIndex) {
                item.style.background = 'var(--color-dropdown-hover)';
                // Scroll into view if needed
                item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            } else {
                item.style.background = 'transparent';
            }
        });
    }

    // Keyboard shortcut: "/" to focus search
    document.addEventListener('keydown', function(event) {
        // Check if typing in input field
        const target = event.target;
        const tagName = target.tagName.toLowerCase();
        if (tagName === 'input' || tagName === 'textarea' || tagName === 'select') {
            return;
        }

        if (event.key === '/') {
            event.preventDefault();
            const searchInput = document.getElementById('global-search-input');
            if (searchInput) {
                searchInput.focus();
            }
        }
    });

    // Initialize: Add search box to header
    function initializeSearch() {
        const header = document.querySelector('.header');
        if (!header) return;

        // Find the navigation or create a controls div
        let nav = header.querySelector('nav');
        if (!nav) return;

        // Create a controls wrapper for privacy, theme, and search
        let controlsWrapper = document.getElementById('header-controls');
        if (!controlsWrapper) {
            controlsWrapper = document.createElement('div');
            controlsWrapper.id = 'header-controls';
            controlsWrapper.style.cssText = `
                position: absolute;
                top: 2rem;
                right: 2rem;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            `;
            header.style.position = 'relative';
            header.appendChild(controlsWrapper);

            // Move existing controls into wrapper
            const privacyToggle = document.getElementById('privacyToggle');
            const themeToggle = document.getElementById('themeToggle');

            if (privacyToggle) {
                privacyToggle.style.float = 'none';
                privacyToggle.style.marginRight = '0';
                controlsWrapper.appendChild(privacyToggle);
            }

            if (themeToggle) {
                themeToggle.style.float = 'none';
                themeToggle.style.marginRight = '0';
                controlsWrapper.appendChild(themeToggle);
            }
        }

        // Add search box to controls
        const searchBox = createSearchBox();
        controlsWrapper.insertBefore(searchBox, controlsWrapper.firstChild);

        // Update keyboard hint to include search
        const keyboardHint = document.getElementById('keyboard-hint');
        if (keyboardHint) {
            keyboardHint.innerHTML = 'Drücke <kbd style="padding: 0.2rem 0.4rem; background: var(--color-bg-secondary); border-radius: 4px; font-family: monospace; color: var(--color-text-primary);">/</kbd> für Suche oder <kbd style="padding: 0.2rem 0.4rem; background: var(--color-bg-secondary); border-radius: 4px; font-family: monospace; color: var(--color-text-primary);">?</kbd> für Shortcuts';
        }
    }

    // Initialize on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeSearch);
    } else {
        initializeSearch();
    }
})();

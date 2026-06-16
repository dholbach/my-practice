/**
 * Widget System - P-003 Phase 3
 * Handles collapsible widgets with LocalStorage state persistence
 */

// LocalStorage key prefix
const WIDGET_STATE_PREFIX = 'widget_state_';

/**
 * Initialize all widgets on page load
 */
function initializeWidgets() {
    // Restore widget states from LocalStorage
    document.querySelectorAll('.dashboard-widget').forEach(widget => {
        const widgetId = widget.dataset.widgetId;
        if (!widgetId) return;

        // Check LocalStorage for saved state
        const savedState = localStorage.getItem(WIDGET_STATE_PREFIX + widgetId);
        const defaultCollapsed = widget.dataset.defaultCollapsed === 'true';

        // Apply state (LocalStorage > default > expanded)
        if (savedState !== null) {
            if (savedState === 'collapsed') {
                widget.classList.add('collapsed');
            } else {
                widget.classList.remove('collapsed');
            }
        } else if (defaultCollapsed) {
            widget.classList.add('collapsed');
        }
    });

    // Wire widget-header click (replaces inline onclick="toggleWidget(...)")
    document.querySelectorAll('.widget-header').forEach(header => {
        header.addEventListener('click', function () {
            const widget = this.closest('.dashboard-widget');
            if (widget) toggleWidget(widget.dataset.widgetId);
        });
    });
}

/**
 * Toggle widget collapsed state
 * @param {string} widgetId - Unique widget identifier
 */
function toggleWidget(widgetId) {
    const widget = document.querySelector(`[data-widget-id="${widgetId}"]`);
    if (!widget) return;

    // Toggle collapsed class
    const isCollapsed = widget.classList.toggle('collapsed');

    // Save state to LocalStorage
    localStorage.setItem(
        WIDGET_STATE_PREFIX + widgetId,
        isCollapsed ? 'collapsed' : 'expanded'
    );

    // Trigger custom event for analytics/tracking
    widget.dispatchEvent(new CustomEvent('widgetToggle', {
        detail: { widgetId, collapsed: isCollapsed }
    }));
}

/**
 * Expand all widgets
 */
function expandAllWidgets() {
    document.querySelectorAll('.dashboard-widget').forEach(widget => {
        widget.classList.remove('collapsed');
        const widgetId = widget.dataset.widgetId;
        if (widgetId) {
            localStorage.setItem(WIDGET_STATE_PREFIX + widgetId, 'expanded');
        }
    });
}

/**
 * Collapse all widgets
 */
function collapseAllWidgets() {
    document.querySelectorAll('.dashboard-widget').forEach(widget => {
        widget.classList.add('collapsed');
        const widgetId = widget.dataset.widgetId;
        if (widgetId) {
            localStorage.setItem(WIDGET_STATE_PREFIX + widgetId, 'collapsed');
        }
    });
}

/**
 * Reset all widget states (clear LocalStorage)
 */
function resetWidgetStates() {
    document.querySelectorAll('.dashboard-widget').forEach(widget => {
        const widgetId = widget.dataset.widgetId;
        if (widgetId) {
            localStorage.removeItem(WIDGET_STATE_PREFIX + widgetId);
        }
        widget.classList.remove('collapsed');
    });
}

// Initialize on DOMContentLoaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeWidgets);
} else {
    initializeWidgets();
}

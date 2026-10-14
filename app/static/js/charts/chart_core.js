/**
 * Chart Core - Theme system and chart registry
 * @module charts/chart_core
 */

// Store chart drawing functions for redrawing on theme change
const chartRegistry = {};

/**
 * Initialize a chart with automatic registration for theme-change redrawing
 *
 * @param {string} canvasId - ID of the canvas element
 * @param {Function} drawFunction - Function that draws the chart, receives canvas element
 * @example
 * initChart('myChart', function(canvas) {
 *   const ctx = canvas.getContext('2d');
 *   // Draw chart...
 * });
 */
function initChart(canvasId, drawFunction) {
    // Store the draw function for later redrawing
    chartRegistry[canvasId] = drawFunction;

    // Browser-only initialization
    if (typeof document !== 'undefined') {
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(function() {
                const canvas = document.getElementById(canvasId);
                if (canvas) {
                    drawFunction(canvas);
                }
            }, 50);
        });
    }
}

// Listen for theme changes and redraw all charts (browser only)
if (typeof window !== 'undefined') {
    window.addEventListener('themeChanged', function() {
        setTimeout(function() {
            Object.keys(chartRegistry).forEach(canvasId => {
                const canvas = document.getElementById(canvasId);
                if (canvas) {
                    // Clear the canvas
                    const ctx = canvas.getContext('2d');
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    // Redraw
                    chartRegistry[canvasId](canvas);
                }
            });
        }, 10);
    });
}

/**
 * Redraw every registered chart whose canvas lives inside a container.
 *
 * M-PAT-03: a chart drawn while its tab/container was display:none gets a
 * zero-sized canvas — call this shortly after the container becomes visible
 * (e.g. on tab switch) to redraw it at its real dimensions.
 *
 * @param {HTMLElement} container - Element to search for canvases in
 */
function redrawChartsIn(container) {
    if (!container) return;
    container.querySelectorAll('canvas').forEach(canvas => {
        const canvasId = canvas.id;
        if (canvasId && typeof chartRegistry !== 'undefined' && chartRegistry[canvasId]) {
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            chartRegistry[canvasId](canvas);
        }
    });
}

/**
 * Read a CSS custom property, e.g. getCSSVariable('--color-text-primary').
 *
 * Use the real --color-* tokens: they flip with [data-theme="dark"], so a chart
 * redrawn after a theme change picks up the new colours. The names this used to
 * be called with (--text-primary, --border-color, ...) were never defined, so
 * gridlines stayed light-theme grey in dark mode.
 */
function getCSSVariable(varName, fallback) {
    // Node test environment: no DOM to read from.
    if (typeof getComputedStyle === 'undefined' || typeof document === 'undefined') {
        return fallback || null;
    }
    const value = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
    return value || fallback || null;
}

// Export functions
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initChart,
        getCSSVariable,
        redrawChartsIn,
        chartRegistry
    };
}

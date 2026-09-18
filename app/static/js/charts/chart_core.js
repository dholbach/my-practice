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
 * Get CSS color variable value with adaptive fallback
 */
function getCSSVariable(varName, fallback) {
    // Browser-only functionality
    if (typeof getComputedStyle === 'undefined' || typeof document === 'undefined') {
        // In Node.js testing environment, return fallback
        if (varName === '--text-primary') return '#2d3748';
        if (varName === '--text-secondary') return '#718096';
        return fallback || null;
    }

    // Try to get the CSS variable value first
    const value = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
    if (value && value !== '') return value;

    // If CSS variable not loaded yet, use theme-aware fallback for text colors
    // Check both data-theme attribute and prefers-color-scheme
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark' ||
                   (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);

    if (varName === '--text-primary') {
        return isDark ? '#f7fafc' : '#2d3748';
    }

    if (varName === '--text-secondary') {
        return isDark ? '#a0aec0' : '#718096';
    }

    return fallback || null;
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

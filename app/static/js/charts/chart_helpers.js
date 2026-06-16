/**
 * Chart Helpers - Validation and empty state functions
 * @module charts/chart_helpers
 */

/**
 * Display empty state message on canvas
 * @param {HTMLCanvasElement} canvas - Canvas element
 * @param {string} message - Message to display
 */
function showChartEmptyState(canvas, message = 'Keine Daten vorhanden') {
    // Size the canvas before drawing so coordinates match the displayed area.
    setupCanvas(canvas);
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = getCSSVariable('--color-text-secondary', '#718096');
    ctx.font = '14px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText(message, canvas.width / 2, canvas.height / 2);
}

/**
 * Initialize chart with standard setup (canvas, grid, axes)
 * @param {HTMLCanvasElement} canvas - Canvas element
 * @param {Object} options - Configuration options
 * @param {Object} options.padding - Chart padding
 * @param {boolean} options.drawGrid - Whether to draw grid (default: true)
 * @param {boolean} options.drawAxes - Whether to draw axes (default: true)
 * @returns {Object|null} Setup object with ctx, padding, dimensions, or null if setup fails
 */
function initializeChart(canvas, options = {}) {
    const padding = options.padding || { top: 30, right: 20, bottom: 60, left: 70 };
    const setup = setupCanvas(canvas, padding);
    if (!setup) return null;

    const { ctx, chartWidth, chartHeight } = setup;

    if (options.drawGrid !== false) {
        drawGrid(ctx, setup.padding, chartWidth, chartHeight);
    }
    if (options.drawAxes !== false) {
        drawAxes(ctx, setup.padding, chartWidth, chartHeight);
    }

    return setup;
}

/**
 * Validate chart data
 * @param {Array<number>} data - Data array to validate
 * @param {Object} options - Validation options
 * @param {boolean} options.checkNonZero - Check if all values are zero
 * @returns {Object} Validation result with valid flag, reason, and maxValue
 */
function validateChartData(data, options = {}) {
    if (!data || data.length === 0) {
        return { valid: false, reason: 'empty' };
    }

    if (options.checkNonZero && data.every(d => d === 0)) {
        return { valid: false, reason: 'all_zeros' };
    }

    // If the caller supplied an explicit positive maxValue, trust it — all-zero
    // data (e.g. 0% cancellation rate) is still valid data worth rendering.
    if (options.maxValue && options.maxValue > 0) {
        return { valid: true, maxValue: options.maxValue };
    }

    const maxValue = Math.max(...data.filter(d => d > 0));
    if (!isFinite(maxValue) || maxValue === 0) {
        return { valid: false, reason: 'invalid_max' };
    }

    return { valid: true, maxValue };
}

/**
 * Get user-friendly message for validation failure reason
 * @param {string} reason - Validation failure reason
 * @returns {string} User-friendly message
 */
function getValidationMessage(reason) {
    const messages = {
        'empty': 'Keine Daten vorhanden',
        'all_zeros': 'Keine Daten im ausgewählten Zeitraum',
        'invalid_max': 'Keine gültigen Daten vorhanden'
    };
    return messages[reason] || 'Keine Daten vorhanden';
}

// Export functions
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        showChartEmptyState,
        initializeChart,
        validateChartData,
        getValidationMessage
    };
}

/**
 * Chart Canvas - Canvas setup, grid, and axes rendering
 * @module charts/chart_canvas
 */

/**
 * Setup canvas with proper dimensions
 */
function setupCanvas(canvas, padding = { top: 30, right: 20, bottom: 60, left: 70 }) {
    if (!canvas) return null;

    const ctx = canvas.getContext('2d');
    const container = canvas.parentElement;

    // Calculate dimensions based on container
    canvas.width = container.clientWidth - 60;
    canvas.height = container.clientHeight - 40;  // Leave space for padding

    const width = canvas.width;
    const height = canvas.height;
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    return { canvas, ctx, width, height, padding, chartWidth, chartHeight };
}

/**
 * Draw grid lines on chart
 */
function drawGrid(ctx, padding, chartWidth, chartHeight, divisions = 4) {
    const borderColor = getCSSVariable('--border-color', '#e2e8f0');
    ctx.strokeStyle = borderColor;
    ctx.lineWidth = 1;
    ctx.setLineDash([5, 5]);

    for (let i = 0; i <= divisions; i++) {
        const y = padding.top + (chartHeight / divisions) * i;
        ctx.beginPath();
        ctx.moveTo(padding.left, y);
        ctx.lineTo(padding.left + chartWidth, y);
        ctx.stroke();
    }

    ctx.setLineDash([]);
}

/**
 * Draw chart axes
 */
function drawAxes(ctx, padding, chartWidth, chartHeight) {
    const textSecondary = getCSSVariable('--text-secondary');
    ctx.strokeStyle = textSecondary;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top);
    ctx.lineTo(padding.left, padding.top + chartHeight);
    ctx.lineTo(padding.left + chartWidth, padding.top + chartHeight);
    ctx.stroke();
}

/**
 * Draw Y-axis labels
 */
function drawYAxisLabels(ctx, padding, chartHeight, maxValue, suffix = '€', divisions = 4) {
    const textSecondary = getCSSVariable('--text-secondary', '#718096');
    ctx.fillStyle = textSecondary;
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'right';

    for (let i = 0; i <= divisions; i++) {
        const value = maxValue * (1 - i / divisions);
        const y = padding.top + (chartHeight / divisions) * i;

        // Format value based on suffix
        let displayValue;
        if (suffix === 'k€') {
            displayValue = Math.round(value / 1000) + suffix;
        } else {
            displayValue = Math.round(value) + suffix;
        }

        ctx.fillText(displayValue, padding.left - 10, y + 4);
    }
}

// Export functions
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        setupCanvas,
        drawGrid,
        drawAxes,
        drawYAxisLabels
    };
}

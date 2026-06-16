/**
 * Chart Primitives - Basic drawing functions (bars, labels, legend)
 * @module charts/chart_primitives
 */

/**
 * Draw X-axis labels (years for bar charts)
 */
function drawXAxisLabels(ctx, padding, chartWidth, chartHeight, labels, barWidth, barSpacing) {
    const textPrimary = getCSSVariable('--text-primary', '#1a202c');
    ctx.fillStyle = textPrimary;
    ctx.font = 'bold 13px sans-serif';
    ctx.textAlign = 'center';

    labels.forEach((label, index) => {
        const x = padding.left + (barWidth + barSpacing) * index + barSpacing + barWidth / 2;
        // Position labels within bottom padding area
        ctx.fillText(label, x, chartHeight + padding.top + padding.bottom - 35);
    });
}

/**
 * Draw a bar with gradient
 */
function drawBarWithGradient(ctx, x, y, width, height, color1, color2) {
    const gradient = ctx.createLinearGradient(x, y, x, y + height);
    gradient.addColorStop(0, color1);
    gradient.addColorStop(1, color2 || color1);
    ctx.fillStyle = gradient;
    ctx.fillRect(x, y, width, height);
}

/**
 * Draw X-axis year label at standard position
 */
function drawYearLabel(ctx, year, x, height, padding) {
    const textPrimary = getCSSVariable('--text-primary');
    ctx.fillStyle = textPrimary || '#2d3748'; // Fallback if null
    ctx.font = 'bold 13px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(String(year), x, height - padding.bottom + 25);
}

/**
 * Draw a legend with colored boxes and labels
 */
function drawLegend(ctx, padding, items) {
    const textSecondary = getCSSVariable('--text-secondary');
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'left';
    const legendY = padding.top - 20;

    let xOffset = 0;
    items.forEach((item, index) => {
        // Draw color box
        ctx.fillStyle = item.color;
        ctx.fillRect(padding.left + xOffset, legendY, 15, 10);

        // Draw label
        ctx.fillStyle = textSecondary;
        ctx.fillText(item.label, padding.left + xOffset + 20, legendY + 9);

        // Calculate next offset (box + text + spacing)
        const textWidth = ctx.measureText(item.label).width;
        xOffset += 20 + textWidth + 20;
    });
}

/**
 * Draw points on chart
 */
function drawPoints(ctx, points, color = '#667eea', radius = 5) {
    points.forEach(point => {
        ctx.beginPath();
        ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 2;
        ctx.stroke();
    });
}

// Export functions
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        drawXAxisLabels,
        drawBarWithGradient,
        drawYearLabel,
        drawLegend,
        drawPoints
    };
}

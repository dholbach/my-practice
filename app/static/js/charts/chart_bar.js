/**
 * Chart Bar - Bar chart rendering functions
 * @module charts/chart_bar
 */

/**
 * Draw grouped bars (multiple bars per x-axis position)
 */
function drawGroupedBars(ctx, padding, chartWidth, chartHeight, height, labels, datasets, maxValue) {
    const groupWidth = chartWidth / labels.length;
    const barsPerGroup = datasets.length;
    const barWidth = groupWidth / (barsPerGroup + 1);
    const barSpacing = barWidth * 0.15;

    labels.forEach((label, index) => {
        const xBase = padding.left + (groupWidth * index) + (groupWidth - barWidth * barsPerGroup - barSpacing * (barsPerGroup - 1)) / 2;

        // Draw each bar in the group
        datasets.forEach((dataset, barIndex) => {
            const value = dataset.data[index];
            const barHeight = (value / maxValue) * chartHeight;
            const x = xBase + (barWidth + barSpacing) * barIndex;
            const y = padding.top + chartHeight - barHeight;

            drawBarWithGradient(ctx, x, y, barWidth, barHeight, dataset.color, dataset.colorEnd || dataset.color);
        });

        // Draw year label centered under the group
        drawYearLabel(ctx, label, xBase + barWidth * (barsPerGroup / 2) + barSpacing * ((barsPerGroup - 1) / 2), height, padding);
    });
}

/**
 * Draw simple bar chart with value labels on top
 */
function drawSimpleBarChart(ctx, padding, chartWidth, chartHeight, height, labels, data, maxValue, colors, options = {}) {
    const barWidth = chartWidth / (labels.length * 1.5);
    const barSpacing = barWidth * 0.5;
    const showValueLabels = options.showValueLabels !== false;
    const valueSuffix = options.valueSuffix || '€';
    const positions = [];

    data.forEach((value, index) => {
        const barHeight = (value / maxValue) * chartHeight;
        const x = padding.left + (barWidth + barSpacing) * index + barSpacing;
        const y = padding.top + chartHeight - barHeight;
        const color = Array.isArray(colors) ? colors[index % colors.length] : colors;

        // Store position for tooltip — center of bar so hoverRadius hits the body, not just the top edge
        positions.push({ x: x + barWidth / 2, y: y + barHeight / 2 });

        // Draw bar with gradient
        drawBarWithGradient(ctx, x, y, barWidth, barHeight, color, color + 'cc');

        // Draw border
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.strokeRect(x, y, barWidth, barHeight);

        // Draw value label on top
        if (showValueLabels) {
            const text = Math.round(value) + valueSuffix;
            ctx.font = 'bold 16px sans-serif';
            ctx.textAlign = 'center';

            const metrics = ctx.measureText(text);
            const textWidth = metrics.width;
            const textX = x + barWidth / 2;
            const textY = y - 12;

            // Background for text
            ctx.fillStyle = color;
            ctx.fillRect(textX - textWidth / 2 - 6, textY - 14, textWidth + 12, 20);

            // White text
            ctx.fillStyle = '#ffffff';
            ctx.fillText(text, textX, textY);
        }

        // Draw x-axis label
        drawYearLabel(ctx, labels[index], x + barWidth / 2, height, padding);
    });

    return positions;
}

// Export functions
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        drawGroupedBars,
        drawSimpleBarChart,
    };
}

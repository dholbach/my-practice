/**
 * Chart Line - Line chart rendering functions
 * @module charts/chart_line
 */

/**
 * Draw year separators
 */
function drawYearSeparators(ctx, padding, chartHeight, chartWidth, dataLength, startYear = 2020, color = 'rgba(102, 126, 234, 0.3)') {
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.setLineDash([]);

    const currentYear = new Date().getFullYear();
    for (let year = startYear + 1; year <= currentYear; year++) {
        const monthIndex = (year - startYear) * 12;
        if (monthIndex < dataLength) {
            const x = padding.left + (chartWidth / (dataLength - 1)) * monthIndex;
            ctx.beginPath();
            ctx.moveTo(x, padding.top);
            ctx.lineTo(x, padding.top + chartHeight);
            ctx.stroke();
        }
    }
}

/**
 * Draw year labels on X-axis
 */
function drawYearLabels(ctx, height, points, startYear = 2020) {
    const textSecondary = getCSSVariable('--text-secondary', '#718096');
    ctx.fillStyle = textSecondary;
    ctx.font = 'bold 14px sans-serif';
    ctx.textAlign = 'center';

    const currentYear = new Date().getFullYear();
    for (let year = startYear; year <= currentYear; year++) {
        const monthIndex = (year - startYear) * 12;
        if (monthIndex < points.length) {
            ctx.fillText(year, points[monthIndex].x, height - 10);
        }
    }
}

/**
 * Draw line chart with area fill
 */
function drawLineChart(ctx, points, padding, chartHeight, colorStart, colorEnd) {
    // Draw area
    const gradient = ctx.createLinearGradient(0, padding.top, 0, padding.top + chartHeight);
    gradient.addColorStop(0, colorStart.replace(')', ', 0.2)').replace('rgb', 'rgba'));
    gradient.addColorStop(1, colorStart.replace(')', ', 0)').replace('rgb', 'rgba'));

    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.moveTo(points[0].x, padding.top + chartHeight);
    points.forEach(point => ctx.lineTo(point.x, point.y));
    ctx.lineTo(points[points.length - 1].x, padding.top + chartHeight);
    ctx.closePath();
    ctx.fill();

    // Draw line
    const lineGradient = ctx.createLinearGradient(padding.left, 0, padding.left + chartHeight, 0);
    lineGradient.addColorStop(0, colorStart);
    lineGradient.addColorStop(1, colorEnd);

    ctx.strokeStyle = lineGradient;
    ctx.lineWidth = 3;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.beginPath();
    points.forEach((point, i) => {
        if (i === 0) ctx.moveTo(point.x, point.y);
        else ctx.lineTo(point.x, point.y);
    });
    ctx.stroke();
}

/**
 * Draw a trendline on a line chart using EMA
 * @param {CanvasRenderingContext2D} ctx - Canvas context
 * @param {Array<{x: number, y: number}>} points - Data points
 * @param {Array<number>} data - Y values
 * @param {number} maxValue - Maximum value for scaling
 * @param {object} padding - Padding object
 * @param {number} chartHeight - Chart height
 * @param {string} color - Trendline color
 * @param {number} span - EMA smoothing span (default 12)
 */
function drawTrendline(ctx, points, data, maxValue, padding, chartHeight, color = 'rgba(255, 107, 107, 0.6)', span = 12) {
    if (points.length < 2) return;

    // Calculate EMA
    const emaData = calculateEMA(data, span);

    // Convert EMA values to canvas coordinates
    const emaPoints = emaData.map((value, index) => ({
        x: points[index].x,
        y: padding.top + chartHeight - (value / maxValue) * chartHeight
    }));

    // Draw smooth curve
    ctx.save();
    ctx.setLineDash([8, 5]);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.5;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.beginPath();

    emaPoints.forEach((point, i) => {
        if (i === 0) {
            ctx.moveTo(point.x, point.y);
        } else {
            ctx.lineTo(point.x, point.y);
        }
    });

    ctx.stroke();
    ctx.restore();
}

// Export functions
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        drawYearSeparators,
        drawYearLabels,
        drawLineChart,
        drawTrendline
    };
}

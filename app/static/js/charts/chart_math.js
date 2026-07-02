/**
 * Chart Math - Business logic and calculations
 * @module charts/chart_math
 */

/**
 * Calculate points for line chart
 */
function calculatePoints(data, padding, chartWidth, chartHeight, maxValue) {
    return data.map((value, index) => ({
        x: padding.left + (chartWidth / (data.length - 1)) * index,
        y: padding.top + chartHeight - (value / maxValue) * chartHeight
    }));
}

/**
 * Parse date string in various formats
 * @param {string} dateStr - Date string (e.g., "2020-10", "Oct 20")
 * @returns {{year: number, month: number}|null} Parsed date or null
 */
function parseMonthString(dateStr) {
    if (!dateStr) return null;

    // Try YYYY-MM format
    const dashMatch = dateStr.match(/^(\d{4})-(\d{1,2})$/);
    if (dashMatch) {
        return {
            year: parseInt(dashMatch[1], 10),
            month: parseInt(dashMatch[2], 10)
        };
    }

    // Try MM/YY format (e.g., "01/17" for January 2017)
    const slashMatch = dateStr.match(/^(\d{1,2})\/(\d{2})$/);
    if (slashMatch) {
        return {
            year: 2000 + parseInt(slashMatch[2], 10),
            month: parseInt(slashMatch[1], 10)
        };
    }

    // Try "Oct 20" format
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const spaceMatch = dateStr.match(/^([A-Za-z]{3})\s+(\d{2})$/);
    if (spaceMatch) {
        const monthIndex = monthNames.indexOf(spaceMatch[1]);
        if (monthIndex !== -1) {
            return {
                year: 2000 + parseInt(spaceMatch[2], 10),
                month: monthIndex + 1
            };
        }
    }

    return null;
}

/**
 * Find first non-zero index in array
 * @param {Array<number>} data - Array of numbers
 * @returns {number} Index of first non-zero value
 */
function findFirstNonZeroIndex(data) {
    for (let i = 0; i < data.length; i++) {
        if (data[i] > 0) {
            return i;
        }
    }
    return 0;
}

/**
 * Aggregate monthly data to yearly totals
 * @param {Array<number>} monthlyData - Monthly values
 * @param {Array<string>} monthlyLabels - Month labels (e.g., "Oct 20" or "2020-10")
 * @returns {{years: string[], data: number[]}} Aggregated yearly data
 */
function aggregateMonthlyToYearly(monthlyData, monthlyLabels) {
    const yearlyTotals = {};

    monthlyLabels.forEach((label, index) => {
        const parsed = parseMonthString(label);
        if (parsed && monthlyData[index] !== undefined) {
            const year = parsed.year.toString();
            if (!yearlyTotals[year]) {
                yearlyTotals[year] = 0;
            }
            yearlyTotals[year] += monthlyData[index];
        }
    });

    const years = Object.keys(yearlyTotals).sort();
    const data = years.map(year => yearlyTotals[year]);

    return { years, data };
}

/**
 * Calculate Exponential Moving Average (EMA)
 * @param {Array<number>} data - Y values
 * @param {number} span - Smoothing span (higher = smoother, typical: 12)
 * @returns {Array<number>} EMA values
 */
function calculateEMA(data, span = 12) {
    if (data.length === 0) return [];

    const alpha = 2 / (span + 1);
    const ema = [data[0]];

    for (let i = 1; i < data.length; i++) {
        ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1];
    }

    return ema;
}

/**
 * Calculate linear regression trendline
 * @param {Array<number>} data - Y values
 * @returns {{slope: number, intercept: number}} Linear regression coefficients
 */
function calculateLinearTrendline(data) {
    const n = data.length;
    if (n < 2) return { slope: 0, intercept: 0 };

    // Calculate means
    let sumX = 0, sumY = 0;
    for (let i = 0; i < n; i++) {
        sumX += i;
        sumY += data[i];
    }
    const meanX = sumX / n;
    const meanY = sumY / n;

    // Calculate slope and intercept
    let numerator = 0, denominator = 0;
    for (let i = 0; i < n; i++) {
        numerator += (i - meanX) * (data[i] - meanY);
        denominator += (i - meanX) * (i - meanX);
    }

    const slope = denominator !== 0 ? numerator / denominator : 0;
    const intercept = meanY - slope * meanX;

    return { slope, intercept };
}

// Export functions
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        calculatePoints,
        parseMonthString,
        findFirstNonZeroIndex,
        aggregateMonthlyToYearly,
        calculateEMA,
        calculateLinearTrendline
    };
}

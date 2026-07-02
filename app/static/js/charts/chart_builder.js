/**
 * Chart Builder - Fluent API for building charts with minimal boilerplate
 * @module charts/chart_builder
 */

/**
 * Chart Builder class - provides fluent API for chart creation
 *
 * @example
 * new ChartBuilder('myChart')
 *   .type('bar')
 *   .data([100, 200, 300])
 *   .labels(['2022', '2023', '2024'])
 *   .preset('expense')
 *   .tooltip((data) => `${data.label}: ${data.value}€`)
 *   .build();
 */
class ChartBuilder {
    /**
     * Create a new chart builder
     * @param {string|HTMLCanvasElement} canvasOrId - Canvas element or ID
     */
    constructor(canvasOrId) {
        this.canvasOrId = canvasOrId;
        this.config = {
            type: 'bar',
            data: null,
            labels: null,
            datasets: null, // For grouped charts
            options: {},
            tooltipFormatter: null,
            preset: null,
            customColors: null
        };
    }

    /**
     * Set chart type
     * @param {string} chartType - 'bar', 'line', 'grouped-bar'
     * @returns {ChartBuilder} Builder instance for chaining
     */
    type(chartType) {
        this.config.type = chartType;
        return this;
    }

    /**
     * Set chart data
     * @param {Array<number>} data - Data values
     * @returns {ChartBuilder} Builder instance for chaining
     */
    data(data) {
        this.config.data = data;
        return this;
    }

    /**
     * Set chart labels
     * @param {Array<string>} labels - Label values
     * @returns {ChartBuilder} Builder instance for chaining
     */
    labels(labels) {
        this.config.labels = labels;
        return this;
    }

    /**
     * Set datasets for grouped charts
     * @param {Array<Object>} datasets - Array of {label, data, color, colorEnd}
     * @returns {ChartBuilder} Builder instance for chaining
     */
    datasets(datasets) {
        this.config.datasets = datasets;
        return this;
    }

    /**
     * Set additional options
     * @param {Object} options - Options object
     * @returns {ChartBuilder} Builder instance for chaining
     */
    options(options) {
        this.config.options = { ...this.config.options, ...options };
        return this;
    }

    /**
     * Set tooltip formatter
     * @param {Function} formatter - Function that takes data and returns HTML string
     * @returns {ChartBuilder} Builder instance for chaining
     */
    tooltip(formatter) {
        this.config.tooltipFormatter = formatter;
        return this;
    }

    /**
     * Use a preset configuration
     * @param {string} presetName - Name of preset (e.g., 'revenue', 'expense')
     * @returns {ChartBuilder} Builder instance for chaining
     */
    preset(presetName) {
        this.config.preset = presetName;
        return this;
    }

    /**
     * Set custom colors (overrides preset)
     * @param {Array<string>|string} colors - Color or array of colors
     * @returns {ChartBuilder} Builder instance for chaining
     */
    colors(colors) {
        this.config.customColors = colors;
        return this;
    }

    /**
     * Build and render the chart
     * @returns {Object|null} Chart object with canvas and redraw method, or null on error
     */
    build() {
        const canvas = typeof this.canvasOrId === 'string'
            ? document.getElementById(this.canvasOrId)
            : this.canvasOrId;

        if (!canvas) {
            console.error(`Canvas ${this.canvasOrId} not found`);
            return null;
        }

        // Validate data
        const dataToValidate = this.config.datasets
            ? this.config.datasets.flatMap(d => d.data)
            : this.config.data;

        const validation = validateChartData(dataToValidate, this.config.options);
        if (!validation.valid) {
            showChartEmptyState(canvas, getValidationMessage(validation.reason));
            return null;
        }

        // Get preset configuration
        const preset = this.config.preset
            ? ChartConfig.getPreset(this.config.preset)
            : {};

        // Merge options with preset
        const mergedOptions = {
            ...preset,
            ...this.config.options,
            padding: this.config.options.padding || ChartConfig.getPadding(
                this.config.type === 'bar' ? 'bar' : 'default'
            )
        };

        // Initialize canvas
        const setup = initializeChart(canvas, mergedOptions);
        if (!setup) return null;

        const { ctx, chartWidth, chartHeight, padding } = setup;

        // Draw based on type
        let dataPoints = null;

        switch (this.config.type) {
            case 'bar':
                dataPoints = this.drawBarChart(ctx, canvas, chartWidth, chartHeight, padding, validation.maxValue, preset);
                break;
            case 'line':
                dataPoints = this.drawLineChart(ctx, canvas, chartWidth, chartHeight, padding, validation.maxValue, preset);
                break;
            case 'grouped-bar':
                dataPoints = this.drawGroupedBarChart(ctx, canvas, chartWidth, chartHeight, padding, validation.maxValue, preset);
                break;
            default:
                console.error(`Unknown chart type: ${this.config.type}`);
                return null;
        }

        // Setup tooltip if requested and we have data points
        if (this.config.tooltipFormatter && dataPoints && dataPoints.length > 0) {
            const tooltip = new ChartTooltip(canvas, {
                formatter: this.config.tooltipFormatter
            });
            tooltip.setup(dataPoints);
        }

        return {
            canvas,
            redraw: () => this.build()
        };
    }

    /**
     * Draw bar chart
     * @private
     */
    drawBarChart(ctx, canvas, chartWidth, chartHeight, padding, maxValue, preset) {
        const colors = this.config.customColors || preset.colors?.bar || ChartConfig.colors.primary.gradient;

        const positions = drawSimpleBarChart(
            ctx,
            padding,
            chartWidth,
            chartHeight,
            canvas.height,
            this.config.labels,
            this.config.data,
            maxValue * 1.1,
            colors,
            this.config.options
        );

        // Convert positions to data points for tooltip
        return positions.map((pos, i) => ({
            x: pos.x,
            y: pos.y,
            label: this.config.labels[i],
            value: this.config.data[i]
        }));
    }

    /**
     * Draw line chart
     * @private
     */
    drawLineChart(ctx, canvas, chartWidth, chartHeight, padding, maxValue, preset) {
        const colors = this.config.customColors || preset.colors?.line || ChartConfig.colors.primary.gradient;

        // Draw Y-axis labels
        const yAxisSuffix = this.config.options.yAxisSuffix || preset.yAxisSuffix || '€';
        drawYAxisLabels(ctx, padding, chartHeight, maxValue * 1.1, yAxisSuffix);

        // Calculate points
        const points = calculatePoints(this.config.data, padding, chartWidth, chartHeight, maxValue * 1.1);

        // Draw line and area
        drawLineChart(ctx, points, padding, chartHeight, colors[0], colors[1]);

        // Draw points
        if (preset.showPoints !== false) {
            drawPoints(ctx, points, colors[0]);
        }

        // Draw year separators and labels if needed
        if (this.config.options.showYearSeparators) {
            const startYear = this.config.options.startYear || 2020;
            const startMonth = this.config.options.startMonth || 1;
            drawYearSeparators(ctx, padding, chartHeight, chartWidth, this.config.data.length, startYear, undefined, startMonth);
            drawYearLabels(ctx, canvas.height, points, startYear, startMonth);
        }

        // Draw trendline if requested
        if (preset.showTrendline && this.config.data.length > 2) {
            drawTrendline(ctx, points, this.config.data, maxValue * 1.1, padding, chartHeight, preset.colors?.trendline);
        }

        // Convert to data points for tooltip
        return points.map((point, i) => ({
            x: point.x,
            y: point.y,
            label: this.config.labels[i],
            value: this.config.data[i]
        }));
    }

    /**
     * Draw grouped bar chart
     * @private
     */
    drawGroupedBarChart(ctx, canvas, chartWidth, chartHeight, padding, maxValue, preset) {
        if (!this.config.datasets || this.config.datasets.length === 0) {
            console.error('Grouped bar chart requires datasets');
            return null;
        }

        // Draw legend if requested
        if (preset.showLegend || this.config.options.showLegend) {
            const legendItems = this.config.datasets.map(ds => ({
                label: ds.label,
                color: ds.color
            }));
            drawLegend(ctx, padding, legendItems);
        }

        // Draw grouped bars
        drawGroupedBars(
            ctx,
            padding,
            chartWidth,
            chartHeight,
            canvas.height,
            this.config.labels,
            this.config.datasets,
            maxValue * 1.1
        );

        // Generate data points for tooltip — one hit-point per bar at bar center.
        // Uses the same geometry as drawGroupedBars() so the hit zones sit inside
        // the actual painted bars instead of a fixed vertical midpoint.
        const groupWidth = chartWidth / this.config.labels.length;
        const barsPerGroup = this.config.datasets.length;
        const barWidth = groupWidth / (barsPerGroup + 1);
        const barSpacing = barWidth * 0.15;
        const scaledMax = maxValue * 1.1;

        const allPoints = [];
        this.config.labels.forEach((label, i) => {
            const xBase = padding.left + (groupWidth * i) +
                (groupWidth - barWidth * barsPerGroup - barSpacing * (barsPerGroup - 1)) / 2;
            const groupValues = this.config.datasets.map(ds => ({
                label: ds.label,
                value: ds.data[i],
                color: ds.color
            }));

            this.config.datasets.forEach((ds, barIndex) => {
                const value = ds.data[i];
                const barHeight = (value / scaledMax) * chartHeight;
                const barCenterX = xBase + (barWidth + barSpacing) * barIndex + barWidth / 2;
                const barCenterY = padding.top + chartHeight - barHeight / 2;

                allPoints.push({
                    x: barCenterX,
                    y: barCenterY,
                    label: label,
                    value: this.config.datasets[0].data[i],
                    values: groupValues
                });
            });
        });
        return allPoints;
    }
}

// Export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ChartBuilder;
}

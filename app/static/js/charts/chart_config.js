/**
 * Chart Configuration - Centralized themes, colors, and settings
 * @module charts/chart_config
 */

const ChartConfig = {
    // Color palettes
    colors: {
        primary: {
            main: '#667eea',
            light: '#a8b5ff',
            dark: '#4c5fd5',
            gradient: ['#667eea', '#764ba2']
        },
        secondary: {
            main: '#f093fb',
            light: '#f5d0fe',
            dark: '#e879f9',
            gradient: ['#f093fb', '#f5576c']
        },
        success: {
            main: '#10b981',
            light: '#86efac',
            dark: '#059669',
            gradient: ['#10b981', '#059669']
        },
        warning: {
            main: '#f59e0b',
            light: '#fcd34d',
            dark: '#ea580c',
            gradient: ['#f59e0b', '#ea580c']
        },
        danger: {
            main: '#ef4444',
            light: '#fca5a5',
            dark: '#dc2626',
            gradient: ['#ef4444', '#dc2626']
        },
        neutral: {
            grid: 'rgba(200, 200, 200, 0.2)',
            axis: '#666',
            text: '#333',
            textLight: '#999',
            border: '#e2e8f0'
        }
    },

    // Typography
    fonts: {
        axis: '12px sans-serif',
        label: '13px sans-serif',
        labelBold: 'bold 13px sans-serif',
        value: 'bold 16px sans-serif',
        title: 'bold 16px sans-serif',
        legend: '12px sans-serif',
        tooltip: '13px sans-serif'
    },

    // Spacing
    spacing: {
        padding: {
            default: { top: 30, right: 20, bottom: 60, left: 70 },
            bar: { top: 35, right: 20, bottom: 60, left: 60 }
        },
        barSpacing: 15,
        pointRadius: 5,
        lineWidth: 3,
        borderWidth: 2,
        legendSpacing: 20
    },

    // Grid settings
    grid: {
        divisions: 4,
        lineWidth: 1,
        dashPattern: [5, 5]
    },

    // Tooltip settings
    tooltip: {
        backgroundColor: 'rgba(0, 0, 0, 0.9)',
        textColor: '#ffffff',
        borderRadius: 6,
        padding: 10,
        fontSize: '13px',
        offset: { x: 10, y: -45 },
        hoverRadius: 20, // Distance from point to show tooltip
        transition: 'opacity 0.2s',
        zIndex: 9999
    },

    // Chart-specific presets
    presets: {
        revenue: {
            name: 'Revenue Trends',
            type: 'line',
            colors: {
                line: ['#667eea', '#764ba2'],
                area: 'rgba(102, 126, 234, 0.2)',
                point: '#667eea',
                trendline: 'rgba(255, 107, 107, 0.6)'
            },
            showTrendline: true,
            showGrid: true,
            showPoints: true,
            valueSuffix: '€'
        },
        expense: {
            name: 'Expense Trends',
            type: 'bar',
            colors: {
                bar: ['#f093fb', '#f5576c']
            },
            showGrid: true,
            showValueLabels: true,
            valueSuffix: '€'
        },
        comparison: {
            name: 'Year Comparison',
            type: 'grouped-bar',
            colors: {
                profit: ['#10b981', '#059669'],
                loss: ['#ef4444', '#dc2626']
            },
            showLegend: true,
            showGrid: true,
            barSpacing: 20,
            valueSuffix: '€'
        },
        multibar: {
            name: 'Multi-bar Comparison',
            type: 'grouped-bar',
            showGrid: true,
            showLegend: true,
            valueSuffix: '€'
        }
    },

    // Animation settings (for future use)
    animation: {
        enabled: false, // Not implemented yet
        duration: 300,
        easing: 'easeInOutQuad'
    }
};

/**
 * Get a color value with CSS variable fallback support
 * Tries CSS variable first (for dark mode), then config, then fallback
 * @param {string} path - Dot-separated path to color (e.g., 'primary.main')
 * @param {string} fallback - Fallback color if not found
 * @returns {string} Color value
 */
ChartConfig.getColor = function(path, fallback) {
    // Try CSS variable first (dark mode support)
    const cssVarName = '--chart-' + path.replace(/\./g, '-');
    const cssValue = getCSSVariable(cssVarName);
    if (cssValue) return cssValue;

    // Fall back to config
    const parts = path.split('.');
    let value = this.colors;
    for (const part of parts) {
        value = value?.[part];
        if (value === undefined) break;
    }

    return value || fallback || '#667eea';
};

/**
 * Get a preset configuration by name
 * @param {string} name - Preset name (e.g., 'revenue', 'expense')
 * @returns {Object} Preset configuration
 */
ChartConfig.getPreset = function(name) {
    return this.presets[name] || this.presets.revenue;
};

/**
 * Get padding configuration
 * @param {string} type - Padding type ('default' or 'bar')
 * @returns {Object} Padding object with top, right, bottom, left
 */
ChartConfig.getPadding = function(type = 'default') {
    return { ...this.spacing.padding[type] };
};

/**
 * Get font configuration
 * @param {string} type - Font type (e.g., 'axis', 'label', 'value')
 * @returns {string} Font specification
 */
ChartConfig.getFont = function(type = 'label') {
    return this.fonts[type] || this.fonts.label;
};

/**
 * Get tooltip configuration
 * @returns {Object} Tooltip configuration
 */
ChartConfig.getTooltipConfig = function() {
    return { ...this.tooltip };
};

/**
 * Create a gradient for canvas context
 * @param {CanvasRenderingContext2D} ctx - Canvas context
 * @param {number} x0 - Start x coordinate
 * @param {number} y0 - Start y coordinate
 * @param {number} x1 - End x coordinate
 * @param {number} y1 - End y coordinate
 * @param {Array<string>} colors - Array of colors [start, end]
 * @returns {CanvasGradient} Gradient object
 */
ChartConfig.createGradient = function(ctx, x0, y0, x1, y1, colors) {
    const gradient = ctx.createLinearGradient(x0, y0, x1, y1);
    if (colors.length === 1) {
        gradient.addColorStop(0, colors[0]);
        gradient.addColorStop(1, colors[0]);
    } else {
        colors.forEach((color, index) => {
            gradient.addColorStop(index / (colors.length - 1), color);
        });
    }
    return gradient;
};

// Export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ChartConfig;
}

/**
 * Enhanced Chart Tooltip - Configurable tooltip system
 * @module charts/chart_tooltip_enhanced
 */

/**
 * Generic tooltip class with configurable formatting and styling
 */
class ChartTooltip {
    /**
     * Create a new tooltip
     * @param {HTMLCanvasElement} canvas - Canvas element
     * @param {Object} options - Configuration options
     * @param {Function} options.formatter - Custom formatter function (data) => string
     * @param {string} options.backgroundColor - Background color
     * @param {string} options.textColor - Text color
     * @param {number} options.borderRadius - Border radius in pixels
     * @param {number} options.padding - Padding in pixels
     * @param {number} options.hoverRadius - Distance threshold for hover detection
     * @param {Object} options.offset - Offset {x, y} from cursor
     */
    constructor(canvas, options = {}) {
        this.canvas = canvas;

        // Get defaults from config if available
        const config = typeof ChartConfig !== 'undefined' ? ChartConfig.getTooltipConfig() : {};

        this.backgroundColor = options.backgroundColor || config.backgroundColor || 'rgba(0, 0, 0, 0.9)';
        this.textColor = options.textColor || config.textColor || '#ffffff';
        this.borderRadius = options.borderRadius || config.borderRadius || 6;
        this.padding = options.padding || config.padding || 10;
        this.hoverRadius = options.hoverRadius || config.hoverRadius || 20;
        this.offset = options.offset || config.offset || { x: 10, y: -45 };
        this.transition = options.transition || config.transition || 'opacity 0.2s';
        this.zIndex = options.zIndex || config.zIndex || 9999;

        // Default formatter
        this.formatter = options.formatter || ((data) => {
            return `<strong>${data.label}</strong><br>${Math.round(data.value)} €`;
        });

        this.tooltipEl = null;
        this.mouseMoveHandler = null;
        this.mouseLeaveHandler = null;
    }

    /**
     * Setup hover detection and tooltip display
     * @param {Array<Object>} dataPoints - Points with metadata
     * Each point should have: {x, y, label, value, [extra]}
     */
    setup(dataPoints) {
        // Create tooltip element if not exists
        if (!this.tooltipEl) {
            this.tooltipEl = document.createElement('div');
            this.tooltipEl.style.cssText = `
                position: fixed;
                background: ${this.backgroundColor};
                color: ${this.textColor};
                border-radius: ${this.borderRadius}px;
                padding: ${this.padding}px;
                font-size: 13px;
                pointer-events: none;
                opacity: 0;
                transition: ${this.transition};
                z-index: ${this.zIndex};
                white-space: nowrap;
            `;
            document.body.appendChild(this.tooltipEl);
        }

        // Remove old handlers if they exist
        if (this.mouseMoveHandler) {
            this.canvas.removeEventListener('mousemove', this.mouseMoveHandler);
        }
        if (this.mouseLeaveHandler) {
            this.canvas.removeEventListener('mouseleave', this.mouseLeaveHandler);
        }

        // Mouse move handler
        this.mouseMoveHandler = (e) => {
            const rect = this.canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;

            // Find closest point
            let closest = null;
            let minDist = Infinity;

            dataPoints.forEach((point, index) => {
                const dist = Math.sqrt(
                    Math.pow(mouseX - point.x, 2) +
                    Math.pow(mouseY - point.y, 2)
                );
                if (dist < minDist && dist < this.hoverRadius) {
                    minDist = dist;
                    closest = { ...point, index };
                }
            });

            if (closest) {
                this.show(e.clientX, e.clientY, closest);
            } else {
                this.hide();
            }
        };

        // Mouse leave handler
        this.mouseLeaveHandler = () => this.hide();

        this.canvas.addEventListener('mousemove', this.mouseMoveHandler);
        this.canvas.addEventListener('mouseleave', this.mouseLeaveHandler);
    }

    /**
     * Show tooltip at position with data
     * @param {number} x - X coordinate (screen)
     * @param {number} y - Y coordinate (screen)
     * @param {Object} data - Data to display
     */
    show(x, y, data) {
        const content = this.formatter(data);
        this.tooltipEl.innerHTML = content;
        this.tooltipEl.style.left = (x + this.offset.x) + 'px';
        this.tooltipEl.style.top = (y + this.offset.y) + 'px';
        this.tooltipEl.style.opacity = '1';
        this.canvas.style.cursor = 'pointer';
    }

    /**
     * Hide tooltip
     */
    hide() {
        if (this.tooltipEl) {
            this.tooltipEl.style.opacity = '0';
        }
        this.canvas.style.cursor = 'default';
    }

    /**
     * Clean up (remove event listeners and DOM element)
     */
    destroy() {
        if (this.mouseMoveHandler) {
            this.canvas.removeEventListener('mousemove', this.mouseMoveHandler);
        }
        if (this.mouseLeaveHandler) {
            this.canvas.removeEventListener('mouseleave', this.mouseLeaveHandler);
        }
        if (this.tooltipEl) {
            this.tooltipEl.remove();
            this.tooltipEl = null;
        }
    }
}

/**
 * Multi-line tooltip with support for additional information
 */
class MultiLineTooltip extends ChartTooltip {
    constructor(canvas, options = {}) {
        super(canvas, {
            ...options,
            formatter: (data) => {
                const lines = [
                    `<div style="font-weight: bold; margin-bottom: 4px;">${data.label}</div>`,
                    `<div style="font-size: 14px;">${Math.round(data.value)}€</div>`
                ];
                if (data.extra) {
                    lines.push(`<div style="opacity: 0.8; margin-top: 4px; font-size: 11px;">${data.extra}</div>`);
                }
                return lines.join('');
            }
        });
    }
}

/**
 * Comparison tooltip showing multiple values
 */
class ComparisonTooltip extends ChartTooltip {
    constructor(canvas, options = {}) {
        super(canvas, {
            ...options,
            formatter: (data) => {
                const lines = [`<div style="font-weight: bold; margin-bottom: 6px;">${data.label}</div>`];

                if (data.values && Array.isArray(data.values)) {
                    data.values.forEach(item => {
                        const color = item.color || '#667eea';
                        lines.push(`
                            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 2px;">
                                <div style="width: 12px; height: 12px; background: ${color}; border-radius: 2px;"></div>
                                <div style="flex: 1;">${item.label}:</div>
                                <div style="font-weight: bold;">${Math.round(item.value)}€</div>
                            </div>
                        `);
                    });
                } else {
                    lines.push(`<div>${Math.round(data.value)}€</div>`);
                }

                return lines.join('');
            }
        });
    }
}

// Export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        ChartTooltip,
        MultiLineTooltip,
        ComparisonTooltip
    };
}

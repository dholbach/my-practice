/**
 * Chart Tooltip - Basic tooltip functionality
 * @module charts/chart_tooltip
 */

/**
 * Setup hover tooltip for chart
 */
function setupTooltip(canvas, points, data, labels) {
    const tooltip = document.createElement('div');
    tooltip.style.cssText = 'position: fixed; background: rgba(0,0,0,0.9); color: white; padding: 8px 12px; border-radius: 6px; font-size: 13px; pointer-events: none; opacity: 0; transition: opacity 0.2s; z-index: 9999; white-space: nowrap;';
    document.body.appendChild(tooltip);

    canvas.addEventListener('mousemove', (e) => {
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        let closestPoint = null;
        let closestDistance = Infinity;

        points.forEach((point, index) => {
            const distance = Math.sqrt(Math.pow(x - point.x, 2) + Math.pow(y - point.y, 2));
            if (distance < closestDistance && distance < 20) {
                closestDistance = distance;
                closestPoint = { ...point, index };
            }
        });

        if (closestPoint) {
            tooltip.innerHTML = `<strong>${labels[closestPoint.index]}</strong><br>${Math.round(data[closestPoint.index])} €`;
            tooltip.style.left = (e.clientX + 10) + 'px';
            tooltip.style.top = (e.clientY - 45) + 'px';
            tooltip.style.opacity = '1';
            canvas.style.cursor = 'pointer';
        } else {
            tooltip.style.opacity = '0';
            canvas.style.cursor = 'default';
        }
    });

    canvas.addEventListener('mouseleave', () => {
        tooltip.style.opacity = '0';
        canvas.style.cursor = 'default';
    });

    return tooltip;
}

// Export functions
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        setupTooltip
    };
}

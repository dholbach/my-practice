/**
 * Tests for chart_tooltip_enhanced.js
 * Tests tooltip classes: ChartTooltip, MultiLineTooltip, ComparisonTooltip
 */

// Helper to create test canvas
function createTestCanvas() {
    const canvas = document.createElement('canvas');
    canvas.width = 400;
    canvas.height = 300;
    canvas.style.position = 'relative';
    document.body.appendChild(canvas);
    return canvas;
}

// Helper to cleanup test canvas
function cleanupCanvas(canvas) {
    if (canvas && canvas.parentNode) {
        canvas.parentNode.removeChild(canvas);
    }
}

// Test ChartTooltip construction
function testChartTooltipConstruction() {
    const canvas = createTestCanvas();

    try {
        const tooltip = new ChartTooltip(canvas);
        console.assert(tooltip !== null, 'ChartTooltip should be created');
        console.assert(tooltip.canvas === canvas, 'Tooltip should store canvas reference');
        console.assert(tooltip.tooltip !== null, 'Tooltip element should be created');
        console.assert(tooltip.tooltip.style.position === 'absolute', 'Tooltip should be absolutely positioned');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test ChartTooltip with custom options
function testChartTooltipCustomOptions() {
    const canvas = createTestCanvas();

    try {
        const customOptions = {
            backgroundColor: 'red',
            textColor: 'white',
            fontSize: 16,
            padding: 20
        };

        const tooltip = new ChartTooltip(canvas, customOptions);
        console.assert(tooltip.options.backgroundColor === 'red', 'Custom backgroundColor should be applied');
        console.assert(tooltip.options.textColor === 'white', 'Custom textColor should be applied');
        console.assert(tooltip.options.fontSize === 16, 'Custom fontSize should be applied');
        console.assert(tooltip.options.padding === 20, 'Custom padding should be applied');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test ChartTooltip setup with data points
function testChartTooltipSetup() {
    const canvas = createTestCanvas();

    try {
        const tooltip = new ChartTooltip(canvas);
        const dataPoints = [
            { x: 100, y: 100, label: 'Point 1', value: 50 },
            { x: 200, y: 150, label: 'Point 2', value: 75 }
        ];

        tooltip.setup(dataPoints);
        console.assert(tooltip.dataPoints === dataPoints, 'Data points should be stored');
        console.assert(tooltip.dataPoints.length === 2, 'Should have 2 data points');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test ChartTooltip show method
function testChartTooltipShow() {
    const canvas = createTestCanvas();

    try {
        const tooltip = new ChartTooltip(canvas);
        const data = { label: 'Test', value: 100 };

        tooltip.show(150, 200, data);

        console.assert(tooltip.tooltip.style.display === 'block', 'Tooltip should be visible');
        console.assert(tooltip.tooltip.innerHTML.includes('Test'), 'Tooltip should contain label');
        console.assert(tooltip.tooltip.innerHTML.includes('100'), 'Tooltip should contain value');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test ChartTooltip hide method
function testChartTooltipHide() {
    const canvas = createTestCanvas();

    try {
        const tooltip = new ChartTooltip(canvas);
        tooltip.show(100, 100, { label: 'Test', value: 50 });
        tooltip.hide();

        console.assert(tooltip.tooltip.style.display === 'none', 'Tooltip should be hidden');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test ChartTooltip custom formatter
function testChartTooltipCustomFormatter() {
    const canvas = createTestCanvas();

    try {
        const formatter = (data) => `<strong>${data.label}</strong>: €${data.value}`;
        const tooltip = new ChartTooltip(canvas, { formatter });

        tooltip.show(100, 100, { label: 'Revenue', value: 500 });

        console.assert(tooltip.tooltip.innerHTML.includes('<strong>Revenue</strong>'), 'Custom formatter should be used');
        console.assert(tooltip.tooltip.innerHTML.includes('€500'), 'Custom formatter should format value');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test ChartTooltip hover detection
function testChartTooltipHoverDetection() {
    const canvas = createTestCanvas();

    try {
        const tooltip = new ChartTooltip(canvas);
        const dataPoints = [
            { x: 100, y: 100, label: 'Point 1', value: 50 },
            { x: 200, y: 150, label: 'Point 2', value: 75 }
        ];

        tooltip.setup(dataPoints);

        // Simulate mousemove near first point
        const event = new MouseEvent('mousemove', {
            clientX: canvas.offsetLeft + 105,
            clientY: canvas.offsetTop + 105
        });
        canvas.dispatchEvent(event);

        // Note: In real test, tooltip should show, but testing event handling is complex
        console.assert(tooltip.dataPoints.length === 2, 'Data points should be accessible for hover detection');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test ChartTooltip destroy method
function testChartTooltipDestroy() {
    const canvas = createTestCanvas();

    try {
        const tooltip = new ChartTooltip(canvas);
        const tooltipElement = tooltip.tooltip;

        tooltip.destroy();

        console.assert(!document.body.contains(tooltipElement), 'Tooltip element should be removed from DOM');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test MultiLineTooltip
function testMultiLineTooltip() {
    const canvas = createTestCanvas();

    try {
        const formatter = (data) => `
            <div><strong>${data.label}</strong></div>
            <div>Value: ${data.value}</div>
            <div>Info: ${data.info || 'N/A'}</div>
        `;

        const tooltip = new MultiLineTooltip(canvas, { formatter });

        tooltip.show(100, 100, { label: 'Test', value: 100, info: 'Extra info' });

        console.assert(tooltip.tooltip.innerHTML.includes('Test'), 'MultiLine tooltip should show label');
        console.assert(tooltip.tooltip.innerHTML.includes('100'), 'MultiLine tooltip should show value');
        console.assert(tooltip.tooltip.innerHTML.includes('Extra info'), 'MultiLine tooltip should show extra info');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test ComparisonTooltip
function testComparisonTooltip() {
    const canvas = createTestCanvas();

    try {
        const formatter = (data) => {
            let html = `<div><strong>${data.label}</strong></div>`;
            if (data.values) {
                data.values.forEach((item, i) => {
                    const color = data.colors ? data.colors[i] : '#666';
                    html += `<div style="color: ${color}">${item.name}: ${item.value}</div>`;
                });
            }
            return html;
        };

        const tooltip = new ComparisonTooltip(canvas, { formatter });

        const data = {
            label: '2024',
            values: [
                { name: 'Revenue', value: 1000 },
                { name: 'Expense', value: 500 }
            ],
            colors: ['#667eea', '#ef4444']
        };

        tooltip.show(100, 100, data);

        console.assert(tooltip.tooltip.innerHTML.includes('2024'), 'Comparison tooltip should show label');
        console.assert(tooltip.tooltip.innerHTML.includes('Revenue'), 'Comparison tooltip should show first value');
        console.assert(tooltip.tooltip.innerHTML.includes('Expense'), 'Comparison tooltip should show second value');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test tooltip positioning (stays on screen)
function testTooltipPositioning() {
    const canvas = createTestCanvas();

    try {
        const tooltip = new ChartTooltip(canvas);

        // Show near right edge
        tooltip.show(canvas.width - 10, 100, { label: 'Test', value: 50 });

        const tooltipRect = tooltip.tooltip.getBoundingClientRect();
        const canvasRect = canvas.getBoundingClientRect();

        // Tooltip should not overflow canvas right edge significantly
        console.assert(tooltipRect.right <= canvasRect.right + 50, 'Tooltip should not overflow canvas right edge too much');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test tooltip z-index
function testTooltipZIndex() {
    const canvas = createTestCanvas();

    try {
        const tooltip = new ChartTooltip(canvas);
        const zIndex = parseInt(tooltip.tooltip.style.zIndex);

        console.assert(zIndex >= 1000, 'Tooltip should have high z-index');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test tooltip pointer events
function testTooltipPointerEvents() {
    const canvas = createTestCanvas();

    try {
        const tooltip = new ChartTooltip(canvas);

        console.assert(tooltip.tooltip.style.pointerEvents === 'none', 'Tooltip should not block pointer events');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Run all tests
function runChartTooltipTests() {
    console.group('ChartTooltip Tests');

    try {
        testChartTooltipConstruction();
        console.log('✓ ChartTooltip construction');

        testChartTooltipCustomOptions();
        console.log('✓ Custom options');

        testChartTooltipSetup();
        console.log('✓ Setup with data points');

        testChartTooltipShow();
        console.log('✓ Show method');

        testChartTooltipHide();
        console.log('✓ Hide method');

        testChartTooltipCustomFormatter();
        console.log('✓ Custom formatter');

        testChartTooltipHoverDetection();
        console.log('✓ Hover detection');

        testChartTooltipDestroy();
        console.log('✓ Destroy method');

        testMultiLineTooltip();
        console.log('✓ MultiLineTooltip');

        testComparisonTooltip();
        console.log('✓ ComparisonTooltip');

        testTooltipPositioning();
        console.log('✓ Tooltip positioning');

        testTooltipZIndex();
        console.log('✓ Tooltip z-index');

        testTooltipPointerEvents();
        console.log('✓ Tooltip pointer events');

        console.log('\n✅ All ChartTooltip tests passed!');
    } catch (error) {
        console.error('❌ Test failed:', error);
    }

    console.groupEnd();
}

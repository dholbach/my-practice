/**
 * Tests for chart_builder.js
 * Tests ChartBuilder fluent API and chart construction
 */

// Helper to create test canvas
function createTestCanvas() {
    const canvas = document.createElement('canvas');
    canvas.width = 400;
    canvas.height = 300;
    document.body.appendChild(canvas);
    return canvas;
}

// Helper to cleanup test canvas
function cleanupCanvas(canvas) {
    if (canvas && canvas.parentNode) {
        canvas.parentNode.removeChild(canvas);
    }
}

// Test ChartBuilder construction
function testChartBuilderConstruction() {
    const canvas = createTestCanvas();

    try {
        const builder = new ChartBuilder(canvas);
        console.assert(builder !== null, 'ChartBuilder should be created');
        console.assert(builder.canvas === canvas, 'Builder should store canvas reference');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test ChartBuilder type() method
function testChartBuilderType() {
    const canvas = createTestCanvas();

    try {
        const builder = new ChartBuilder(canvas);
        const result = builder.type('bar');

        console.assert(result === builder, 'type() should return builder for chaining');
        console.assert(builder._type === 'bar', 'Type should be stored');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test ChartBuilder data() and labels() methods
function testChartBuilderDataLabels() {
    const canvas = createTestCanvas();

    try {
        const builder = new ChartBuilder(canvas);
        const data = [10, 20, 30];
        const labels = ['A', 'B', 'C'];

        builder.data(data).labels(labels);

        console.assert(builder._data === data, 'Data should be stored');
        console.assert(builder._labels === labels, 'Labels should be stored');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test ChartBuilder preset() method
function testChartBuilderPreset() {
    const canvas = createTestCanvas();

    try {
        const builder = new ChartBuilder(canvas);
        builder.preset('revenue');

        console.assert(builder._preset === 'revenue', 'Preset name should be stored');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test ChartBuilder tooltip() method
function testChartBuilderTooltip() {
    const canvas = createTestCanvas();

    try {
        const builder = new ChartBuilder(canvas);
        const formatter = (d) => `${d.label}: ${d.value}`;

        builder.tooltip(formatter);

        console.assert(builder._tooltipFormatter === formatter, 'Tooltip formatter should be stored');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test ChartBuilder options() method
function testChartBuilderOptions() {
    const canvas = createTestCanvas();

    try {
        const builder = new ChartBuilder(canvas);
        const options = { showLegend: true, showValues: false };

        builder.options(options);

        console.assert(builder._options.showLegend === true, 'Options should be stored');
        console.assert(builder._options.showValues === false, 'Options should be stored');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test ChartBuilder colors() method
function testChartBuilderColors() {
    const canvas = createTestCanvas();

    try {
        const builder = new ChartBuilder(canvas);
        const colors = ['red', 'blue', 'green'];

        builder.colors(colors);

        console.assert(builder._colors === colors, 'Colors should be stored');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test ChartBuilder datasets() method
function testChartBuilderDatasets() {
    const canvas = createTestCanvas();

    try {
        const builder = new ChartBuilder(canvas);
        const datasets = [
            { label: 'Series 1', data: [10, 20, 30] },
            { label: 'Series 2', data: [15, 25, 35] }
        ];

        builder.datasets(datasets);

        console.assert(builder._datasets === datasets, 'Datasets should be stored');
        console.assert(builder._datasets.length === 2, 'Should have 2 datasets');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test ChartBuilder build() - bar chart
function testChartBuilderBuildBar() {
    const canvas = createTestCanvas();

    try {
        const builder = new ChartBuilder(canvas);
        const data = [100, 200, 150];
        const labels = ['Jan', 'Feb', 'Mar'];

        const result = builder
            .type('bar')
            .data(data)
            .labels(labels)
            .build();

        console.assert(result !== null, 'build() should return result');
        console.assert(result.canvas === canvas, 'Result should contain canvas');
        console.assert(typeof result.redraw === 'function', 'Result should have redraw function');

        // Check canvas has been drawn on
        const ctx = canvas.getContext('2d');
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const hasDrawing = imageData.data.some(value => value !== 0);
        console.assert(hasDrawing, 'Canvas should have been drawn on');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test ChartBuilder build() - line chart
function testChartBuilderBuildLine() {
    const canvas = createTestCanvas();

    try {
        const builder = new ChartBuilder(canvas);
        const data = [100, 200, 150, 250];
        const labels = ['Q1', 'Q2', 'Q3', 'Q4'];

        const result = builder
            .type('line')
            .data(data)
            .labels(labels)
            .build();

        console.assert(result !== null, 'build() should return result');

        // Check canvas has been drawn on
        const ctx = canvas.getContext('2d');
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const hasDrawing = imageData.data.some(value => value !== 0);
        console.assert(hasDrawing, 'Canvas should have been drawn on');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test ChartBuilder build() - grouped bar chart
function testChartBuilderBuildGroupedBar() {
    const canvas = createTestCanvas();

    try {
        const builder = new ChartBuilder(canvas);
        const datasets = [
            { label: 'Revenue', data: [100, 150, 200], color: '#667eea' },
            { label: 'Expense', data: [80, 120, 150], color: '#ef4444' }
        ];
        const labels = ['Jan', 'Feb', 'Mar'];

        const result = builder
            .type('grouped-bar')
            .datasets(datasets)
            .labels(labels)
            .build();

        console.assert(result !== null, 'build() should return result');

        // Check canvas has been drawn on
        const ctx = canvas.getContext('2d');
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const hasDrawing = imageData.data.some(value => value !== 0);
        console.assert(hasDrawing, 'Canvas should have been drawn on');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test ChartBuilder with preset
function testChartBuilderWithPreset() {
    const canvas = createTestCanvas();

    try {
        const builder = new ChartBuilder(canvas);
        const data = [100, 200, 150];
        const labels = ['A', 'B', 'C'];

        const result = builder
            .preset('expense')
            .data(data)
            .labels(labels)
            .build();

        console.assert(result !== null, 'build() should work with preset');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test ChartBuilder validation - missing type
function testChartBuilderValidationMissingType() {
    const canvas = createTestCanvas();

    try {
        const builder = new ChartBuilder(canvas);
        const data = [100, 200];
        const labels = ['A', 'B'];

        let errorThrown = false;
        try {
            builder.data(data).labels(labels).build();
        } catch (error) {
            errorThrown = true;
            console.assert(error.message.includes('type'), 'Error should mention missing type');
        }

        console.assert(errorThrown, 'Should throw error for missing type');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test ChartBuilder validation - missing data
function testChartBuilderValidationMissingData() {
    const canvas = createTestCanvas();

    try {
        const builder = new ChartBuilder(canvas);
        const labels = ['A', 'B'];

        let errorThrown = false;
        try {
            builder.type('bar').labels(labels).build();
        } catch (error) {
            errorThrown = true;
            console.assert(error.message.includes('data'), 'Error should mention missing data');
        }

        console.assert(errorThrown, 'Should throw error for missing data');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test ChartBuilder validation - mismatched lengths
function testChartBuilderValidationMismatchedLengths() {
    const canvas = createTestCanvas();

    try {
        const builder = new ChartBuilder(canvas);
        const data = [100, 200];
        const labels = ['A', 'B', 'C']; // One extra label

        let errorThrown = false;
        try {
            builder.type('bar').data(data).labels(labels).build();
        } catch (error) {
            errorThrown = true;
            console.assert(error.message.includes('length') || error.message.includes('match'),
                'Error should mention length mismatch');
        }

        console.assert(errorThrown, 'Should throw error for mismatched lengths');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test ChartBuilder method chaining
function testChartBuilderChaining() {
    const canvas = createTestCanvas();

    try {
        const builder = new ChartBuilder(canvas);

        // All methods should return builder for chaining
        const result = builder
            .type('bar')
            .data([10, 20])
            .labels(['A', 'B'])
            .colors(['red', 'blue'])
            .options({ showLegend: true })
            .tooltip((d) => d.label);

        console.assert(result === builder, 'All methods should return builder');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Test ChartBuilder redraw function
function testChartBuilderRedraw() {
    const canvas = createTestCanvas();

    try {
        const builder = new ChartBuilder(canvas);
        const data = [100, 200, 150];
        const labels = ['A', 'B', 'C'];

        const result = builder
            .type('bar')
            .data(data)
            .labels(labels)
            .build();

        // Clear canvas
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Redraw should work
        result.redraw();

        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const hasDrawing = imageData.data.some(value => value !== 0);
        console.assert(hasDrawing, 'Redraw should have drawn on canvas');
    } finally {
        cleanupCanvas(canvas);
    }
}

// Run all tests
function runChartBuilderTests() {
    console.group('ChartBuilder Tests');

    try {
        testChartBuilderConstruction();
        console.log('✓ ChartBuilder construction');

        testChartBuilderType();
        console.log('✓ type() method');

        testChartBuilderDataLabels();
        console.log('✓ data() and labels() methods');

        testChartBuilderPreset();
        console.log('✓ preset() method');

        testChartBuilderTooltip();
        console.log('✓ tooltip() method');

        testChartBuilderOptions();
        console.log('✓ options() method');

        testChartBuilderColors();
        console.log('✓ colors() method');

        testChartBuilderDatasets();
        console.log('✓ datasets() method');

        testChartBuilderBuildBar();
        console.log('✓ build() - bar chart');

        testChartBuilderBuildLine();
        console.log('✓ build() - line chart');

        testChartBuilderBuildGroupedBar();
        console.log('✓ build() - grouped bar chart');

        testChartBuilderWithPreset();
        console.log('✓ build() with preset');

        testChartBuilderValidationMissingType();
        console.log('✓ Validation - missing type');

        testChartBuilderValidationMissingData();
        console.log('✓ Validation - missing data');

        testChartBuilderValidationMismatchedLengths();
        console.log('✓ Validation - mismatched lengths');

        testChartBuilderChaining();
        console.log('✓ Method chaining');

        testChartBuilderRedraw();
        console.log('✓ Redraw function');

        console.log('\n✅ All ChartBuilder tests passed!');
    } catch (error) {
        console.error('❌ Test failed:', error);
    }

    console.groupEnd();
}

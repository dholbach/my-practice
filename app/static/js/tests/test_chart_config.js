/**
 * Tests for chart_config.js
 * Tests configuration system, color palettes, presets, and helper methods
 */

// Test ChartConfig object structure
function testChartConfigStructure() {
    console.assert(typeof ChartConfig === 'object', 'ChartConfig should be an object');
    console.assert(typeof ChartConfig.colors === 'object', 'ChartConfig.colors should exist');
    console.assert(typeof ChartConfig.fonts === 'object', 'ChartConfig.fonts should exist');
    console.assert(typeof ChartConfig.spacing === 'object', 'ChartConfig.spacing should exist');
    console.assert(typeof ChartConfig.grid === 'object', 'ChartConfig.grid should exist');
    console.assert(typeof ChartConfig.tooltip === 'object', 'ChartConfig.tooltip should exist');
    console.assert(typeof ChartConfig.presets === 'object', 'ChartConfig.presets should exist');
    console.assert(typeof ChartConfig.animation === 'object', 'ChartConfig.animation should exist');
}

// Test color palette
function testColorPalette() {
    const colors = ChartConfig.colors;

    // Primary colors
    console.assert(colors.primary === '#667eea', 'Primary color should be #667eea');
    console.assert(colors.secondary === '#f093fb', 'Secondary color should be #f093fb');

    // Status colors
    console.assert(colors.success === '#10b981', 'Success color should be #10b981');
    console.assert(colors.warning === '#f59e0b', 'Warning color should be #f59e0b');
    console.assert(colors.danger === '#ef4444', 'Danger color should be #ef4444');

    // Neutral colors array
    console.assert(Array.isArray(colors.neutral), 'Neutral should be an array');
    console.assert(colors.neutral.length >= 5, 'Neutral should have at least 5 colors');
}

// Test getColor helper
function testGetColor() {
    // Get by name
    console.assert(ChartConfig.getColor('primary') === '#667eea', 'getColor("primary") should return #667eea');
    console.assert(ChartConfig.getColor('success') === '#10b981', 'getColor("success") should return #10b981');

    // Get by index
    console.assert(ChartConfig.getColor(0) === '#667eea', 'getColor(0) should return primary color');
    console.assert(ChartConfig.getColor(1) === '#f093fb', 'getColor(1) should return secondary color');

    // Invalid inputs should return primary
    console.assert(ChartConfig.getColor('invalid') === '#667eea', 'Invalid color name should return primary');
    console.assert(ChartConfig.getColor(999) === '#667eea', 'Out of range index should return primary');
}

// Test font configuration
function testFontConfig() {
    const fonts = ChartConfig.fonts;

    console.assert(typeof fonts.family === 'string', 'Font family should be a string');
    console.assert(fonts.family.includes('Inter'), 'Font family should include Inter');

    console.assert(typeof fonts.axis === 'object', 'Axis font should be an object');
    console.assert(fonts.axis.size === 10, 'Axis font size should be 10');
    console.assert(fonts.axis.color === '#6b7280', 'Axis font color should be #6b7280');

    console.assert(typeof fonts.label === 'object', 'Label font should be an object');
    console.assert(fonts.label.size === 11, 'Label font size should be 11');

    console.assert(typeof fonts.value === 'object', 'Value font should be an object');
    console.assert(fonts.value.size === 13, 'Value font size should be 13');
}

// Test getFont helper
function testGetFont() {
    const axisFont = ChartConfig.getFont('axis');
    console.assert(typeof axisFont === 'string', 'getFont should return a string');
    console.assert(axisFont.includes('10px'), 'Axis font should include 10px');
    console.assert(axisFont.includes('Inter'), 'Axis font should include Inter');

    const labelFont = ChartConfig.getFont('label');
    console.assert(labelFont.includes('11px'), 'Label font should include 11px');

    // With custom family
    const customFont = ChartConfig.getFont('axis', 'Arial');
    console.assert(customFont.includes('Arial'), 'Custom font family should be used');
}

// Test spacing configuration
function testSpacingConfig() {
    const spacing = ChartConfig.spacing;

    console.assert(typeof spacing.barSpacing === 'number', 'barSpacing should be a number');
    console.assert(spacing.barSpacing === 12, 'barSpacing should be 12');

    console.assert(typeof spacing.groupSpacing === 'number', 'groupSpacing should be a number');
    console.assert(spacing.groupSpacing === 40, 'groupSpacing should be 40');

    console.assert(typeof spacing.lineWidth === 'number', 'lineWidth should be a number');
    console.assert(spacing.lineWidth === 2, 'lineWidth should be 2');

    console.assert(typeof spacing.pointRadius === 'number', 'pointRadius should be a number');
    console.assert(spacing.pointRadius === 4, 'pointRadius should be 4');
}

// Test getPadding helper
function testGetPadding() {
    const defaultPadding = ChartConfig.getPadding();

    console.assert(typeof defaultPadding === 'object', 'getPadding should return an object');
    console.assert(defaultPadding.top === 40, 'Default top padding should be 40');
    console.assert(defaultPadding.right === 20, 'Default right padding should be 20');
    console.assert(defaultPadding.bottom === 60, 'Default bottom padding should be 60');
    console.assert(defaultPadding.left === 60, 'Default left padding should be 60');

    // With custom overrides
    const customPadding = ChartConfig.getPadding({ top: 100, left: 80 });
    console.assert(customPadding.top === 100, 'Custom top padding should be used');
    console.assert(customPadding.left === 80, 'Custom left padding should be used');
    console.assert(customPadding.right === 20, 'Non-overridden values should use defaults');
}

// Test grid configuration
function testGridConfig() {
    const grid = ChartConfig.grid;

    console.assert(typeof grid.color === 'string', 'Grid color should be a string');
    console.assert(grid.color === '#e5e7eb', 'Grid color should be #e5e7eb');

    console.assert(typeof grid.lineWidth === 'number', 'Grid lineWidth should be a number');
    console.assert(grid.lineWidth === 1, 'Grid lineWidth should be 1');

    console.assert(typeof grid.horizontalLines === 'number', 'horizontalLines should be a number');
    console.assert(grid.horizontalLines === 5, 'horizontalLines should be 5');
}

// Test tooltip configuration
function testTooltipConfig() {
    const tooltip = ChartConfig.tooltip;

    console.assert(typeof tooltip.backgroundColor === 'string', 'Tooltip backgroundColor should be a string');
    console.assert(typeof tooltip.textColor === 'string', 'Tooltip textColor should be a string');
    console.assert(typeof tooltip.borderColor === 'string', 'Tooltip borderColor should be a string');
    console.assert(typeof tooltip.fontSize === 'number', 'Tooltip fontSize should be a number');
    console.assert(typeof tooltip.padding === 'number', 'Tooltip padding should be a number');
    console.assert(typeof tooltip.borderRadius === 'number', 'Tooltip borderRadius should be a number');
    console.assert(typeof tooltip.offsetX === 'number', 'Tooltip offsetX should be a number');
    console.assert(typeof tooltip.offsetY === 'number', 'Tooltip offsetY should be a number');
}

// Test getTooltipConfig helper
function testGetTooltipConfig() {
    const defaultTooltip = ChartConfig.getTooltipConfig();

    console.assert(typeof defaultTooltip === 'object', 'getTooltipConfig should return an object');
    console.assert(defaultTooltip.backgroundColor === 'rgba(31, 41, 55, 0.95)', 'Default backgroundColor should match');

    // With custom overrides
    const customTooltip = ChartConfig.getTooltipConfig({ fontSize: 16, padding: 20 });
    console.assert(customTooltip.fontSize === 16, 'Custom fontSize should be used');
    console.assert(customTooltip.padding === 20, 'Custom padding should be used');
    console.assert(customTooltip.borderRadius === 6, 'Non-overridden values should use defaults');
}

// Test presets existence
function testPresetsExistence() {
    const presets = ChartConfig.presets;

    console.assert(typeof presets.revenue === 'object', 'Revenue preset should exist');
    console.assert(typeof presets.expense === 'object', 'Expense preset should exist');
    console.assert(typeof presets.comparison === 'object', 'Comparison preset should exist');
    console.assert(typeof presets.multibar === 'object', 'Multibar preset should exist');
}

// Test revenue preset
function testRevenuePreset() {
    const preset = ChartConfig.presets.revenue;

    console.assert(preset.type === 'line', 'Revenue preset type should be line');
    console.assert(preset.color === '#667eea', 'Revenue preset color should be primary');
    console.assert(preset.showArea === true, 'Revenue preset should show area');
    console.assert(preset.showTrendline === true, 'Revenue preset should show trendline');
    console.assert(preset.showPoints === true, 'Revenue preset should show points');
    console.assert(typeof preset.padding === 'object', 'Revenue preset should have padding');
}

// Test expense preset
function testExpensePreset() {
    const preset = ChartConfig.presets.expense;

    console.assert(preset.type === 'bar', 'Expense preset type should be bar');
    console.assert(preset.color === '#ef4444', 'Expense preset color should be danger');
    console.assert(preset.showValues === false, 'Expense preset should not show values by default');
    console.assert(typeof preset.padding === 'object', 'Expense preset should have padding');
}

// Test comparison preset
function testComparisonPreset() {
    const preset = ChartConfig.presets.comparison;

    console.assert(preset.type === 'grouped-bar', 'Comparison preset type should be grouped-bar');
    console.assert(preset.showLegend === true, 'Comparison preset should show legend');
    console.assert(Array.isArray(preset.colors), 'Comparison preset colors should be an array');
    console.assert(preset.colors.length >= 3, 'Comparison preset should have at least 3 colors');
}

// Test multibar preset
function testMultibarPreset() {
    const preset = ChartConfig.presets.multibar;

    console.assert(preset.type === 'grouped-bar', 'Multibar preset type should be grouped-bar');
    console.assert(preset.showLegend === true, 'Multibar preset should show legend');
    console.assert(Array.isArray(preset.colors), 'Multibar preset colors should be an array');
}

// Test getPreset helper
function testGetPreset() {
    const revenuePreset = ChartConfig.getPreset('revenue');
    console.assert(typeof revenuePreset === 'object', 'getPreset should return an object');
    console.assert(revenuePreset.type === 'line', 'Revenue preset should have correct type');

    const expensePreset = ChartConfig.getPreset('expense');
    console.assert(expensePreset.type === 'bar', 'Expense preset should have correct type');

    // Invalid preset should return empty object
    const invalidPreset = ChartConfig.getPreset('invalid');
    console.assert(typeof invalidPreset === 'object', 'Invalid preset should return object');
    console.assert(Object.keys(invalidPreset).length === 0, 'Invalid preset should be empty');
}

// Test animation configuration
function testAnimationConfig() {
    const animation = ChartConfig.animation;

    console.assert(typeof animation.enabled === 'boolean', 'Animation enabled should be boolean');
    console.assert(typeof animation.duration === 'number', 'Animation duration should be a number');
    console.assert(typeof animation.easing === 'string', 'Animation easing should be a string');
}

// Test createGradient helper
function testCreateGradient() {
    // Need a canvas context to test gradient creation
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');

    const gradient = ChartConfig.createGradient(ctx, 0, 0, 0, 100, '#667eea');
    console.assert(gradient !== null, 'createGradient should return a gradient');
    console.assert(typeof gradient === 'object', 'Gradient should be an object');

    // Test with color array
    const multiGradient = ChartConfig.createGradient(ctx, 0, 0, 0, 100, ['#667eea', '#f093fb']);
    console.assert(multiGradient !== null, 'createGradient should work with color array');
}

// Run all tests
function runChartConfigTests() {
    console.group('ChartConfig Tests');

    try {
        testChartConfigStructure();
        console.log('✓ ChartConfig structure');

        testColorPalette();
        console.log('✓ Color palette');

        testGetColor();
        console.log('✓ getColor()');

        testFontConfig();
        console.log('✓ Font configuration');

        testGetFont();
        console.log('✓ getFont()');

        testSpacingConfig();
        console.log('✓ Spacing configuration');

        testGetPadding();
        console.log('✓ getPadding()');

        testGridConfig();
        console.log('✓ Grid configuration');

        testTooltipConfig();
        console.log('✓ Tooltip configuration');

        testGetTooltipConfig();
        console.log('✓ getTooltipConfig()');

        testPresetsExistence();
        console.log('✓ Presets existence');

        testRevenuePreset();
        console.log('✓ Revenue preset');

        testExpensePreset();
        console.log('✓ Expense preset');

        testComparisonPreset();
        console.log('✓ Comparison preset');

        testMultibarPreset();
        console.log('✓ Multibar preset');

        testGetPreset();
        console.log('✓ getPreset()');

        testAnimationConfig();
        console.log('✓ Animation configuration');

        testCreateGradient();
        console.log('✓ createGradient()');

        console.log('\n✅ All ChartConfig tests passed!');
    } catch (error) {
        console.error('❌ Test failed:', error);
    }

    console.groupEnd();
}

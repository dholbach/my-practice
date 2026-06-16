/**
 * Tests for chart utility functions
 * Run with: node chart_utils.test.js
 */

// Mock module system for browser code
if (typeof module === 'undefined') {
    var module = { exports: {} };
}

// Load the functions from refactored chart_math module
const {
    calculateYearLabels,
    parseMonthString,
    findFirstNonZeroIndex,
    calculatePoints,
    aggregateMonthlyToYearly
} = require('./charts/chart_math.js');

// Simple test framework
function test(name, fn) {
    try {
        fn();
        console.log(`✓ ${name}`);
    } catch (error) {
        console.error(`✗ ${name}`);
        console.error(`  ${error.message}`);
    }
}

function assertEquals(actual, expected, message) {
    const actualStr = JSON.stringify(actual);
    const expectedStr = JSON.stringify(expected);
    if (actualStr !== expectedStr) {
        throw new Error(`${message}\n  Expected: ${expectedStr}\n  Actual: ${actualStr}`);
    }
}

function assertNotNull(value, message) {
    if (value === null || value === undefined) {
        throw new Error(message);
    }
}

// Tests
console.log('\n📊 Running Chart Utils Tests\n');

test('calculateYearLabels - basic case with 24 months', () => {
    // 24 data points = indices 0-23, so labels at index 0 (2020) and 12 (2021)
    const labels = calculateYearLabels(24, 2020, 12);
    assertEquals(labels.length, 2, 'Should have 2 labels');
    assertEquals(labels[0], { index: 0, year: 2020 }, 'First label');
    assertEquals(labels[1], { index: 12, year: 2021 }, 'Second label');
});

test('calculateYearLabels - 63 months starting 2020', () => {
    const labels = calculateYearLabels(63, 2020, 12);
    assertEquals(labels.length, 6, 'Should have 6 labels');
    assertEquals(labels[0].year, 2020, 'First year');
    assertEquals(labels[5].year, 2025, 'Last year');
});

test('parseMonthString - YYYY-MM format', () => {
    const result = parseMonthString('2020-10');
    assertNotNull(result, 'Should parse successfully');
    assertEquals(result, { year: 2020, month: 10 }, 'Should parse correctly');
});

test('parseMonthString - MMM YY format', () => {
    const result = parseMonthString('Oct 20');
    assertNotNull(result, 'Should parse successfully');
    assertEquals(result, { year: 2020, month: 10 }, 'Should parse correctly');
});

test('parseMonthString - various month names', () => {
    assertEquals(parseMonthString('Jan 20'), { year: 2020, month: 1 }, 'January');
    assertEquals(parseMonthString('Dec 25'), { year: 2025, month: 12 }, 'December');
    assertEquals(parseMonthString('Mar 22'), { year: 2022, month: 3 }, 'March');
});

test('parseMonthString - invalid format returns null', () => {
    assertEquals(parseMonthString('invalid'), null, 'Invalid string');
    assertEquals(parseMonthString(''), null, 'Empty string');
    assertEquals(parseMonthString(null), null, 'Null input');
});

test('findFirstNonZeroIndex - finds first non-zero', () => {
    const data = [0, 0, 0, 5, 10, 15];
    assertEquals(findFirstNonZeroIndex(data), 3, 'Should find index 3');
});

test('findFirstNonZeroIndex - all zeros returns 0', () => {
    const data = [0, 0, 0, 0];
    assertEquals(findFirstNonZeroIndex(data), 0, 'Should return 0');
});

test('findFirstNonZeroIndex - no zeros returns 0', () => {
    const data = [1, 2, 3, 4];
    assertEquals(findFirstNonZeroIndex(data), 0, 'Should return 0');
});

test('calculatePoints - basic line chart points', () => {
    const data = [0, 50, 100];
    const padding = { left: 10, top: 10 };
    const chartWidth = 100;
    const chartHeight = 100;
    const maxValue = 100;

    const points = calculatePoints(data, padding, chartWidth, chartHeight, maxValue);

    assertEquals(points.length, 3, 'Should have 3 points');
    assertEquals(points[0], { x: 10, y: 110 }, 'First point (0 value)');
    assertEquals(points[1], { x: 60, y: 60 }, 'Second point (50 value)');
    assertEquals(points[2], { x: 110, y: 10 }, 'Third point (100 value)');
});

test('aggregateMonthlyToYearly - basic aggregation', () => {
    const monthlyData = [100, 200, 300, 150, 250, 350];
    const monthlyLabels = ['Jan 20', 'Feb 20', 'Mar 20', 'Jan 21', 'Feb 21', 'Mar 21'];

    const result = aggregateMonthlyToYearly(monthlyData, monthlyLabels);

    assertEquals(result.years, ['2020', '2021'], 'Should have 2 years');
    assertEquals(result.data, [600, 750], 'Should sum correctly');
});

test('aggregateMonthlyToYearly - handles YYYY-MM format', () => {
    const monthlyData = [100, 200, 300];
    const monthlyLabels = ['2020-01', '2020-02', '2021-01'];

    const result = aggregateMonthlyToYearly(monthlyData, monthlyLabels);

    assertEquals(result.years, ['2020', '2021'], 'Should parse YYYY-MM format');
    assertEquals(result.data, [300, 300], 'Should sum correctly');
});

test('aggregateMonthlyToYearly - handles mixed formats', () => {
    const monthlyData = [100, 200, 300];
    const monthlyLabels = ['2020-01', 'Feb 20', 'Jan 21'];

    const result = aggregateMonthlyToYearly(monthlyData, monthlyLabels);

    assertEquals(result.years, ['2020', '2021'], 'Should handle mixed formats');
    assertEquals(result.data, [300, 300], 'Should sum correctly');
});

test('aggregateMonthlyToYearly - ignores invalid labels', () => {
    const monthlyData = [100, 200, 300, 400];
    const monthlyLabels = ['Jan 20', 'invalid', 'Feb 20', 'Jan 21'];

    const result = aggregateMonthlyToYearly(monthlyData, monthlyLabels);

    assertEquals(result.years, ['2020', '2021'], 'Should skip invalid labels');
    assertEquals(result.data, [400, 400], 'Should sum only valid entries');
});

test('aggregateMonthlyToYearly - sorts years', () => {
    const monthlyData = [100, 200, 300];
    const monthlyLabels = ['Jan 21', 'Jan 20', 'Jan 22'];

    const result = aggregateMonthlyToYearly(monthlyData, monthlyLabels);

    assertEquals(result.years, ['2020', '2021', '2022'], 'Should sort years');
    assertEquals(result.data, [200, 100, 300], 'Should map data to sorted years');
});

console.log('\n✅ All tests completed!\n');

/**
 * Additional tests for chart utility functions
 * Tests for edge cases and error handling
 */

// Load the functions from refactored chart_math module
const {
    parseMonthString,
    findFirstNonZeroIndex,
    calculatePoints,
    aggregateMonthlyToYearly
} = require('./charts/chart_math.js');

// Test framework
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

console.log('\n📊 Additional Chart Utils Tests\n');

// Edge case tests
test('parseMonthString - handles all month names', () => {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    months.forEach((month, idx) => {
        const result = parseMonthString(`${month} 20`);
        assertEquals(result.month, idx + 1, `Should parse ${month} correctly`);
    });
});

test('parseMonthString - handles single digit months', () => {
    const result = parseMonthString('2020-1');
    assertEquals(result, { year: 2020, month: 1 }, 'Should parse single digit month');
});

test('findFirstNonZeroIndex - handles negative numbers', () => {
    const data = [0, 0, -5, 10];
    assertEquals(findFirstNonZeroIndex(data), 3, 'Negative is zero in this context, finds first positive');
});

test('findFirstNonZeroIndex - empty array', () => {
    const data = [];
    assertEquals(findFirstNonZeroIndex(data), 0, 'Should return 0 for empty array');
});

test('calculatePoints - handles single point', () => {
    const data = [50];
    const padding = { left: 10, top: 10 };
    const points = calculatePoints(data, padding, 100, 100, 100);
    assertEquals(points.length, 1, 'Should handle single point');
});

test('calculatePoints - handles max value', () => {
    const data = [100, 100, 100];
    const padding = { left: 10, top: 10 };
    const points = calculatePoints(data, padding, 100, 100, 100);
    points.forEach(point => {
        assertEquals(point.y, 10, 'Max value should be at top');
    });
});

test('aggregateMonthlyToYearly - empty arrays', () => {
    const result = aggregateMonthlyToYearly([], []);
    assertEquals(result, { years: [], data: [] }, 'Should handle empty input');
});

test('aggregateMonthlyToYearly - single year multiple months', () => {
    const monthlyData = [10, 20, 30, 40];
    const monthlyLabels = ['Jan 20', 'Feb 20', 'Mar 20', 'Apr 20'];
    const result = aggregateMonthlyToYearly(monthlyData, monthlyLabels);
    assertEquals(result, { years: ['2020'], data: [100] }, 'Should aggregate to single year');
});

test('aggregateMonthlyToYearly - handles December to January transition', () => {
    const monthlyData = [100, 200];
    const monthlyLabels = ['2020-12', '2021-01'];
    const result = aggregateMonthlyToYearly(monthlyData, monthlyLabels);
    assertEquals(result.years, ['2020', '2021'], 'Should handle year transition');
    assertEquals(result.data, [100, 200], 'Should separate years correctly');
});

test('aggregateMonthlyToYearly - ignores undefined/null values', () => {
    const monthlyData = [100, undefined, null, 200];
    const monthlyLabels = ['Jan 20', 'Feb 20', 'Mar 20', 'Apr 20'];
    const result = aggregateMonthlyToYearly(monthlyData, monthlyLabels);
    // Should only sum defined values
    assertEquals(result.data, [300], 'Should skip undefined/null values');
});

console.log('\n✅ All additional tests completed!\n');

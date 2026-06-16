/**
 * Tests for chart_math.js functions
 * @module tests/test_chart_math
 */

// Test parseMonthString
function testParseMonthString() {
    const tests = [
        { input: '2024-01', expected: { year: 2024, month: 1 }, desc: 'YYYY-MM format' },
        { input: '2024-12', expected: { year: 2024, month: 12 }, desc: 'YYYY-MM December' },
        { input: '01/17', expected: { year: 2017, month: 1 }, desc: 'MM/YY format' },
        { input: '12/25', expected: { year: 2025, month: 12 }, desc: 'MM/YY December 2025' },
        { input: 'Jan 20', expected: { year: 2020, month: 1 }, desc: 'Mon YY format' },
        { input: 'Dec 24', expected: { year: 2024, month: 12 }, desc: 'Mon YY December' },
        { input: '', expected: null, desc: 'Empty string' },
        { input: null, expected: null, desc: 'Null input' },
        { input: 'invalid', expected: null, desc: 'Invalid format' }
    ];

    const results = tests.map(test => {
        const result = parseMonthString(test.input);
        const passed = JSON.stringify(result) === JSON.stringify(test.expected);
        return {
            test: test.desc,
            input: test.input,
            expected: test.expected,
            actual: result,
            passed
        };
    });

    const passedCount = results.filter(r => r.passed).length;
    console.log(`parseMonthString: ${passedCount}/${tests.length} tests passed`);
    results.forEach(r => {
        if (!r.passed) {
            console.error(`❌ ${r.test}:`, r);
        } else {
            console.log(`✅ ${r.test}`);
        }
    });

    return results;
}

// Test aggregateMonthlyToYearly
function testAggregateMonthlyToYearly() {
    const tests = [
        {
            desc: 'Simple monthly to yearly aggregation',
            monthlyData: [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100], // 12 months
            monthlyLabels: ['01/20', '02/20', '03/20', '04/20', '05/20', '06/20', '07/20', '08/20', '09/20', '10/20', '11/20', '12/20'],
            expected: { years: ['2020'], data: [1200] }
        },
        {
            desc: 'Multiple years aggregation',
            monthlyData: [10, 10, 10, 10], // 4 months across 2 years
            monthlyLabels: ['11/23', '12/23', '01/24', '02/24'],
            expected: { years: ['2023', '2024'], data: [20, 20] }
        },
        {
            desc: 'Empty data',
            monthlyData: [],
            monthlyLabels: [],
            expected: { years: [], data: [] }
        },
        {
            desc: 'MM/YY format',
            monthlyData: [119.67, 119.67, 119.67],
            monthlyLabels: ['01/17', '02/17', '03/17'],
            expected: { years: ['2017'], data: [359.01] }
        },
        {
            desc: 'YYYY-MM format',
            monthlyData: [50, 50, 50],
            monthlyLabels: ['2024-01', '2024-02', '2024-03'],
            expected: { years: ['2024'], data: [150] }
        }
    ];

    const results = tests.map(test => {
        const result = aggregateMonthlyToYearly(test.monthlyData, test.monthlyLabels);

        // Compare with tolerance for floating point
        const yearsMatch = JSON.stringify(result.years) === JSON.stringify(test.expected.years);
        const dataMatch = result.data.every((val, i) =>
            Math.abs(val - test.expected.data[i]) < 0.01
        ) && result.data.length === test.expected.data.length;

        const passed = yearsMatch && dataMatch;

        return {
            test: test.desc,
            expected: test.expected,
            actual: result,
            passed
        };
    });

    const passedCount = results.filter(r => r.passed).length;
    console.log(`aggregateMonthlyToYearly: ${passedCount}/${tests.length} tests passed`);
    results.forEach(r => {
        if (!r.passed) {
            console.error(`❌ ${r.test}:`, r);
        } else {
            console.log(`✅ ${r.test}`);
        }
    });

    return results;
}

// Test calculateYearLabels
function testCalculateYearLabels() {
    const tests = [
        {
            desc: 'Single year (12 months)',
            dataLength: 12,
            startYear: 2024,
            monthsPerYear: 12,
            expected: [{ year: 2024, index: 0 }]
        },
        {
            desc: 'Two years (24 months)',
            dataLength: 24,
            startYear: 2023,
            monthsPerYear: 12,
            expected: [
                { year: 2023, index: 0 },
                { year: 2024, index: 12 }
            ]
        },
        {
            desc: 'Partial year (6 months)',
            dataLength: 6,
            startYear: 2024,
            monthsPerYear: 12,
            expected: [{ year: 2024, index: 0 }]
        }
    ];

    const results = tests.map(test => {
        const result = calculateYearLabels(test.dataLength, test.startYear, test.monthsPerYear);
        const passed = JSON.stringify(result) === JSON.stringify(test.expected);
        return {
            test: test.desc,
            expected: test.expected,
            actual: result,
            passed
        };
    });

    const passedCount = results.filter(r => r.passed).length;
    console.log(`calculateYearLabels: ${passedCount}/${tests.length} tests passed`);
    results.forEach(r => {
        if (!r.passed) {
            console.error(`❌ ${r.test}:`, r);
        } else {
            console.log(`✅ ${r.test}`);
        }
    });

    return results;
}

// Export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        testParseMonthString,
        testAggregateMonthlyToYearly,
        testCalculateYearLabels
    };
}

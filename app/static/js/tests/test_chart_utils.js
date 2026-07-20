/**
 * Tests for chart_utils.js functions
 * Run these tests in browser console or with a test framework like Jest
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

// Test formatNumber
function testFormatNumber() {
    const tests = [
        { input: 1234.56, expected: '1.234,56', desc: 'Normal number' },
        { input: 1000000, expected: '1.000.000,00', desc: 'Million' },
        { input: 0, expected: '0,00', desc: 'Zero' },
        { input: -500.5, expected: '-500,50', desc: 'Negative number' },
        { input: 99.9, expected: '99,90', desc: 'Two decimals' }
    ];

    const results = tests.map(test => {
        const result = formatNumber(test.input);
        const passed = result === test.expected;
        return {
            test: test.desc,
            input: test.input,
            expected: test.expected,
            actual: result,
            passed
        };
    });

    const passedCount = results.filter(r => r.passed).length;
    console.log(`formatNumber: ${passedCount}/${tests.length} tests passed`);
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

// Test validateChartData
function testValidateChartData() {
    const tests = [
        {
            desc: 'Valid data',
            data: [100, 200, 300],
            options: {},
            expected: { valid: true, maxValue: 300 }
        },
        {
            desc: 'Empty array',
            data: [],
            options: {},
            expected: { valid: false, reason: 'empty' }
        },
        {
            desc: 'Null data',
            data: null,
            options: {},
            expected: { valid: false, reason: 'empty' }
        },
        {
            desc: 'All zeros with checkNonZero',
            data: [0, 0, 0],
            options: { checkNonZero: true },
            expected: { valid: false, reason: 'all_zeros' }
        },
        {
            desc: 'All zeros without checkNonZero',
            data: [0, 0, 0],
            options: {},
            expected: { valid: false, reason: 'invalid_max' }
        },
        {
            desc: 'Mixed with zeros',
            data: [0, 100, 0, 200],
            options: {},
            expected: { valid: true, maxValue: 200 }
        },
        {
            desc: 'Negative values',
            data: [-100, 200, -50],
            options: {},
            expected: { valid: true, maxValue: 200 }
        }
    ];

    const results = tests.map(test => {
        const result = validateChartData(test.data, test.options);

        let passed = result.valid === test.expected.valid && result.reason === test.expected.reason;
        if (test.expected.maxValue !== undefined) {
            passed = passed && Math.abs(result.maxValue - test.expected.maxValue) < 0.01;
        }

        return {
            test: test.desc,
            expected: test.expected,
            actual: result,
            passed
        };
    });

    const passedCount = results.filter(r => r.passed).length;
    console.log(`validateChartData: ${passedCount}/${tests.length} tests passed`);
    results.forEach(r => {
        if (!r.passed) {
            console.error(`❌ ${r.test}:`, r);
        } else {
            console.log(`✅ ${r.test}`);
        }
    });

    return results;
}

// Test getValidationMessage
function testGetValidationMessage() {
    const tests = [
        { input: 'empty', expected: 'No data available', desc: 'Empty reason' },
        { input: 'all_zeros', expected: 'No data in selected period', desc: 'All zeros reason' },
        { input: 'invalid_max', expected: 'No valid data available', desc: 'Invalid max reason' },
        { input: 'unknown', expected: 'No data available', desc: 'Unknown reason defaults' }
    ];

    const results = tests.map(test => {
        const result = getValidationMessage(test.input);
        const passed = result === test.expected;
        return {
            test: test.desc,
            input: test.input,
            expected: test.expected,
            actual: result,
            passed
        };
    });

    const passedCount = results.filter(r => r.passed).length;
    console.log(`getValidationMessage: ${passedCount}/${tests.length} tests passed`);
    results.forEach(r => {
        if (!r.passed) {
            console.error(`❌ ${r.test}:`, r);
        } else {
            console.log(`✅ ${r.test}`);
        }
    });

    return results;
}

// Run all tests
function runAllChartTests() {
    console.log('=== Running Chart Utils Tests ===\n');

    const results = {
        parseMonthString: testParseMonthString(),
        aggregateMonthlyToYearly: testAggregateMonthlyToYearly(),
        formatNumber: testFormatNumber(),
        calculateYearLabels: testCalculateYearLabels(),
        validateChartData: testValidateChartData(),
        getValidationMessage: testGetValidationMessage()
    };

    // Summary
    let totalTests = 0;
    let totalPassed = 0;

    Object.entries(results).forEach(([name, testResults]) => {
        const passed = testResults.filter(r => r.passed).length;
        totalTests += testResults.length;
        totalPassed += passed;
    });

    console.log(`\n=== Test Summary ===`);
    console.log(`Total: ${totalPassed}/${totalTests} tests passed`);

    if (totalPassed === totalTests) {
        console.log('✅ All tests passed!');
    } else {
        console.error(`❌ ${totalTests - totalPassed} tests failed`);
    }

    return results;
}

// Auto-run if loaded in browser
if (typeof window !== 'undefined') {
    console.log('Chart utils tests loaded. Run runAllChartTests() to execute.');
}

// Export for Node.js if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        testParseMonthString,
        testAggregateMonthlyToYearly,
        testFormatNumber,
        testCalculateYearLabels,
        testValidateChartData,
        testGetValidationMessage,
        runAllChartTests
    };
}

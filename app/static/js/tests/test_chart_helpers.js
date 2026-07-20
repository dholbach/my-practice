/**
 * Tests for chart_helpers.js functions
 * @module tests/test_chart_helpers
 */

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

// Export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        testValidateChartData,
        testGetValidationMessage
    };
}

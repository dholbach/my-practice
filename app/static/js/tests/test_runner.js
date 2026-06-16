/**
 * Test runner for all chart tests
 * @module tests/test_runner
 */

// Test formatNumber (utility function - if exists)
function testFormatNumber() {
    // Check if formatNumber exists
    if (typeof formatNumber === 'undefined') {
        console.log('formatNumber: function not found, skipping tests');
        return [];
    }

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

// Run all tests
function runAllChartTests() {
    console.log('=== Running All Chart Tests ===\n');

    // Run utility tests
    console.log('--- Chart Math & Helpers Tests ---');
    const utilResults = {
        parseMonthString: testParseMonthString(),
        aggregateMonthlyToYearly: testAggregateMonthlyToYearly(),
        formatNumber: testFormatNumber(),
        calculateYearLabels: testCalculateYearLabels(),
        validateChartData: testValidateChartData(),
        getValidationMessage: testGetValidationMessage()
    };

    // Run Phase 2b tests (if functions exist)
    console.log('\n--- Phase 2b Infrastructure Tests ---');

    if (typeof runChartConfigTests === 'function') {
        runChartConfigTests();
    } else {
        console.log('⚠️  ChartConfig tests not loaded (test_chart_config.js)');
    }

    if (typeof runChartTooltipTests === 'function') {
        runChartTooltipTests();
    } else {
        console.log('⚠️  ChartTooltip tests not loaded (test_chart_tooltip.js)');
    }

    if (typeof runChartBuilderTests === 'function') {
        runChartBuilderTests();
    } else {
        console.log('⚠️  ChartBuilder tests not loaded (test_chart_builder.js)');
    }

    // Summary for utility tests
    let totalTests = 0;
    let totalPassed = 0;

    Object.entries(utilResults).forEach(([name, testResults]) => {
        const passed = testResults.filter(r => r.passed).length;
        totalTests += testResults.length;
        totalPassed += passed;
    });

    console.log(`\n=== Test Summary ===`);
    console.log(`Utility Tests: ${totalPassed}/${totalTests} passed`);
    console.log('Infrastructure Tests: See output above');

    if (totalPassed === totalTests) {
        console.log('✅ All utility tests passed!');
    } else {
        console.error(`❌ ${totalTests - totalPassed} utility tests failed`);
    }

    return utilResults;
}

// Auto-run if loaded in browser
if (typeof window !== 'undefined') {
    console.log('Chart utils tests loaded. Run runAllChartTests() to execute.');
}

// Export for Node.js if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        testFormatNumber,
        runAllChartTests
    };
}

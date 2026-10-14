/**
 * Tests for the pure helpers in charts.js (the Chart.js wiring itself needs a
 * browser; it is checked by rendering the analytics page).
 * Run with: node charts.test.js
 */

const { parseMonth, firstNonZero, ema, monthTick, yearStarts, formatNumber } = require("./charts.js");

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
let failures = 0;
function test(name, fn) {
    try {
        fn();
        console.log(`✓ ${name}`);
    } catch (err) {
        failures += 1;
        console.log(`✗ ${name}\n  ${err.message}`);
    }
}
function eq(actual, expected, label) {
    const a = JSON.stringify(actual);
    const e = JSON.stringify(expected);
    if (a !== e) throw new Error(`${label}: expected ${e}, got ${a}`);
}

test("parseMonth reads MM/YY, YYYY-MM and 'Mon YY'", () => {
    eq(parseMonth("01/25"), { year: 2025, month: 1 }, "MM/YY");
    eq(parseMonth("2024-11"), { year: 2024, month: 11 }, "YYYY-MM");
    eq(parseMonth("Oct 20"), { year: 2020, month: 10 }, "Mon YY");
    eq(parseMonth("Q1"), null, "unknown");
    eq(parseMonth(""), null, "empty");
});

test("firstNonZero skips an empty lead-in", () => {
    eq(firstNonZero([0, 0, 3, 0, 5]), 2, "index");
    eq(firstNonZero([0, 0]), 0, "all zero");
});

test("ema starts at the first value and smooths towards later ones", () => {
    eq(ema([], 12), [], "empty");
    const out = ema([10, 20], 3); // alpha 0.5
    eq(out, [10, 15], "values");
});

test("month axis marks every January with its year, and the first tick", () => {
    const labels = ["11/24", "12/24", "01/25", "02/25"];
    eq(monthTick(labels, 0, MONTHS), ["Nov", "2024"], "first");
    eq(monthTick(labels, 1, MONTHS), "Dec", "plain month");
    eq(monthTick(labels, 2, MONTHS), ["Jan", "2025"], "january");
    eq(yearStarts(labels), [2], "separator before January");
});

test("long month axes thin out to quarters but keep every January", () => {
    const labels = [];
    for (let i = 0; i < 24; i++) {
        const month = (i % 12) + 1;
        labels.push(`${String(month).padStart(2, "0")}/${24 + Math.floor(i / 12)}`);
    }
    eq(monthTick(labels, 1, MONTHS), "", "February hidden");
    eq(monthTick(labels, 3, MONTHS), "Apr", "April shown");
    eq(monthTick(labels, 12, MONTHS), ["Jan", "2025"], "January shown");
    eq(yearStarts(labels), [12], "one separator");
});

test("labels that are not months pass through unchanged", () => {
    eq(monthTick(["2024", "2025"], 1, MONTHS), "2025", "year label");
    eq(yearStarts(["2024", "2025"]), [], "no separators");
});

test("formatNumber follows the language and drops trailing zeros", () => {
    eq(formatNumber(32435, 0, "de"), "32.435", "de grouping");
    eq(formatNumber(32435, 0, "en"), "32,435", "en grouping");
    eq(formatNumber(2.5, 1, "de"), "2,5", "de decimal");
    eq(formatNumber(3, 1, "de"), "3", "no trailing zero");
});

if (failures) {
    console.log(`\n${failures} test(s) failed`);
    process.exit(1);
}
console.log("\nAll charts tests passed");

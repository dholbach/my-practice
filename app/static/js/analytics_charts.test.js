/**
 * Tests for analytics_charts.js — the analytics page chart option builders.
 * Run with: node analytics_charts.test.js
 *
 * MPChart and the DOM are stubs; the real source is loaded via `vm`. Pinned: the
 * empty-state fallbacks, which series each chart hands to MPChart, and the
 * tooltip texts, which are built from the data-* labels.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "analytics_charts.js"), "utf8");

let failures = 0;
function check(name, condition) {
    if (condition) {
        console.log(`  ok   ${name}`);
    } else {
        failures += 1;
        console.log(`  FAIL ${name}`);
    }
}

const LABELS = {
    noData: "No data", revenue: "Revenue", expenses: "Expenses", withdrawals: "Withdrawals",
    trend: "Trend", utilisation: "Utilisation", booked: "Booked", capacity: "Capacity",
    avg: "Avg", days: "days", invoices: "Invoices", cancellationRate: "Cancellation rate",
    cancelled: "Cancelled",
};
for (let i = 0; i < 12; i++) LABELS["month" + i] = "M" + i;

function load(data) {
    const calls = [];
    const registered = {};
    const MPChart = {
        init: (id, build) => { registered[id] = build; },
        empty: (canvas, message) => calls.push({ kind: "empty", message }),
        line: (canvas, options) => calls.push({ kind: "line", options }),
        bar: (canvas, options) => calls.push({ kind: "bar", options }),
        firstNonZero: (values) => Math.max(0, values.findIndex((v) => v > 0)),
    };
    const document = {
        getElementById: (id) => {
            if (id === "analytics-labels") return { dataset: LABELS };
            const name = id.replace(/-data$/, "");
            return name in data ? { textContent: JSON.stringify(data[name]) } : null;
        },
    };
    vm.runInNewContext(SOURCE, { window: { MPChart }, document, String, Math, JSON, Array, Object });
    return { calls, build: (id) => registered[id]({}) };
}

console.log("analytics_charts.js");

(function () {
    const page = load({ comparison: [] });
    page.build("comparisonChart");
    page.build("expenseTrendsChart");
    check("empty comparison rows show the no-data message", page.calls.every((c) => c.kind === "empty" && c.message === "No data"));
})();

(function () {
    const page = load({ comparison: [{ year: "2025", revenue: 10, expenses: 4, withdrawals: 2 }] });
    page.build("comparisonChart");
    const series = page.calls[0].options.series;
    check("comparison bars: revenue, expenses, withdrawals", series.map((s) => s.label).join() === "Revenue,Expenses,Withdrawals" && series[1].data[0] === 4);
    page.build("expenseTrendsChart");
    check("expense chart reuses the comparison rows", page.calls[1].options.series[0].data[0] === 4);
})();

(function () {
    const page = load({ "revenue-trend": [{ month: "01/25", revenue: 0 }, { month: "02/25", revenue: 5 }] });
    page.build("revenueLineChart");
    const options = page.calls[0].options;
    check("revenue line drops the empty lead-in", options.labels.join() === "02/25" && options.series[0].data.join() === "5");
    check("revenue line gets the month names", options.monthNames.length === 12 && options.monthNames[0] === "M0");
})();

(function () {
    const page = load({ "capacity-trend": [{ month: "01/25", percentage: 50, booked_hours: 20, capacity_hours: 40 }] });
    page.build("capacityTrendsChart");
    const options = page.calls[0].options;
    check("capacity tooltip lists utilisation, booked and capacity", options.tooltipLabel({ datasetIndex: 0, dataIndex: 0, parsed: { y: 50 } }).join("|") === "Utilisation: 50 %|Booked: 20 h|Capacity: 40 h");
    check("capacity tooltip skips the trend line", options.tooltipLabel({ datasetIndex: 1, dataIndex: 0, parsed: { y: 50 } }) === null);
})();

(function () {
    const page = load({ "days-to-payment": [{ month: "01/25", avg_days: 100, count: 3 }] });
    page.build("daysToPaymentChart");
    const options = page.calls[0].options;
    check("days to payment scales the axis to the data", options.max === 130);
    check("days to payment tooltip", options.tooltipLabel({ dataIndex: 0, parsed: { y: 100 } }).join("|") === "Ø 100 days|3 Invoices");
})();

(function () {
    const page = load({ "cancellation-trends": [{ month: "01/25", rate: 5, cancelled: 1, total: 20 }] });
    page.build("cancellationTrendsChart");
    const options = page.calls[0].options;
    check("cancellation axis has a floor of 20", options.max === 20);
    check("cancellation tooltip", options.tooltipLabel({ dataIndex: 0, parsed: { y: 5 } }).join("|") === "Cancellation rate: 5 %|Cancelled: 1 / 20");
})();

(function () {
    const page = load({ "cumulative-year": { years: [2024, 2025], datasets: { 2024: [1], 2025: [2] }, average: [1.5] } });
    page.build("cumulativeYearsChart");
    const series = page.calls[0].options.series;
    check("cumulative years: oldest thinnest, newest thickest", series[0].width === 1.5 && series[1].width === 3);
    check("cumulative years end with a dashed average", series[2].label === "Avg" && series[2].dashed === true);
    const none = load({ "cumulative-year": { years: [] } });
    none.build("cumulativeYearsChart");
    check("no years show the no-data message", none.calls[0].kind === "empty");
})();

process.exit(failures ? 1 : 0);

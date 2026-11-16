/**
 * Tests for inquiry_chart.js — the inquiries-per-month chart.
 * Run with: node inquiry_chart.test.js
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "inquiry_chart.js"), "utf8");

let failures = 0;
function check(name, condition) {
    if (condition) {
        console.log(`  ok   ${name}`);
    } else {
        failures += 1;
        console.log(`  FAIL ${name}`);
    }
}

const data = { labels: ["01/25"], lanes: [{ from: 0 }], counts: [3] };
let registered = null;
let options = null;
const MPChart = { init: (id, build) => (registered = { id, build }), bar: (canvas, o) => (options = o) };
vm.runInNewContext(SOURCE, {
    window: { MPChart },
    document: { getElementById: () => ({ textContent: JSON.stringify(data) }) },
    JSON,
});
registered.build({ dataset: { monthNames: "Jan,Feb,Mar", seriesLabel: "Inquiries" } });

console.log("inquiry_chart.js");
check("registers on the inquiryMonthlyChart canvas", registered.id === "inquiryMonthlyChart");
check("month names are split from the data attribute", options.monthNames.join() === "Jan,Feb,Mar");
check("series carries the label, counts and lanes", options.series[0].label === "Inquiries" && options.series[0].data[0] === 3 && JSON.stringify(options.lanes) === JSON.stringify(data.lanes));
process.exit(failures ? 1 : 0);

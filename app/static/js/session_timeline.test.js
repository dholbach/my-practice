/**
 * Tests for session_timeline.js — the client detail session hours chart.
 * Run with: node session_timeline.test.js
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "session_timeline.js"), "utf8");

let failures = 0;
function check(name, condition) {
    if (condition) {
        console.log(`  ok   ${name}`);
    } else {
        failures += 1;
        console.log(`  FAIL ${name}`);
    }
}

const rows = [{ month: "01/25", hours: 4.5 }, { month: "02/25", hours: 6 }];
let registered = null;
let options = null;
const MPChart = { init: (id, build) => (registered = { id, build }), bar: (canvas, o) => (options = o) };
vm.runInNewContext(SOURCE, {
    window: { MPChart },
    document: { getElementById: () => ({ textContent: JSON.stringify(rows) }) },
    JSON,
});
registered.build({});

console.log("session_timeline.js");
check("registers on the sessionTimeline canvas", registered.id === "sessionTimeline");
check("months are the labels, hours the series", options.labels.join() === "01/25,02/25" && options.series[0].data.join() === "4.5,6");
check("hours are shown with one decimal", options.suffix === " h" && options.decimals === 1);
process.exit(failures ? 1 : 0);

/**
 * Client detail, billing tab: monthly session hours as a bar chart.
 * Rows come from the JSON block #session-timeline-data ([{month, hours}]).
 */

(function (root) {
    "use strict";

    function build(canvas) {
        const rows = JSON.parse(document.getElementById("session-timeline-data").textContent);
        root.MPChart.bar(canvas, {
            labels: rows.map((row) => row.month),
            suffix: " h",
            decimals: 1,
            series: [{ data: rows.map((row) => row.hours), color: "chart2" }],
        });
    }

    root.MPChart.init("sessionTimeline", build);
    root.SessionTimeline = { build };
})(typeof window !== "undefined" ? window : globalThis);

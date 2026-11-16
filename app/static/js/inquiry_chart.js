/**
 * Inquiry list: inquiries per month as a bar chart.
 * Rows come from #inquiry-monthly-data ({labels, lanes, counts}); the month
 * names and the series label from data-* attributes on the canvas.
 */

(function (root) {
    "use strict";

    function build(canvas) {
        const data = JSON.parse(document.getElementById("inquiry-monthly-data").textContent);
        root.MPChart.bar(canvas, {
            labels: data.labels,
            monthNames: canvas.dataset.monthNames.split(","),
            lanes: data.lanes,
            series: [{ label: canvas.dataset.seriesLabel, data: data.counts, color: "chart1" }],
        });
    }

    root.MPChart.init("inquiryMonthlyChart", build);
})(typeof window !== "undefined" ? window : globalThis);

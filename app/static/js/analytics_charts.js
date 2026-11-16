/**
 * Analytics page charts. Each chart reads its rows from a JSON <script> block
 * (id "<name>-data") and its texts from data-* attributes on #analytics-labels, so
 * every string stays in the template where the i18n coverage guardrail scans it.
 * Rendering is MPChart (charts.js); this file only maps the rows to chart options.
 *
 * Month names come from data-month-0 … data-month-11.
 */

(function (root) {
    "use strict";

    const YEAR_COLORS = {
        2020: "#374151", 2021: "#64748b", 2022: "#14b8a6",
        2023: "#8b5cf6", 2024: "#0ea5e9", 2025: "#22c55e", 2026: "#f59e0b",
    };

    function labels() {
        return document.getElementById("analytics-labels").dataset;
    }

    function monthNames() {
        const text = labels();
        return Array.from({ length: 12 }, (_, i) => text["month" + i]);
    }

    function rows(name) {
        const el = document.getElementById(name + "-data");
        return el ? JSON.parse(el.textContent) : null;
    }

    function noData(canvas) {
        return root.MPChart.empty(canvas, labels().noData);
    }

    const BUILDERS = {
        comparisonChart(canvas) {
            const items = rows("comparison");
            if (!items.length) return noData(canvas);
            const text = labels();
            root.MPChart.bar(canvas, {
                labels: items.map((d) => d.year),
                suffix: " €",
                series: [
                    { label: text.revenue, data: items.map((d) => d.revenue), color: "chart2" },
                    { label: text.expenses, data: items.map((d) => d.expenses), color: "chart6" },
                    { label: text.withdrawals, data: items.map((d) => d.withdrawals), color: "chart7" },
                ],
            });
        },

        revenueLineChart(canvas) {
            const items = rows("revenue-trend");
            const values = items.map((d) => d.revenue);
            if (!values.some((v) => v > 0)) return noData(canvas);
            const start = root.MPChart.firstNonZero(values);
            root.MPChart.line(canvas, {
                labels: items.map((d) => d.month).slice(start),
                monthNames: monthNames(),
                suffix: " €",
                trend: labels().trend,
                series: [{ label: labels().revenue, data: values.slice(start), color: "chart1", fill: true }],
            });
        },

        daysToPaymentChart(canvas) {
            const raw = rows("days-to-payment");
            if (!raw || raw.length === 0) return noData(canvas);
            const text = labels();
            const days = raw.map((d) => d.avg_days);
            root.MPChart.line(canvas, {
                labels: raw.map((d) => d.month),
                monthNames: monthNames(),
                suffix: " d",
                max: Math.max(60, Math.ceil(Math.max(...days) * 1.3)),
                series: [{ data: days, color: "chart8" }],
                tooltipLabel: (ctx) => [
                    "Ø " + ctx.parsed.y + " " + text.days,
                    raw[ctx.dataIndex].count + " " + text.invoices,
                ],
            });
        },

        capacityTrendsChart(canvas) {
            const items = rows("capacity-trend");
            const values = items.map((d) => d.percentage);
            if (!values.some((v) => v > 0)) return noData(canvas);
            const text = labels();
            const start = root.MPChart.firstNonZero(values);
            const booked = items.map((d) => d.booked_hours).slice(start);
            const capacity = items.map((d) => d.capacity_hours).slice(start);
            root.MPChart.line(canvas, {
                labels: items.map((d) => d.month).slice(start),
                monthNames: monthNames(),
                suffix: " %",
                max: 120,
                trend: text.trend,
                series: [{ label: text.utilisation, data: values.slice(start), color: "chart1", fill: true }],
                tooltipLabel: (ctx) =>
                    ctx.datasetIndex > 0
                        ? null
                        : [
                              text.utilisation + ": " + ctx.parsed.y + " %",
                              text.booked + ": " + booked[ctx.dataIndex] + " h",
                              text.capacity + ": " + capacity[ctx.dataIndex] + " h",
                          ],
            });
        },

        cumulativeYearsChart(canvas) {
            const cyd = rows("cumulative-year");
            if (!cyd || !cyd.years || cyd.years.length === 0) return noData(canvas);
            const n = cyd.years.length;
            // Oldest year thinnest, newest on top and thickest.
            const series = cyd.years.map((y, i) => ({
                label: String(y),
                data: cyd.datasets[String(y)],
                color: YEAR_COLORS[y] || "#888888",
                width: 1.5 + (i / Math.max(n - 1, 1)) * 1.5,
            }));
            if (cyd.average) {
                series.push({ label: labels().avg, data: cyd.average, color: "text", dashed: true, width: 2 });
            }
            root.MPChart.line(canvas, {
                labels: monthNames(),
                suffix: " h",
                points: false,
                legend: true,
                series: series,
            });
        },

        cancellationTrendsChart(canvas) {
            const raw = rows("cancellation-trends");
            if (!raw || raw.length === 0) return noData(canvas);
            const text = labels();
            const rates = raw.map((d) => d.rate);
            root.MPChart.line(canvas, {
                labels: raw.map((d) => d.month),
                monthNames: monthNames(),
                suffix: " %",
                max: Math.max(20, Math.ceil(Math.max(...rates) * 1.3)),
                series: [{ data: rates, color: "chart6" }],
                tooltipLabel: (ctx) => [
                    text.cancellationRate + ": " + ctx.parsed.y + " %",
                    text.cancelled + ": " + raw[ctx.dataIndex].cancelled + " / " + raw[ctx.dataIndex].total,
                ],
            });
        },

        expenseTrendsChart(canvas) {
            // Yearly totals from the comparison rows (same source as the profit
            // table), so the current year shows actual expenses, not a partial sum.
            const items = rows("comparison");
            const values = items.map((d) => d.expenses);
            if (!values.some((v) => v > 0)) return noData(canvas);
            root.MPChart.bar(canvas, {
                labels: items.map((d) => d.year),
                suffix: " €",
                series: [{ label: labels().expenses, data: values, color: "chart6" }],
            });
        },
    };

    Object.keys(BUILDERS).forEach(function (canvasId) {
        root.MPChart.init(canvasId, BUILDERS[canvasId]);
    });

    root.AnalyticsCharts = { BUILDERS };
})(typeof window !== "undefined" ? window : globalThis);

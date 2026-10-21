/* Chart.js with the app's theme, and the few chart shapes it draws.
 *
 *   MPChart.init("canvasId", function (canvas) {
 *       return MPChart.line(canvas, { labels, series: [{ label, data }], suffix: " €" });
 *   });
 *
 * Colours come from the CSS tokens (--color-text-secondary, --color-border,
 * --color-chart-N) and are read again on the "themeChanged" event, so a chart
 * follows the dark-mode toggle. Chart.js watches its container's size, so a
 * chart in a hidden tab sizes itself when the tab is shown — no redraw call.
 *
 * Labels in "MM/YY" form ("01/25") get a month axis: every January is marked
 * with its year and a dashed separator, other months thin out to quarters.
 *
 * A bar chart's `lanes` ([{label, from, to}], positions in bar slots — slot i
 * spans i - 0.5 … i + 0.5) are drawn as labelled strips above the bars, one
 * row each so overlapping periods stay readable, with a dashed line wherever
 * a lane starts or ends inside the axis.
 */
(function (root) {
    "use strict";

    // ── pure helpers (unit-tested in charts.test.js) ─────────────────────────

    /** {year, month} from "MM/YY", "YYYY-MM" or "Oct 20"; null otherwise. */
    function parseMonth(label) {
        if (!label) return null;
        let m = /^(\d{4})-(\d{1,2})$/.exec(label);
        if (m) return { year: +m[1], month: +m[2] };
        m = /^(\d{1,2})\/(\d{2})$/.exec(label);
        if (m) return { year: 2000 + +m[2], month: +m[1] };
        const names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        m = /^([A-Za-z]{3})\s+(\d{2})$/.exec(label);
        if (m && names.indexOf(m[1]) !== -1) return { year: 2000 + +m[2], month: names.indexOf(m[1]) + 1 };
        return null;
    }

    /** Index of the first value above zero (0 if none), to skip an empty lead-in. */
    function firstNonZero(values) {
        for (let i = 0; i < values.length; i++) if (values[i] > 0) return i;
        return 0;
    }

    /** Exponential moving average, the dashed trend under the revenue line. */
    function ema(values, span) {
        if (!values.length) return [];
        const alpha = 2 / ((span || 12) + 1);
        const out = [values[0]];
        for (let i = 1; i < values.length; i++) out[i] = alpha * values[i] + (1 - alpha) * out[i - 1];
        return out;
    }

    /** Month-axis tick text for label i: [month, year] on January (and the first tick). */
    function monthTick(labels, i, monthNames) {
        const p = parseMonth(labels[i]);
        if (!p) return labels[i];
        if (p.month === 1 || i === 0) return [monthNames[p.month - 1], String(p.year)];
        return labels.length > 18 && (p.month - 1) % 3 !== 0 ? "" : monthNames[p.month - 1];
    }

    /** Indices where a new year starts (a separator is drawn before each). */
    function yearStarts(labels) {
        const starts = [];
        labels.forEach(function (label, i) {
            const p = parseMonth(label);
            if (i > 0 && p && p.month === 1) starts.push(i);
        });
        return starts;
    }

    /** value in the page language; up to `decimals` places, trailing zeros dropped. */
    function formatNumber(value, decimals, lang) {
        lang = lang || (root.document && root.document.documentElement.lang) || "de";
        return Number(value).toLocaleString(lang, { maximumFractionDigits: decimals || 0 });
    }

    const helpers = { parseMonth, firstNonZero, ema, monthTick, yearStarts, formatNumber };
    if (typeof module !== "undefined" && module.exports) {
        module.exports = helpers;
        return;
    }

    // ── browser: theme + Chart.js setup ──────────────────────────────────────

    const theme = {};
    function readTheme() {
        const css = getComputedStyle(document.documentElement);
        const token = function (name) {
            return css.getPropertyValue(name).trim();
        };
        theme.text = token("--color-text-secondary");
        theme.grid = token("--color-border");
        theme.surface = token("--color-surface");
        for (let n = 1; n <= 8; n++) theme["chart" + n] = token("--color-chart-" + n);
    }
    const charts = [];
    root.addEventListener("themeChanged", function () {
        // The new data-theme attribute is set before the event fires.
        readTheme();
        charts.forEach(function (chart) {
            chart.update("none");
        });
    });

    Chart.defaults.maintainAspectRatio = false;
    Chart.defaults.animation = false;
    Chart.defaults.plugins.tooltip.padding = 10;

    const LANE_HEIGHT = 18;
    const LANE_COLOURS = ["chart3", "chart2", "chart5", "chart6"];

    // Labelled strips above the plot area, e.g. marketing periods on a month axis.
    const lanes = {
        id: "lanes",
        beforeDatasetsDraw: function (chart, _args, opts) {
            if (!opts.items || !opts.items.length) return;
            const x = chart.scales.x;
            const area = chart.chartArea;
            const n = chart.data.labels.length;
            const step = n > 1 ? x.getPixelForValue(1) - x.getPixelForValue(0) : area.right - area.left;
            const px = function (slot) {
                return x.getPixelForValue(0) + slot * step;
            };
            const ctx = chart.ctx;
            ctx.save();
            ctx.font = "11px " + Chart.defaults.font.family;
            ctx.textBaseline = "middle";
            opts.items.forEach(function (lane, row) {
                const token = LANE_COLOURS[row % LANE_COLOURS.length];
                const left = px(lane.from);
                const right = px(lane.to);
                const top = area.top - (opts.items.length - row) * LANE_HEIGHT - 4;
                ctx.fillStyle = fade(token, 0.3)();
                ctx.fillRect(left, top, right - left, LANE_HEIGHT - 3);
                ctx.save();
                ctx.beginPath();
                ctx.rect(left, top, right - left, LANE_HEIGHT - 3);
                ctx.clip();
                ctx.fillStyle = theme.text;
                ctx.fillText(lane.label, left + 4, top + (LANE_HEIGHT - 3) / 2);
                ctx.restore();

                ctx.strokeStyle = colour(token)();
                ctx.setLineDash([3, 3]);
                [lane.from, lane.to].forEach(function (slot) {
                    if (slot <= -0.5 || slot >= n - 0.5) return;
                    ctx.beginPath();
                    ctx.moveTo(px(slot), top + LANE_HEIGHT - 3);
                    ctx.lineTo(px(slot), area.bottom);
                    ctx.stroke();
                });
                ctx.setLineDash([]);
            });
            ctx.restore();
        },
    };

    // Dashed line before each January on a month axis.
    const yearSeparators = {
        id: "yearSeparators",
        beforeDatasetsDraw: function (chart, _args, opts) {
            if (!opts.starts || !opts.starts.length) return;
            const x = chart.scales.x;
            const area = chart.chartArea;
            const ctx = chart.ctx;
            ctx.save();
            ctx.strokeStyle = theme.grid;
            ctx.setLineDash([4, 4]);
            opts.starts.forEach(function (i) {
                const px = (x.getPixelForValue(i - 1) + x.getPixelForValue(i)) / 2;
                ctx.beginPath();
                ctx.moveTo(px, area.top);
                ctx.lineTo(px, area.bottom);
                ctx.stroke();
            });
            ctx.restore();
        },
    };

    function scales(opts) {
        const suffix = opts.suffix || "";
        const x = {
            grid: { display: false },
            ticks: {
                color: function () {
                    return theme.text;
                },
                maxRotation: 0,
            },
        };
        if (opts.monthNames) {
            x.ticks.autoSkip = false;
            x.ticks.callback = function (_value, i) {
                return monthTick(opts.labels, i, opts.monthNames);
            };
        }
        return {
            x: x,
            y: {
                beginAtZero: true,
                suggestedMax: opts.max,
                grid: {
                    color: function () {
                        return theme.grid;
                    },
                },
                border: { display: false },
                ticks: {
                    color: function () {
                        return theme.text;
                    },
                    // One decimal so 0.5-steps on a small axis do not repeat.
                    callback: function (value) {
                        return formatNumber(value, 1) + suffix;
                    },
                },
            },
        };
    }

    function colour(name) {
        return function () {
            return theme[name] || name;
        };
    }

    /** A token colour (#rrggbb) at the given opacity, for area fills. */
    function fade(name, opacity) {
        return function () {
            const hex = theme[name] || name;
            const m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex);
            if (!m) return hex;
            const rgb = [m[1], m[2], m[3]].map(function (h) {
                return parseInt(h, 16);
            });
            return "rgba(" + rgb.join(", ") + ", " + opacity + ")";
        };
    }

    function tooltip(opts) {
        const suffix = opts.suffix || "";
        return {
            callbacks: {
                title: function (items) {
                    const label = items.length ? items[0].label : "";
                    const p = opts.monthNames && parseMonth(label);
                    return p ? opts.monthNames[p.month - 1] + " " + p.year : label;
                },
                label:
                    opts.tooltipLabel ||
                    function (ctx) {
                        const value = formatNumber(ctx.parsed.y, opts.decimals) + suffix;
                        return ctx.dataset.label ? ctx.dataset.label + ": " + value : value;
                    },
            },
        };
    }

    function make(canvas, config) {
        const chart = new Chart(canvas, config);
        charts.push(chart);
        return chart;
    }

    function empty(canvas, message) {
        const note = document.createElement("p");
        note.className = "chart-empty";
        note.textContent = message;
        canvas.replaceWith(note);
        return null;
    }

    /**
     * Line chart. series: [{label, data, color, fill, dashed, width}], colours
     * by token name ("chart1") or any CSS colour; fill: shade the area under
     * the line. trend: a label; adds a dashed moving average of the first series.
     */
    function line(canvas, opts) {
        const series = opts.series.map(function (s, i) {
            return {
                label: s.label,
                data: s.data,
                borderColor: colour(s.color || "chart1"),
                backgroundColor: s.fill ? fade(s.color || "chart1", 0.15) : "transparent",
                fill: Boolean(s.fill),
                borderDash: s.dashed ? [6, 4] : [],
                borderWidth: s.width || 2.5,
                pointRadius: opts.points === false ? 0 : 3,
                pointHoverRadius: 5,
                spanGaps: false,
                tension: 0.25,
                order: i,
            };
        });
        if (opts.trend && opts.series[0].data.length > 2) {
            series.push({
                label: opts.trend,
                data: ema(opts.series[0].data, 12),
                borderColor: colour("chart4"),
                borderDash: [8, 5],
                borderWidth: 2,
                pointRadius: 0,
                pointHoverRadius: 0,
                fill: false,
                tension: 0.3,
            });
        }
        return make(canvas, {
            type: "line",
            data: { labels: opts.labels, datasets: series },
            options: {
                interaction: { mode: "index", intersect: false },
                scales: scales(opts),
                plugins: {
                    legend: {
                        display: Boolean(opts.legend),
                        labels: { color: colour("text"), usePointStyle: true, pointStyle: "line" },
                    },
                    tooltip: tooltip(opts),
                    yearSeparators: { starts: opts.monthNames ? yearStarts(opts.labels) : [] },
                },
            },
            plugins: [yearSeparators],
        });
    }

    /** Bar chart; several series give grouped bars with a legend. lanes: see the header. */
    function bar(canvas, opts) {
        const datasets = opts.series.map(function (s) {
            return {
                label: s.label,
                data: s.data,
                backgroundColor: colour(s.color || "chart1"),
                borderRadius: 4,
                maxBarThickness: 80,
            };
        });
        const laneItems = opts.lanes || [];
        return make(canvas, {
            type: "bar",
            data: { labels: opts.labels, datasets: datasets },
            options: {
                interaction: { mode: "index", intersect: false },
                layout: { padding: { top: laneItems.length ? laneItems.length * LANE_HEIGHT + 6 : 0 } },
                scales: scales(opts),
                plugins: {
                    lanes: { items: laneItems },
                    legend: {
                        display: datasets.length > 1,
                        position: "top",
                        align: "start",
                        labels: { color: colour("text"), boxWidth: 12 },
                    },
                    tooltip: tooltip(opts),
                },
            },
            plugins: [lanes],
        });
    }

    /** Run build(canvas) once the page is ready; keeps the chart for theme updates. */
    function init(canvasId, build) {
        document.addEventListener("DOMContentLoaded", function () {
            // Read here, not at load: this file runs in <head>, before <body>
            // has its font and before the theme attribute is final.
            readTheme();
            Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
            const canvas = document.getElementById(canvasId);
            if (canvas) build(canvas);
        });
    }

    root.MPChart = Object.assign({ init, line, bar, empty }, helpers);
})(typeof window !== "undefined" ? window : globalThis);

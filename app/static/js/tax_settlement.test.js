/**
 * Tests for tax_settlement.js — the Alpine component behind the tax assessment
 * card on the quarter overview. Run with: node tax_settlement.test.js
 *
 * The script registers its component on "alpine:init". The test provides a fake
 * Alpine that records the factory, builds the component the way Alpine does
 * (an object whose $el is the element carrying x-data) and drives its methods
 * (plain `node <file>`, see dev.py cmd_test_js).
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "tax_settlement.js"), "utf8");

let failures = 0;
function check(name, condition) {
    if (condition) {
        console.log(`  ok   ${name}`);
    } else {
        failures += 1;
        console.log(`  FAIL ${name}`);
    }
}

function component({ fetchImpl, dataset = {} } = {}) {
    const listeners = {};
    const registered = {};
    const calls = [];
    const sandbox = {
        document: {
            body: { dataset: { csrfToken: "tok123" } },
            addEventListener: (type, fn) => (listeners[type] = fn),
        },
        Alpine: { data: (name, factory) => (registered[name] = factory) },
        fetch: (url, options) => {
            calls.push({ url, options });
            return fetchImpl();
        },
        FormData,
        window: { location: { reload: () => (sandbox.reloaded = true) } },
    };
    vm.createContext(sandbox);
    vm.runInContext(SOURCE, sandbox);
    listeners["alpine:init"]();
    const instance = registered.taxSettlement();
    instance.$el = {
        dataset: { year: "2025", saveUrl: "/tax/settlement/", amount: "123.45", settlementDate: "2026-03-01", saveFailed: "Save failed.", networkError: "Network error.", ...dataset },
    };
    instance.init();
    return { instance, calls, sandbox };
}

(async () => {
    console.log("tax_settlement.js");

    {
        const { instance } = component();
        check("init takes the stored amount and date from the element", instance.amount === "123.45" && instance.settlementDate === "2026-03-01");
        instance.startEdit();
        check("startEdit opens the form", instance.editing === true);
        instance.error = "x";
        instance.cancel();
        check("cancel closes it and clears the error", instance.editing === false && instance.error === "");
    }
    {
        const { instance, calls, sandbox } = component({ fetchImpl: () => Promise.resolve({ json: () => Promise.resolve({ saved: true }) }) });
        await instance.save();
        const body = calls[0].options.body;
        check("save posts to the element's URL", calls[0].url === "/tax/settlement/" && calls[0].options.method === "POST");
        check("it sends year, amount, date and token", body.get("year") === "2025" && body.get("settlement_amount") === "123.45" && body.get("settlement_date") === "2026-03-01" && body.get("csrfmiddlewaretoken") === "tok123");
        check("a saved settlement reloads the page", sandbox.reloaded === true);
        check("saving is over afterwards", instance.saving === false);
    }
    {
        const { instance } = component({ fetchImpl: () => Promise.resolve({ json: () => Promise.resolve({ saved: false, error: "Amount invalid" }) }) });
        await instance.save();
        check("the server's error message is shown", instance.error === "Amount invalid");
    }
    {
        const { instance } = component({ fetchImpl: () => Promise.resolve({ json: () => Promise.resolve({ saved: false }) }) });
        await instance.save();
        check("without one the generic message is shown", instance.error === "Save failed.");
    }
    {
        const { instance } = component({ fetchImpl: () => Promise.reject(new Error("offline")) });
        await instance.save();
        check("a network failure shows the network error and ends saving", instance.error === "Network error." && instance.saving === false);
    }
    {
        const { instance, calls } = component({ fetchImpl: () => Promise.resolve({ json: () => Promise.resolve({ saved: true }) }) });
        await instance.clear();
        const body = calls[0].options.body;
        check("clear empties both fields and saves", instance.amount === "" && body.get("settlement_amount") === "" && body.get("settlement_date") === "");
    }

    if (failures > 0) {
        console.log(`\n${failures} check(s) failed`);
        process.exit(1);
    }
    console.log("\nAll checks passed");
})();

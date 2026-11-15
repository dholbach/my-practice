/**
 * Tests for inquiry_convert_confirm.js — client-code suggestions when an inquiry
 * is converted to a client. Run with: node inquiry_convert_confirm.test.js
 *
 * A throwaway DOM stub, a stand-in MPCodeSuggestions that records its calls and
 * fake timers, with the real source loaded via `vm` (plain `node <file>`).
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "inquiry_convert_confirm.js"), "utf8");

let failures = 0;
function check(name, condition) {
    if (condition) {
        console.log(`  ok   ${name}`);
    } else {
        failures += 1;
        console.log(`  FAIL ${name}`);
    }
}

class FakeNode {
    constructor() {
        this.value = "";
        this.dataset = {};
        this._listeners = {};
        this.children = [1];
    }
    addEventListener(type, fn) {
        this._listeners[type] = fn;
    }
    replaceChildren() {
        this.children = [];
    }
}

function load({ inquiryName = "Max Mustermann" } = {}) {
    const ids = {
        "inquiry-convert-js": Object.assign(new FakeNode(), {
            dataset: { suggestUrl: "/suggest/", inquiryName, label: "Suggestions:", pickTitle: "Click to use" },
        }),
        id_client_code: new FakeNode(),
        "convert-code-suggestions": new FakeNode(),
    };
    const timers = [];
    const loads = [];
    const renders = [];
    const sandbox = {
        document: { getElementById: (id) => ids[id] || null },
        setTimeout: (fn, ms) => timers.push({ fn, ms }) && timers.length,
        clearTimeout: (n) => {
            if (n) timers[n - 1].cancelled = true;
        },
        MPCodeSuggestions: {
            load: (url, name) => {
                loads.push({ url, name });
                return Promise.resolve(["AB-1", "AB-2"]);
            },
            render: (strip, options) => renders.push(options),
        },
    };
    vm.createContext(sandbox);
    vm.runInContext(SOURCE, sandbox);
    return { ids, timers, loads, renders };
}

const flush = async () => {
    await Promise.resolve();
    await Promise.resolve();
};

(async () => {
    console.log("inquiry_convert_confirm.js");

    {
        const { loads, renders } = load();
        await flush();
        check("suggestions for the inquiry name load on page load", loads[0].url === "/suggest/" && loads[0].name === "Max Mustermann");
        check("they render with the label and tooltip", renders[0].label === "Suggestions:" && renders[0].pickTitle === "Click to use" && renders[0].codes.length === 2);
    }
    {
        const { ids, renders } = load();
        await flush();
        renders[0].onPick("AB-2");
        check("picking a chip fills the code field", ids.id_client_code.value === "AB-2");
        check("and clears the strip", renders[1].codes.length === 0);
    }
    {
        const { loads } = load({ inquiryName: "" });
        check("no inquiry name: nothing is requested", loads.length === 0);
    }
    {
        const { ids, timers, loads } = load();
        await flush();
        ids.id_client_code.value = "AB-1";
        ids.id_client_code._listeners.input.call(ids.id_client_code);
        check("typing a code clears the strip", ids["convert-code-suggestions"].children.length === 0 && timers.length === 0);
        ids.id_client_code.value = "";
        ids.id_client_code._listeners.input.call(ids.id_client_code);
        check("clearing the code waits 200 ms", timers.length === 1 && timers[0].ms === 200);
        timers[0].fn();
        check("then asks again for the inquiry name", loads.length === 2 && loads[1].name === "Max Mustermann");
    }

    if (failures > 0) {
        console.log(`\n${failures} check(s) failed`);
        process.exit(1);
    }
    console.log("\nAll checks passed");
})();

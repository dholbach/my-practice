/**
 * Shared stand-ins for the browser objects the *.test.js suites drive.
 *
 * Not a test itself (the runner globs *.test.js), and not jsdom: the suites run
 * as plain `node <file>` with no devDependencies. Each suite still keeps its own
 * FakeNode, because what a node has to do differs per script under test; only
 * the pieces that were identical in spirit live here, as a superset.
 */

class FakeEvent {
    constructor(type, options = {}) {
        this.type = type;
        this.key = options.key ?? "";
        this.detail = options.detail;
        this.bubbles = Boolean(options.bubbles);
        this.ctrlKey = Boolean(options.ctrlKey);
        this.altKey = Boolean(options.altKey);
        this.metaKey = Boolean(options.metaKey);
        this.target = options.target || null;
        this.relatedTarget = options.relatedTarget || null;
        this.dataTransfer = options.dataTransfer || null;
        this.defaultPrevented = false;
    }

    preventDefault() {
        this.defaultPrevented = true;
    }
}

class FakeClassList {
    constructor() {
        this._set = new Set();
    }

    add(name) {
        this._set.add(name);
    }

    remove(name) {
        this._set.delete(name);
    }

    contains(name) {
        return this._set.has(name);
    }

    /** Returns the resulting state, as DOMTokenList.toggle does. */
    toggle(name) {
        if (this._set.has(name)) {
            this._set.delete(name);
            return false;
        }
        this._set.add(name);
        return true;
    }
}

module.exports = { FakeEvent, FakeClassList };

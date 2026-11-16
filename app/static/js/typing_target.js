/**
 * MPTyping.isTyping(target): true when a keystroke aimed at target belongs to a
 * text field, so single-key shortcuts (the "/" palette key, the n/e/? keys) must
 * stay out of the way. Covers input, textarea, select and contenteditable
 * elements, including anything nested inside a contenteditable parent.
 *
 * Loaded before command_palette.js and keyboard-nav.js (see base.html).
 */

(function (root) {
    "use strict";

    function isEditable(node) {
        return Boolean(node.isContentEditable) || node.contentEditable === "true";
    }

    function isTyping(target) {
        if (!target || !target.tagName) return false;
        const tag = target.tagName.toLowerCase();
        if (tag === "input" || tag === "textarea" || tag === "select") return true;
        for (let node = target; node; node = node.parentElement) {
            if (isEditable(node)) return true;
        }
        return false;
    }

    root.MPTyping = { isTyping };
})(typeof window !== "undefined" ? window : globalThis);

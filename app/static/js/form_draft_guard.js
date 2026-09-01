/* Draft autosave + unsaved-changes guard, opt-in per form via data-draft-guard.
 * Protects against accidental navigation (e.g. Alt+Left/Right, closed tab)
 * wiping out in-progress text before it's submitted.
 *
 * Usage: add to any <form> —
 *   <form data-draft-guard
 *         data-draft-message="..."
 *         data-draft-restore-label="..."
 *         data-draft-discard-label="...">
 * A stable `id` on the form keeps drafts scoped correctly if a page ever
 * has more than one guarded form. */
(function () {
    "use strict";

    const SKIP_TYPES = new Set(["hidden", "submit", "button", "reset", "file"]);
    const dirtyForms = new Set();

    function markDirty(form) {
        if (dirtyForms.has(form)) return;
        dirtyForms.add(form);
        form.dispatchEvent(new CustomEvent("draftguard:dirty", { bubbles: true, detail: { dirty: true } }));
    }

    function markClean(form) {
        if (!dirtyForms.has(form)) return;
        dirtyForms.delete(form);
        form.dispatchEvent(new CustomEvent("draftguard:dirty", { bubbles: true, detail: { dirty: false } }));
    }

    function isTracked(el) {
        return el.name && el.name !== "csrfmiddlewaretoken" && !SKIP_TYPES.has((el.type || "").toLowerCase());
    }

    function collectFields(form) {
        const data = {};
        const groups = {};
        for (const el of form.elements) {
            if (!isTracked(el)) continue;
            const type = (el.type || "").toLowerCase();
            if (type === "checkbox" || type === "radio") {
                if (!groups[el.name]) groups[el.name] = [];
                if (el.checked) groups[el.name].push(el.value);
            } else {
                data[el.name] = el.value;
            }
        }
        Object.assign(data, groups);
        return data;
    }

    function applyFields(form, fields) {
        const groupChecks = {};
        for (const el of form.elements) {
            if (!isTracked(el)) continue;
            const type = (el.type || "").toLowerCase();
            if (type === "checkbox" || type === "radio") {
                if (!groupChecks[el.name]) groupChecks[el.name] = new Set(fields[el.name] || []);
                el.checked = groupChecks[el.name].has(el.value);
            } else if (fields[el.name] !== undefined) {
                el.value = fields[el.name];
            }
        }
    }

    // Normalizes a collected field value for comparison: arrays (checkbox/radio
    // groups) become an order-independent signature, scalars are trimmed. An
    // empty array and "no value" both normalize to "" so undefined/missing
    // keys compare equal to fields that exist but hold nothing.
    function normalizeValue(value) {
        if (value === undefined || value === null) return "";
        if (Array.isArray(value)) {
            const sorted = value.map(String).sort();
            return sorted.length ? JSON.stringify(sorted) : "";
        }
        return String(value).trim();
    }

    // Compares two collectFields() snapshots, ignoring differences that don't
    // amount to a real edit (whitespace-only, or unchecked-vs-absent groups).
    function fieldsEqual(a, b) {
        const keys = new Set([...Object.keys(a || {}), ...Object.keys(b || {})]);
        for (const key of keys) {
            if (normalizeValue(a[key]) !== normalizeValue(b[key])) return false;
        }
        return true;
    }

    function draftKeyFor(form) {
        return "form_draft:" + window.location.pathname + window.location.search + "#" + (form.id || "form");
    }

    function saveDraft(form, key) {
        try {
            localStorage.setItem(key, JSON.stringify({ fields: collectFields(form) }));
        } catch (e) {
            /* localStorage unavailable (private mode, quota) — autosave is best-effort */
        }
    }

    function clearDraft(key) {
        try {
            localStorage.removeItem(key);
        } catch (e) {
            /* ignore */
        }
    }

    function showRestoreBanner(form, draft, key) {
        const banner = document.createElement("div");
        banner.className = "draft-restore-banner";
        banner.innerHTML =
            "<span>" + form.dataset.draftMessage + "</span>" +
            '<button type="button" class="draft-restore-banner__restore" data-action="restore">' +
            form.dataset.draftRestoreLabel +
            "</button>" +
            '<button type="button" class="draft-restore-banner__dismiss" data-action="discard">' +
            form.dataset.draftDiscardLabel +
            "</button>";
        form.parentNode.insertBefore(banner, form);

        banner.querySelector('[data-action="restore"]').addEventListener("click", function () {
            applyFields(form, draft.fields);
            markDirty(form);
            banner.remove();
        });
        banner.querySelector('[data-action="discard"]').addEventListener("click", function () {
            clearDraft(key);
            banner.remove();
        });
    }

    function initForm(form) {
        const key = draftKeyFor(form);
        // Snapshot fields as rendered (including any non-blank server-side
        // default, e.g. a boilerplate notes template) so "unsaved draft" means
        // "differs from what's already on the page", not just "non-blank".
        const baseline = collectFields(form);

        try {
            const raw = localStorage.getItem(key);
            if (raw) {
                const draft = JSON.parse(raw);
                if (draft && draft.fields && !fieldsEqual(draft.fields, baseline)) {
                    showRestoreBanner(form, draft, key);
                } else {
                    clearDraft(key);
                }
            }
        } catch (e) {
            clearDraft(key);
        }

        let saveTimer = null;
        function handleEdit(debounce) {
            if (fieldsEqual(collectFields(form), baseline)) {
                clearTimeout(saveTimer);
                markClean(form);
                clearDraft(key);
                return;
            }
            markDirty(form);
            if (debounce) {
                clearTimeout(saveTimer);
                saveTimer = setTimeout(function () {
                    saveDraft(form, key);
                }, 500);
            } else {
                clearTimeout(saveTimer);
                saveDraft(form, key);
            }
        }
        form.addEventListener("input", function () {
            handleEdit(true);
        });
        form.addEventListener("change", function () {
            handleEdit(false);
        });

        form.addEventListener("submit", function () {
            markClean(form);
            clearDraft(key);
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("form[data-draft-guard]").forEach(initForm);
    });

    window.addEventListener("beforeunload", function (e) {
        if (dirtyForms.size > 0) {
            e.preventDefault();
            e.returnValue = "";
        }
    });
})();

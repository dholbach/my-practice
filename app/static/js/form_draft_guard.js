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

    function fieldsHaveContent(fields) {
        return Object.values(fields).some((value) =>
            Array.isArray(value) ? value.length > 0 : String(value || "").trim() !== ""
        );
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
            dirtyForms.add(form);
            banner.remove();
        });
        banner.querySelector('[data-action="discard"]').addEventListener("click", function () {
            clearDraft(key);
            banner.remove();
        });
    }

    function initForm(form) {
        const key = draftKeyFor(form);

        try {
            const raw = localStorage.getItem(key);
            if (raw) {
                const draft = JSON.parse(raw);
                if (draft && draft.fields && fieldsHaveContent(draft.fields)) {
                    showRestoreBanner(form, draft, key);
                } else {
                    clearDraft(key);
                }
            }
        } catch (e) {
            clearDraft(key);
        }

        let saveTimer = null;
        form.addEventListener("input", function () {
            dirtyForms.add(form);
            clearTimeout(saveTimer);
            saveTimer = setTimeout(function () {
                saveDraft(form, key);
            }, 500);
        });
        form.addEventListener("change", function () {
            dirtyForms.add(form);
            saveDraft(form, key);
        });

        form.addEventListener("submit", function () {
            dirtyForms.delete(form);
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

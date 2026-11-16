/**
 * Client detail sidebar: upload client documents (drag and drop or click) and
 * delete them.
 *
 * The upload URL and the texts come from data-* attributes on #client-documents
 * (see client_detail_documents.html); the CSRF token from <body data-csrf-token>.
 * Date, type and description are pre-filled from a filename such as
 * "2026-01-09-behandlungsvertrag.pdf".
 */

(function () {
    "use strict";

    const section = document.getElementById("client-documents");
    if (!section) return;
    const text = section.dataset;
    const csrfToken = document.body.dataset.csrfToken;

    const dropZone = document.getElementById("docDropZone");
    const fileInput = document.getElementById("docFileInput");
    const uploadForm = document.getElementById("docUploadForm");
    const uploadBtn = document.getElementById("docUploadBtn");
    const cancelBtn = document.getElementById("docCancelBtn");
    const progress = document.getElementById("docProgress");
    const dateInput = document.getElementById("docDate");

    dateInput.value = new Date().toISOString().slice(0, 10);

    let selectedFile = null;

    // German filename keywords matched against uploaded filenames, not UI text.
    const TYPE_KEYWORDS = [
        ["vorgespräch", "intro_notes"],
        ["vorgesprach", "intro_notes"], // without umlaut
        ["aufnahmebogen", "intake"],
        ["intake", "intake"],
        ["anamnesebogen", "anamnese"],
        ["anamnese", "anamnese"],
        ["behandlungsvertrag", "contract"],
        ["vertrag", "contract"],
        ["überweisung", "referral"],
        ["uberweisung", "referral"], // without umlaut
        ["referral", "referral"],
    ];

    function inferFromFilename(name) {
        const stem = name.replace(/\.[^.]+$/, "").toLowerCase();
        const dateMatch = stem.match(/^(\d{4}-\d{2}-\d{2})[-_]?(.*)$/);
        const inferredDate = dateMatch ? dateMatch[1] : null;
        const inferredDesc = dateMatch && dateMatch[2] ? dateMatch[2].replace(/[-_]+/g, " ").trim() : null;
        let inferredType = null;
        for (const [keyword, type] of TYPE_KEYWORDS) {
            if (stem.includes(keyword)) {
                inferredType = type;
                break;
            }
        }
        return { inferredDate, inferredType, inferredDesc };
    }

    function showUploadForm(file) {
        selectedFile = file;
        dropZone.querySelector("p").textContent = file.name;

        const { inferredDate, inferredType, inferredDesc } = inferFromFilename(file.name);
        if (inferredDate) dateInput.value = inferredDate;
        if (inferredType) document.getElementById("docTypeSelect").value = inferredType;
        if (inferredDesc) document.getElementById("docDescription").value = inferredDesc;

        uploadForm.style.display = "block";
    }

    function formatDate(iso) {
        const [y, m, d] = iso.split("-");
        return d + "." + m + "." + y;
    }

    function docDelete(btn) {
        if (!confirm(text.deleteConfirm)) return;
        const docId = btn.dataset.docId;
        fetch("/documents/" + docId + "/delete/", {
            method: "POST",
            headers: { "X-CSRFToken": btn.dataset.csrf, "Content-Type": "application/x-www-form-urlencoded" },
        })
            .then((r) => r.json())
            .then(function (data) {
                if (data.success) {
                    const li = document.getElementById("doc-" + docId);
                    if (li) li.remove();
                }
            })
            .catch(() => alert(text.deleteFailed));
    }

    /* Append the freshly uploaded file to the visible list, mirroring the
       server-rendered <li> (same id and delete button). Built with DOM calls
       rather than innerHTML: description and filename are user-supplied. */
    function appendDocRow(doc) {
        const list = document.querySelector(".sidebar-doc-list");
        const empty = document.getElementById("docEmptyState");
        if (empty) empty.remove();

        const li = document.createElement("li");
        li.id = "doc-" + doc.id;
        li.className = "sidebar-doc-item";

        const badge = document.createElement("span");
        badge.className = "doc-type-badge sidebar-doc-badge";
        badge.textContent = doc.document_type_display;

        const link = document.createElement("a");
        link.className = "sidebar-doc-name";
        link.href = doc.url;
        link.target = "_blank";
        link.title = doc.filename;
        link.textContent = doc.description || doc.filename;

        const date = document.createElement("span");
        date.className = "sidebar-doc-date";
        date.textContent = formatDate(doc.document_date);

        const del = document.createElement("button");
        del.className = "btn btn-danger btn-sm";
        del.textContent = "🗑️";
        del.dataset.docId = doc.id;
        del.dataset.csrf = csrfToken;
        del.addEventListener("click", function () {
            docDelete(del);
        });

        li.append(badge, link, date, del);
        list.appendChild(li);
    }

    dropZone.addEventListener("click", () => fileInput.click());
    dropZone.addEventListener("dragover", function (e) {
        e.preventDefault();
        dropZone.classList.add("dragover");
    });
    dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
    dropZone.addEventListener("drop", function (e) {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        if (e.dataTransfer.files.length) showUploadForm(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener("change", function () {
        if (fileInput.files.length) showUploadForm(fileInput.files[0]);
    });

    cancelBtn.addEventListener("click", function () {
        selectedFile = null;
        fileInput.value = "";
        uploadForm.style.display = "none";
        dropZone.querySelector("p").innerHTML = text.dropHint;
    });

    uploadBtn.addEventListener("click", function () {
        if (!selectedFile) return;
        const formData = new FormData();
        formData.append("file", selectedFile);
        formData.append("document_type", document.getElementById("docTypeSelect").value);
        formData.append("description", document.getElementById("docDescription").value);
        formData.append("document_date", dateInput.value);
        formData.append("csrfmiddlewaretoken", csrfToken);

        uploadBtn.disabled = true;
        progress.classList.add("visible");

        fetch(text.uploadUrl, { method: "POST", body: formData })
            .then((r) => r.json())
            .then(function (data) {
                if (data.error) {
                    alert(data.error);
                    return;
                }
                if (data.onboarding_step_completed) {
                    location.reload();
                    return;
                }
                appendDocRow(data);
                cancelBtn.click();
            })
            .catch(() => alert(text.uploadFailed))
            .finally(function () {
                uploadBtn.disabled = false;
                progress.classList.remove("visible");
            });
    });

    // Server-rendered rows; appendDocRow() wires the ones added after an upload.
    document.querySelectorAll(".sidebar-doc-list button[data-doc-id]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            docDelete(btn);
        });
    });
})();

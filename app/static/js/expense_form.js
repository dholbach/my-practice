/* Drag-and-drop multi-file upload for expense receipt field */

(function () {
    "use strict";

    function markHasInvoice() {
        const checkbox = document.getElementById("id_has_invoice");
        if (checkbox && !checkbox.checked) {
            checkbox.checked = true;
        }
    }

    function showFilelist(filelistEl, files) {
        if (!filelistEl || files.length === 0) return;
        filelistEl.innerHTML = "";
        for (const file of files) {
            const line = document.createElement("div");
            line.textContent = "✓ " + file.name;
            filelistEl.appendChild(line);
        }
        filelistEl.classList.remove("hidden");
    }

    function initDropzone(dropzone) {
        const input = dropzone.querySelector(".receipt-input");
        const filelistEl = dropzone.querySelector("#dropzone-filelist");
        if (!input) return;

        input.addEventListener("change", function () {
            if (input.files.length > 0) {
                showFilelist(filelistEl, input.files);
                markHasInvoice();
            }
        });

        dropzone.addEventListener("dragover", function (e) {
            e.preventDefault();
            dropzone.classList.add("dragover");
        });

        dropzone.addEventListener("dragleave", function () {
            dropzone.classList.remove("dragover");
        });

        dropzone.addEventListener("drop", function (e) {
            e.preventDefault();
            dropzone.classList.remove("dragover");

            if (e.dataTransfer.files.length > 0) {
                // Merge dropped files with already-selected files
                const dt = new DataTransfer();
                for (const f of input.files) dt.items.add(f);
                for (const f of e.dataTransfer.files) dt.items.add(f);
                input.files = dt.files;
                showFilelist(filelistEl, input.files);
                markHasInvoice();
            }
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        const dropzone = document.getElementById("receipt-dropzone");
        if (dropzone) initDropzone(dropzone);
    });
})();

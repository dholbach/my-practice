/**
 * Time-off notice form: the "select all" checkbox over the recipient list.
 * Ticking it ticks every recipient; unticking any recipient unticks it, and
 * ticking the last unticked one ticks it again.
 */

(function () {
    "use strict";

    const selectAll = document.getElementById("recipients-select-all");
    const boxes = Array.from(document.querySelectorAll(".recipient-checkbox"));

    if (selectAll) {
        selectAll.addEventListener("change", function () {
            boxes.forEach((cb) => {
                cb.checked = selectAll.checked;
            });
        });
    }

    boxes.forEach((cb) => {
        cb.addEventListener("change", function () {
            if (selectAll) selectAll.checked = boxes.every((b) => b.checked);
        });
    });
})();

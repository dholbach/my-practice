/**
 * Client tags: add a tag from the dropdown, remove one with its ×.
 *
 * Wired per .tag-container[data-client-id]; the error texts come from
 * data-add-error / data-remove-error on the container so they stay in the
 * template. Both requests go out through MPHttp.postForm (post_json.js), which
 * adds the CSRF token.
 */

(function () {
    "use strict";

    function toggleDropdown(clientId) {
        const dropdown = document.getElementById("tagDropdown" + clientId);
        const content = document.getElementById("tagDropdownContent" + clientId);
        const button = dropdown.querySelector(".tag-add-btn");

        dropdown.classList.toggle("active");
        if (!dropdown.classList.contains("active")) return;

        const rect = button.getBoundingClientRect();
        content.style.top = rect.bottom + 5 + "px";
        content.style.left = rect.left + "px";

        setTimeout(function () {
            document.addEventListener("click", function closeDropdown(e) {
                if (!dropdown.contains(e.target)) {
                    dropdown.classList.remove("active");
                    document.removeEventListener("click", closeDropdown);
                }
            });
        }, 100);
    }

    function addTag(clientId, tagId, container) {
        MPHttp.postForm("/api/clients/" + clientId + "/tags/add/", { tag_id: tagId })
            .then((response) => response.json())
            .then(function (data) {
                if (data.success) {
                    location.reload();
                } else {
                    alert(container.dataset.addError);
                }
            })
            .catch(function (error) {
                console.error("Error:", error);
                alert(container.dataset.addError);
            });
    }

    function removeTag(clientId, tagId, element, container) {
        MPHttp.postForm("/api/clients/" + clientId + "/tags/" + tagId + "/remove/")
            .then((response) => response.json())
            .then(function (data) {
                if (data.success) {
                    element.closest(".tag").remove();
                } else {
                    alert(container.dataset.removeError);
                }
            })
            .catch(function (error) {
                console.error("Error:", error);
                alert(container.dataset.removeError);
            });
    }

    document.querySelectorAll(".tag-container[data-client-id]").forEach(function (container) {
        const clientId = container.dataset.clientId;
        const dropdown = document.getElementById("tagDropdown" + clientId);
        if (!dropdown) return;

        container.querySelectorAll(".tag-remove[data-tag-id]").forEach(function (el) {
            el.addEventListener("click", function () {
                removeTag(clientId, parseInt(el.dataset.tagId), el, container);
            });
        });

        const addButton = dropdown.querySelector(".tag-add-btn");
        if (addButton) {
            addButton.addEventListener("click", function () {
                toggleDropdown(clientId);
            });
        }

        dropdown.querySelectorAll(".tag-dropdown-item[data-tag-id]").forEach(function (item) {
            item.addEventListener("click", function () {
                addTag(clientId, parseInt(item.dataset.tagId), container);
            });
        });
    });
})();

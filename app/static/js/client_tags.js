/**
 * Client tags: add a tag from the dropdown, remove one with its ×.
 *
 * Wired per .tag-container[data-client-id]; the error texts come from
 * data-add-error / data-remove-error on the container so they stay in the
 * template. The CSRF token is read from the csrftoken cookie, falling back to
 * the csrfmiddlewaretoken input of a form on the page.
 */

(function () {
    "use strict";

    function getCookie(name) {
        let value = null;
        if (document.cookie && document.cookie !== "") {
            document.cookie.split(";").forEach(function (part) {
                const cookie = part.trim();
                if (value === null && cookie.substring(0, name.length + 1) === name + "=") {
                    value = decodeURIComponent(cookie.substring(name.length + 1));
                }
            });
        }
        if (!value) {
            const input = document.querySelector("[name=csrfmiddlewaretoken]");
            if (input) value = input.value;
        }
        return value;
    }

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
        fetch("/api/clients/" + clientId + "/tags/add/", {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRFToken": getCookie("csrftoken"),
            },
            body: "tag_id=" + tagId,
        })
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
        fetch("/api/clients/" + clientId + "/tags/" + tagId + "/remove/", {
            method: "POST",
            headers: { "X-CSRFToken": getCookie("csrftoken") },
        })
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

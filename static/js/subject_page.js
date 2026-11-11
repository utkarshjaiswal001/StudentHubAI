// Subject page: save ⭐ notes and tick syllabus topics without reloading the page.
(function () {
    "use strict";

    function post(url, data) {
        return fetch(url, {
            method: "POST",
            body: data,
            credentials: "same-origin",
            headers: { "X-Requested-With": "fetch" }
        }).then(function (response) {
            if (!response.ok) throw new Error("Request failed");
            return response.json();
        });
    }

    // Stars: fall back to the normal form post if anything goes wrong.
    document.querySelectorAll(".subject-save-form").forEach(function (form) {
        form.addEventListener("submit", function (event) {
            event.preventDefault();
            var button = form.querySelector(".subject-star");
            button.disabled = true;
            post(form.action, new FormData(form)).then(function (result) {
                button.classList.toggle("is-saved", result.saved);
                button.setAttribute("aria-pressed", String(result.saved));
                button.title = result.saved ? "Remove from saved notes" : "Save to my notes";
                button.querySelector("[aria-hidden]").textContent = result.saved ? "★" : "☆";
            }).catch(function () { form.submit(); })
              .then(function () { button.disabled = false; });
        });
    });

    var panel = document.querySelector(".subject-syllabus");
    var form = document.querySelector(".subject-progress-form");
    if (!panel || !form) return;
    var code = panel.getAttribute("data-code");
    var total = Number(panel.getAttribute("data-total")) || 0;

    function refreshUnit(unit) {
        var boxes = unit.querySelectorAll("input[data-topic]");
        var done = unit.querySelectorAll("input[data-topic]:checked").length;
        unit.querySelector("[data-unit-count]").textContent = done + "/" + boxes.length;
    }

    function refreshTotal(studied) {
        var percent = total ? Math.round(studied * 100 / total) : 0;
        panel.querySelector("[data-studied]").textContent = studied;
        panel.querySelector("[data-percent]").textContent = percent;
        var bar = panel.querySelector(".subject-progress-bar");
        bar.setAttribute("aria-valuenow", percent);
        bar.querySelector("span").style.width = percent + "%";
    }

    panel.addEventListener("change", function (event) {
        var box = event.target;
        if (!box.matches || !box.matches("input[data-topic]")) return;
        var label = box.closest(".subject-topic");
        label.classList.toggle("is-done", box.checked);
        refreshUnit(box.closest(".subject-unit"));
        var data = new FormData(form);
        data.append("code", code);
        data.append("topic", box.getAttribute("data-topic"));
        data.append("done", box.checked ? "1" : "0");
        post(form.action, data).then(function (result) {
            refreshTotal(result.studied);
        }).catch(function () {
            // Undo the tick so the page never shows something that wasn't saved.
            box.checked = !box.checked;
            label.classList.toggle("is-done", box.checked);
            refreshUnit(box.closest(".subject-unit"));
            alert("Couldn't save that. Please check your connection and try again.");
        });
    });
})();

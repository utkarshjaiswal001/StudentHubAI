// Theme gallery: "Use" buttons apply a theme and mark the one in use.
(function () {
    function mark() {
        var theme = window.StudentHubTheme;
        if (!theme) return;
        document.querySelectorAll(".theme-use-button").forEach(function (button) {
            var active = button.dataset.mode === theme.mode() && button.dataset.palette === theme.palette();
            button.classList.toggle("is-active", active);
            button.setAttribute("aria-pressed", String(active));
            var base = button.textContent.replace(/^✓ In use · |^Use /, "");
            button.textContent = (active ? "✓ In use · " : "Use ") + base;
        });
    }

    document.addEventListener("click", function (event) {
        var button = event.target.closest(".theme-use-button");
        if (!button || !window.StudentHubTheme) return;
        window.StudentHubTheme.apply(button.dataset.mode, button.dataset.palette);
    });
    document.addEventListener("studenthub:theme", mark);
    window.addEventListener("load", mark);
})();

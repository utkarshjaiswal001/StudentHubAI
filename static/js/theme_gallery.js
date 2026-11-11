// Theme gallery: "Use" buttons apply a theme or light background and mark the one in use.
(function () {
    function setLabel(button, active, base) {
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", String(active));
        button.textContent = (active ? "✓ In use · " : "Use ") + base;
    }

    function mark() {
        var theme = window.StudentHubTheme;
        if (!theme) return;
        document.querySelectorAll(".theme-use-button[data-palette]").forEach(function (button) {
            var active = button.dataset.mode === theme.mode() && button.dataset.palette === theme.palette();
            setLabel(button, active, button.textContent.replace(/^✓ In use · |^Use /, ""));
        });
        document.querySelectorAll(".theme-bg-use").forEach(function (button) {
            var active = theme.mode() === "light" && button.dataset.bg === theme.background();
            setLabel(button, active, button.textContent.replace(/^✓ In use · |^Use /, ""));
        });
        document.querySelectorAll(".theme-layout-use").forEach(function (button) {
            setLabel(button, button.dataset.layout === theme.layout(), button.textContent.replace(/^✓ In use · |^Use /, ""));
        });
        // Background previews show the colour set currently in use.
        document.querySelectorAll("[data-follow-palette]").forEach(function (sample) {
            sample.setAttribute("data-palette", theme.palette());
        });
    }

    document.addEventListener("click", function (event) {
        var button = event.target.closest(".theme-use-button");
        if (!button || !window.StudentHubTheme) return;
        if (button.dataset.layout) {
            window.StudentHubTheme.setLayout(button.dataset.layout);
        } else if (button.dataset.bg) {
            window.StudentHubTheme.apply("light", null, button.dataset.bg);
        } else {
            window.StudentHubTheme.apply(button.dataset.mode, button.dataset.palette);
        }
    });
    document.addEventListener("studenthub:theme", mark);
    window.addEventListener("load", mark);
})();

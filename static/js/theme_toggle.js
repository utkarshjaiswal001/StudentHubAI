// Theme menu: a 🎨 button in the top bar to pick Dark/Light and a colour set.
// The choice is saved in this browser (localStorage) and applied before the
// page paints by the small script in templates/_theme_assets.html.
(function () {
    var root = document.documentElement;
    var dataEl = document.getElementById("theme-palettes");
    var palettes = dataEl ? JSON.parse(dataEl.textContent) : [];
    var bgEl = document.getElementById("theme-backgrounds");
    var backgrounds = bgEl ? JSON.parse(bgEl.textContent) : [];

    function mode() {
        return root.getAttribute("data-theme") === "light" ? "light" : "dark";
    }

    function palette() {
        return root.getAttribute("data-palette") || "aurora";
    }

    function background() {
        return root.getAttribute("data-bg") || "auto";
    }

    function apply(newMode, newPalette, newBackground) {
        root.classList.add("theme-switching");
        if (newMode) root.setAttribute("data-theme", newMode);
        if (newPalette) root.setAttribute("data-palette", newPalette);
        if (newBackground) root.setAttribute("data-bg", newBackground);
        try {
            localStorage.setItem("sh-theme", mode());
            localStorage.setItem("sh-palette", palette());
            localStorage.setItem("sh-bg", background());
        } catch (e) { /* private browsing: still works for this page */ }
        setTimeout(function () { root.classList.remove("theme-switching"); }, 400);
        document.dispatchEvent(new CustomEvent("studenthub:theme"));
    }

    window.StudentHubTheme = {
        apply: apply, mode: mode, palette: palette, background: background,
        palettes: palettes, backgrounds: backgrounds
    };

    function el(tag, className, text) {
        var node = document.createElement(tag);
        if (className) node.className = className;
        if (text) node.textContent = text;
        return node;
    }

    function buildMenu() {
        var wrap = el("div", "theme-menu");
        var button = el("button", "theme-toggle", "🎨");
        button.type = "button";
        button.setAttribute("aria-haspopup", "true");
        button.setAttribute("aria-expanded", "false");
        button.setAttribute("aria-label", "Change theme and colours");
        button.title = "Change theme and colours";

        var panel = el("div", "theme-panel");
        panel.hidden = true;
        panel.setAttribute("role", "dialog");
        panel.setAttribute("aria-label", "Theme");

        panel.appendChild(el("p", "theme-panel-label", "Mode"));
        var modes = el("div", "theme-mode-row");
        [["dark", "🌙 Dark"], ["light", "☀️ Light"]].forEach(function (item) {
            var b = el("button", "theme-mode-btn", item[1]);
            b.type = "button";
            b.dataset.mode = item[0];
            b.addEventListener("click", function () { apply(item[0]); });
            modes.appendChild(b);
        });
        panel.appendChild(modes);

        panel.appendChild(el("p", "theme-panel-label", "Colours"));
        var list = el("div", "theme-palette-list");
        palettes.forEach(function (p) {
            var b = el("button", "theme-palette-btn");
            b.type = "button";
            b.dataset.palette = p.id;
            b.title = p.mood;
            var dots = el("span", "theme-dots");
            p.swatches.forEach(function (color) {
                var dot = el("span", "theme-dot");
                dot.style.background = color;
                dots.appendChild(dot);
            });
            b.appendChild(dots);
            b.appendChild(el("span", "theme-palette-name", p.name));
            b.addEventListener("click", function () { apply(null, p.id); });
            list.appendChild(b);
        });
        panel.appendChild(list);

        if (backgrounds.length) {
            panel.appendChild(el("p", "theme-panel-label", "Light background"));
            var tones = el("div", "theme-bg-row");
            backgrounds.forEach(function (bg) {
                var b = el("button", "theme-bg-btn" + (bg.id === "auto" ? " is-auto" : ""));
                b.type = "button";
                b.dataset.bg = bg.id;
                b.title = bg.name + ": " + bg.mood;
                b.setAttribute("aria-label", "Light background: " + bg.name);
                if (bg.color) b.style.background = bg.color;
                b.addEventListener("click", function () { apply("light", null, bg.id); });
                tones.appendChild(b);
            });
            panel.appendChild(tones);
            panel.appendChild(el("p", "theme-bg-name"));
        }

        var more = el("a", "theme-gallery-link", "See all themes with previews →");
        more.href = "/themes";
        panel.appendChild(more);

        function refresh() {
            panel.querySelectorAll(".theme-mode-btn").forEach(function (b) {
                b.setAttribute("aria-pressed", String(b.dataset.mode === mode()));
            });
            panel.querySelectorAll(".theme-palette-btn").forEach(function (b) {
                b.setAttribute("aria-pressed", String(b.dataset.palette === palette()));
            });
            panel.querySelectorAll(".theme-bg-btn").forEach(function (b) {
                b.setAttribute("aria-pressed", String(b.dataset.bg === background()));
            });
            var label = panel.querySelector(".theme-bg-name");
            if (label) {
                var current = backgrounds.filter(function (bg) { return bg.id === background(); })[0];
                label.textContent = mode() === "light"
                    ? (current ? current.name + " · " + current.mood : "")
                    : "Used in light mode.";
            }
        }

        function open(show) {
            panel.hidden = !show;
            button.setAttribute("aria-expanded", String(show));
            if (show) refresh();
        }

        button.addEventListener("click", function (event) {
            event.stopPropagation();
            open(panel.hidden);
        });
        panel.addEventListener("click", function (event) { event.stopPropagation(); });
        document.addEventListener("click", function () { open(false); });
        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape" && !panel.hidden) {
                open(false);
                button.focus();
            }
        });
        document.addEventListener("studenthub:theme", refresh);

        wrap.appendChild(button);
        wrap.appendChild(panel);
        return wrap;
    }

    function placeMenu() {
        var menu = buildMenu();
        var list = document.querySelector(".navbar .nav-links, .navbar .nav-menu");
        if (list && list.tagName === "UL") {
            var item = el("li", "theme-toggle-item");
            item.appendChild(menu);
            list.appendChild(item);
        } else if (list) {
            list.appendChild(menu);
        } else {
            var nav = document.querySelector(".navbar");
            if (nav) nav.appendChild(menu);
        }
    }

    // Friendly greeting on pages that ask for one.
    function greet() {
        var node = document.querySelector("[data-greeting]");
        if (!node) return;
        var hour = new Date().getHours();
        var part = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
        var name = node.getAttribute("data-greeting");
        node.textContent = part + (name ? ", " + name : "") + " 👋";
        node.hidden = false;
    }

    function start() {
        placeMenu();
        greet();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
})();

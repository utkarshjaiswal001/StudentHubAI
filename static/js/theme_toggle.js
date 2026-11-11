// Light/dark switch: adds a 🌙/☀️ button to the top bar and remembers the choice.
(function () {
    var root = document.documentElement;
    var KEY = "sh-theme";

    function current() {
        return root.getAttribute("data-theme") === "light" ? "light" : "dark";
    }

    function label(button) {
        var dark = current() === "dark";
        button.textContent = dark ? "☀️" : "🌙";
        button.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
        button.title = button.getAttribute("aria-label");
    }

    function build() {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "theme-toggle";
        label(button);
        button.addEventListener("click", function () {
            var next = current() === "dark" ? "light" : "dark";
            root.classList.add("theme-switching");
            root.setAttribute("data-theme", next);
            try { localStorage.setItem(KEY, next); } catch (e) { /* private mode */ }
            label(button);
            setTimeout(function () { root.classList.remove("theme-switching"); }, 400);
        });

        var list = document.querySelector(".navbar .nav-links, .navbar .nav-menu");
        if (list && list.tagName === "UL") {
            var item = document.createElement("li");
            item.className = "theme-toggle-item";
            item.appendChild(button);
            list.appendChild(item);
        } else if (list) {
            list.appendChild(button);
        } else {
            var nav = document.querySelector(".navbar");
            if (nav) nav.appendChild(button);
        }
    }

    // Friendly greeting on pages that ask for one.
    function greet() {
        var el = document.querySelector("[data-greeting]");
        if (!el) return;
        var hour = new Date().getHours();
        var part = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
        var name = el.getAttribute("data-greeting");
        el.textContent = part + (name ? ", " + name : "") + " 👋";
        el.hidden = false;
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () { build(); greet(); });
    } else {
        build();
        greet();
    }
})();

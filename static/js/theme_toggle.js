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
        return root.getAttribute("data-palette") || "galaxy";
    }

    function background() {
        return root.getAttribute("data-bg") || "auto";
    }

    function layout() {
        return root.getAttribute("data-layout") === "classic" ? "classic" : "glass";
    }

    function setLayout(value) {
        root.setAttribute("data-layout", value === "classic" ? "classic" : "glass");
        try { localStorage.setItem("sh-layout", layout()); } catch (e) { /* ignore */ }
        document.dispatchEvent(new CustomEvent("studenthub:theme"));
    }

    function fx() {
        return root.getAttribute("data-fx") === "calm" ? "calm" : "shine";
    }

    function setFx(value) {
        root.setAttribute("data-fx", value === "calm" ? "calm" : "shine");
        try { localStorage.setItem("sh-fx", fx()); } catch (e) { /* ignore */ }
        document.dispatchEvent(new CustomEvent("studenthub:theme"));
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
        layout: layout, setLayout: setLayout, fx: fx, setFx: setFx,
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

        panel.appendChild(el("p", "theme-panel-label", "Layout"));
        var layouts = el("div", "theme-mode-row");
        [["classic", "▭ Classic"], ["glass", "✨ Glass"]].forEach(function (item) {
            var b = el("button", "theme-mode-btn theme-layout-btn", item[1]);
            b.type = "button";
            b.dataset.layout = item[0];
            b.addEventListener("click", function () { setLayout(item[0]); });
            layouts.appendChild(b);
        });
        panel.appendChild(layouts);

        panel.appendChild(el("p", "theme-panel-label", "Effects"));
        var effects = el("div", "theme-mode-row");
        [["shine", "✨ Shine"], ["calm", "🍃 Calm"]].forEach(function (item) {
            var b = el("button", "theme-mode-btn theme-fx-btn", item[1]);
            b.type = "button";
            b.dataset.fx = item[0];
            b.title = item[0] === "shine" ? "Glossy edges, sparkles and soft shine" : "No sparkles or moving shine";
            b.addEventListener("click", function () { setFx(item[0]); });
            effects.appendChild(b);
        });
        panel.appendChild(effects);

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
            panel.querySelectorAll(".theme-mode-btn[data-mode]").forEach(function (b) {
                b.setAttribute("aria-pressed", String(b.dataset.mode === mode()));
            });
            panel.querySelectorAll(".theme-layout-btn").forEach(function (b) {
                b.setAttribute("aria-pressed", String(b.dataset.layout === layout()));
            });
            panel.querySelectorAll(".theme-fx-btn").forEach(function (b) {
                b.setAttribute("aria-pressed", String(b.dataset.fx === fx()));
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
            if (show) {
                refresh();
                keepOnScreen();
            }
        }

        // On narrow screens, slide the menu sideways so it never runs off the edge.
        function keepOnScreen() {
            panel.style.transform = "";
            var gap = 10;
            var box = panel.getBoundingClientRect();
            var room = document.documentElement.clientWidth;
            var shift = 0;
            if (box.right > room - gap) shift = (room - gap) - box.right;
            if (box.left + shift < gap) shift = gap - box.left;
            if (shift) panel.style.transform = "translateX(" + Math.round(shift) + "px)";
        }
        window.addEventListener("resize", function () { if (!panel.hidden) keepOnScreen(); });

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

    // Glass layout: small icon rail on the left (CSS shows it only in Glass on big screens).
    function placeRail() {
        var rail = el("nav", "glass-rail");
        rail.setAttribute("aria-label", "Quick links");
        var path = window.location.pathname;
        [["/", "🏠", "Home"], ["/notes", "📚", "Notes"], ["/dashboard", "📊", "Dashboard"],
         ["/chatbot", "🤖", "AI Career Mentor"]].forEach(function (item) {
            var a = el("a", "", item[1]);
            a.href = item[0];
            a.title = item[2];
            a.setAttribute("aria-label", item[2]);
            var here = item[0] === "/" ? path === "/" : path.indexOf(item[0]) === 0;
            if (here) a.setAttribute("aria-current", "page");
            rail.appendChild(a);
        });

        // Bottom of the rail: a small dark/light switch and a colour picker, like the reel.
        rail.appendChild(el("span", "rail-divider"));

        var modeSwitch = el("button", "rail-mode");
        modeSwitch.type = "button";
        modeSwitch.setAttribute("role", "switch");
        modeSwitch.setAttribute("aria-label", "Dark mode");
        modeSwitch.appendChild(el("span", "rail-mode-knob"));
        modeSwitch.addEventListener("click", function () { apply(mode() === "dark" ? "light" : "dark"); });
        rail.appendChild(modeSwitch);

        var pick = el("button", "rail-palette", "🎨");
        pick.type = "button";
        pick.title = "Colours";
        pick.setAttribute("aria-label", "Choose colours");
        pick.setAttribute("aria-haspopup", "true");
        pick.setAttribute("aria-expanded", "false");
        rail.appendChild(pick);

        var pop = el("div", "rail-pop");
        pop.hidden = true;
        pop.setAttribute("role", "dialog");
        pop.setAttribute("aria-label", "Colours");
        pop.appendChild(el("p", "rail-pop-title", "Colours"));
        palettes.forEach(function (p) {
            var b = el("button", "rail-pop-item");
            b.type = "button";
            b.dataset.palette = p.id;
            var dots = el("span", "theme-dots");
            p.swatches.forEach(function (color) {
                var dot = el("span", "theme-dot");
                dot.style.background = color;
                dots.appendChild(dot);
            });
            b.appendChild(dots);
            b.appendChild(el("span", "", p.name));
            b.addEventListener("click", function () { apply(null, p.id); });
            pop.appendChild(b);
        });
        var all = el("a", "rail-pop-more", "All themes →");
        all.href = "/themes";
        pop.appendChild(all);
        rail.appendChild(pop);

        function sync() {
            modeSwitch.setAttribute("aria-checked", String(mode() === "dark"));
            modeSwitch.title = mode() === "dark" ? "Switch to light mode" : "Switch to dark mode";
            pop.querySelectorAll(".rail-pop-item").forEach(function (b) {
                b.setAttribute("aria-pressed", String(b.dataset.palette === palette()));
            });
        }
        function openPop(show) {
            pop.hidden = !show;
            pick.setAttribute("aria-expanded", String(show));
        }
        pick.addEventListener("click", function (event) {
            event.stopPropagation();
            openPop(pop.hidden);
        });
        pop.addEventListener("click", function (event) { event.stopPropagation(); });
        document.addEventListener("click", function () { openPop(false); });
        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape" && !pop.hidden) { openPop(false); pick.focus(); }
        });
        document.addEventListener("studenthub:theme", sync);
        sync();

        document.body.appendChild(rail);
    }

    // Shine effects: sparkles in page headers and a spotlight that follows the mouse.
    function addSparkles() {
        document.querySelectorAll(".hero, .hero-section, .notes-flow-hero").forEach(function (host) {
            if (host.querySelector(".fx-sparkles")) return;
            var layer = el("span", "fx-sparkles");
            layer.setAttribute("aria-hidden", "true");
            for (var i = 0; i < 26; i++) {
                var star = el("span", "fx-sparkle" + (i % 3 === 2 ? " is-dot" : ""));
                var size = i % 3 === 2 ? 3 + Math.random() * 4 : (i % 7 === 0 ? 18 + Math.random() * 8 : 8 + Math.random() * 10);
                star.style.setProperty("--s", size.toFixed(1) + "px");
                star.style.setProperty("--d", (2.6 + Math.random() * 2.6).toFixed(2) + "s");
                star.style.setProperty("--delay", (-Math.random() * 5).toFixed(2) + "s");
                star.style.left = (3 + Math.random() * 94).toFixed(1) + "%";
                star.style.top = (4 + Math.random() * 88).toFixed(1) + "%";
                layer.appendChild(star);
            }
            host.insertBefore(layer, host.firstChild);
        });
    }

    // Metal headings paint text with a gradient; wrap emojis so they keep their colours.
    function protectEmojis() {
        var emoji = /(\p{Extended_Pictographic}(?:\uFE0F|\u200D\p{Extended_Pictographic})*)/u;
        document.querySelectorAll("h1, h2, h3").forEach(function (heading) {
            var walker = document.createTreeWalker(heading, NodeFilter.SHOW_TEXT);
            var nodes = [];
            while (walker.nextNode()) nodes.push(walker.currentNode);
            nodes.forEach(function (node) {
                if (!emoji.test(node.nodeValue) || (node.parentNode.classList && node.parentNode.classList.contains("fx-emoji"))) return;
                var parts = node.nodeValue.split(new RegExp(emoji.source, "gu"));
                var frag = document.createDocumentFragment();
                parts.forEach(function (part, index) {
                    if (!part) return;
                    if (index % 2 === 1) frag.appendChild(el("span", "fx-emoji", part));
                    else frag.appendChild(document.createTextNode(part));
                });
                node.parentNode.replaceChild(frag, node);
            });
        });
    }

    var SPOT = ".card, .service-card, .future-card, .notes-choice-card, .notes-subject-dropdown, " +
               ".form-card, .process-card, .account-stats > *";
    function spotlight(event) {
        if (!event.target.closest) return;
        var card = event.target.closest(SPOT);
        if (!card) return;
        var box = card.getBoundingClientRect();
        card.style.setProperty("--mx", (event.clientX - box.left) + "px");
        card.style.setProperty("--my", (event.clientY - box.top) + "px");
    }

    function start() {
        placeMenu();
        placeRail();
        addSparkles();
        protectEmojis();
        document.addEventListener("pointermove", spotlight, { passive: true });
        greet();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
})();

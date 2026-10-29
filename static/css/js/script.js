/* =========================================================
   STUDENTHUB AI
   MAIN JAVASCRIPT
   ========================================================= */


/* =========================
   ELEMENTS
========================= */

const navLinks = document.querySelectorAll(".nav-link");
const sections = document.querySelectorAll(".page-section");

const menuToggle = document.querySelector(".menu-toggle");
const navMenu = document.querySelector(".nav-menu");

const serviceCards = document.querySelectorAll(".service-card:not(.service-notes)");
const isAuthenticated = document.body.dataset.authenticated === "true";

const loginModal = document.getElementById("loginModal");
const modalMessage = document.getElementById("modalMessage");
const modalClose = document.querySelector(".modal-close");

const mentorInput =
    document.getElementById("mentorInput");

const promptButtons =
    document.querySelectorAll(".prompt-chip");


/* =========================
   MOBILE NAVIGATION
========================= */

if (menuToggle && navMenu) {

    const closeMenu = () => {
        navMenu.classList.remove("open");
        menuToggle.setAttribute("aria-expanded", "false");
        menuToggle.setAttribute("aria-label", "Open navigation menu");
    };

    menuToggle.addEventListener("click", () => {
        const isOpen = navMenu.classList.toggle("open");
        menuToggle.setAttribute("aria-expanded", String(isOpen));
        menuToggle.setAttribute(
            "aria-label",
            isOpen ? "Close navigation menu" : "Open navigation menu"
        );
    });

    document.addEventListener("click", (event) => {
        if (!navMenu.contains(event.target) && !menuToggle.contains(event.target)) {
            closeMenu();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && navMenu.classList.contains("open")) {
            closeMenu();
            menuToggle.focus();
        }
    });

}


/* =========================
   CLOSE MOBILE MENU
   AFTER CLICKING A NAV LINK
========================= */

navLinks.forEach((link) => {

    link.addEventListener("click", () => {

        if (navMenu) {
            navMenu.classList.remove("open");
            if (menuToggle) {
                menuToggle.setAttribute("aria-expanded", "false");
                menuToggle.setAttribute("aria-label", "Open navigation menu");
            }
        }

    });

});


/* =========================
   ACTIVE SECTION HIGHLIGHT
========================= */

const sectionToNavLink = {};


/*
   Connect section IDs to navbar links.
*/

navLinks.forEach((link) => {

    const target =
        link.getAttribute("href");

    if (target && target.startsWith("#")) {

        const section =
            document.querySelector(target);

        if (section) {

            sectionToNavLink[section.id] = link;

        }

    }

});


/*
   Observe sections while scrolling.
*/

if (sections.length > 0) {

    const observer =
        new IntersectionObserver(
            (entries) => {

                entries.forEach((entry) => {

                    if (entry.isIntersecting) {

                        const activeLink =
                            sectionToNavLink[entry.target.id];

                        if (!activeLink) {
                            return;
                        }

                        navLinks.forEach((link) => {

                            link.classList.remove(
                                "active"
                            );

                        });

                        activeLink.classList.add(
                            "active"
                        );

                    }

                });

            },
            {
                threshold: 0.35,
                rootMargin: "-80px 0px -35% 0px"
            }
        );

    sections.forEach((section) => {

        observer.observe(section);

    });

}


/* =========================
   LOGIN REQUIRED MODAL
========================= */

function openLoginModal(message) {

    if (!loginModal) {
        return;
    }

    if (modalMessage && message) {

        modalMessage.textContent = message;

    }

    loginModal.classList.add("show");

    loginModal.setAttribute(
        "aria-hidden",
        "false"
    );

    document.body.classList.add(
        "modal-open"
    );

}


function closeLoginModal() {

    if (!loginModal) {
        return;
    }

    loginModal.classList.remove("show");

    loginModal.setAttribute(
        "aria-hidden",
        "true"
    );

    document.body.classList.remove(
        "modal-open"
    );

}


if (modalClose) {

    modalClose.addEventListener(
        "click",
        closeLoginModal
    );

}


if (loginModal) {

    loginModal.addEventListener(
        "click",
        (event) => {

            if (
                event.target ===
                loginModal
            ) {

                closeLoginModal();

            }

        }
    );

}


document.addEventListener(
    "keydown",
    (event) => {

        if (
            event.key === "Escape" &&
            loginModal &&
            loginModal.classList.contains("show")
        ) {

            closeLoginModal();

        }

    }
);


/* =========================
   SERVICE CARD CLICK
========================= */

serviceCards.forEach((card) => {

    card.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            card.click();
        }
    });

    card.addEventListener("click", () => {

        const service =
            card.dataset.service;

        if (isAuthenticated) {
            const destinations = {
                notes: "/notes",
                mentor: "/chatbot",
                placement: "/chatbot"
            };
            if (destinations[service]) {
                window.location.href = destinations[service];
                return;
            }
        }

        if (service === "mentor") {

            openLoginModal(
                "Please login or register to use the AI Career Mentor."
            );

        }

        else if (service === "placement") {

            openLoginModal(
                "Please login or register to access personalized placement guidance."
            );

        }

        else if (
            service === "resume" ||
            service === "interview" ||
            service === "internship"
        ) {

            const serviceNotice = document.getElementById("serviceNotice");
            const serviceNames = {
                resume: "Resume Analyzer",
                interview: "Interview Preparation",
                internship: "Internship Opportunities"
            };
            if (serviceNotice) {
                serviceNotice.textContent =
                    `${serviceNames[service]} is coming soon. Explore Notes or the AI Career Mentor in the meantime.`;
                serviceNotice.classList.add("visible");
            }

        }

    });

});


/* =========================
   MOBILE / KEYBOARD POPUP
========================= */

serviceCards.forEach((card) => {

    card.addEventListener(
        "focus",
        () => {

            card.classList.add(
                "show-popup"
            );

        }
    );


    card.addEventListener(
        "blur",
        () => {

            card.classList.remove(
                "show-popup"
            );

        }
    );

});


/* =========================
   AI MENTOR PROMPTS
========================= */

promptButtons.forEach((button) => {

    button.addEventListener(
        "click",
        () => {

            const prompt =
                button.textContent.trim();

            if (mentorInput) {

                mentorInput.value = prompt;

                mentorInput.focus();

            }

        }
    );

});


/* =========================
   INITIAL ACTIVE TAB
========================= */

const homeLink =
    document.querySelector(
        '.nav-link[href="#home"]'
    );

if (homeLink) {

    homeLink.classList.add(
        "active"
    );

}

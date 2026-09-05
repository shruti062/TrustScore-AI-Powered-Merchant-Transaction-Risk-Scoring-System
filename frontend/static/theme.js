// theme.js
// Simple dark mode toggle. Applies a `data-theme="dark"` attribute to
// <html>, which style.css uses to swap colors via CSS variables.
// Preference is remembered in localStorage across visits.

(function () {
    const STORAGE_KEY = "trustscore_theme";

    function applyTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        const btn = document.getElementById("themeToggle");
        if (btn) btn.innerText = theme === "dark" ? "☀️" : "🌙";
    }

    // Apply saved theme immediately (before other scripts run) to avoid a flash
    const saved = localStorage.getItem(STORAGE_KEY) || "light";
    applyTheme(saved);

    document.addEventListener("DOMContentLoaded", () => {
        const btn = document.getElementById("themeToggle");
        if (!btn) return;

        applyTheme(localStorage.getItem(STORAGE_KEY) || "light");

        btn.addEventListener("click", () => {
            const current = document.documentElement.getAttribute("data-theme");
            const next = current === "dark" ? "light" : "dark";
            localStorage.setItem(STORAGE_KEY, next);
            applyTheme(next);
        });
    });
})();

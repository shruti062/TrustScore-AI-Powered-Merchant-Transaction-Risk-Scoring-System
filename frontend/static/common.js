// common.js
// Shared logic for every authenticated page: guards the page if not
// logged in, wires up the navbar (username, admin link, logout), and
// exposes small helpers other page scripts rely on.
//
// Include this BEFORE any page-specific script (script.js, admin.js, etc).

const TOKEN = localStorage.getItem("trustscore_token");
const USERNAME = localStorage.getItem("trustscore_username");
const ROLE = localStorage.getItem("trustscore_role");

if (!TOKEN) {
    window.location.href = "/login";
}

function authHeaders() {
    return {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${TOKEN}`,
    };
}

document.addEventListener("DOMContentLoaded", () => {
    const userEl = document.getElementById("currentUser");
    if (userEl) userEl.innerText = USERNAME || "-";

    const adminLink = document.getElementById("adminLink");
    if (adminLink && ROLE === "admin") {
        adminLink.classList.remove("d-none");
    }

    const logoutBtn = document.getElementById("logoutBtn");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", () => {
            localStorage.clear();
            window.location.href = "/login";
        });
    }
});

// notifications.js
// Wires up the navbar's notification bell: fetches recent alerts,
// shows a badge count, and toggles a dropdown panel listing them.
// Polls every 30 seconds so the count stays reasonably fresh without
// needing a websocket connection.

(function () {
    const POLL_INTERVAL_MS = 30000;

    async function fetchAlerts() {
        try {
            const response = await fetch("/api/alerts");
            if (!response.ok) return [];
            return await response.json();
        } catch (e) {
            return [];
        }
    }

    function renderPanel(alerts) {
        const panel = document.getElementById("notifPanel");
        if (!panel) return;

        if (alerts.length === 0) {
            panel.innerHTML = '<div class="notif-empty">No alerts yet</div>';
            return;
        }

        panel.innerHTML = alerts
            .slice(0, 8)
            .map(a => `
                <div class="notif-item">
                    <a href="/merchant/${a.merchant_id}" class="notif-link">
                        <strong>${a.merchant_id}</strong> — avg risk ${a.avg_risk_score}
                    </a>
                    <div class="notif-message">${a.message}</div>
                </div>
            `)
            .join("");
    }

    async function refreshNotifications() {
        const alerts = await fetchAlerts();
        const countBadge = document.getElementById("notifCount");

        if (countBadge) {
            if (alerts.length > 0) {
                countBadge.innerText = alerts.length > 9 ? "9+" : alerts.length;
                countBadge.classList.remove("d-none");
            } else {
                countBadge.classList.add("d-none");
            }
        }

        renderPanel(alerts);
    }

    document.addEventListener("DOMContentLoaded", () => {
        const bell = document.getElementById("notifBell");
        const panel = document.getElementById("notifPanel");
        if (!bell || !panel) return;

        panel.classList.add("notif-panel");

        bell.addEventListener("click", (e) => {
            e.stopPropagation();
            panel.classList.toggle("d-none");
        });

        document.addEventListener("click", (e) => {
            if (!panel.contains(e.target) && e.target !== bell) {
                panel.classList.add("d-none");
            }
        });

        refreshNotifications();
        setInterval(refreshNotifications, POLL_INTERVAL_MS);
    });
})();

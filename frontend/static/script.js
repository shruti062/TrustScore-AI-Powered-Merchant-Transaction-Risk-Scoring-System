// script.js
// Dashboard logic: fetching data from the Flask API and rendering
// tables, charts, filters, and pagination. Auth guarding and navbar
// wiring (username, admin link, logout) live in common.js, which is
// loaded before this file.

// ---- pagination + filter state ----
let currentPage = 1;
const pageSize = 10;

const transactionsTable = document.getElementById("transactionsTable");
const merchantTable = document.getElementById("merchantTable");
const modelMetricsTable = document.getElementById("modelMetricsTable");
const alertsPanel = document.getElementById("alertsPanel");
const simulateBtn = document.getElementById("simulateBtn");
const pageInfo = document.getElementById("pageInfo");

function actionBadge(action) {
    const classMap = { block: "risk-block", review: "risk-review", allow: "risk-allow" };
    return `<span class="risk-badge ${classMap[action] || "risk-allow"}">${action.toUpperCase()}</span>`;
}

async function submitFeedback(txnId, verdict, button) {
    button.disabled = true;
    const response = await fetch("/api/feedback", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ txn_id: txnId, verdict }),
    });

    if (response.ok) {
        button.parentElement.innerHTML = verdict === "confirmed_fraud"
            ? '<span class="text-danger small">Marked fraud</span>'
            : '<span class="text-success small">Marked safe</span>';
        showToast("Feedback recorded", "success");
    } else {
        showToast("Could not save feedback", "error");
        button.disabled = false;
    }
}
window.submitFeedback = submitFeedback; // exposed for inline onclick handlers

async function loadRecentTransactions() {
    const merchantId = document.getElementById("filterMerchant").value.trim();
    const action = document.getElementById("filterAction").value;

    const params = new URLSearchParams({
        limit: pageSize,
        page: currentPage,
    });
    if (merchantId) params.set("merchant_id", merchantId);
    if (action) params.set("action", action);

    const response = await fetch(`/api/recent-transactions?${params}`);
    const data = await response.json();

    transactionsTable.innerHTML = "";

    data.transactions.forEach(txn => {
        const topReason = (txn.reasons || "").split(" | ")[0];
        const row = document.createElement("tr");
        row.style.cursor = "pointer";
        row.innerHTML = `
            <td>${txn.txn_id}</td>
            <td><a href="/merchant/${txn.merchant_id}" onclick="event.stopPropagation()">${txn.merchant_id}</a></td>
            <td>₹${Number(txn.amount).toLocaleString("en-IN")}</td>
            <td><strong>${txn.risk_score}</strong></td>
            <td>${actionBadge(txn.recommended_action)}</td>
            <td class="reasons-cell">${topReason}</td>
            <td>
                <button class="btn btn-outline-danger feedback-btn" onclick="event.stopPropagation(); submitFeedback('${txn.txn_id}', 'confirmed_fraud', this)">Fraud</button>
                <button class="btn btn-outline-success feedback-btn" onclick="event.stopPropagation(); submitFeedback('${txn.txn_id}', 'confirmed_safe', this)">Safe</button>
            </td>
        `;
        row.addEventListener("click", () => {
            window.location.href = `/transaction/${txn.txn_id}`;
        });
        transactionsTable.appendChild(row);
    });

    pageInfo.innerText = `Page ${data.page} of ${data.total_pages} (${data.total} total)`;
    document.getElementById("prevPageBtn").disabled = data.page <= 1;
    document.getElementById("nextPageBtn").disabled = data.page >= data.total_pages;

    return data;
}

async function loadSummaryStats() {
    // Summary cards use the full unfiltered distribution, not the current page
    const response = await fetch("/api/action-distribution");
    const dist = await response.json();

    const blocked = dist.block || 0;
    const review = dist.review || 0;
    const allowed = dist.allow || 0;

    document.getElementById("statTotal").innerText = blocked + review + allowed;
    document.getElementById("statBlocked").innerText = blocked;
    document.getElementById("statReview").innerText = review;
    document.getElementById("statAllowed").innerText = allowed;

    return dist;
}

async function loadMerchantSummary() {
    const response = await fetch("/api/merchant-summary");
    const merchants = await response.json();

    merchantTable.innerHTML = "";
    merchants.slice(0, 10).forEach(m => {
        const row = document.createElement("tr");
        row.style.cursor = "pointer";
        row.innerHTML = `
            <td><a href="/merchant/${m.merchant_id}">${m.merchant_id}</a></td>
            <td>${m.avg_risk_score}</td>
            <td>${m.flagged_count}</td>
        `;
        row.addEventListener("click", (e) => {
            if (e.target.tagName !== "A") window.location.href = `/merchant/${m.merchant_id}`;
        });
        merchantTable.appendChild(row);
    });
}

async function loadAlerts() {
    const response = await fetch("/api/alerts");
    const alerts = await response.json();

    alertsPanel.innerHTML = "";
    alerts.slice(0, 5).forEach(a => {
        const div = document.createElement("div");
        div.className = "alert-card";
        div.innerText = `⚠ ${a.message}`;
        alertsPanel.appendChild(div);
    });
}

async function loadModelMetrics() {
    const response = await fetch("/api/model-metrics");
    if (!response.ok) return;
    const data = await response.json();

    modelMetricsTable.innerHTML = "";
    data.all_models.forEach(m => {
        const isBest = m.name === data.best_model;
        const row = document.createElement("tr");
        if (isBest) row.classList.add("table-success");
        row.innerHTML = `
            <td>${m.name} ${isBest ? "⭐" : ""}</td>
            <td>${m.accuracy}</td>
            <td>${m.precision}</td>
            <td>${m.recall}</td>
            <td>${m.f1_score}</td>
            <td>${m.roc_auc}</td>
        `;
        modelMetricsTable.appendChild(row);
    });

    document.getElementById("bestModelNote").innerText =
        `Currently using ${data.best_model} (highest ROC-AUC), trained on ${data.trained_on_rows} transactions.`;
}

// ---- Charts ----
let trendChart = null;
let distributionChart = null;
let hourlyRiskChart = null;

async function loadTrendChart() {
    const response = await fetch("/api/risk-trend");
    const trend = await response.json();

    const labels = trend.map(t => t.txn_id);
    const scores = trend.map(t => t.risk_score);

    const ctx = document.getElementById("trendChart");
    if (trendChart) trendChart.destroy();

    trendChart = new Chart(ctx, {
        type: "line",
        data: {
            labels,
            datasets: [{
                label: "Risk Score",
                data: scores,
                borderColor: "#0d6efd",
                backgroundColor: "rgba(13,110,253,0.1)",
                tension: 0.3,
                fill: true,
                pointRadius: 2,
            }],
        },
        options: {
            scales: { y: { min: 0, max: 100 } },
            plugins: { legend: { display: false } },
        },
    });
}

async function loadDistributionChart(dist) {
    const ctx = document.getElementById("distributionChart");
    if (distributionChart) distributionChart.destroy();

    distributionChart = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels: ["Allow", "Review", "Block"],
            datasets: [{
                data: [dist.allow || 0, dist.review || 0, dist.block || 0],
                backgroundColor: ["#198754", "#ffc107", "#dc3545"],
            }],
        },
    });
}

async function loadHourlyRiskChart() {
    const response = await fetch("/api/risk-by-hour");
    const data = await response.json();

    // Fill in all 24 hours even if some have no data, so the x-axis is complete
    const byHour = {};
    data.forEach(d => { byHour[d.hour_of_day] = d.avg_risk_score; });
    const labels = Array.from({ length: 24 }, (_, h) => `${h}:00`);
    const scores = Array.from({ length: 24 }, (_, h) => byHour[h] ?? 0);

    // Color bars by risk level so the riskiest hours stand out at a glance
    const colors = scores.map(s => s >= 50 ? "#dc3545" : s >= 25 ? "#ffc107" : "#198754");

    const ctx = document.getElementById("hourlyRiskChart");
    if (hourlyRiskChart) hourlyRiskChart.destroy();

    hourlyRiskChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels,
            datasets: [{
                label: "Avg Risk Score",
                data: scores,
                backgroundColor: colors,
            }],
        },
        options: {
            scales: { y: { min: 0, max: 100 } },
            plugins: { legend: { display: false } },
        },
    });
}

async function refreshDashboard() {
    await loadRecentTransactions();
    const dist = await loadSummaryStats();
    await loadMerchantSummary();
    await loadAlerts();
    await loadTrendChart();
    await loadDistributionChart(dist);
    await loadHourlyRiskChart();
}

simulateBtn.addEventListener("click", async () => {
    simulateBtn.disabled = true;
    simulateBtn.innerText = "Scoring...";
    await fetch("/api/simulate-transaction", { method: "POST" });
    await refreshDashboard();
    simulateBtn.disabled = false;
    simulateBtn.innerText = "Simulate Transaction";
    showToast("New transaction simulated", "info");
});

document.getElementById("applyFilters").addEventListener("click", () => {
    currentPage = 1;
    loadRecentTransactions();
});

document.getElementById("prevPageBtn").addEventListener("click", () => {
    if (currentPage > 1) {
        currentPage -= 1;
        loadRecentTransactions();
    }
});

document.getElementById("nextPageBtn").addEventListener("click", () => {
    currentPage += 1;
    loadRecentTransactions();
});

refreshDashboard();
loadModelMetrics();

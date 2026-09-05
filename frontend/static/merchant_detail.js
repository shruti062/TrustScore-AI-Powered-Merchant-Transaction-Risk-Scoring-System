// merchant_detail.js
// Loads and renders one merchant's full transaction history and risk
// trend. MERCHANT_ID is injected by the page template.

function actionBadge(action) {
    const classMap = { block: "risk-block", review: "risk-review", allow: "risk-allow" };
    return `<span class="risk-badge ${classMap[action] || "risk-allow"}">${action.toUpperCase()}</span>`;
}

let merchantTrendChart = null;

function renderTrendChart(trend) {
    const ctx = document.getElementById("merchantTrendChart");
    const labels = trend.map(t => t.txn_id);
    const scores = trend.map(t => t.risk_score);

    if (merchantTrendChart) merchantTrendChart.destroy();
    merchantTrendChart = new Chart(ctx, {
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

async function loadMerchantDetail() {
    const response = await fetch(`/api/merchant/${encodeURIComponent(MERCHANT_ID)}`);
    const data = await response.json();

    document.getElementById("merchantTitle").innerText = data.merchant_id;
    document.getElementById("txnCount").innerText = data.total_transactions;

    const avgScore = data.avg_risk_score;
    document.getElementById("avgRiskScore").innerText = avgScore ?? "-";

    // Color the average-score card border by severity, matching the
    // same red/yellow/green language used for risk badges elsewhere
    const scoreCard = document.getElementById("avgScoreCard");
    scoreCard.classList.remove("stat-card-high", "stat-card-medium", "stat-card-low");
    if (avgScore != null) {
        if (avgScore >= 70) scoreCard.classList.add("stat-card-high");
        else if (avgScore >= 35) scoreCard.classList.add("stat-card-medium");
        else scoreCard.classList.add("stat-card-low");
    }

    renderTrendChart(data.trend);

    const table = document.getElementById("merchantTxnTable");
    table.innerHTML = data.transactions.map(txn => `
        <tr style="cursor:pointer" onclick="window.location.href='/transaction/${txn.txn_id}'">
            <td>${txn.txn_id}</td>
            <td>₹${Number(txn.amount).toLocaleString("en-IN")}</td>
            <td><strong>${txn.risk_score}</strong></td>
            <td>${actionBadge(txn.recommended_action)}</td>
            <td class="text-muted small">${txn.created_at}</td>
        </tr>
    `).join("") || '<tr><td colspan="5" class="text-muted text-center py-3">No transactions yet</td></tr>';
}

loadMerchantDetail();

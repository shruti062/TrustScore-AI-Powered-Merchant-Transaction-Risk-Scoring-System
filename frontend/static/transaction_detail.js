// transaction_detail.js
// Loads and renders a single transaction's full detail, including
// its SHAP feature contribution chart and feedback history. TXN_ID
// is injected by the page template.

function actionBadge(action) {
    const classMap = { block: "risk-block", review: "risk-review", allow: "risk-allow" };
    return `<span class="risk-badge ${classMap[action] || "risk-allow"}">${action.toUpperCase()}</span>`;
}

let shapChart = null;

function renderShapChart(topFeatures) {
    const ctx = document.getElementById("shapChart");
    if (!topFeatures || topFeatures.length === 0) {
        ctx.parentElement.innerHTML = '<p class="text-muted small">No SHAP data available for this transaction.</p>';
        return;
    }

    const labels = topFeatures.map(f => f.feature);
    const values = topFeatures.map(f => f.impact);
    const colors = values.map(v => v >= 0 ? "#dc3545" : "#198754");

    if (shapChart) shapChart.destroy();
    shapChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels,
            datasets: [{ label: "SHAP impact", data: values, backgroundColor: colors }],
        },
        options: {
            indexAxis: "y",
            plugins: { legend: { display: false } },
        },
    });
}

function renderFeedbackHistory(history) {
    const table = document.getElementById("feedbackHistoryTable");
    const emptyMsg = document.getElementById("noFeedbackYet");

    if (!history || history.length === 0) {
        table.innerHTML = "";
        emptyMsg.classList.remove("d-none");
        return;
    }

    emptyMsg.classList.add("d-none");
    table.innerHTML = history.map(f => `
        <tr>
            <td>${f.reviewer_username}</td>
            <td>${f.verdict === "confirmed_fraud"
                ? '<span class="text-danger">Fraud</span>'
                : '<span class="text-success">Safe</span>'}</td>
            <td class="text-muted small">${f.created_at}</td>
        </tr>
    `).join("");
}

async function loadTransactionDetail() {
    const response = await fetch(`/api/transaction/${encodeURIComponent(TXN_ID)}`);

    if (!response.ok) {
        document.getElementById("notFound").classList.remove("d-none");
        return;
    }

    const data = await response.json();
    const txn = data.transaction;

    document.getElementById("detailContent").classList.remove("d-none");
    document.getElementById("txnId").innerText = txn.txn_id;
    document.getElementById("merchantLink").innerText = txn.merchant_id;
    document.getElementById("merchantLink").href = `/merchant/${txn.merchant_id}`;
    document.getElementById("txnTime").innerText = txn.created_at;
    document.getElementById("riskScore").innerText = txn.risk_score;

    const riskScoreCard = document.getElementById("riskScoreCard");
    riskScoreCard.classList.remove("stat-card-high", "stat-card-medium", "stat-card-low");
    if (txn.risk_score >= 70) riskScoreCard.classList.add("stat-card-high");
    else if (txn.risk_score >= 35) riskScoreCard.classList.add("stat-card-medium");
    else riskScoreCard.classList.add("stat-card-low");
    document.getElementById("amount").innerText = `₹${Number(txn.amount).toLocaleString("en-IN")}`;
    document.getElementById("hourOfDay").innerText = `${txn.hour_of_day}:00`;
    document.getElementById("actionBadgeContainer").innerHTML = actionBadge(txn.recommended_action);

    const reasons = (txn.reasons || "").split(" | ").filter(Boolean);
    document.getElementById("reasonsList").innerHTML =
        reasons.map(r => `<li>${r}</li>`).join("") || "<li>No reasons recorded</li>";

    // top_contributing_features is stored as a Python-repr string in the DB;
    // parse it defensively rather than assuming valid JSON
    let topFeatures = [];
    try {
        const raw = txn.top_contributing_features || "[]";
        topFeatures = JSON.parse(raw.replace(/'/g, '"'));
    } catch (e) {
        topFeatures = [];
    }
    renderShapChart(topFeatures);

    renderFeedbackHistory(data.feedback_history);
}

async function submitFeedbackFromDetail(verdict) {
    const response = await fetch("/api/feedback", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ txn_id: TXN_ID, verdict }),
    });

    if (response.ok) {
        showToast("Feedback recorded", "success");
        loadTransactionDetail(); // refresh the feedback history table
    } else {
        showToast("Could not save feedback", "error");
    }
}

document.getElementById("markFraudBtn").addEventListener("click", () => submitFeedbackFromDetail("confirmed_fraud"));
document.getElementById("markSafeBtn").addEventListener("click", () => submitFeedbackFromDetail("confirmed_safe"));

loadTransactionDetail();

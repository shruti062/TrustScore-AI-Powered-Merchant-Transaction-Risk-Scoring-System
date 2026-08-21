
const transactionsTable = document.getElementById("transactionsTable");
const merchantTable = document.getElementById("merchantTable");
const simulateBtn = document.getElementById("simulateBtn");

function actionBadge(action) {
    const classMap = {
        block: "risk-block",
        review: "risk-review",
        allow: "risk-allow",
    };
    const cls = classMap[action] || "risk-allow";
    return `<span class="risk-badge ${cls}">${action.toUpperCase()}</span>`;
}

async function loadRecentTransactions() {
    const response = await fetch("/api/recent-transactions?limit=25");
    const transactions = await response.json();

    transactionsTable.innerHTML = "";

    let blocked = 0, review = 0, allowed = 0;

    transactions.forEach(txn => {
        if (txn.recommended_action === "block") blocked++;
        else if (txn.recommended_action === "review") review++;
        else allowed++;

        const row = document.createElement("tr");
        row.innerHTML = `
            <td>${txn.txn_id}</td>
            <td>${txn.merchant_id}</td>
            <td>₹${Number(txn.amount).toLocaleString("en-IN")}</td>
            <td><strong>${txn.risk_score}</strong></td>
            <td>${actionBadge(txn.recommended_action)}</td>
            <td class="reasons-cell">${txn.reasons}</td>
        `;
        transactionsTable.appendChild(row);
    });

    document.getElementById("statTotal").innerText = transactions.length;
    document.getElementById("statBlocked").innerText = blocked;
    document.getElementById("statReview").innerText = review;
    document.getElementById("statAllowed").innerText = allowed;
}

async function loadMerchantSummary() {
    const response = await fetch("/api/merchant-summary");
    const merchants = await response.json();

    merchantTable.innerHTML = "";

    merchants.slice(0, 10).forEach(m => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td>${m.merchant_id}</td>
            <td>${m.avg_risk_score}</td>
            <td>${m.flagged_count}</td>
        `;
        merchantTable.appendChild(row);
    });
}

async function refreshDashboard() {
    await loadRecentTransactions();
    await loadMerchantSummary();
}

simulateBtn.addEventListener("click", async () => {
    simulateBtn.disabled = true;
    simulateBtn.innerText = "Scoring...";

    await fetch("/api/simulate-transaction", { method: "POST" });
    await refreshDashboard();

    simulateBtn.disabled = false;
    simulateBtn.innerText = "Simulate Transaction";
});

// Load data
refreshDashboard();

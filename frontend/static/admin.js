// admin.js
// Handles the admin panel: viewing/updating risk thresholds and
// triggering a model retrain. Auth guarding and navbar wiring live in
// common.js (loaded before this file). This script additionally
// checks the ROLE to hide admin content from non-admin accounts.

if (ROLE !== "admin") {
    document.getElementById("accessDenied").classList.remove("d-none");
} else {
    document.getElementById("adminContent").classList.remove("d-none");
    loadSettings();
    loadFeedbackCount();
}

async function loadSettings() {
    const response = await fetch("/api/settings", { headers: authHeaders() });
    const settings = await response.json();

    document.getElementById("reviewThreshold").value = settings.review_threshold;
    document.getElementById("blockThreshold").value = settings.block_threshold;
    document.getElementById("alertThreshold").value = settings.alert_threshold;
}

async function loadFeedbackCount() {
    const response = await fetch("/api/feedback-summary", { headers: authHeaders() });
    if (!response.ok) return;
    const data = await response.json();
    document.getElementById("feedbackCount").innerText = data.total_feedback;
}

document.getElementById("saveSettingsBtn").addEventListener("click", async () => {
    const payload = {
        review_threshold: Number(document.getElementById("reviewThreshold").value),
        block_threshold: Number(document.getElementById("blockThreshold").value),
        alert_threshold: Number(document.getElementById("alertThreshold").value),
    };

    const response = await fetch("/api/settings", {
        method: "PUT",
        headers: authHeaders(),
        body: JSON.stringify(payload),
    });

    if (response.ok) {
        const savedLabel = document.getElementById("settingsSaved");
        savedLabel.classList.remove("d-none");
        setTimeout(() => savedLabel.classList.add("d-none"), 2000);
        showToast("Settings saved", "success");
    } else {
        showToast("Could not save settings", "error");
    }
});

document.getElementById("retrainBtn").addEventListener("click", async () => {
    const btn = document.getElementById("retrainBtn");
    btn.disabled = true;
    btn.innerText = "Retraining...";

    const response = await fetch("/api/trigger-retrain", {
        method: "POST",
        headers: authHeaders(),
    });
    const data = await response.json();

    const resultBox = document.getElementById("retrainResult");
    resultBox.classList.remove("d-none");
    resultBox.innerText = response.ok
        ? data.message
        : (data.error || "Retrain failed");

    if (response.ok) {
        showToast("Model retrained successfully", "success");
    } else {
        showToast("Retrain failed", "error");
    }

    btn.disabled = false;
    btn.innerText = "Retrain Model Now";
    loadFeedbackCount();
});

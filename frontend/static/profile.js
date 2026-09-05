// profile.js
// Loads the current user's account info and handles password changes.

async function loadProfile() {
    const response = await fetch("/api/profile", { headers: authHeaders() });
    if (!response.ok) return;
    const data = await response.json();

    document.getElementById("profileUsername").innerText = data.username;
    document.getElementById("profileRole").innerText = data.role;
    document.getElementById("profileJoined").innerText = data.created_at;
    document.getElementById("profileFeedbackCount").innerText = data.feedback_submitted;
}

document.getElementById("changePasswordBtn").addEventListener("click", async () => {
    const oldPassword = document.getElementById("oldPassword").value;
    const newPassword = document.getElementById("newPassword").value;
    const errorBox = document.getElementById("passwordError");
    errorBox.classList.add("d-none");

    const response = await fetch("/api/profile/password", {
        method: "PUT",
        headers: authHeaders(),
        body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    });
    const data = await response.json();

    if (response.ok) {
        showToast("Password updated", "success");
        document.getElementById("oldPassword").value = "";
        document.getElementById("newPassword").value = "";
    } else {
        errorBox.innerText = data.error || "Could not update password";
        errorBox.classList.remove("d-none");
    }
});

loadProfile();

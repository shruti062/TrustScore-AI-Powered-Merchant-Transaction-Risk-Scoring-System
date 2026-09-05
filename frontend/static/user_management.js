// user_management.js
// Admin-only page: lists all accounts and lets an admin change roles.

if (ROLE !== "admin") {
    document.getElementById("accessDenied").classList.remove("d-none");
} else {
    document.getElementById("usersContent").classList.remove("d-none");
    loadUsers();
}

async function changeRole(username, newRole, selectEl) {
    const response = await fetch(`/api/users/${encodeURIComponent(username)}/role`, {
        method: "PUT",
        headers: authHeaders(),
        body: JSON.stringify({ role: newRole }),
    });

    if (response.ok) {
        showToast(`${username}'s role updated to ${newRole}`, "success");
    } else {
        showToast("Could not update role", "error");
        loadUsers(); // revert the dropdown to the actual current value
    }
}

async function loadUsers() {
    const response = await fetch("/api/users", { headers: authHeaders() });
    if (!response.ok) return;
    const users = await response.json();

    const table = document.getElementById("usersTable");
    table.innerHTML = users.map(u => `
        <tr>
            <td>${u.username}${u.username === USERNAME ? ' <span class="badge bg-secondary">you</span>' : ""}</td>
            <td>${u.role}</td>
            <td class="text-muted small">${u.created_at}</td>
            <td>
                <select class="form-select form-select-sm" style="width:130px" ${u.username === USERNAME ? "disabled" : ""}
                    onchange="changeRole('${u.username}', this.value, this)">
                    <option value="analyst" ${u.role === "analyst" ? "selected" : ""}>Analyst</option>
                    <option value="admin" ${u.role === "admin" ? "selected" : ""}>Admin</option>
                </select>
            </td>
        </tr>
    `).join("");
}

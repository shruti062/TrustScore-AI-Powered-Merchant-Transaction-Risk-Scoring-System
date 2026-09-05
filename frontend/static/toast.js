// toast.js
// A small toast notification helper. Call showToast("message", "success")
// from anywhere after this script has loaded. Replaces alert()-style
// popups with a non-blocking notification that fades out on its own.

function showToast(message, type = "info") {
    let container = document.getElementById("toastContainer");
    if (!container) {
        container = document.createElement("div");
        container.id = "toastContainer";
        container.style.cssText =
            "position:fixed; bottom:20px; right:20px; z-index:2000; display:flex; flex-direction:column; gap:8px;";
        document.body.appendChild(container);
    }

    const colors = {
        success: "#198754",
        error: "#dc3545",
        info: "#0d6efd",
        warning: "#ffc107",
    };

    const toast = document.createElement("div");
    toast.innerText = message;
    toast.style.cssText = `
        background: ${colors[type] || colors.info};
        color: white;
        padding: 10px 16px;
        border-radius: 6px;
        font-size: 0.9rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        opacity: 0;
        transition: opacity 0.25s ease;
        max-width: 320px;
    `;

    container.appendChild(toast);
    requestAnimationFrame(() => { toast.style.opacity = "1"; });

    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

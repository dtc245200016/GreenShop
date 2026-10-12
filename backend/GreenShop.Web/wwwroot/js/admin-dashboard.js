(() => {
    "use strict";
    document.querySelectorAll("[data-chart]").forEach(chart => {
        const tooltip = chart.querySelector("[role=tooltip]");
        const hide = () => { tooltip.hidden = true; };
        chart.querySelectorAll(".dash-bar").forEach(bar => {
            const show = () => {
                tooltip.textContent = `${bar.dataset.label} · ${bar.dataset.value}`;
                tooltip.hidden = false;
                const area = chart.getBoundingClientRect(), point = bar.getBoundingClientRect();
                tooltip.style.left = `${Math.max(0, Math.min(point.left - area.left, area.width - tooltip.offsetWidth))}px`;
                tooltip.style.top = `${Math.max(0, point.top - area.top - tooltip.offsetHeight - 8)}px`;
            };
            bar.addEventListener("mouseenter",show);bar.addEventListener("focus",show);
            bar.addEventListener("mouseleave",hide);bar.addEventListener("blur",hide);
            bar.addEventListener("keydown",event => { if (event.key === "Escape") hide(); });
        });
    });
    const fallback = img => { if (img.dataset.fallback) return; img.dataset.fallback = "true"; img.src = "/images/product-placeholder.svg"; };
    document.querySelectorAll("img[data-dashboard-image]").forEach(img => { img.addEventListener("error",()=>fallback(img)); if (img.complete && !img.naturalWidth) fallback(img); });
    const form = document.querySelector(".dash-filter");
    form?.addEventListener("submit",event => {
        if (form.dataset.busy) { event.preventDefault(); return; }
        form.dataset.busy = "true";form.setAttribute("aria-busy","true");
        const button = form.querySelector("button[type=submit]");button.style.minWidth = `${button.offsetWidth}px`;
        button.disabled = true;button.textContent = "Đang tải…";
    });
    window.addEventListener("pageshow",event => { if (event.persisted && form?.dataset.busy) window.location.reload(); });
})();

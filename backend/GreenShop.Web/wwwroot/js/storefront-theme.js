// Visual feedback only. Existing storefront.js owns menus and form submissions.
(() => {
    "use strict";
    const reduced=matchMedia("(prefers-reduced-motion: reduce)");
    const timers=new WeakMap();
    document.addEventListener("pointerdown",event=>{
        if(reduced.matches || !event.isPrimary || event.button!==0)return;
        const button=event.target.closest(".storefront :is(.shop-btn,.shop-icon-button,.auth-form-wrapper .btn)");
        if(!button || button.disabled || button.classList.contains("disabled"))return;
        const bounds=button.getBoundingClientRect();
        button.style.setProperty("--press-x",`${event.clientX-bounds.left}px`);
        button.style.setProperty("--press-y",`${event.clientY-bounds.top}px`);
        clearTimeout(timers.get(button));button.classList.add("customer-pressed");
        timers.set(button,setTimeout(()=>button.classList.remove("customer-pressed"),260));
    });
})();

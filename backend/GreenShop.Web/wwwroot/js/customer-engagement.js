(() => {
    "use strict";
    const reduced=matchMedia("(prefers-reduced-motion: reduce)");
    document.querySelectorAll('input[type="file"]').forEach((input,index)=>{
        if(!/image\/(jpeg|png|webp)|\.(jpg|jpeg|png|webp)/i.test(input.accept))return;
        const picker=document.createElement("div"),button=document.createElement("button"),icon=document.createElement("i"),name=document.createElement("span");
        picker.className="image-file-picker";button.type="button";button.className="file-picker-button";button.disabled=input.disabled;
        icon.className="fa-regular fa-image";icon.setAttribute("aria-hidden","true");button.append(icon,document.createTextNode("Chọn file"));
        name.className="file-picker-name";name.id=`image-file-name-${index}`;name.setAttribute("role","status");name.setAttribute("aria-live","polite");button.setAttribute("aria-describedby",name.id);
        input.before(picker);picker.append(input,button,name);input.classList.add("image-file-input");
        let timer=0;
        const update=()=>{const files=[...input.files];name.textContent=files.length>1?`${files.length} file: ${files.map(f=>f.name).join(", ")}`:files[0]?.name||"Chưa chọn file";name.title=files.map(f=>f.name).join(", ");clearTimeout(timer);picker.classList.remove("is-selected");if(files.length&&!reduced.matches){void picker.offsetWidth;picker.classList.add("is-selected");timer=setTimeout(()=>picker.classList.remove("is-selected"),260);}};
        button.addEventListener("click",()=>input.click());input.addEventListener("change",update);input.addEventListener("invalid",()=>button.focus());input.form?.addEventListener("reset",()=>setTimeout(update,0));update();
    });
    document.querySelectorAll("form[data-engagement-submit]").forEach(form=>{
        form.addEventListener("submit",e=>{
            if(form.dataset.engagementBusy==="true"){e.preventDefault();return;}if(e.defaultPrevented||!form.checkValidity())return;
            form.dataset.engagementBusy="true";form.setAttribute("aria-busy","true");form.querySelectorAll('button[type="submit"]').forEach(button=>button.disabled=true);
        });
        window.addEventListener("pageshow",()=>{delete form.dataset.engagementBusy;form.removeAttribute("aria-busy");form.querySelectorAll('button[type="submit"]').forEach(button=>button.disabled=false);});
    });
    document.querySelectorAll("[data-hero-slider]").forEach(root=>{
        const track=root.querySelector("[data-hero-track]"),slides=[...root.querySelectorAll("[data-hero-slide]")];
        if(!track||slides.length<2)return;
        let index=0,timer=0,paused=false,visible=true,start=null,dragging=false,suppressClick=false,wrapping=false,wrapTimer=0;
        const clone=slide=>{const copy=slide.cloneNode(true);copy.removeAttribute("data-hero-slide");copy.removeAttribute("data-product-id");copy.inert=true;copy.setAttribute("aria-hidden","true");copy.setAttribute("data-hero-clone","");copy.querySelectorAll("[id]").forEach(e=>e.removeAttribute("id"));return copy;};
        track.prepend(clone(slides.at(-1)));track.append(clone(slides[0]));
        const normalize=()=>{clearTimeout(wrapTimer);wrapping=false;track.style.transition="none";track.style.transform=`translateX(-${(index+1)*100}%)`;void track.offsetWidth;track.style.transition="";};
        normalize();
        const pause=root.querySelector("[data-hero-pause]"),counter=root.querySelector("[data-hero-counter]"),announcement=root.querySelector("[data-hero-announcement]");
        const schedule=()=>{clearTimeout(timer);const running=!paused&&!document.hidden&&visible&&!reduced.matches&&!start;root.dataset.heroAutoplay=running?"running":"paused";if(running)timer=setTimeout(()=>go(index+1,false),5000);};
        const go=(value,manual=true)=>{
            if(wrapping)normalize();index=(value+slides.length)%slides.length;
            const edge=value<0||value>=slides.length;
            const position=edge&&!reduced.matches?(value<0?0:slides.length+1):index+1;
            track.style.transform=`translateX(-${position*100}%)`;
            if(edge&&!reduced.matches){wrapping=true;wrapTimer=setTimeout(normalize,650);}
            slides.forEach((slide,i)=>{slide.inert=i!==index;slide.setAttribute("aria-hidden",String(i!==index));});
            for(const offset of [-1,0,1])slides[(index+offset+slides.length)%slides.length].querySelector("img").loading="eager";
            counter.textContent=`${index+1} / ${slides.length}`;root.dataset.heroIndex=String(index);
            if(manual)announcement.textContent=`${slides[index].querySelector("img").alt}, sản phẩm ${index+1} trên ${slides.length}`;
            schedule();
        };
        root.querySelector("[data-hero-prev]").addEventListener("click",()=>go(index-1));root.querySelector("[data-hero-next]").addEventListener("click",()=>go(index+1));
        pause.addEventListener("click",()=>{paused=!paused;pause.setAttribute("aria-pressed",String(paused));pause.textContent=paused?"Bật tự trượt":"Tạm dừng tự trượt";schedule();});
        document.addEventListener("visibilitychange",schedule);reduced.addEventListener("change",schedule);
        root.addEventListener("keydown",e=>{if(e.target.matches("input,textarea,select")||!["ArrowLeft","ArrowRight"].includes(e.key))return;e.preventDefault();go(index+(e.key==="ArrowRight"?1:-1));});
        const viewport=root.querySelector(".hero-slider-viewport");
        viewport.addEventListener("pointerdown",e=>{if(e.button!==0||e.target.closest("button,input,textarea,form"))return;if(wrapping)normalize();start={x:e.clientX,y:e.clientY,id:e.pointerId};dragging=false;schedule();});
        viewport.addEventListener("pointermove",e=>{
            if(!start||e.pointerId!==start.id)return;const dx=e.clientX-start.x,dy=e.clientY-start.y;
            if(!dragging&&Math.abs(dy)>Math.abs(dx)+8){start=null;schedule();return;}
            if(!dragging&&Math.abs(dx)>10){dragging=true;viewport.setPointerCapture(e.pointerId);track.classList.add("is-dragging");}
            if(dragging){e.preventDefault();track.style.transform=`translateX(calc(-${(index+1)*100}% + ${dx}px))`;}
        });
        const end=e=>{if(!start)return;const dx=e.clientX-start.x;start=null;track.classList.remove("is-dragging");if(dragging){suppressClick=true;go(index+(Math.abs(dx)>Math.min(65,viewport.clientWidth*.15)?(dx<0?1:-1):0));setTimeout(()=>{suppressClick=false;},0);}else schedule();dragging=false;};
        viewport.addEventListener("pointerup",end);viewport.addEventListener("pointercancel",()=>{start=null;dragging=false;track.classList.remove("is-dragging");go(index,false);});
        viewport.addEventListener("click",e=>{if(suppressClick){e.preventDefault();e.stopPropagation();}},true);
        new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;schedule();},{threshold:.15}).observe(root);go(0,false);
    });

    const fetchJson=async(url,options={})=>{
        const response=await fetch(url,{credentials:"same-origin",redirect:"error",signal:AbortSignal.timeout(7000),...options});
        if(!response.ok){let message="Mất kết nối. Vui lòng thử lại.";try{message=(await response.json()).message||message;}catch{}throw new Error(message);}
        return response.status===204?null:response.json();
    };
    const alerts=document.querySelector("[data-admin-alerts]");
    if(alerts){
        let timer=0,loading=false,previous=null;
        const poll=async()=>{
            clearTimeout(timer);if(document.hidden||loading)return;loading=true;
            try{const counts=await fetchJson(alerts.dataset.alertsUrl);for(const key of ["orders","messages","reviews","total"])document.querySelectorAll(`[data-alert-count="${key}"]`).forEach(e=>{e.textContent=e.classList.contains("shop-alert-badge")&&counts[key]>99?"99+":String(counts[key]);if(e.classList.contains("shop-alert-badge"))e.hidden=counts[key]===0;e.setAttribute("aria-label",`${counts[key]} ${key==="orders"?"đơn chờ xác nhận":key==="messages"?"tin nhắn chưa đọc":key==="reviews"?"đánh giá mới":"thông báo"}`);});if(previous!==null&&counts.total>previous)alerts.querySelector("[data-alert-status]").textContent="Cửa hàng có thông báo mới.";previous=counts.total;}catch{}finally{loading=false;if(!document.hidden)timer=setTimeout(poll,15000);}
        };document.addEventListener("visibilitychange",()=>document.hidden?clearTimeout(timer):poll());poll();
    }
    const chat=document.querySelector("[data-shop-chat]");if(!chat)return;
    const form=chat.querySelector("[data-chat-form]"),list=chat.querySelector("[data-chat-messages]"),empty=chat.querySelector("[data-chat-empty]"),feedback=chat.querySelector("[data-chat-feedback]"),input=form.elements.Content,button=form.querySelector('[type="submit"]'),admin=chat.dataset.admin==="true";
    let last=0,timer=0,loading=false,sending=false,readThrough=0;
    const token=()=>form.querySelector('[name="__RequestVerificationToken"]').value;
    const markRead=async()=>{if(!last||last<=readThrough||document.hidden)return;const body=new URLSearchParams({through:String(last),__RequestVerificationToken:token()});await fetchJson(chat.dataset.readUrl,{method:"POST",body});readThrough=last;};
    const poll=async()=>{
        clearTimeout(timer);timer=0;if(document.hidden||loading)return;loading=true;
        try {
            const data=await fetchJson(`${chat.dataset.messagesUrl}?after=${last}`);const nearBottom=list.scrollHeight-list.scrollTop-list.clientHeight<80;
            for(const message of data.messages){if(message.id<=last)continue;const bubble=document.createElement("article");bubble.className=`chat-bubble${message.fromAdmin===admin?" is-own":""}`;bubble.dataset.messageId=String(message.id);const who=document.createElement("strong"),text=document.createElement("p"),time=document.createElement("small");who.textContent=message.fromAdmin?"GreenShop":"Khách hàng";text.textContent=message.content;time.textContent=new Intl.DateTimeFormat("vi-VN",{timeZone:"Asia/Ho_Chi_Minh",hour:"2-digit",minute:"2-digit",day:"2-digit",month:"2-digit"}).format(new Date(message.createdAt+(/Z$|[+-]\d\d:\d\d$/.test(message.createdAt)?"":"Z")));bubble.append(who,text,time);list.append(bubble);last=message.id;}
            empty.hidden=last>0;if(!last)empty.textContent="Chưa có tin nhắn. Gửi lời chào để bắt đầu.";if(nearBottom)list.scrollTop=list.scrollHeight;
            if(nearBottom)await markRead();if(!sending)feedback.textContent="";if(data.hasMore)timer=setTimeout(poll,0);
        } catch(error){feedback.textContent=error.message;} finally {loading=false;if(!timer&&!document.hidden)timer=setTimeout(poll,5000);}
    };
    form.addEventListener("submit",async e=>{
        e.preventDefault();if(sending||!input.value.trim())return;sending=true;button.disabled=true;form.setAttribute("aria-busy","true");feedback.textContent="Đang gửi…";
        const sent=input.value;
        try{await fetchJson(form.action,{method:"POST",body:new FormData(form)});if(input.value===sent)input.value="";form.elements.RequestToken.value=crypto.randomUUID().replaceAll("-","");feedback.textContent="Đã gửi tin nhắn.";list.scrollTop=list.scrollHeight;poll();}catch(error){feedback.textContent=error.message;}finally{sending=false;button.disabled=false;form.removeAttribute("aria-busy");input.focus();}
    });input.addEventListener("keydown",e=>{if(e.ctrlKey&&e.key==="Enter"){e.preventDefault();form.requestSubmit();}});
    list.addEventListener("scroll",()=>{if(list.scrollHeight-list.scrollTop-list.clientHeight<80)markRead().catch(()=>{});},{passive:true});
    document.addEventListener("visibilitychange",()=>document.hidden?clearTimeout(timer):poll());window.addEventListener("pagehide",()=>clearTimeout(timer));poll();
})();

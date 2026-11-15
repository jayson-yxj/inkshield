/* Read-only probes plus synthetic DOM input. Does not modify application state directly. */
window.__workspaceProbe = {
  errors: [],
  rect(selector) { const e=document.querySelector(selector);if(!e)throw Error('Missing '+selector);const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,transform:getComputedStyle(e).transform,hidden:e.hidden}; },
  async toggle(d,selector,panelSelector) {
    const button=document.querySelector(selector), before=this.rect(panelSelector), expanded=button.getAttribute('aria-expanded');
    let settled=false;const handler=()=>{settled=true};window.addEventListener('workspace:layoutsettled',handler);document.addEventListener('workspace:layoutsettled',handler);
    try { button.click();await d.pause(50);const during=this.rect(panelSelector);await d.wait(()=>settled,5000);await d.pause(80);const after=this.rect(panelSelector);d.check(selector+' aria-expanded toggles',button.getAttribute('aria-expanded')!==expanded);return {before,during,after,expanded:button.getAttribute('aria-expanded')}; }
    finally {window.removeEventListener('workspace:layoutsettled',handler);document.removeEventListener('workspace:layoutsettled',handler);}
  },
  wheel(selector,x,y,deltaY) { const e=document.querySelector(selector);e.dispatchEvent(new WheelEvent('wheel',{bubbles:true,cancelable:true,clientX:x,clientY:y,deltaY,deltaMode:0})); },
  async pan(d,selector,dx,dy,{middle=false,space=true}={}) {
    const e=document.querySelector(selector),r=e.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2;
    if(space)document.dispatchEvent(new KeyboardEvent('keydown',{key:' ',code:'Space',bubbles:true,cancelable:true}));
    const send=(type,px,py)=>e.dispatchEvent(new PointerEvent(type,{bubbles:true,cancelable:true,pointerId:1701,pointerType:'mouse',isPrimary:true,button:middle?1:0,buttons:type==='pointerup'?0:middle?4:1,clientX:px,clientY:py}));
    try {send('pointerdown',x,y);for(let i=1;i<=12;i++){send('pointermove',x+dx*i/12,y+dy*i/12);await d.pause(25)}send('pointerup',x+dx,y+dy)}
    finally {if(space)document.dispatchEvent(new KeyboardEvent('keyup',{key:' ',code:'Space',bubbles:true}));}
  }
};

'use strict';
const fs=require('fs');
let base=fs.readFileSync(__dirname+'/verify_segments_ui.js','utf8');base=base.slice(0,base.indexOf('async function main()'));
const tests=`
async function main(){
 const stored=new Map(),writes=[];context.window.innerWidth=1280;context.window.innerHeight=900;context.window.listeners={};context.window.addEventListener=(name,fn)=>(context.window.listeners[name]??=[]).push(fn);context.localStorage={getItem:key=>stored.get(key)||null,setItem:(key,value)=>{stored.set(key,value);writes.push(value)}};
 const ws=elements.get('#editorWorkspace');ws.clientWidth=1252;ws.clientHeight=796;ws.style.setProperty=(key,value)=>{ws.style[key]=value};const classes=new Set();ws.classList={toggle:(name,value)=>value?classes.add(name):classes.delete(name),remove:name=>classes.delete(name)};
 for(const id of ['mediaResize','inspectorResize','timelineResize']){const el=elements.get('#'+id);el.setPointerCapture=id=>{el.capture=id};el.hasPointerCapture=id=>el.capture===id;el.releasePointerCapture=id=>{el.capture=null}}
 stored.set('inkshield.pane-layout.v1',JSON.stringify({left:250,right:280,timeline:330}));
 run(html.match(/<script>([\\s\\S]*?)<\\/script>/)[1]);await tick();
 assert.equal(run('paneSizes.left'),250);assert.equal(run('paneSizes.right'),280);assert.equal(ws.style['--timeline-height'],'330px');assert.equal(elements.get('#mediaResize')['aria-valuenow'],'250');
 const beforeCalls=calls.length,position=run('globalFrame'),generation=run('generation');
 const el=elements.get('#mediaResize');const event={button:0,pointerId:7,clientX:250,clientY:100,preventDefault(){},stopPropagation(){}};
 el.listeners.pointerdown[0](event);assert.equal(el.capture,7);assert.ok(classes.has('resizing-panes'));
 el.listeners.pointermove[0]({...event,clientX:99999});assert.equal(run('paneSizes.left'),1252-16-320-280);assert.equal(run('paneSizes.right'),280);
 el.listeners.pointercancel[0](event);assert.equal(run('paneDrag'),null);assert.equal(el.capture,null);assert.equal(classes.size,0);assert.ok(writes.length>0);
 // Right/bottom have inverted pointer direction; all sizes preserve center/top minima.
 const right=elements.get('#inspectorResize');right.listeners.pointerdown[0](event);right.listeners.pointermove[0]({...event,clientX:99999});assert.equal(run('paneSizes.right'),220);right.listeners.pointerup[0](event);
 const row=elements.get('#timelineResize');row.listeners.pointerdown[0](event);row.listeners.pointermove[0]({...event,clientY:-99999});assert.equal(run('paneSizes.timeline'),796-8-240);row.listeners.lostpointercapture[0](event);assert.equal(run('paneDrag'),null);
 let stopped=false,prevented=false;row.listeners.keydown[0]({key:'ArrowDown',preventDefault(){prevented=true},stopPropagation(){stopped=true}});assert.ok(stopped&&prevented);assert.equal(run('paneSizes.timeline'),538);
 row.listeners.keydown[0]({key:'ArrowDown',shiftKey:true,preventDefault(){},stopPropagation(){}});assert.equal(run('paneSizes.timeline'),498);
 await elements.get('#resetLayout').fire('click');assert.equal(run('paneSizes.timeline'),290);assert.equal(run('paneSizes.left'),220);assert.equal(run('paneSizes.right'),310);
 // Corrupt/blocked storage does not prevent resizing or reset.
 context.localStorage.setItem=()=>{throw Error('storage disabled')};run('resetPaneLayout()');el.listeners.pointerdown[0](event);el.listeners.pointermove[0]({...event,clientX:0});el.listeners.pointerup[0](event);assert.equal(run('paneSizes.left'),140);
 context.window.innerWidth=850;ws.clientWidth=834;context.window.listeners.resize.at(-1)();assert.ok(run('paneSizes.left+paneSizes.right')<=834-16-260);assert.ok(run('paneSizes.left')>=140);assert.ok(run('paneSizes.right')>=220);
 el.listeners.pointerdown[0](event);context.window.innerWidth=700;context.window.listeners.resize.at(-1)();assert.equal(run('paneDrag'),null);assert.equal(classes.size,0);const sizes=run('JSON.stringify(paneSizes)');el.listeners.pointerdown[0](event);assert.equal(run('paneDrag'),null);assert.equal(run('JSON.stringify(paneSizes)'),sizes);
 assert.equal(calls.length,beforeCalls);assert.equal(run('globalFrame'),position);assert.equal(run('generation'),generation);
 // A blocked storage getter also leaves startup functional.
 context.localStorage.getItem=()=>{throw Error('blocked')};run('try{localStorage.getItem(paneStorageKey)}catch{paneSizes=paneDefaults()}');assert.equal(run('paneSizes.timeline'),290);
 assert.ok(html.includes('grid-template-areas:'));assert.ok(html.includes('role="separator"'));assert.ok(html.includes('@media(max-width:800px){.pane-separator{display:none}'));
 console.log('LAYOUT PASS: stored sizes, pointer clamp and direction, capture/cancel/lost cleanup, ARIA, keyboard propagation, reset, storage failures, narrow viewport/mobile, no inference/seek/state changes');
}
main().catch(e=>{console.error(e);process.exitCode=1});`;
new Function('require','__dirname',base+tests)(require,__dirname);

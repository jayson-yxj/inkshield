/* Native DOM panel and navigation cases; final SAM/tail hooks required, not optional. */
window.runFrozenWorkspaceCases=async function(d,a){
 const checks=[],errors=[],baseD=d;d=Object.assign({},d,{check(name,ok,detail){checks.push({name,ok,detail});return baseD.check(name,ok,detail)}});
 const p=__workspaceProbe, prompts=()=>JSON.stringify(segments.map(s=>s.layers.map(l=>l.settings.samPrompts))), baseline=prompts();
 for(const [button,panel,axis] of [['#toggleMediaPanel','.media-panel','width'],['#toggleInspectorPanel','.controls','width'],['#toggleTimelinePanel','.timeline','height']]){
   const before=p.rect(panel),collapsed=await p.toggle(d,button,panel),expanded=await p.toggle(d,button,panel);
   d.check('panel shrinks '+panel,collapsed.after[axis]<before[axis]);
   d.check('panel has intermediate collapse geometry '+panel,collapsed.during[axis]>collapsed.after[axis]&&collapsed.during[axis]<collapsed.before[axis],collapsed);
   d.check('panel restores expanded size '+panel,Math.abs(expanded.after[axis]-before[axis])<=2,{before,collapsed,expanded});
   __nativeSuite.observations.push({kind:'panel-animation',panel,before,collapsed,expanded});
 }
 d.click('#previewZoomReset');d.check('workspace tools do not add SAM prompts',prompts()===baseline);
 const viewer=document.querySelector('#viewer'),r=viewer.getBoundingClientRect();viewer.focus();
 p.wheel('#viewer',r.left+r.width/2,r.top+r.height/2,-350);await d.pause(100);
 const zoom=p.rect('#previewTransform');d.check('wheel scales shared preview',new DOMMatrixReadOnly(zoom.transform).a>1);
 // Synthetic pointers lack an active-pointer registry; shim capture only.
 const capture=viewer.setPointerCapture,hasCapture=viewer.hasPointerCapture;
 viewer.setPointerCapture=()=>{};viewer.hasPointerCapture=()=>false;
 try{await p.pan(d,'#viewer',30,20,{middle:true,space:false})}finally{viewer.setPointerCapture=capture;viewer.hasPointerCapture=hasCapture}
 await d.pause(100);
 const pan=p.rect('#previewTransform');d.check('pan changes shared transform',pan.transform!==zoom.transform,{zoom,pan});
 d.check('navigation does not add SAM prompts',prompts()===baseline);
 d.check('frozen SAM attribution case available',typeof runFrozenSamAttribution==='function');await runFrozenSamAttribution(d,a);
 d.click('#previewZoomReset');
 return {checks,errors}; // Tail is owned and invoked by dom_suite.js.
};

/* Draft integration suite. Execution allowed only after final freeze and oracle plan. */
window.runMaskTimelineAcceptance=async function(d){
 const a=__layersAdapter;window.__nativeAssets=[];window.__nativeImages=[];
 const snap=()=>{saveSegment();return a.state()}, stable=ls=>JSON.stringify(ls.map(l=>({id:l.id,settings:l.settings,analysisId:l.analysisId,analysisReady:l.analysisReady}))),
 cfg=l=>JSON.stringify(l.settings), region=(id)=>document.querySelector(a.regionSelector(id)),
 pick=async id=>{const e=region(id);d.check('layer region exists '+id,!!e);e.click();await d.pause(100);d.check('region click selects actual layer '+id,selectedSegment.activeLayerId===id&&!!selectedMaskRegion());},
 style=v=>d.click('.seg[data-group="style"] button[data-value="'+v+'"]'),
 undo=async()=>{d.click('#undoSplit');await d.pause(250)};
 const initial=snap();await a.addCustom();
 d.check('new pending custom retains previous automatic layer',cfg(snap()[0])===cfg(initial[0])&&snap()[0].analysisId===initial[0].analysisId);
 d.check('new custom is active and pending',settings.mode==='custom'&&!analysisReady&&snap().length===2);
 d.check('pending custom shows SAM controls',!$('#samControls').hidden);
 a.bindActive('controlled-custom-a');await d.wait(()=>analysisReady);
 await a.addCustom();a.bindActive('controlled-custom-b');await d.wait(()=>analysisReady);
 let ls=snap();const ids=ls.map(l=>l.id);d.check('one automatic and two custom on same segment',ls.length===3&&ls[0].settings.mode==='automatic'&&ls.slice(1).every(l=>l.settings.mode==='custom'));
 d.check('three separate effect tracks',ids.every(id=>document.querySelector('.layer-mask-row[data-layer-id="'+id+'"]')));
 // Do not preselect target: this specifically exercises nonactive layer pointer proxy handling.
 await a.select(2);let before=snap(),history=splitHistory.length;
 await d.trim(a.regionSelector(ids[0])+' .mask-handle.start',0,20);
 ls=snap();d.check('nonactive automatic trim targets its own layer',ls[0].settings.maskRegions[0].start===20&&selectedSegment.activeLayerId===ids[0]);
 d.check('nonactive trim isolates other layers',cfg(ls[1])===cfg(before[1])&&cfg(ls[2])===cfg(before[2]));
 d.check('nonactive trim commits exactly one undo',splitHistory.length===history+1);
 await undo();d.check('undo restores complete layer stack',stable(snap())===stable(before));
 // Overlapping temporal ranges across distinct layers are legal.
 for(const [i,start,end,strength,effect] of [[0,20,100,100,'black'],[1,40,120,65,'blur'],[2,60,140,80,'mosaic']]){
   await a.select((i+1)%3);before=snap();await d.trim(a.regionSelector(ids[i])+' .mask-handle.start',0,start);
   await d.trim(a.regionSelector(ids[i])+' .mask-handle.end',150,end);await pick(ids[i]);style(effect);d.input('#intensity',strength);await d.pause(120);
   ls=snap();d.check('edited range and parameter '+i,ls[i].settings.maskRegions[0].start===start&&ls[i].settings.maskRegions[0].end===end&&ls[i].settings.maskRegions[0].strength===strength);
   d.check('selection parameter isolation '+i,ls.every((l,j)=>j===i||cfg(l)===cfg(before[j])));
 }
 for(const [i,strength] of [[0,100],[1,65],[2,80]]){await pick(ids[i]);d.check('reselection inspector reflects layer '+i,Number($('#intensity').value)===strength)}
 d.check('overlap preserved in ordered full payload',a.payload().length===3&&a.payload().every((l,i)=>l.analysis_id===['controlled-auto','controlled-custom-a','controlled-custom-b'][i]));
 // Removing a selected region creates explicit [] only on its own layer.
 before=snap();await pick(ids[1]);document.dispatchEvent(new KeyboardEvent('keydown',{key:'Delete',bubbles:true,cancelable:true}));await d.pause(180);
 ls=snap();d.check('delete clears only active layer region',Array.isArray(ls[1].settings.maskRegions)&&ls[1].settings.maskRegions.length===0&&cfg(ls[0])===cfg(before[0])&&cfg(ls[2])===cfg(before[2]));
 await a.select(0);await a.select(1);d.check('explicit empty layer survives selection',settings.maskRegions.length===0);await undo();d.check('undo empty layer restores layer stack',stable(snap())===stable(before));
 // Owner-frozen supplementary cases implement real SAM click, panel geometry and final-tail scenarios.
 d.check('frozen extension suite available',typeof window.runFrozenWorkspaceCases==='function');
 await runFrozenWorkspaceCases(d,a);
 await runFrozenTailCases(d,a);
 await a.select(2);await d.scrub('custom_layers_continuous',5,135);
 // JPEG pixel and ordered render references are prepared independently, never endpoint self-comparison.
 d.check('frozen pixel capture hook available',typeof window.captureFrozenLayerPixels==='function');
 await captureFrozenLayerPixels(d,a);
 if(previewMuted)d.click('#previewMute');
 await d.frame(0);d.click('#playPause');await d.wait(()=>playing&&!startingPlayback&&!protectedVideo.hidden,90000);await d.wait(()=>protectedVideo.currentTime>.12);d.click('#playPause');
 __nativeAssets.push({name:'layers-protected',url:protectedVideo.currentSrc,frames:150,codec:'h264',pixel_expectations:__integration.pixel_expectations.protected});
 d.click('#exportBtn');await d.wait(()=>!exporting&&!$('#download').hidden,90000);
 __nativeAssets.push({name:'layers-export',url:$('#download').href,frames:150,codec:'mpeg4',pixel_expectations:__integration.pixel_expectations.export});
 d.check('no browser errors',!__errors.length,__errors);d.snapshot('final_layers');
};

/* DOM edits for final-tail regression; fixtures inject identity/readiness only. */
window.runFrozenTailCases=async function(d,a){
 const stable=()=>JSON.stringify(segments.map(s=>({start:s.start,end:s.end,layers:s.layers.map(l=>({id:l.id,settings:l.settings,analysisId:l.analysisId,analysisReady:l.analysisReady}))}))),
 bindAll=async suffix=>{for(let i=0;i<selectedSegment.layers.length;i++){await a.select(i);a.bindActive('controlled-'+(i===0?'auto':i===1?'custom-a':'custom-b')+suffix);await d.wait(()=>analysisReady)}};
 for(const [cut,head,tail,forced]of [[140,'-head','-tail',false],[148,'-short-head','-short-tail',false],[148,'-short-head','-short-tail',true]]){
   saveSegment();const baseline=stable(),history=splitHistory.length;
   await d.frame(cut);d.click('#splitBtn');await d.pause(200);d.check('DOM split for short tail '+cut,segments.length===2&&segments[1].start===cut);
   // Tail gets a full local custom region by DOM, independent of prior half-open ranges.
   await a.select(1);await d.frame(0);if(!fullMaskRegions(settings,frames).length)d.click('#addMaskRegion');
   const target=document.querySelector(a.regionSelector(selectedSegment.activeLayerId)+'[data-segment-id="'+selectedSegment.id+'"]');target.click();
   d.click('.seg[data-group="style"] button[data-value="black"]');d.input('#intensity',100);
   d.check('tail custom region covers entire local segment '+cut,settings.maskRegions.length===1&&settings.maskRegions[0].start===0&&settings.maskRegions[0].end===150-cut);
   await bindAll(tail);
   document.querySelectorAll('#clipLane .timeline-clip')[0].click();await d.pause(100);
   // Make head automatic-only by deleting custom layers through actual buttons.
   while(selectedSegment.layers.length>1){const rows=document.querySelectorAll('#layerPanel button[aria-pressed]');rows[rows.length-1].parentElement.querySelectorAll('button')[1].click();await d.pause(80)}
   a.bindActive('controlled-auto'+head);await d.wait(()=>analysisReady&&!!playback);
   await d.frame(Math.max(0,cut-12));document.querySelector('.stage-bar').dispatchEvent(new MouseEvent('click',{bubbles:true}));
   d.check('background click enters continuous mode selection',!clipSelected);
   const events=[],listeners=[];for(const [node,label]of [[source,'source'],[protectedVideo,'protected']])for(const type of ['play','pause','ended','seeking','seeked']){const fn=()=>events.push({node:label,type,at:performance.now(),state:a.snapshot()});node.addEventListener(type,fn);listeners.push([node,type,fn])}
   const errorAt=__errors.length;d.click('#playPause');
   try{
     await d.wait(()=>playing||startingPlayback,10000);
     if(forced){await d.wait(()=>playing&&!startingPlayback&&!protectedActive,10000);source.dispatchEvent(new Event('ended'));__nativeSuite.observations.push({kind:'synthetic-source-ended-fallback',cut,natural:false})}
     await d.wait(()=>!playing&&!startingPlayback&&globalFrame===149,90000);await d.pause(180);
     const last=d.image();__nativeImages.push({name:'tail-'+cut+(forced?'-forced':'-natural')+'-last',...last});
     d.check('tail ends on protected final frame '+cut,last.element===protectedVideo.id&&globalFrame===149,{last,state:a.snapshot(),events});
     d.check('tail does not throw protection-not-ready '+cut,__errors.length===errorAt&&!$('#previewFeedback').textContent.includes('连续播放已停止'),{errors:__errors.slice(errorAt),feedback:$('#previewFeedback').textContent});
     const canvas=document.createElement('canvas');canvas.width=320;canvas.height=240;const ctx=canvas.getContext('2d');ctx.drawImage(protectedVideo,0,0,320,240);const pix=[...ctx.getImageData(135,180,1,1).data];d.check('tail final custom ROI remains black '+cut,pix.slice(0,3).every(v=>v<25),pix);
     __nativeSuite.observations.push({kind:'automatic-to-final-custom',cut,forced_source_ended:forced,events,final:a.snapshot()});
   }finally{for(const [node,type,fn]of listeners)node.removeEventListener(type,fn)}
   document.querySelector('#clipLane .timeline-clip').click();
   while(splitHistory.length>history){d.click('#undoSplit');await d.pause(100)}
   d.check('tail test DOM undo restores full stack '+cut,stable()===baseline);
 }
 // Same-segment aggregate source reaches its protected ended path independently.
 await a.select(2);await d.frame(145);const mark=__errors.length;d.click('#playPause');await d.wait(()=>playing||startingPlayback);await d.wait(()=>!playing&&!startingPlayback,90000);
 d.check('same-segment layers end without protection error',__errors.length===mark&&!protectedVideo.hidden,{state:a.snapshot(),errors:__errors.slice(mark)});
 d.check('same-segment end selects final local frame',Number($('#frameSlider').value)===149);
 d.click('#playPause');await d.wait(()=>playing&&!startingPlayback,15000);
 d.check('aggregate replay from last frame starts at beginning',protectedVideo.currentTime<1,{time:protectedVideo.currentTime,state:a.snapshot()});d.click('#playPause');
};

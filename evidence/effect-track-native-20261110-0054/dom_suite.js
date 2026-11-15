/* WebView2 dispatched DOM events. Only controlled analysis identities are injected. */
window.runMaskTimelineAcceptance=async function(d){
 window.__nativeAssets=[];window.__nativeImages=[];
 const canonical=()=>JSON.stringify(settings.maskRegions),bounds=()=>JSON.stringify(segments.map(s=>[s.start,s.end]));
 const sel=i=>document.querySelectorAll('#maskLane .timeline-mask')[i];
 const pick=async i=>{const el=sel(i);d.check('effect button exists '+i,!!el);el.click();await d.pause(80);d.check('click selects without modal',!!selectedMaskRegion()&&!document.querySelector('dialog[open]'))};
 const css=i=>'.timeline-mask[data-region-id="'+sel(i).dataset.regionId+'"]';
 const undo=async()=>{d.click('#undoSplit');await d.pause(300)};
 const key=(key,extra={})=>timelinePlane.dispatchEvent(new KeyboardEvent('keydown',{key,bubbles:true,cancelable:true,...extra}));
 const style=value=>d.click('.seg[data-group="style"] button[data-value="'+value+'"]');
 const originalBounds=bounds();
 await pick(0);let history=splitHistory.length;
 await d.trim(css(0)+' .mask-handle.start',0,20);
 d.check('left trim commits one undo',settings.maskRegions[0].start===20&&splitHistory.length===history+1);
 await d.trim(css(0)+' .mask-handle.end',150,50);
 d.check('right trim sets half-open end',settings.maskRegions[0].end===50&&bounds()===originalBounds);
 await pick(0);style('black');d.input('#intensity',100);
 await d.frame(80);d.click('#addMaskRegion');await d.pause(180);
 await d.trim(css(1)+' .mask-handle.end',150,110);await pick(1);style('mosaic');d.input('#intensity',35);
 const second=JSON.stringify(settings.maskRegions[1]);await pick(0);d.input('#intensity',90);
 d.check('right inspector isolates selected effect',settings.maskRegions[0].strength===90&&JSON.stringify(settings.maskRegions[1])===second&&bounds()===originalBounds);
 await pick(1);d.check('switch effect reflects strength',Number($('#intensity').value)===35&&inspectorConfig().style==='mosaic');
 const effects=canonical();d.click('#clipLane .timeline-clip');style('blur');d.input('#intensity',60);
 d.check('video defaults do not mutate effects',!selectedMaskRegion()&&canonical()===effects);
 await pick(0);style('black');d.input('#intensity',100);
 const beforeMove=canonical();history=splitHistory.length;await d.trim(css(0),30,35);
 d.check('body move translates both edges with one undo',settings.maskRegions[0].start===25&&settings.maskRegions[0].end===55&&splitHistory.length===history+1);await undo();d.check('body undo restores effects',canonical()===beforeMove);
 for(const cancel of ['Escape','pointercancel']){await pick(0);const state=canonical(),count=splitHistory.length;d.pointer(css(0),'pointerdown',30);d.pointer(timelinePlane,'pointermove',35);await d.pause(70);key('b',{ctrlKey:true});key('Delete');d.check('held drag blocks effect keyboard mutation '+cancel,canonical()===state&&splitHistory.length===count);if(cancel==='Escape')key('Escape');else d.pointer(timelinePlane,'pointercancel',35);await d.pause(100);d.check(cancel+' leaves data and history unchanged',canonical()===state&&splitHistory.length===count)}
 await pick(0);await d.frame(35);history=splitHistory.length;key('b',{ctrlKey:true});await d.pause(150);
 d.check('Ctrl+B splits selected effect only',settings.maskRegions.length===3&&settings.maskRegions[0].end===35&&settings.maskRegions[1].start===35&&bounds()===originalBounds&&splitHistory.length===history+1);await undo();
 await pick(1);const beforeDelete=canonical();key('Delete');await d.pause(150);d.check('Delete removes effect not video',settings.maskRegions.length===1&&bounds()===originalBounds);await undo();d.check('delete undo restores parameters',canonical()===beforeDelete);
 // Local half-open boundaries on real automatic preview canvas.
 for(const frame of [19,20,49,50,79,80,109,110]){
  await d.frame(frame);await d.wait(()=>decodedSourceFrame===frame);await d.pause(100);
  const image=d.image();__nativeImages.push({name:'auto-frame-'+frame,...image});
  d.check('automatic preview uses canvas frame '+frame,image.element==='playbackCanvas');
  const c=document.createElement('canvas');c.width=320;c.height=240;const x=c.getContext('2d');x.drawImage(playbackCanvas,0,0);const pixel=Array.from(x.getImageData(160,120,1,1).data);
  if(frame===20||frame===49)d.check('black inside half-open region '+frame,pixel.slice(0,3).every(v=>v<25),pixel);
  if([19,50,79,110].includes(frame))d.check('unmasked outside regions '+frame,pixel.slice(0,3).some(v=>v>45),pixel);
 }
 d.snapshot('edited_two_regions');
 await d.scrub('automatic_regions_continuous',5,140);
 // Real export is triggered by production UI and frozen serialized region settings.
 if(previewMuted)d.click('#previewMute');
 d.click('#exportBtn');await d.wait(()=>!exporting&&!$('#download').hidden,90000);
 __nativeAssets.push({name:'automatic-regions-export',url:$('#download').href});
 // Split across a region: old [80,110) becomes right-local [5,35).
 const prior=canonical();await d.frame(75);d.click('#splitBtn');await d.pause(300);
 d.check('split actual video boundary',segments.length===2&&segments[0].end===75&&segments[1].start===75);
 d.check('split shifts right region to local coordinates',segments[1].settings.maskRegions.length===1&&segments[1].settings.maskRegions[0].start===5&&segments[1].settings.maskRegions[0].end===35);
 d.check('split keeps left region clipped',segments[0].settings.maskRegions.length===1&&segments[0].settings.maskRegions[0].start===20&&segments[0].settings.maskRegions[0].end===50);
 await undo();d.check('undo split restores whole local regions',segments.length===1&&canonical()===prior&&bounds()===originalBounds);
 // UI mode switch retains regions and maps target policy. Inject only controlled analysis cache.
 d.click('#clipLane .timeline-clip');d.click('#customMode');
 selectedSegment.analysisId='controlled-custom';selectedSegment.analysisReady=true;selectedSegment.playback=null;selectedSegment.status='已分析';selectSegment(selectedSegment,false);
 await d.wait(()=>analysisReady&&!!playback);await d.wait(()=>samDisplayed===JSON.stringify([selectedSegment.id,Number($('#frameSlider').value),generation]));await d.pause(400);await d.frame(20);
 await d.wait(()=>samDisplayed===JSON.stringify([selectedSegment.id,20,generation]));
 __nativeImages.push({name:'custom-inside-preview',...d.image()});
 d.check('custom JPEG inside region is protected',__sample().center.slice(0,3).every(v=>v<25));
 await d.frame(50);await d.wait(()=>samDisplayed===JSON.stringify([selectedSegment.id,50,generation]));
 __nativeImages.push({name:'custom-outside-preview',...d.image()});
 d.check('custom JPEG outside half-open region is original',__sample().center.slice(0,3).some(v=>v>45));
 await d.frame(0);d.click('#playPause');await d.wait(()=>playing&&!startingPlayback&&!protectedVideo.hidden,90000);
 await d.wait(()=>protectedVideo.currentTime>.12);d.click('#playPause');
 __nativeAssets.push({name:'custom-regions-protected',url:protectedVideo.currentSrc});
 await d.scrub('custom_regions_cached_continuous',5,65);
 protectedSources.clear();protectedVideo.hidden=true;
 await d.scrub('custom_regions_uncached_continuous',5,65);
 d.click('#exportBtn');await d.wait(()=>!exporting&&!$('#download').hidden,90000);
 __nativeAssets.push({name:'custom-regions-export',url:$('#download').href});
 // Real rapid custom re-selection plus immediate slider input/change; no injected settings.
 const rapidRequests=__fetches.length;
 for(const frame of [20,50,19,49]){d.click('#segmentList .segment-item');d.input('#frameSlider',frame);await d.pause(18)}
 await d.wait(()=>samDisplayed===JSON.stringify([selectedSegment.id,49,generation]),20000);await d.pause(500);
 d.check('rapid custom DOM reselect and slider settles on latest protected frame',__sample().center.slice(0,3).every(v=>v<25));
 d.check('rapid custom DOM reselect and slider has no busy preview responses',!__fetches.slice(rapidRequests).some(r=>r.status===429));
 d.snapshot('rapid_custom_selection');
 // Create mixed-mode neighbors through DOM. Only analysis readiness is fixture-injected.
 await d.frame(75);d.click('#splitBtn');await d.pause(200);
 d.click('#automaticMode');
 selectedSegment.analysisId='controlled-auto-right';selectedSegment.analysisReady=true;selectedSegment.status='已分析';selectSegment(selectedSegment,false);await d.wait(()=>analysisReady&&!!playback);
 d.click('#clipLane .timeline-clip');selectedSegment.analysisId='controlled-custom-left';selectedSegment.analysisReady=true;selectedSegment.status='已分析';selectSegment(selectedSegment,false);await d.wait(()=>analysisReady&&!!playback);
 const mixed=()=>JSON.stringify(segments.map(s=>({start:s.start,end:s.end,mode:s.settings.mode,regions:s.settings.maskRegions,analysisId:s.analysisId,analysisReady:s.analysisReady})));
 const baseline=mixed();
 for(const target of [90,60]){history=splitHistory.length;await d.trim('.cut-marker',75,target);
 d.check('mixed cut moves '+target,segments[0].end===target&&segments[1].start===target);
 d.check('mixed modes retained '+target,segments[0].settings.mode==='custom'&&segments[1].settings.mode==='automatic');
 d.check('mixed caches invalidated '+target,segments.every(s=>!s.analysisReady&&!s.analysisId&&!s.playback&&!s.download));
 d.check('explicit effects remain selectable after invalidation '+target,document.querySelectorAll('#maskLane .timeline-mask').length===2);await pick(0);d.check('pending effect selected without analysis ready '+target,!!selectedMaskRegion()&&!analysisReady);
 const left=segments[0].settings.maskRegions,right=segments[1].settings.maskRegions;
 d.check('custom own interval and target retained '+target,left.length===1&&left[0].start===20&&left[0].end===50&&JSON.stringify(left[0].targets)==='["custom"]');
 d.check('automatic own absolute intersection '+target,right.length===1&&right[0].start===(target===90?0:20)&&right[0].end===110-target&&!right[0].targets.includes('custom'));
 d.check('newly extended gap unmasked '+target,target===90?!left.some(r=>r.start<=80&&80<r.end):!right.some(r=>r.start<=10&&10<r.end));
 d.check('cut single undo '+target,splitHistory.length===history+1);await undo();d.check('mixed undo restores original config and analysis '+target,mixed()===baseline);
 }
 d.snapshot('mixed_cut_restored');

};

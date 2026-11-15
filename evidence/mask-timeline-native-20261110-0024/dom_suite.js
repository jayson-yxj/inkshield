/* Actual DOM editing only. Analysis references may be fixture-injected; settings are read-only to this suite. */
window.runMaskTimelineAcceptance=async function(d){
 window.__nativeAssets=[];window.__nativeImages=[];
 const canonical=()=>JSON.stringify(settings.maskRegions);
 const boundaries=()=>JSON.stringify(segments.map(s=>[s.start,s.end]));
 const save=async()=>{d.click('#regionForm button[type=submit]');await d.wait(()=>!$('#regionDialog').open);await d.pause(200)};
 const open=async(index=0)=>{const el=document.querySelectorAll('#maskLane button.timeline-mask')[index];d.check('region DOM button exists '+index,!!el);el.click();await d.wait(()=>$('#regionDialog').open)};
 const edit=async(index,values)=>{await open(index);for(const [key,value] of Object.entries(values))d.input('#region'+key,value);await save()};
 const undo=async()=>{d.click('#undoSplit');await d.pause(250)};
 const baseBoundaries=boundaries();
 d.check('legacy starts undefined whole segment',settings.maskRegions===undefined);
 await open();d.check('legacy region dialog local range',Number($('#regionStart').value)===0&&Number($('#regionEnd').value)===150);
 const modalFrame=globalFrame;for(const event of [{key:' ',code:'Space'},{key:'ArrowLeft',code:'ArrowLeft'}])$('#regionTitle').dispatchEvent(new KeyboardEvent('keydown',{bubbles:true,...event}));await d.pause(150);d.check('modal Space and ArrowLeft preserve paused transport',globalFrame===modalFrame&&!playing&&!startingPlayback&&$('#regionDialog').open);
 d.input('#regionStart',20);d.input('#regionEnd',50);d.input('#regionStyle','black');d.input('#regionStrength',90);await save();
 d.check('legacy whole region clipped through DOM',settings.maskRegions.length===1&&settings.maskRegions[0].start===20&&settings.maskRegions[0].end===50&&settings.maskRegions[0].style==='black');
 const first=JSON.stringify(settings.maskRegions[0]);
 d.click('#addMaskRegion');await d.wait(()=>$('#regionDialog').open);
 d.input('#regionStart',80);d.input('#regionEnd',110);d.input('#regionStyle','mosaic');d.input('#regionStrength',35);await save();
 d.check('new independent region added',settings.maskRegions.length===2&&JSON.stringify(settings.maskRegions[0])===first);
 const second=JSON.stringify(settings.maskRegions[1]);
 await edit(0,{Strength:100});
 d.check('parameter edit isolated from other region and video bounds',settings.maskRegions[0].strength===100&&JSON.stringify(settings.maskRegions[1])===second&&boundaries()===baseBoundaries);
 await open(0);d.input('#regionEnd',90);d.click('#regionForm button[type=submit]');await d.pause(150);
 d.check('overlap rejected without commit',$('#regionDialog').open&&$('#regionError').textContent.length>0&&settings.maskRegions[0].end===50);d.click('#regionCancel');
 await edit(0,{Start:25,End:45});d.check('region cropping preserves other region and video',settings.maskRegions[0].start===25&&settings.maskRegions[0].end===45&&JSON.stringify(settings.maskRegions[1])===second&&boundaries()===baseBoundaries);
 await undo();d.check('undo cropping restores range',settings.maskRegions[0].start===20&&settings.maskRegions[0].end===50);
 const beforeDelete=canonical();await open(1);d.click('#regionDelete');await d.wait(()=>!$('#regionDialog').open);
 d.check('delete selected region',settings.maskRegions.length===1);await undo();d.check('undo restores deleted region parameters',canonical()===beforeDelete);
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
 await undo();d.check('undo split restores whole local regions',segments.length===1&&canonical()===prior&&boundaries()===baseBoundaries);
 // UI mode switch retains regions and maps target policy. Inject only controlled analysis cache.
 d.click('#customMode');
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
 // Explicit none remains distinct from undefined legacy whole.
 await open(1);d.click('#regionDelete');await d.wait(()=>!$('#regionDialog').open);
 await open(0);d.click('#regionDelete');await d.wait(()=>!$('#regionDialog').open);
 d.check('deleting all yields explicit none',Array.isArray(settings.maskRegions)&&settings.maskRegions.length===0&&document.querySelectorAll('#maskLane button.timeline-mask').length===0);
 await undo();d.check('undo explicit none restores last region',settings.maskRegions.length===1);
 d.snapshot('final');
};

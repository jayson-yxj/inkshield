/* Controlled inference only: production DOM click, coordinate mapping and request queue. */
window.runFrozenSamAttribution=async function(d,a){
 const checks=[],errors=[],check=(name,ok,detail)=>{checks.push({name,ok,detail});d.check(name,ok,detail)},clone=x=>JSON.parse(JSON.stringify(x));
 saveSegment();const seg=selectedSegment,saved={layers:clone(seg.layers),active:seg.activeLayerId,frame:seg.frame,download:seg.download,exportNote:seg.exportNote,clip:clipSelected,cap:samCapabilities,warm:samWarmup};
 const originalFetch=window.fetch,calls=[];
 const mask=document.createElement('canvas');mask.width=media.width;mask.height=media.height;const png=mask.toDataURL('image/png');
 window.fetch=async function(url,options){if(String(url).split('?')[0].endsWith('/api/sam/preview')){calls.push({url:String(url),body:JSON.parse(options.body),layerId:selectedSegment.activeLayerId,segmentId:selectedSegment.id});return new Response(JSON.stringify({mask:png,empty:true,seconds:0,cache_hit:false}),{status:200,headers:{'Content-Type':'application/json'}})}return originalFetch.apply(this,arguments)};
 try{
  const index=seg.layers.findIndex(l=>l.settings.mode==='custom');check('SAM custom layer exists',index>=0);await a.select(index);
  clipSelected=true;samCapabilities={available:true,max_width:1280,max_height:720,max_frames:150};samWarmup={...samWarmup,state:'ready'};
  const target=seg.activeLayerId;const other=()=>JSON.stringify(seg.layers.filter(l=>l.id!==target));const untouched=other();
  settings.samPrompts={};invalidateCustom();seg.settings=cloneSettings(settings);await seekSamRaw();
  await d.wait(()=>!playbackCanvas.hidden&&samDisplayed===JSON.stringify([seg.id,Number($('#frameSlider').value),generation]));
  const rect=playbackCanvas.getBoundingClientRect(),iw=playbackCanvas.width,ih=playbackCanvas.height,scale=Math.min(rect.width/iw,rect.height/ih),w=iw*scale,h=ih*scale,left=rect.left+(rect.width-w)/2,top=rect.top+(rect.height-h)/2;
  const vr=$('#viewer').getBoundingClientRect(),cx=Math.floor(vr.left+vr.width/2),cy=Math.floor(vr.top+vr.height/2);
  const expected={x:Math.floor((cx-left)/w*media.width),y:Math.floor((cy-top)/h*media.height)},frame=Number($('#frameSlider').value);
  check('SAM click is tested under zoom',new DOMMatrixReadOnly(getComputedStyle($('#previewTransform')).transform).a>1);
  const valid=samDisplayed;samDisplayed=JSON.stringify([seg.id,frame-1,generation]);
  $('#viewer').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,button:0,buttons:1,pointerId:1702,clientX:cx,clientY:cy}));$('#viewer').dispatchEvent(new PointerEvent('pointerup',{bubbles:true,button:0,pointerId:1702,clientX:cx,clientY:cy}));$('#viewer').dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:cx,clientY:cy}));
  check('stale SAM frame rejects click',calls.length===0&&Object.keys(settings.samPrompts).length===0&&$('#samStatus').textContent.includes('正在定位本帧'));
  samDisplayed=valid;$('#viewer').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,button:0,buttons:1,pointerId:1702,clientX:cx,clientY:cy}));$('#viewer').dispatchEvent(new PointerEvent('pointerup',{bubbles:true,button:0,pointerId:1702,clientX:cx,clientY:cy}));$('#viewer').dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:cx,clientY:cy}));
  await d.wait(()=>calls.length>0);await d.wait(()=>!samClickRunning&&!samClickPending);
  saveSegment();const call=calls[0],point=call.body.prompts?.slice(-1)[0];
  check('SAM request uses real preview route',call.url.endsWith('/api/sam/preview'));
  check('zoomed SAM payload maps to source pixels',!!point&&point.x===expected.x&&point.y===expected.y,{expected,point,rect:{x:rect.x,y:rect.y,width:rect.width,height:rect.height}});
  check('SAM payload frame and segment attribution',call.body.frame===frame&&call.body.start_frame===seg.start&&call.body.end_frame===seg.end&&call.body.media_id===media.media_id,call);
  check('SAM prompt belongs to selected custom layer',call.layerId===target&&!!seg.layers.find(l=>l.id===target).settings.samPrompts[String(frame)]);
  check('SAM leaves other layers unchanged',other()===untouched);
  check('controlled empty mask retains visible points',!playbackCanvas.hidden&&$('#samStatus').textContent.includes('此帧不打码'));
  window.__nativeSuite?.observations.push({kind:'sam-zoom-attribution',calls,expected,controlledInference:true});
 }catch(e){errors.push(String(e));throw e}finally{
  window.fetch=originalFetch;samCapabilities=saved.cap;samWarmup=saved.warm;samRevision++;samRawRevision++;samClickPending=null;clearTimeout(previewTimer);invalidatePreview(true);
  seg.layers=saved.layers;seg.activeLayerId=saved.active;seg.frame=saved.frame;seg.download=saved.download;seg.exportNote=saved.exportNote;attachLayers(seg);clipSelected=saved.clip;selectSegment(seg,false);
  check('SAM fixture restores complete layer snapshot',JSON.stringify(seg.layers)===JSON.stringify(saved.layers));
 }
 return {checks,errors};
};

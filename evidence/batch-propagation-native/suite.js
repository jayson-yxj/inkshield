window.__suite={state:'running',checks:[],observations:[]};
window.runSuite=async function(){
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 const check=(name,value,detail)=>{__suite.checks.push({name,passed:!!value,detail});if(!value)throw Error(name+': '+JSON.stringify(detail))};
 const wait=async(fn,ms=45000)=>{const end=Date.now()+ms;while(Date.now()<end){if(fn())return;await sleep(40)}__suite.observations.push({timeout:String(fn),status:$('#samStatus').textContent,analyzing,clipSelected,settingsMode:settings.mode,layers:selectedSegment.layers,fixture:await state()});throw Error('Timeout '+fn)};
 const state=()=>fetch('/__fixture/state').then(r=>r.json());
 const reset=fail_at=>fetch('/__fixture/reset',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({fail_at})});
 const prompt=x=>({'0':[{x,y:100,label:1},{x:x+10,y:120,label:0}]});
 const fixture=async(count)=>{
  stopPlayback();invalidatePreview();
  const seg=selectedSegment,base=cloneSettings(settings);
  // Explicit controlled starting-state fixture. Actions under test are real DOM clicks.
  const layer=(id,mode,prompts={},ready=false,device='cpu')=>({id,name:id,enabled:true,analysisId:ready?'controlled-custom-a':'',analysisReady:ready,cachedThreshold:null,submittedThreshold:null,threshold:.5,samDeviceManual:true,settings:{...cloneSettings(base),mode,samPrompts:prompts,samDevice:device},playback:null,status:ready?'已分析':'待分析'});
  seg.layers=[layer('pending-a','custom',prompt(50)),layer('pending-b','custom',prompt(150),false,'cuda')];
  if(count===3)seg.layers.push(layer('pending-c','custom',prompt(220)));
  seg.layers.push(layer('ready','custom',prompt(80),true),layer('automatic','automatic'),layer('empty','custom'));
  seg.activeLayerId='empty';attachLayers(seg);selectSegment(seg,false);
  await wait(()=>!samClickRunning&&!samClickPending&&!busy());await sleep(150);
  return seg;
 };
 const run=async()=>{
  check('active empty custom can start batch',!$('#analyzeBtn').disabled,$('#analyzeBtn').textContent);
  const active=selectedSegment.activeLayerId;$('#analyzeBtn').click();await wait(()=>analyzing);
  check('busy gates editing',busy()&&$('#addLayerBtn').disabled&&$('#modeToggle').disabled&&[...document.querySelectorAll('.layer-select')].every(n=>n.disabled));
  $('#analyzeBtn').click();
  const samples=[];
  while(analyzing){samples.push({text:$('#progressMeta').textContent,value:$('#progressValue').textContent,dialog:$('#dialogProgress').textContent,active:selectedSegment.activeLayerId});if(samples.length>1100)throw Error('Batch timeout');await sleep(50)}
  __suite.observations.push({progress:samples});
  check('active layer unchanged during batch',samples.every(s=>s.active===active)&&selectedSegment.activeLayerId===active);
  check('progress has intermediate values',samples.some(s=>parseFloat(s.value)>0&&parseFloat(s.value)<100),samples);
  check('overall progress never decreases',samples.every((s,i)=>!i||parseFloat(s.value)>=parseFloat(samples[i-1].value)),samples);
  check('dialog identifies batch layer index',samples.some(s=>/传播第.*\//.test(s.dialog)),samples);
  return state();
 };
 await reset(null);let seg=await fixture(2);
 seg.layers[1].settings.samPrompts={'150':[{x:150,y:100,label:1}]};syncControls();$('#analyzeBtn').click();await sleep(250);
 check('invalid later layer prevents entire queue submission',(await state()).requests.length===0&&!analyzing);
 seg.layers[1].settings.samPrompts=prompt(150);syncControls();let r=await run();
 check('successful overall progress reaches 100',$('#progressValue').textContent==='100%');
 check('only two pending custom requests',r.requests.length===2,r);
 check('independent prompt and device payloads',JSON.stringify(r.requests[0].body.prompts)===JSON.stringify(prompt(50))&&r.requests[0].body.device==='cpu'&&JSON.stringify(r.requests[1].body.prompts)===JSON.stringify(prompt(150))&&r.requests[1].body.device==='cuda',r.requests);
 check('requests serial after previous terminal status',!r.overlap&&r.requests[1].at>=r.jobs[r.requests[0].job_id].terminal_at,r);
 check('independent result binding',seg.layers[0].analysisReady&&seg.layers[1].analysisReady&&seg.layers[0].analysisId!==seg.layers[1].analysisId,seg.layers);
 check('ready empty automatic skipped',seg.layers.find(l=>l.id==='ready').analysisId==='controlled-custom-a'&&!seg.layers.find(l=>l.id==='automatic').analysisReady&&!seg.layers.find(l=>l.id==='empty').analysisReady);
 await reset(2);seg=await fixture(3);r=await run();
 check('failure stops remaining queue',r.requests.length===2&&!r.overlap,r);
 check('failure preserves completed result and pending remainder',seg.layers[0].analysisReady&&!seg.layers[1].analysisReady&&!seg.layers[2].analysisReady,seg.layers);
 const kept=seg.layers[0].analysisId;
 // Keep fixture request history for retry: fail_at=2 only affects the previous request.
 r=await run();
 check('retry only pending layers',r.requests.length===4&&JSON.stringify(r.requests[2].body.prompts)===JSON.stringify(prompt(150))&&JSON.stringify(r.requests[3].body.prompts)===JSON.stringify(prompt(220)),r);
 check('retry preserves prior result',seg.layers[0].analysisId===kept&&seg.layers.slice(0,3).every(l=>l.analysisReady));
 check('busy released',!busy()&&!$('#addLayerBtn').disabled);
 __suite.observations.push({finalFixture:r});__suite.state='done';
};

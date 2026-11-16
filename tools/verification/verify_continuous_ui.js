'use strict';
const fs=require('fs');
let base=fs.readFileSync(__dirname+'/verify_segments_ui.js','utf8');base=base.slice(0,base.indexOf('async function main()'));
base=base.replace('const run=code=>',`Element.prototype.click=function(){if(!this.disabled)for(const fn of this.listeners.click||[])fn({target:this,preventDefault(){},stopPropagation(){}})};Element.prototype.getBoundingClientRect=function(){return {left:0,width:720}};const run=code=>`);
const tests=`
async function main(){
 run(html.match(/<script>([\\s\\S]*?)<\\/script>/)[1]);await tick();elements.get('#file').files=[{name:'whole.mp4'}];await run('importMedia()');
 run('seekGlobal(30)');elements.get('#splitBtn').click();run('seekGlobal(60)');elements.get('#splitBtn').click();
 // Explicit selection remains distinct from context and protects analysis/export/config.
 run('deselectClip()');assert.equal(run('clipSelected'),false);assert.equal(elements.get('#analyzeBtn').disabled,true);assert.equal(elements.get('#exportBtn').disabled,true);assert.equal(elements.get('#threshold').disabled,true);assert.ok(elements.get('#clipLane').children.every(x=>x['aria-pressed']==='false'));
 const inferBefore=calls.filter(x=>x.url.endsWith('/api/analyze')).length;await run('analyze()');assert.equal(calls.filter(x=>x.url.endsWith('/api/analyze')).length,inferBefore);
 run('selectSegment(segments[0]);seekGlobal(10)');assert.equal(run('clipSelected'),true);
 // Prepare mixed cached/raw/cached; production renderer receives each segment's own geometry/config.
 run("analysisReady=true;analysisId='a';playback={start_frame:0,frames:30,fps:25,width:10,height:10,shapes:Array.from({length:30},()=>[])};settings.style='black';settings.targets=['plate'];saveSegment();segments[2].analysisReady=true;segments[2].analysisId='c';segments[2].settings.style='blur';segments[2].playback={start_frame:60,frames:41,fps:25,width:10,height:10,shapes:Array.from({length:41},()=>[])};deselectClip();seekGlobal(10)");
 const video=elements.get('#source');let playCalls=0;video.play=async()=>{playCalls++};video.currentTime=10/25;
 const inference=calls.filter(x=>x.url.endsWith('/api/analyze')).length;await run('startContinuousPlayback()');assert.equal(playCalls,1);assert.equal(run('playing'),true);assert.equal(run('continuousMode'),true);assert.equal(video.hidden,true);assert.equal(run('clipSelected'),false);
 const active=run('selectedSegment.id');run('renderContinuous(29/25)');assert.equal(run('globalFrame'),29);assert.ok(elements.get('#previewMode').textContent.includes('已分析'));
 run('renderContinuous(30/25)');assert.equal(run('globalFrame'),30);assert.ok(elements.get('#previewMode').textContent.includes('未遮罩'));assert.equal(video.hidden,true);
 run('renderContinuous(60/25)');assert.equal(run('globalFrame'),60);assert.ok(elements.get('#previewMode').textContent.includes('已分析'));assert.equal(run('selectedSegment.id'),active);assert.equal(run('settings.style'),'black');assert.equal(run('segments[2].settings.style'),'blur');assert.equal(calls.filter(x=>x.url.endsWith('/api/analyze')).length,inference);assert.equal(playCalls,1);
 // Browser EOF sets fullsource terminal frame, not activecontext end30.
 await video.fire('ended');assert.equal(run('playing'),false);assert.equal(run('globalFrame'),100);assert.equal(run('continuousMode'),false);
 // Clicking a clip restores selected-only path; timeline drag clears actual highlighting.
 run('selectSegment(segments[1]);seekGlobal(40)');assert.equal(run('clipSelected'),true);await run('startRawPlayback()');assert.equal(run('playing'),true);run('stopPlayback()');
 const plane=elements.get('#timelinePlane');const e={target:plane,button:0,pointerId:3,clientX:100,preventDefault(){}};plane.listeners.pointerdown[0](e);assert.equal(run('clipSelected'),true);assert.equal(run('selectedSegment.start <= globalFrame && globalFrame < selectedSegment.end'),true);plane.listeners.pointercancel[0](e);
 // Passive surfaces clear selection; controls and busy tasks retain it.
 for(const functional of [true,false]){run('selectSegment(segments[1])');context.backgroundTarget={closest:()=>functional?{}:null};run('handleWorkspaceBackgroundClick({target:backgroundTarget})');assert.equal(run('clipSelected'),functional)}
 run('selectSegment(segments[1]);analyzing=true');context.backgroundTarget={closest:()=>null};run('handleWorkspaceBackgroundClick({target:backgroundTarget})');assert.equal(run('clipSelected'),true);run('analyzing=false');
 // Invalid cache fails closed and clears old overlay rather than exposing raw analyzed frames.
 run("selectSegment(segments[0]);deselectClip();segments[0].playback={start_frame:0,frames:30,fps:25,width:10,height:10,shapes:[]};playback=segments[0].playback;globalFrame=0");await run('startContinuousPlayback()');assert.equal(run('playing'),false);assert.equal(elements.get('#playbackCanvas').hidden,true);assert.equal(video.hidden,true);assert.ok(elements.get('#previewFeedback').textContent.includes('停止'));
 // Delayed geometry cannot be assigned after cancel or explicit selection changes.
 run("segments[0].playback=null;playback=null;globalFrame=0");let finish;const originalFetch=context.fetch;context.fetch=async(url,opts)=>{if(url.includes('/api/playback/'))return new Promise(resolve=>{finish=()=>resolve({ok:true,json:async()=>({start_frame:0,frames:30,fps:25,width:10,height:10,shapes:Array.from({length:30},()=>[])})})});return originalFetch(url,opts)};
 const pending=run('startContinuousPlayback()');await tick();assert.equal(run('startingPlayback'),true);assert.equal(elements.get('#playPause').disabled,false);assert.equal(elements.get('#playPause').textContent,'取消准备');run('stopPlayback()');assert.ok(elements.get('#previewFeedback').textContent.includes('已取消'));finish();await pending;assert.equal(run('segments[0].playback'),null);assert.equal(run('playing'),false);context.fetch=originalFetch;
 run('analyzing=true');const prior=run('clipSelected');run('deselectClip();selectSegment(segments[2])');assert.equal(run('clipSelected'),prior);await run('startContinuousPlayback()');assert.equal(run('playing'),false);run('analyzing=false');
 // Export uses shared mute at click time despite later preview changes.
 assert.equal(elements.has('#exportMuted'),false);
 const beforeExportFetch=context.fetch;context.exportSnapshot=null;run('pollExport=async(job,token,snapshot)=>{exportSnapshot=snapshot;exporting=false}');
 for(const muted of [true,false]){run('selectSegment(segments[1]);analysisReady=true;analysisId="shared-audio";previewMuted='+muted);let finishExport;context.fetch=async(url,opts)=>{if(url.includes('/api/export/')){calls.push({url,body:opts.body.data});return new Promise(resolve=>{finishExport=()=>resolve({ok:true,status:200,json:async()=>({job_id:"shared-export"})})})}return beforeExportFetch(url,opts)};const exportingNow=elements.get('#exportBtn').fire('click');await tick();const payload=calls.filter(c=>c.url.includes('/api/export/')).at(-1).body;assert.equal(payload.muted,String(muted));elements.get('#previewMute').click();assert.equal(run('previewMuted'),!muted);finishExport();await exportingNow;assert.equal(context.exportSnapshot.muted,muted)}context.fetch=beforeExportFetch;
 console.log('CONTINUOUS PASS: shared mute frozen export payload,  explicit selection and disabled actions, mixed cached/raw boundaries, original persegment settings, no inference, single source play across clips, source hidden, EOF, selected playback, ruler deselect, invalidcache failclosed, stale payload cancellation, cancel preparation, busyguards');
}
main().catch(e=>{console.error(e);process.exitCode=1});`;
const watchdog=setTimeout(()=>{console.error('Continuous suite did not settle');process.exitCode=1},1500);
new Function('require','__dirname','watchdog',base+tests.replace("main().catch(e=>{console.error(e);process.exitCode=1});","main().then(()=>clearTimeout(watchdog)).catch(e=>{clearTimeout(watchdog);console.error(e);process.exitCode=1});")) (require,__dirname,watchdog);

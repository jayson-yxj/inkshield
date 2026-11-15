'use strict';
// Reuse the existing mock definitions verbatim, extending only browser geometry/events.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
let base=fs.readFileSync(__dirname+'/verify_segments_ui.js','utf8');
base=base.slice(0,base.indexOf('async function main()'));
base=base.replace("const fs=require('fs'),vm=require('vm'),assert=require('assert');",'');
base=base.replace("const html=fs.readFileSync(require('path').join(__dirname,'index.html'),'utf8');", "const html=fs.readFileSync(require('path').join(__dirname,'index.html'),'utf8');");
base=base.replace('const run=code=>',`Element.prototype.getBoundingClientRect=function(){return {left:100-(this.scrollLeft||elements.get('#timelineScroll').scrollLeft||0),width:720}};
Element.prototype.setPointerCapture=function(id){this.capture=id};Element.prototype.releasePointerCapture=function(){this.capture=null};
Element.prototype.click=function(){if(!this.disabled)for(const fn of this.listeners.click||[])fn({target:this,preventDefault(){},stopPropagation(){}})};
elements.get('#timelineScroll').clientWidth=720;elements.get('#timelineScroll').scrollLeft=0;
const run=code=>`);
base=base.replace("document:{querySelector:","document:{listeners:{},querySelector:");
base=base.replace("createElement:()=>new Element(),addEventListener(){}", "createElement:()=>new Element(),addEventListener(type,fn){(this.listeners[type]??=[]).push(fn)}");
const tests=`
async function main(){
 run(html.match(/<script>([\\s\\S]*?)<\\/script>/)[1]);await tick();
 elements.get('#file').files=[{name:'timeline.mp4'}];await run('importMedia()');
 assert.equal(calls.filter(c=>c.url.endsWith('/api/analyze')).length,0);
 assert.equal(run('timelineWidth()'),720);assert.equal(elements.get('#clipLane').children.length,1);
 run('seekGlobal(40)');assert.equal(run('globalFrame'),40);elements.get('#splitBtn').click();
 assert.equal(run('JSON.stringify(segments.map(s=>[s.start,s.end]))'),'[[0,40],[40,101]]');assert.equal(run('globalFrame'),40);
 assert.equal(parseFloat(elements.get('#clipLane').children[0].style.width),40/101*720);
 // Selecting a clip clamps to its nearest boundary instead of restoring arbitrary old local frame.
 run('seekGlobal(75);selectSegment(segments[0])');assert.equal(run('globalFrame'),39);
 run('seekGlobal(70)');assert.equal(run('selectedSegment.start'),40);assert.equal(Number(elements.get('#frameSlider').value),30);assert.equal(elements.get('#source').currentTime,70/25);
 run('stepFrame(-31)');assert.equal(run('globalFrame'),39);assert.equal(run('selectedSegment.start'),0);
 // Cache/config state survives a split and undo; children never share their targets arrays.
 run("settings.style='black';settings.targets=['plate'];analysisId='cached-original';analysisReady=true;cachedThreshold=.5;playback={start_frame:0,frames:40,fps:25,width:10,height:10,shapes:Array.from({length:40},()=>[])};seekGlobal(20)");
 elements.get('#splitBtn').click();assert.equal(run('segments.length'),3);assert.equal(run('analysisReady'),false);
 run("settings.targets.push('eyes');undoSplit()");assert.equal(run('segments.length'),2);assert.equal(run('analysisId'),'cached-original');assert.equal(run('analysisReady'),true);assert.equal(run('settings.style'),'black');assert.equal(run('settings.targets.join()'),'plate');assert.equal(run('globalFrame'),20);
 // Editing an unaffected B after splitting A must survive undo of A.
 run('seekGlobal(10)');elements.get('#splitBtn').click();run("seekGlobal(80);settings.style='blur';settings.strength=87;analysisId='new-B';analysisReady=true;$('#download').hidden=false;$('#download').href='http://localhost/newB';undoSplit();seekGlobal(80)");assert.equal(run('settings.strength'),87);assert.equal(run('analysisId'),'new-B');assert.equal(elements.get('#download').href,'http://localhost/newB');run('seekGlobal(10)');
 // A later edit to a restored object cannot corrupt older split snapshots.
 run("settings.strength=93;seekGlobal(10)");elements.get('#splitBtn').click();run('undoSplit()');assert.equal(run('settings.strength'),93);
 run('seekGlobal(-500)');assert.equal(run('globalFrame'),0);run('seekGlobal(9999)');assert.equal(run('globalFrame'),100);
 run('stepFrame(1)');assert.equal(run('globalFrame'),100);run('stepFrame(-1)');assert.equal(run('globalFrame'),99);
 run('zoomTimeline(4,460)');assert.equal(run('timelineWidth()'),2880);assert.equal(elements.get('#timelineScroll').scrollLeft,1080);assert.equal(run('clipSelected'),true);
 elements.get('#timelineScroll').scrollLeft=1000;assert.equal(run('pointerFrame({clientX:100})'),Math.floor(1000/2880*101));
 const plane=elements.get('#timelinePlane'),event={target:plane,button:0,pointerId:5,clientX:200,preventDefault(){}};
 await plane.listeners.pointerdown[0](event);assert.equal(run('timelineDrag'),5);assert.equal(plane.capture,5);assert.equal(run('clipSelected'),true);assert.equal(run('selectedSegment.start <= globalFrame && globalFrame < selectedSegment.end'),true);
 await plane.listeners.pointermove[0]({...event,clientX:-9999});assert.equal(run('globalFrame'),0);
 await plane.listeners.pointercancel[0](event);assert.equal(run('timelineDrag'),null);
 run('analyzing=true');const old=run('globalFrame');run('seekGlobal(75);undoSplit()');assert.equal(run('globalFrame'),old);run('analyzing=false');
 // Keyboard split/undo uses global playhead and excludes editable inputs.
 run('selectSegment(segments[1]);seekGlobal(80)');const keys=context.document.listeners.keydown;const key={target:{tagName:'DIV'},ctrlKey:true,key:'b',preventDefault(){}};for(const fn of keys)fn(key);assert.equal(run('segments.length'),3);for(const fn of keys)fn({...key,key:'z'});assert.equal(run('segments.length'),2);
 const count=run('segments.length');for(const fn of keys)fn({...key,target:{tagName:'INPUT'}});assert.equal(run('segments.length'),count);
 await run('importMedia()');assert.equal(run('splitHistory.length'),0);assert.equal(run('timelineZoom'),1);
 // Keyboard-generated clip clicks carry clientX=0; select that clip instead of seeking frame0.
 run('seekGlobal(40)');elements.get('#splitBtn').click();run('seekGlobal(15)');const keyboardClip=elements.get('#clipLane').children[1];keyboardClip.listeners.click[0]({detail:0,clientX:0,stopPropagation(){}});assert.equal(run('selectedSegment.start'),40);assert.equal(run('globalFrame'),40);
 console.log('TIMELINE PASS: fullsource geometry, global seek/clamp, proportional clips, boundary stepping, selection, split/undo cache and settings isolation, zoom, scroll coordinates, pointer capture/cancel, busy guards, keyboard edit guard, metadata-only import/reset');
 // The previous segment suite expected restoring local12 on clip selection. Fullsource selection
 // now clamps the global playhead to the clicked clip; adapt only that explicit semantic assertion.
 const legacy=fs.readFileSync(__dirname+'/verify_segments_ui.js','utf8').replace(\"assert.equal(elements.get('#frameSlider').value,'12')\",\"assert.equal(elements.get('#frameSlider').value,'0')\");
 new Function('require','__dirname',legacy)(require,__dirname);
}
main().catch(e=>{console.error(e);process.exitCode=1});`;
new Function('require','__dirname','fs','vm','assert',base+tests)(require,__dirname,fs,vm,assert);

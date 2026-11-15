/* Draft against owner1dd WIP; integration state prevents running until freeze. */
window.__layersAdapter={
  state(){return JSON.parse(JSON.stringify(window.inkshieldLayers.getState()))},
  button(text){const e=[...document.querySelectorAll('#layerPanel button')].find(b=>b.textContent.trim()===text);if(!e||e.disabled)throw Error('Missing/enabled layer button '+text);return e},
  async addCustom(){this.button('+ 自定义层').click();await __dom.pause(150);return selectedSegment.activeLayerId},
  async select(index){const e=document.querySelectorAll('#layerPanel button[aria-pressed]')[index];if(!e||e.disabled)throw Error('Missing layer '+index);e.click();await __dom.pause(150)},
  regionSelector(layerId){return '.timeline-mask[data-layer-id="'+CSS.escape(layerId)+'"]'},
  bindActive(analysisId){
    // Fixture exception: identities/readiness only, never settings, bounds or layers.
    const l=selectedSegment.layers.find(l=>l.id===selectedSegment.activeLayerId);
    l.analysisId=analysisId;l.analysisReady=true;l.playback=null;l.status='已分析';
    attachLayers(selectedSegment);selectSegment(selectedSegment,false);
  },
  async bootstrap(){await __dom.wait(()=>!!window.inkshieldLayers);this.bindActive('controlled-auto');await __dom.wait(()=>analysisReady&&!!playback)},
  async triple(){await this.addCustom();this.bindActive('controlled-custom-a');await __dom.wait(()=>analysisReady);await this.addCustom();this.bindActive('controlled-custom-b');await __dom.wait(()=>analysisReady);__dom.check('three DOM-created layers',selectedSegment.layers.length===3);return this.state()},
  payload(){return JSON.parse(JSON.stringify(stackPayload(selectedSegment)))},
  snapshot(){return {frame:globalFrame,activeLayerId:selectedSegment?.activeLayerId,layers:this.state(),samDisplayed,playing,startingPlayback,continuousMode,sourceEnded:source.ended,protectedEnded:protectedVideo.ended,sourceTime:source.currentTime,protectedTime:protectedVideo.currentTime,protectedHidden:protectedVideo.hidden,protectedActive:protectedActive?{segment:protectedActive.seg?.id}:null}}
};

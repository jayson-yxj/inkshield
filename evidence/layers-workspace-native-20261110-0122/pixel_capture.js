window.captureFrozenLayerPixels=async function(d,a){
 window.__pixelPayload=a.payload();window.__jpegPixels=[];
 for(const frame of [0,19,20,39,40,59,60,80,99,100,119,120,139,140,149]){
  await d.frame(frame);await d.wait(()=>!preview.hidden&&preview.complete&&preview.naturalWidth===320,30000);await d.pause(100);
  const shot=d.image();d.check('JPEG visible frame '+frame,shot.element===preview.id&&globalFrame===frame,shot.element);
  __nativeImages.push({name:'jpeg-'+frame,...shot});__jpegPixels.push({frame,name:'jpeg-'+frame+'.png'});
 }
};

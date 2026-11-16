'use strict';
const assert = require('node:assert/strict');
const { zoomAt, clampPan } = require('../../src/inkshield/web/workspace_ui.js');
let checks = 0;
function near(actual, expected) { assert.ok(Math.abs(actual - expected) < 1e-8, `${actual} != ${expected}`); checks++; }
for (const initial of [{ zoom: 1, x: 0, y: 0 }, { zoom: 3, x: -130, y: 80 }]) {
  for (const zoom of [1, 2, 5, 8, 100, .1]) {
    const result = zoomAt(initial, zoom, 120, -70);
    near((120 - result.x) / result.zoom, (120 - initial.x) / initial.zoom);
    near((-70 - result.y) / result.zoom, (-70 - initial.y) / initial.zoom);
    assert.ok(result.zoom >= 1 && result.zoom <= 8); checks++;
  }
}
assert.deepEqual(clampPan({ zoom: 1, x: 200, y: -200 }, 800, 600, 1920, 1080), { zoom: 1, x: 0, y: -0 }); checks++;
assert.deepEqual(clampPan({ zoom: 2, x: 9999, y: -9999 }, 800, 600, 1920, 1080), { zoom: 2, x: 400, y: -150 }); checks++;
// Reproduce the host's exact contain/SAM calculation on a transformed element.
for (const [vw, vh, iw, ih] of [[800, 600, 1920, 1080], [600, 800, 1080, 1920]]) {
  for (const zoom of [1, 2.75, 8]) {
    const tx = -42, ty = 31, fit = Math.min(vw / iw, vh / ih);
    const rect = { left: 100 + vw / 2 - vw * zoom / 2 + tx, top: 60 + vh / 2 - vh * zoom / 2 + ty, width: vw * zoom, height: vh * zoom };
    const scale = Math.min(rect.width / iw, rect.height / ih), width = iw * scale, height = ih * scale;
    const left = rect.left + (rect.width - width) / 2, top = rect.top + (rect.height - height) / 2;
    for (const [px, py] of [[0, 0], [646.25, 218.25], [iw - 1, ih - 1]]) {
      const clientX = 100 + vw / 2 + tx + (px - iw / 2) * fit * zoom;
      const clientY = 60 + vh / 2 + ty + (py - ih / 2) * fit * zoom;
      near((clientX - left) / width * iw, px); near((clientY - top) / height * ih, py);
    }
  }
}
console.log(`PASS ${checks} preview geometry assertions (focal zoom, limits, pan clamp, transformed SAM coordinates)`);

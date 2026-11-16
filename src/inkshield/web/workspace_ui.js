/* Preview transforms and pane visibility. Load after the editor's main script.
 * SAM contract: getBoundingClientRect() already includes this uniform transform;
 * retain the existing object-fit:contain calculation, without a second inverse.
 * Host: listen for workspace:layoutsettled to renderTimeline once per toggle.
 */
(() => {
  'use strict';
  const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));
  function zoomAt(state, next, x, y) {
    next = clamp(next, 1, 8);
    const ratio = next / state.zoom;
    return { zoom: next, x: x - (x - state.x) * ratio, y: y - (y - state.y) * ratio };
  }
  function clampPan(state, width, height, imageWidth, imageHeight) {
    const fit = Math.min(width / imageWidth, height / imageHeight);
    const mx = Math.max(0, (imageWidth * fit * state.zoom - width) / 2);
    const my = Math.max(0, (imageHeight * fit * state.zoom - height) / 2);
    return { zoom: state.zoom, x: clamp(state.x, -mx, mx), y: clamp(state.y, -my, my) };
  }
  // Pure geometry is exported only in Node for the owned regression tests.
  if (typeof module !== 'undefined' && module.exports) module.exports = { zoomAt, clampPan };
  if (typeof document === 'undefined') return;
  function init() {
    const viewer = document.getElementById('viewer'), workspace = document.getElementById('editorWorkspace');
    if (!viewer || !workspace || document.getElementById('previewTransform')) return;
    const stage = workspace.querySelector('.stage');
    const layer = document.createElement('div');
    layer.id = 'previewTransform';
    viewer.prepend(layer);
    const layerSelector = '#source,#preview,#playbackCanvas,#protectedPlayback,#samOverlay,#samoverlay';
    function moveLayers() {
      viewer.querySelectorAll(layerSelector).forEach(node => { if (node.parentElement !== layer) layer.append(node); });
    }
    moveLayers();
    new MutationObserver(moveLayers).observe(viewer, { childList: true });
    let state = { zoom: 1, x: 0, y: 0 }, drag = null, space = false, hovering = false, suppressClick = false;
    const custom = () => document.getElementById('customMode')?.getAttribute('aria-pressed') === 'true';
    const mediaNode = () => [...layer.querySelectorAll('video,img,canvas')].find(node => !node.hidden && !['samOverlay', 'samoverlay'].includes(node.id));
    const toolbar = document.createElement('div');
    toolbar.className = 'workspace-view-tools';
    toolbar.setAttribute('role', 'group');
    toolbar.setAttribute('aria-label', '预览视图与工作区');
    stage.querySelector('.stage-bar').after(toolbar);
    function button(id, text, title) {
      const node = document.createElement('button');
      node.type = 'button'; node.id = id; node.className = 'secondary'; node.textContent = text; node.title = title;
      toolbar.append(node); return node;
    }
    const resetButton = button('previewZoomReset', '100% · 复位', '复位预览缩放和平移；也可双击预览画面');
    const hint = document.createElement('span'); hint.id = 'previewNavigationHint'; hint.className = 'preview-navigation-hint';
    hint.textContent = '滚轮缩放 · 空格＋左拖 / 中键平移 · 双击复位';
    toolbar.append(hint);
    viewer.setAttribute('aria-describedby', 'previewNavigationHint');
    viewer.tabIndex = 0;
    viewer.title = '滚轮缩放 1–8 倍；自定义模式左键添加点，空格＋左拖或中键平移；自动模式可左拖；双击复位';
    function paint() {
      const node = mediaNode(), width = viewer.clientWidth, height = viewer.clientHeight;
      if (node && width && height) {
        const iw = node.videoWidth || node.naturalWidth || node.width || width;
        const ih = node.videoHeight || node.naturalHeight || node.height || height;
        state = clampPan(state, width, height, iw, ih);
      }
      // All layers may be briefly hidden while a decoded frame is exchanged.
      // Preserve the view through that hand-off; file changes explicitly reset it.
      layer.style.transform = `translate(${state.x}px, ${state.y}px) scale(${state.zoom})`;
      resetButton.textContent = `${Math.round(state.zoom * 100)}% · 复位`;
      viewer.classList.toggle('preview-can-pan', state.zoom > 1 && (!custom() || space));
      hint.textContent = custom() ? '左键点选 · 滚轮缩放 · 空格＋左拖 / 中键平移 · 按钮复位' : '滚轮缩放 · 左拖 / 中键平移 · 双击复位';
      viewer.title = custom() ? '滚轮缩放 1–8 倍；左键添加提示点，空格＋左拖或中键平移；使用上方复位按钮' : '滚轮缩放 1–8 倍；左键或中键拖动平移；双击复位';
    }
    function reset() { state = { zoom: 1, x: 0, y: 0 }; paint(); }
    resetButton.addEventListener('click', reset);
    viewer.addEventListener('wheel', event => {
      if (!mediaNode()) return;
      event.preventDefault(); event.stopPropagation();
      const rect = viewer.getBoundingClientRect(), unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? rect.height : 1;
      state = zoomAt(state, state.zoom * Math.exp(-clamp(event.deltaY * unit, -400, 400) * .002), event.clientX - rect.left - rect.width / 2, event.clientY - rect.top - rect.height / 2);
      paint();
    }, { passive: false });
    viewer.addEventListener('pointerenter', () => { hovering = true; });
    viewer.addEventListener('pointerleave', () => { hovering = false; });
    const editable = target => target?.closest?.('input,textarea,select,button,a,summary,[contenteditable]:not([contenteditable="false"]),dialog');
    document.addEventListener('keydown', event => {
      if (event.code !== 'Space' || editable(event.target) || (!hovering && document.activeElement !== viewer && !drag)) return;
      space = true; event.preventDefault(); event.stopImmediatePropagation(); paint();
    }, true);
    document.addEventListener('keyup', event => {
      if (event.code !== 'Space' || !space) return;
      space = false; event.preventDefault(); event.stopImmediatePropagation(); paint();
    }, true);
    viewer.addEventListener('pointerdown', event => {
      // Clear a stale suppression on a new deliberate gesture, never on pointerup.
      suppressClick = false;
      if (editable(event.target) || !mediaNode() || !(event.button === 1 || (event.button === 0 && (space || !custom())))) return;
      if (state.zoom <= 1 && event.button === 0 && !space) return;
      event.preventDefault(); event.stopImmediatePropagation();
      drag = { id: event.pointerId, x: event.clientX, y: event.clientY, start: { ...state } };
      suppressClick = true;
      viewer.setPointerCapture(event.pointerId); viewer.classList.add('preview-panning');
    }, true);
    viewer.addEventListener('pointermove', event => {
      if (!drag || drag.id !== event.pointerId) return;
      event.preventDefault(); event.stopImmediatePropagation();
      state = { zoom: drag.start.zoom, x: drag.start.x + event.clientX - drag.x, y: drag.start.y + event.clientY - drag.y }; paint();
    }, true);
    function finish(event, cancel = false) {
      if (!drag || (event?.pointerId != null && event.pointerId !== drag.id)) return;
      const previous = drag; drag = null;
      if (cancel) state = previous.start;
      if (viewer.hasPointerCapture(previous.id)) viewer.releasePointerCapture(previous.id);
      viewer.classList.remove('preview-panning'); paint();
    }
    viewer.addEventListener('pointerup', event => finish(event), true);
    viewer.addEventListener('pointercancel', event => finish(event, true), true);
    viewer.addEventListener('lostpointercapture', event => finish(event), true);
    window.addEventListener('blur', () => { finish(null, true); space = false; paint(); });
    viewer.addEventListener('click', event => {
      if (!suppressClick && !space) return;
      event.preventDefault(); event.stopImmediatePropagation(); suppressClick = false;
    }, true);
    viewer.addEventListener('auxclick', event => { if (event.button === 1) { event.preventDefault(); event.stopImmediatePropagation(); } }, true);
    viewer.addEventListener('dblclick', event => {
      // Custom mode treats each click as a SAM prompt. Its explicit reset button
      // avoids turning a double prompt into an unrelated view reset.
      if (custom() || editable(event.target)) return;
      event.preventDefault(); event.stopImmediatePropagation(); reset();
    }, true);
    viewer.addEventListener('dragstart', event => event.preventDefault());
    document.getElementById('file')?.addEventListener('change', reset);
    new ResizeObserver(paint).observe(viewer);
    new MutationObserver(paint).observe(layer, { subtree: true, attributes: true, attributeFilter: ['hidden', 'width', 'height', 'src'] });
    layer.addEventListener('loadedmetadata', paint, true); layer.addEventListener('load', paint, true);
    document.getElementById('customMode') && new MutationObserver(paint).observe(document.getElementById('customMode'), { attributes: true, attributeFilter: ['aria-pressed'] });

    workspace.classList.add('workspace-ui-ready');
    let settleTimer = 0, layoutPending = false;
    function settled() {
      if (!layoutPending) return;
      layoutPending = false; clearTimeout(settleTimer); paint();
      workspace.dispatchEvent(new CustomEvent('workspace:layoutsettled', { bubbles: true }));
    }
    function scheduleSettled() {
      layoutPending = true; clearTimeout(settleTimer);
      settleTimer = setTimeout(settled, matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 280);
    }
    workspace.addEventListener('transitionend', event => {
      if (event.target === workspace && ['grid-template-columns', 'grid-template-rows'].includes(event.propertyName)) settled();
    });
    const paneSpecs = [
      ['media', '.media-panel', 'mediaResize', 'toggleMediaPanel', '素材库'],
      ['inspector', '.controls', 'inspectorResize', 'toggleInspectorPanel', '检查器'],
      ['timeline', '.timeline', 'timelineResize', 'toggleTimelinePanel', '时间线']
    ];
    const panes = paneSpecs.map(([key, selector, splitterId, buttonId, label]) => {
      const panel = workspace.querySelector(selector), splitter = document.getElementById(splitterId);
      if (!panel.id) panel.id = `workspace-${key}-panel`;
      const toggle = button(buttonId, `收起${label}`, `收起${label}面板；再次点击可展开`);
      toggle.setAttribute('aria-label', `收起${label}面板`);
      toggle.setAttribute('aria-controls', panel.id); toggle.setAttribute('aria-expanded', 'true');
      function setCollapsed(collapsed) {
        if (collapsed && panel.contains(document.activeElement)) toggle.focus();
        workspace.classList.toggle(`workspace-${key}-collapsed`, collapsed);
        panel.inert = collapsed; panel.setAttribute('aria-hidden', String(collapsed));
        splitter.inert = collapsed; splitter.setAttribute('aria-hidden', String(collapsed));
        const action = collapsed ? '展开' : '收起';
        toggle.setAttribute('aria-expanded', String(!collapsed));
        toggle.textContent = `${action}${label}`;
        toggle.setAttribute('aria-label', `${action}${label}面板`);
        toggle.title = `${action}${label}面板；${collapsed ? '恢复工作区面板' : '再次点击可展开'}`;
        scheduleSettled();
      }
      toggle.addEventListener('click', () => setCollapsed(toggle.getAttribute('aria-expanded') === 'true'));
      return { setCollapsed };
    });
    document.getElementById('resetLayout')?.addEventListener('click', () => panes.forEach(pane => pane.setCollapsed(false)));
    window.inkshieldWorkspaceUI = Object.freeze({ resetPreview: reset, getPreviewState: () => ({ ...state }) });
    paint();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();

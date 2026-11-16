"""Lightweight playback endpoint contract tests; no model invocation."""

import sys as _tool_sys
from pathlib import Path as _ToolPath
_TOOL_ROOT = _ToolPath(__file__).resolve().parents[2]
for _tool_path in (_TOOL_ROOT / 'src', _TOOL_ROOT / 'tools/verification'):
    if str(_tool_path) not in _tool_sys.path:
        _tool_sys.path.insert(0, str(_tool_path))

from pathlib import Path
import threading
from fastapi.testclient import TestClient
from inkshield import server

with TestClient(server.app) as client:
    job='playback-contract-test'
    head=(0,0,100,100,.9,7)
    eye_a=(20,30,32,38,.9,17)
    eye_b=(56,40,68,48,.9,17)
    boxes=((head,eye_a,eye_b),(head,eye_a),())
    analysis=server.Analysis(Path('unused.mp4'),boxes,100,100,30.)
    server.new_job(job,'analysis',state='ready')
    server.ANALYSES[job]=analysis
    def forbidden():
        raise AssertionError('playback called inference')
    server.get_detector=forbidden
    response=client.get('/api/playback/'+job)
    assert response.status_code==200,response.text
    data=response.json()
    assert data['frames']==3 and data['fps']==30 and data['width']==100
    eyes=[s for s in data['shapes'][0] if s[-1]==17]
    assert len(eyes)==1 and eyes[0][0]=='rectangle'
    assert [s for s in data['shapes'][1] if s[-1]==17][0][0]=='ellipse'
    assert data['shapes'][2]==[]
    assert client.get('/api/playback/missing').status_code==404
    server.new_job('pending','analysis')
    assert client.get('/api/playback/pending').status_code==409
    for _ in range(server.MAX_ACTIVE_PREVIEWS):server.PREVIEW_SLOTS.acquire()
    try:assert client.get('/api/playback/'+job).status_code==429
    finally:
        for _ in range(server.MAX_ACTIVE_PREVIEWS):server.PREVIEW_SLOTS.release()
    print('PLAYBACK CONTRACT PASS: paired/single/empty frames, class IDs, readiness, admission, zero inference')

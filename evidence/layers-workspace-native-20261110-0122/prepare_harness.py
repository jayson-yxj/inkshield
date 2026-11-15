"""One-time preparation of an owned copy, never modifies production files."""
from pathlib import Path
import hashlib, json
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
old = ROOT / 'evidence/effect-track-native-20261110-0054/verify_mask_timeline_native.py'
s = old.read_text(encoding='utf-8')
s = s.replace('Isolated real Windows WebView2 mask-timeline acceptance', 'Isolated real Windows WebView2 layers/workspace acceptance')
a = s.index('    mask = np.zeros((240, 320), np.uint8)')
b = s.index('    sock = socket.socket()', a)
s = s[:a] + '''    from controlled_fixtures import install
    install(server, source)
''' + s[b:]
s = s.replace("for required in ['index.html','server.py','preview_video.py','sam_service.py','mask_timeline.py','sam_engine.py']:", "for required in ['index.html','server.py','preview_video.py','sam_service.py','mask_timeline.py','mask_layers.py','sam_engine.py']:")
s = s.replace("    suite = args.suite.read_text(encoding='utf-8')", '''    contract = json.loads((OUT/'integration.json').read_text(encoding='utf-8-sig'))
    assert contract['state'] == 'frozen', 'Integration pending: owner selectors and fixture binding must be frozen'
    for name in contract['source_files']:
        assert name in frozen, 'Freeze missing UI dependency '+name
    for name, expected in contract['acceptance_hashes'].items():
        assert sha(OUT/name) == expected, 'Acceptance dependency changed '+name
    assert all(contract['selectors'].values()), 'Missing owner selector'
    assert contract['backend_sam_over_five_evidence'], 'Missing backend SAM >5 evidence reference'
    assert (OUT/'frozen_adapter.js').is_file(), 'Owner-specific DOM adapter not finalized'
    adapter = (OUT/'frozen_adapter.js').read_text(encoding='utf-8')
    suite = args.suite.read_text(encoding='utf-8')''')
s = s.replace("'hashes':frozen,'suite_sha256':sha(args.suite),'passed':False}", "'hashes':frozen,'suite_sha256':sha(args.suite),'integration':contract,'input_method':'Synthetic DOM PointerEvent/WheelEvent; not OS input','passed':False}")
a = s.index('                # Controlled analysis identity injection only')
b = s.index('                js(suite)', a)
s = s[:a] + '''                # Only readiness/analysis identities may be injected by owner-reviewed adapter.
                js('window.__integration='+json.dumps(contract))
                js(adapter)
                js("window.__fixtureBoot='running';Promise.resolve(__layersAdapter.bootstrap()).then(()=>__fixtureBoot='done').catch(e=>{__fixtureBoot=String(e.stack||e)})")
                wait("__fixtureBoot==='done'",30)
''' + s[b:]
a = s.index("                    expected_codec = 'h264'")
b = s.index('                screenshots=js(', a)
s = s[:a] + '''                    expected_codec = asset.get('codec','h264' if asset['name'].endswith('protected') else 'mpeg4')
                    assert next(s['codec'] for s in decoded['streams'] if s['type']=='video') == expected_codec, decoded['streams']
                    assert decoded['frames']==asset['frames'], decoded
                    from pixel_oracle import validate_asset
                    report.setdefault('pixel_checks',[]).append(validate_asset(destination, asset, OUT))
                assert len(assets)>=2, 'DOM suite must publish protected H264 and export'
''' + s[b:]
s = s.replace("'dependencies':['av','numpy','PIL','webview'],", "'dependencies':['av','numpy','PIL','webview'],'integration_state':json.loads((OUT/'integration.json').read_text(encoding='utf-8'))['state'],")
(OUT/'verify_mask_timeline_native.py').write_text(s,encoding='utf-8')
(OUT/'harness-provenance.json').write_text(json.dumps({'source':str(old),'source_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),'changes':['distinct face/custom-a/custom-b fixtures','frozen integration and adapter gate','multi ROI artifact oracle hook','per-asset frame count','explicit synthetic input disclosure'],'execution':'not run'},indent=2),encoding='utf-8')
print('Prepared isolated harness copy:', OUT)

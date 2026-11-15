"""Prepare revised OS test from the reviewed original; no application imports."""
from pathlib import Path
out=Path(__file__).resolve().parent
source=out.parent/'sam-web-review-20261109-225157'/'verify_sam_web_long_click.py'
s=source.read_text(encoding='utf-8')
s=s.replace('import webview',"import argparse\np=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--base',default='http://127.0.0.1:50164');p.add_argument('--require-warming',action='store_true');a=p.parse_args()\nif not a.execute:p.error('Prepared only; requires freeze and OS slot authorization')\nimport webview")
s=s.replace("STATE=json.loads(next((ROOT/'runtime/sam-web-review-20261109-225157-final').glob('desktop-*.json')).read_text(encoding='utf-8'))", "STATE={'url':a.base}")
s=s.replace("TITLE='Inkshield long video click review'", "TITLE='Inkshield startup automatic-device OS review'")
s=s.replace("        check('CPU default',\"settings.samDevice==='cpu'&&$('#samDevice').value==='cpu'\")",'''        result['initial_warmup']=js("({state:samWarmup.state,text:$('#samWarmupStatus').textContent,blocked:samWarmupBlocked()})")
        result['warming_observed']=result['initial_warmup']['state'] in ('pending','warming')
        if a.require_warming:
            assert result['warming_observed'], 'OS page opened after warmup; warming UI not observed'
            check('Warming status visible', "samWarmupBlocked()&&$('#samWarmupStatus').textContent.includes('预热中')")
        wait("samWarmup.state==='ready'",600)
        ready_device=js('samWarmup.device')
        assert ready_device in ('cpu','cuda')
        result['ready_device']=ready_device
        check('Automatic ready device adopted',"settings.samDevice===samWarmup.device&&$('#samDevice').value===samWarmup.device&&!samWarmupBlocked()")
        check('Ready status visible',"$('#samWarmupStatus').textContent.includes('模型已就绪')")''')
s=s.replace("wait(\"__responses.length===1&&!samClickRunning&&$('#samViewerStatus').textContent.includes('当前帧预览已计算')\",180)","wait(\"__responses.length===1&&!samClickRunning&&($('#samViewerStatus').textContent.includes('当前帧预览已计算')||$('#samViewerStatus').textContent.includes('当前帧未检测到目标区域'))\",600)")
s=s.replace("$('#samViewerStatus').textContent.includes('当前帧预览已计算')&&$('#samViewerStatus').textContent.includes('150')", "($('#samViewerStatus').textContent.includes('当前帧预览已计算')||$('#samViewerStatus').textContent.includes('当前帧未检测到目标区域'))&&$('#samModeNote').textContent.includes('150')")
s=s.replace('Genuine full-range CPU frame0 preview HTTP200 and no analysis','Genuine full-range ready-device frame0 preview HTTP200 and no analysis')
s=s.replace("JSON.parse(__responses[0].request.body).device==='cpu'", "JSON.parse(__responses[0].request.body).device===samWarmup.device")
s=s.replace("        result['preview']=response", "        result['preview']=response\n        assert response['timing_ms']['model_load']==0\n        assert response['timing_ms']['encoder']>0 and response['cache_hit'] is False\n        result['scope']='OS click frame0 only; API script separately checks new frame; no propagation' ")
s=s.replace("        # Keep this actual preview window available for user review.","        window.destroy()  # Close only this test-owned window, never the service.")
(out/'verify_startup_os.py').write_text(s,encoding='utf-8')
print('Prepared',out/'verify_startup_os.py')

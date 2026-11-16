
import sys as _tool_sys
from pathlib import Path as _ToolPath
_TOOL_ROOT = _ToolPath(__file__).resolve().parents[2]
for _tool_path in (_TOOL_ROOT / 'src', _TOOL_ROOT / 'tools/verification'):
    if str(_tool_path) not in _tool_sys.path:
        _tool_sys.path.insert(0, str(_tool_path))

from pathlib import Path
from html.parser import HTMLParser
import re
class Check(HTMLParser):
 def __init__(self):super().__init__();self.ids=[];self.stack=[]
 def handle_starttag(self,tag,attrs):
  attrs=dict(attrs)
  if 'id' in attrs:self.ids.append(attrs['id'])
p=(_TOOL_ROOT / 'src/inkshield/web/index.html');s=p.read_text(encoding='utf-8');c=Check();c.feed(s)
assert len(c.ids)==len(set(c.ids)),'duplicate IDs'
script=s.split('<script>',1)[1].split('</script>',1)[0]
for ident in re.findall(r"\$\('#([\w-]+)'\)",script):assert ident in c.ids,ident
assert s.count('<aside')==s.count('</aside>')==2
assert s.count('<section')==s.count('</section>')==2
assert s.count('<div')==s.count('</div>'),(s.count('<div'),s.count('</div>'))
assert all('data-value="'+t+'"' in s for t in ('face','plate'))
assert all('data-value="'+t+'"' not in s for t in ('head','eyes','nose','mouth','ears'))
assert 'function renderPlayback(time,context=null)' in script and 'function stepFrame(delta)' in script
(_TOOL_ROOT / 'runtime').mkdir(exist_ok=True)
(_TOOL_ROOT / 'runtime').joinpath('editor-script.js').write_text(script,encoding='utf-8')
print('EDITOR STRUCTURE PASS: unique IDs, all script references, balanced layout tags, face/plate targets and transport functions')

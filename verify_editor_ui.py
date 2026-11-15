from pathlib import Path
from html.parser import HTMLParser
import re
class Check(HTMLParser):
 def __init__(self):super().__init__();self.ids=[];self.stack=[]
 def handle_starttag(self,tag,attrs):
  attrs=dict(attrs)
  if 'id' in attrs:self.ids.append(attrs['id'])
p=Path(__file__).with_name('index.html');s=p.read_text(encoding='utf-8');c=Check();c.feed(s)
assert len(c.ids)==len(set(c.ids)),'duplicate IDs'
script=s.split('<script>',1)[1].split('</script>',1)[0]
for ident in re.findall(r"\$\('#([\w-]+)'\)",script):assert ident in c.ids,ident
assert s.count('<aside')==s.count('</aside>')==2
assert s.count('<section')==s.count('</section>')==2
assert s.count('<div')==s.count('</div>'),(s.count('<div'),s.count('</div>'))
assert all('data-value="'+t+'"' in s for t in ('face','plate'))
assert all('data-value="'+t+'"' not in s for t in ('head','eyes','nose','mouth','ears'))
assert 'function renderPlayback(time,context=null)' in script and 'function stepFrame(delta)' in script
Path(__file__).with_name('runtime').mkdir(exist_ok=True)
Path(__file__).with_name('runtime').joinpath('editor-script.js').write_text(script,encoding='utf-8')
print('EDITOR STRUCTURE PASS: unique IDs, all script references, balanced layout tags, face/plate targets and transport functions')

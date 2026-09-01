# -*- coding: utf-8 -*-
"""מפצל את הערכים למנות לתיוג. כל סוכן קורא מנה אחת בלבד."""
import io, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
E = json.load(io.open(os.path.join(ROOT, 'search-index.json'), encoding='utf-8'))['entries']

BATCH = 50
MAX_CHARS = 2600     # מספיק כדי להבין על מה הערך, בלי להעמיס טוקנים

out_dir = os.path.join(HERE, 'batches')
os.makedirs(out_dir, exist_ok=True)
for f in os.listdir(out_dir):
    os.remove(os.path.join(out_dir, f))

n = 0
for b in range(0, len(E), BATCH):
    chunk = []
    for e in E[b:b+BATCH]:
        body = ' ⟡ '.join(e['d'])
        body = re.sub(r'\s+', ' ', body).strip()
        chunk.append({'id': e['i'], 'term': e['t'],
                      'text': body[:MAX_CHARS] + ('…' if len(body) > MAX_CHARS else '')})
    p = os.path.join(out_dir, f'batch-{b//BATCH:02d}.json')
    json.dump(chunk, io.open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    n += 1
print(f'{len(E)} ערכים -> {n} מנות של עד {BATCH}')
print('גודל ממוצע למנה: %.0f KB' % (sum(os.path.getsize(os.path.join(out_dir,f)) for f in os.listdir(out_dir))/n/1024))

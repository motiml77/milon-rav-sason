# -*- coding: utf-8 -*-
"""
בונה רשימת מועמדים לאוצר המושגים — מתוך הקורפוס עצמו, בלי LLM.

הרעיון: שמות הערכים שהמחבר כתב *הם* אוצר המושגים של התחום. מושג שחוזר
כראש-כותרת בכמה ערכים, או שהוא מילה נדירה-ומבחינה בגוף, הוא מועמד טוב.
"""
import io, json, os, re
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
E = json.load(io.open(os.path.join(ROOT, 'search-index.json'), encoding='utf-8'))['entries']

SOF = {'ך':'כ','ם':'מ','ן':'נ','ף':'פ','ץ':'צ'}
def norm(s):
    s = re.sub(r'[\u0591-\u05c7]', '', s or '')
    return ''.join(SOF.get(c, c) for c in s)
def toks(s):
    return [w for w in re.split(r'[^\u05d0-\u05ea0-9a-z]+', norm(s).lower()) if len(w) >= 3]

# ── מועמדים א׳: ראש-הכותרת (החלק שלפני המקף) ──
heads = Counter()
for e in E:
    h = re.split(r'\s*[–—]\s*', e['t'])[0].strip()
    h = re.sub(r'^["\u05f4\'\u05f3]+|["\u05f4\'\u05f3]+$', '', h).strip()
    if 2 <= len(h) <= 34:
        heads[h] += 1

# ── מועמדים ב׳: מילים מבחינות — נדירות מספיק כדי להעיד, נפוצות מספיק כדי לקשר ──
df = Counter()
for e in E:
    for w in set(toks(e['t'] + ' ' + ' '.join(e['d']))):
        df[w] += 1
N = len(E)
disc = [(w, c) for w, c in df.items() if 4 <= c <= N * 0.12]
disc.sort(key=lambda x: -x[1])

out = {
    'note': 'מועמדים לאוצר מושגים. LLM יקבע מהם את הרשימה הקנונית הסופית.',
    'from_titles': [{'term': k, 'entries': v} for k, v in heads.most_common() if v >= 2],
    'discriminative_tokens': [{'token': w, 'df': c} for w, c in disc[:400]],
}
dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vocab-candidates.json')
json.dump(out, io.open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'ראשי-כותרת שחוזרים (>=2 ערכים): {len(out["from_titles"])}')
print(f'מילים מבחינות (df 4..{int(N*0.12)}):  {len(out["discriminative_tokens"])}')
print('דוגמאות ראשים:', ', '.join(x['term'] for x in out['from_titles'][:12]))
print('דוגמאות מילים:', ', '.join(x['token'] for x in out['discriminative_tokens'][:14]))

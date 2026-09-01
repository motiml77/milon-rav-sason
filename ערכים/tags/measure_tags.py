# -*- coding: utf-8 -*-
"""
מודד אם התיוג תפס מבנה אמיתי — מול ההפניות שהמחבר כתב בעצמו.

ההיגיון: אם התגיות משקפות קרבה רעיונית, זוגות ערכים שהמחבר קישר חייבים
לחלוק תגיות הרבה יותר מזוגות אקראיים. אם לא — התיוג נכשל ואין לשלוח אותו.

    python "ערכים/tags/measure_tags.py"
"""
import io, json, os, random, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TAGS = os.path.join(HERE, 'entry-tags.json')
if not os.path.exists(TAGS):
    sys.exit('אין entry-tags.json — הרץ קודם את התיוג.')

tags = {k: set(v) for k, v in json.load(io.open(TAGS, encoding='utf-8'))['tags'].items()}
E = json.load(io.open(os.path.join(ROOT, 'search-index.json'), encoding='utf-8'))['entries']
by_id = {e['i']: e for e in E}

# זוגות שהמחבר קישר = אמת-מידה לקרבה רעיונית
pairs = []
import glob
for f in glob.glob(os.path.join(ROOT, 'entries', '*.json')):
    d = json.load(io.open(f, encoding='utf-8'))
    for r in d.get('related', []):
        if r in by_id and r != d['id'] and d['id'] in tags and r in tags:
            pairs.append((d['id'], r))

def jac(a, b):
    A, B = tags.get(a, set()), tags.get(b, set())
    return len(A & B) / max(1, len(A | B))

rnd = random.Random(11)
ids = [i for i in by_id if i in tags]
linked = [jac(a, b) for a, b in pairs]
rand = [jac(rnd.choice(ids), rnd.choice(ids)) for _ in range(6000)]
med = lambda v: sorted(v)[len(v)//2] if v else 0
avg = lambda v: sum(v)/len(v) if v else 0

print(f'ערכים מתויגים: {len(tags)}/{len(E)}')
cnt = Counter(len(v) for v in tags.values())
print('תגיות לערך:', dict(sorted(cnt.items())))
use = Counter(t for v in tags.values() for t in v)
print(f'מושגים בשימוש: {len(use)}   הנפוצים: ' +
      ', '.join(f'{t}({c})' for t, c in use.most_common(8)))
lonely = [t for t, c in use.items() if c == 1]
print(f'מושגים שהופיעו פעם אחת בלבד: {len(lonely)}  (לא מקשרים כלום)')

print()
print(f'זוגות מקושרים שנבדקו: {len(pairs)}')
print(f'  חפיפת תגיות ממוצעת — מקושרים: {avg(linked):.3f}')
print(f'  חפיפת תגיות ממוצעת — אקראיים: {avg(rand):.3f}')
ratio = avg(linked) / max(1e-9, avg(rand))
print(f'  ==> יחס: פי {ratio:.1f}')
print()
share = sum(1 for a, b in pairs if tags.get(a, set()) & tags.get(b, set()))
print(f'זוגות מקושרים שחולקים לפחות תגית אחת: {share}/{len(pairs)} ({share*100//max(1,len(pairs))}%)')
rshare = sum(1 for _ in range(2000) if tags.get(rnd.choice(ids), set()) & tags.get(rnd.choice(ids), set()))
print(f'זוגות אקראיים שחולקים לפחות תגית אחת:  {rshare*100//2000}%')
print()
print('הרף שקבעתי מראש: יחס >= 10 כדי לשלוח. מילולית היחס היום הוא פי 3.4.')
print('פסק דין:', 'עובר ✓' if ratio >= 10 else ('גבולי' if ratio >= 6 else 'נכשל ✗'))

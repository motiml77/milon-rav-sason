# -*- coding: utf-8 -*-
"""בדיקה מקיפה של הפניות "ראה ערך" — על כל הערכים וכל ההגדרות.

    python "ערכים/audit_refs.py"
"""
import io, json, os, re, sys
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import refs as R

raw = json.loads(re.search(r'=\s*(\{.*\})\s*;?\s*$',
    io.open(os.path.join(HERE,'data.js'), encoding='utf-8').read(), re.S).group(1))
terms = [t['term'] for s in raw['sections'] for t in s['terms']]
index = R.build_index(terms)
keys = sorted(index.keys(), key=len, reverse=True)

total = ok = 0
kinds, fails = Counter(), Counter()
per_entry = {}
for sec in raw['sections']:
    for t in sec['terms']:
        found = []
        for d in t['definition']:
            txt = R.plain(d)
            for m in R.TRIGGER.finditer(txt):
                total += 1
                tail = txt[m.end():m.end()+140]
                cut = R.STOP.search(tail)
                if cut: tail = tail[:cut.start()]
                name, via, kind = R.resolve(tail, index, keys)
                if name:
                    ok += 1; kinds[kind] += 1
                    if name != t['term'] and name not in found: found.append(name)
                else:
                    fails[tail.strip()[:70]] += 1
        per_entry[t['term']] = found

print(f'סה"כ אזכורי "ראה ערך":  {total}')
print(f'נפתרו:                  {ok}  ({ok*100//max(total,1)}%)')
print(f'  מדויק {kinds["exact"]} | תחילית {kinds["prefix"]} | תת-מחרוזת {kinds["contains"]}')
print(f'לא נפתרו:               {total-ok}')
linked = sum(1 for v in per_entry.values() if v)
print(f'\nערכים עם הפניות: {linked}/{len(per_entry)}   סה"כ קישורים: {sum(len(v) for v in per_entry.values())}')
if fails:
    print('\n--- לא נפתרו ---')
    for r, c in fails.most_common(30): print(f'  x{c}  {r}')

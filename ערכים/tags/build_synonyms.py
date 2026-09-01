# -*- coding: utf-8 -*-
"""
מפיק קבוצות מילים נרדפות לחיפוש, מתוך אוצר המושגים.

כל קבוצה = מושג קנוני + הניסוחים שמתייחסים אליו. משמש להרחבת שאילתה
בלבד: חיפוש "שכינה" יוכל למצוא גם ערכים שכתוב בהם "נוקבא".
"""
import io, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
V = json.load(io.open(os.path.join(HERE, 'vocabulary.json'), encoding='utf-8'))['concepts']

def clean(s):
    s = re.sub(r'\s+', ' ', (s or '')).strip()
    return s

groups, seen_terms = [], {}
skipped = []
for c in V:
    members = [clean(c['tag'])] + [clean(a) for a in c.get('aliases', [])]
    members = [m for m in members if 2 <= len(m) <= 26]
    # ניסוח שמופיע בשתי קבוצות שונות הוא דו-משמעי — מסירים אותו, אחרת
    # חיפוש אחד ימשוך שני מושגים שונים.
    uniq = []
    for m in members:
        if m in seen_terms and seen_terms[m] != c['tag']:
            skipped.append(m); continue
        seen_terms[m] = c['tag']
        if m not in uniq: uniq.append(m)
    if len(uniq) >= 2:
        groups.append(uniq)

dst = os.path.join(HERE, 'synonyms.json')
json.dump({'note': 'קבוצות ניסוחים לאותו מושג — להרחבת שאילתה בלבד', 'groups': groups},
          io.open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'קבוצות: {len(groups)}   ניסוחים סה"כ: {sum(len(g) for g in groups)}')
print(f'ניסוחים דו-משמעיים שהוסרו: {len(set(skipped))}' + (f'  {sorted(set(skipped))[:6]}' if skipped else ''))
print('גודל: %.0f KB' % (os.path.getsize(dst)/1024))
print('\nדוגמאות:')
for g in groups[:5]: print('   ' + '  ·  '.join(g[:7]))

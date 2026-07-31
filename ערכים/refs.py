# -*- coding: utf-8 -*-
"""
פותר הפניות "ראה ערך ..." — מקור אמת יחיד.

משמש גם את convert_to_milon.py (בפריסה) וגם את audit_refs.py (בבדיקה),
כדי שהבדיקה תמדוד בדיוק את מה שרץ בפועל.

הדו-משמעות המרכזית היא המקף:
    "ראה ערך יסוד דאבא - מרדכי"              -> השם המלא הוא שם הערך
    "ראה ערך פנימיות וחיצוניות - שם הסברנו"  -> השם הוא רק החלק שלפני המקף
לכן מנסים תמיד את החיתוך *הארוך ביותר* קודם, ויורדים בהדרגה.
"""
import re

HTML_TAG = re.compile(r'<[^>]+>')

# תגיות inline מוסרות בלי רווח — אחרת מילה שחלקה מודגשת
# (אור<strong>ות</strong>) נשברת לשתי מילים.
def plain(s):
    return re.sub(r'\s+', ' ', HTML_TAG.sub('', s or '')).strip()

def normalize_term(s):
    s = HTML_TAG.sub('', s or '')
    s = re.sub(r'[֑-ׇ]', '', s)
    for ch in '"״\'׳`':
        s = s.replace(ch, '')
    s = re.sub(r'\s+', ' ', s).strip()
    return s.strip('.,;:')

# "ראה ערך" / "וראה לעיל ערך" / "עיין ערך" / "וכן ערך" / "גם ערך"
TRIGGER = re.compile(
    r'(?:ו?(?:ראה|עיין)(?:\s+(?:לעיל|להלן|לקמן|בערך|עוד))*\s+ערך'
    r'|(?:וכן|גם)\s+(?:ראה\s+)?ערך)\s+'
)
# הפניה נגמרת בסוגר, נקודה-פסיק, או תחילת הפניה נוספת
STOP = re.compile(r'[\]\[;]|\.\s|(?=\s*(?:ו?(?:ראה|עיין)|וכן|גם)\s+(?:ראה\s+)?ערך)')

IGNORE = {'שם', 'לעיל', 'לקמן', 'להלן', 'שם שם', 'שם בהערה', ''}
SEPS = ['–', '—', ' - ', '־', ',', ':', '(', ')', '[', ']', ';', '.', '?', '!']
# סימוני עריכה שהמחבר משאיר לעצמו
EDITORIAL = re.compile(r'\?\?\*\*|\*\*|\?\?')


def build_index(terms):
    """שם ערך מנורמל -> השם המקורי. הראשון קובע במקרה כפילות."""
    idx = {}
    for t in terms:
        idx.setdefault(normalize_term(t), t)
    return idx


def candidates(after):
    """כל החיתוכים הסבירים של הטקסט שאחרי 'ראה ערך', מהארוך לקצר."""
    n = normalize_term(EDITORIAL.sub(' ', after))
    out, seen = [], set()

    def add(x):
        x = x.strip().strip('.,;:-–— ')
        if x and x not in seen:
            seen.add(x)
            out.append(x)

    add(n)
    for sep in SEPS:
        cur = n
        while sep in cur:
            cur = cur.rsplit(sep, 1)[0]
            add(cur)
    w = n.split()
    for k in range(len(w) - 1, 0, -1):
        add(' '.join(w[:k]))
    return out


def resolve(after, index, sorted_keys=None):
    """
    מחזיר (שם_ערך_מקורי, החיתוך_שהתאים, סוג_ההתאמה) או (None, None, None).
    סדר: התאמה מדויקת -> תחילית -> תת-מחרוזת ייחודית.
    """
    if sorted_keys is None:
        sorted_keys = sorted(index.keys(), key=len, reverse=True)
    cands = candidates(after)

    # 1. התאמה מדויקת, מהחיתוך הארוך לקצר
    for c in cands:
        if c in IGNORE:
            continue
        if c in index:
            return index[c], c, 'exact'

    # 2. ההפניה היא תחילית של שם ערך ארוך יותר (על גבול מילה)
    for c in cands:
        if c in IGNORE or len(c) < 2:
            continue
        pref = [k for k in sorted_keys
                if k == c or k.startswith(c + ' ') or k.startswith(c + '–') or k.startswith(c + '-')]
        if pref:
            pref.sort(key=len)          # הקצר ביותר = הקרוב ביותר לשם המבוקש
            return index[pref[0]], c, 'prefix'

    # 3. ההפניה מופיעה בתוך שם ערך אחד ויחיד (למשל "ענווה" -> "מידת הענווה")
    for c in cands:
        if c in IGNORE or len(c) < 3:
            continue
        hits = [k for k in sorted_keys if re.search(r'(?:^|\s)' + re.escape(c) + r'(?:$|\s|–|-)', k)]
        if len(hits) == 1:
            return index[hits[0]], c, 'contains'

    return None, None, None


def find_references(text, index, sorted_keys=None, current_term=None):
    """
    מאתר את *כל* אזכורי 'ראה ערך' בטקסט (בתוך סוגריים או לא) ומחזיר
    רשימת שמות ערכים מקוריים, ללא כפילויות וללא הפניה עצמית.
    """
    if sorted_keys is None:
        sorted_keys = sorted(index.keys(), key=len, reverse=True)
    txt = plain(text)
    out = []
    for m in TRIGGER.finditer(txt):
        tail = txt[m.end():m.end() + 140]
        cut = STOP.search(tail)
        if cut:
            tail = tail[:cut.start()]
        name, _, _ = resolve(tail, index, sorted_keys)
        if name and name != current_term and name not in out:
            out.append(name)
    return out

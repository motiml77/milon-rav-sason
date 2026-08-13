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


# ── מפתח מקופל: פיסוק->רווח, אותיות סופיות, תחילית עברית, כתיב מלא/חסר ──
# זה מה שמאפשר להתאים "לבושים" ל"לבושים, בגדים", "ענווה" ל"מידת הענווה",
# "שירה ורינה" ל"שירה, רינה", ו"נצוץ" ל"ניצוץ".
_SOF = {'ך': 'כ', 'ם': 'מ', 'ן': 'נ', 'ף': 'פ', 'ץ': 'צ'}
_PRE = 'הובלמשכ'

def _skel(w):
    return w if len(w) <= 2 else w[0] + re.sub(r'[יו]', '', w[1:-1]) + w[-1]

def _bare(w):
    return w[1:] if len(w) >= 4 and w[0] in _PRE else w

def fold_key(s):
    s = re.sub(r'[֑-ׇ]', '', s or '')
    for ch in ('"', '״', "'", '׳', '`'):
        s = s.replace(ch, '')
    s = ''.join(_SOF.get(c, c) for c in s)
    s = re.sub(r'[^\w\s֐-׿]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip().lower()
    return ' '.join(_skel(_bare(w)) for w in s.split())


def build_index(terms):
    """שם ערך מנורמל -> השם המקורי. הראשון קובע במקרה כפילות."""
    idx = {}
    for t in terms:
        idx.setdefault(normalize_term(t), t)
    return idx


def build_fold_index(terms):
    """מפתח מקופל -> שם ערך מקורי (הראשון קובע)."""
    idx = {}
    for t in terms:
        idx.setdefault(fold_key(t), t)
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
    # חיתוך מהסוף: "פנימיות וחיצוניות - שם הסברנו" -> "פנימיות וחיצוניות"
    for sep in SEPS:
        cur = n
        while sep in cur:
            cur = cur.rsplit(sep, 1)[0]
            add(cur)
    w = n.split()
    for k in range(len(w) - 1, 0, -1):
        add(' '.join(w[:k]))
    # חיתוך מההתחלה *לא* נעשה בכוונה: הוא מייצר התאמות שווא
    # (למשל "מקטרג - שליח בי\"ד" נתפס על "ביד" בשם ערך אחר לגמרי).
    # הארוך ביותר קודם — הוא הספציפי ביותר, ולכן הבטוח ביותר.
    out.sort(key=len, reverse=True)
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
    full = cands[0] if cands else ''
    for c in cands:
        if c in IGNORE or len(c) < 3:
            continue
        hits = [k for k in sorted_keys if re.search(r'(?:^|\s)' + re.escape(c) + r'(?:$|\s|–|-)', k)]
        if len(hits) != 1:
            continue
        # שבר גנרי באמצע שם ארוך יוצר התאמות שווא ("שנה", "בי\"ד", "אבא ואמא").
        # מקבלים רק שבר משמעותי, או שבר שהוא *כל* ההפניה וגם סוף שם הערך.
        if len(c) >= 10 or (c == full and hits[0].endswith(c)):
            return index[hits[0]], c, 'contains'

    # 4. התאמה על המפתח המקופל — פיסוק, ה' הידיעה, ו' החיבור, כתיב מלא/חסר
    fold_idx = _FOLD_CACHE.get(id(index))
    if fold_idx is None:
        fold_idx = build_fold_index(index.values())
        _FOLD_CACHE[id(index)] = fold_idx
    fold_keys = sorted(fold_idx.keys(), key=len)
    for c in cands:
        if c in IGNORE or len(c) < 3:
            continue
        fk = fold_key(c)
        if not fk:
            continue
        if fk in fold_idx:
            return fold_idx[fk], c, 'folded'
        pref = [k for k in fold_keys if k.startswith(fk + ' ')]
        if pref:
            return fold_idx[pref[0]], c, 'folded'
        inner = [k for k in fold_keys
                 if re.search(r'(?:^|\s)' + re.escape(fk) + r'(?:$|\s)', k)]
        if len(inner) == 1 and (len(fk) >= 10 or (c == cands[0] and inner[0].endswith(fk))):
            return fold_idx[inner[0]], c, 'folded'
    return None, None, None


_FOLD_CACHE = {}


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

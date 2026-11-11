# -*- coding: utf-8 -*-
"""
ממיר את data.js (פלט convert_docx_hierarchical.py) לפורמט שמצופה ע"י milon.html.

עיקרי השינוי:
- sections -> topics, name -> title (+ subtitle ריק), terms -> entries
- definition: ["טקסט [מקור]"]  ->  definitions: [{text, source}]
- מפצל את ציון המקור הסופי [..] מהטקסט (רק [..] שאינו עטוף ב-<span class="text-small">)
- מזהה הפניות [ראה ערך X] בתוך טקסט ההגדרות וממלא את שדה related
- שומר על תגיות HTML (<strong>, <u>, <span class="text-small">) כפי שהן
"""
import json
import re
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refs as _R

INPUT_JS = os.path.join(os.path.dirname(__file__), "data.js")
OUTPUT_JSON = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data.json")

# ---------- קריאת data.js ----------
with open(INPUT_JS, encoding="utf-8") as f:
    content = f.read().strip()

# הסרת "const rawData = " ו-";" בסוף
m = re.match(r'^const\s+\w+\s*=\s*', content)
if m:
    content = content[m.end():]
content = content.rstrip().rstrip(";")

raw = json.loads(content)

# ---------- פיצול מקור ----------
SOURCE_REGEX = re.compile(r'\s*\[([^\[\]]+)\]\s*$')
SPAN_OPEN = re.compile(r'<span\b[^>]*>')
SPAN_CLOSE = re.compile(r'</span>')
HTML_TAG = re.compile(r'<[^>]+>')

def split_source(text):
    """
    מחלץ את ציון המקור [..] מסוף הטקסט.
    מחזיר (text_without_source, source).
    אם [..] בסוף עטוף ב-<span> שטרם נסגר -> אינו מקור (חלק מתוכן).
    """
    if not text:
        return text, ""
    text = text.rstrip()
    m = SOURCE_REGEX.search(text)
    if not m:
        return text, ""
    pos = m.start()
    before = text[:pos]
    if len(SPAN_OPEN.findall(before)) != len(SPAN_CLOSE.findall(before)):
        return text, ""
    source = m.group(1).strip()
    text_only = text[:pos].rstrip()
    return text_only, source

# ---------- זיהוי הפניות [ראה ערך X] ----------
# לוכד גושים בסוגריים מרובעים שמכילים "ראה ערך" / "עיין ערך" (אחרי הסרת תגיות HTML)
BRACKET_REF = re.compile(r'\[([^\[\]]*?(?:ראה|עיין)[^\[\]]*?ערך[^\[\]]*?)\]')

# trigger בתוך גוש: גם "ראה ערך X", גם "וכן ערך X", גם "עיין ערך X"
# המילים המקדימות: ראה / וראה / ראה לעיל/לקמן/להלן / עיין / ועיין / וכן
TRIGGER = re.compile(
    r'(?:'
    r'ו?(?:ראה|עיין)(?:\s+(?:לעיל|להלן|לקמן|בערך|עוד))*\s+ערך'
    r'|'
    r'(?:וכן|גם)\s+(?:ראה\s+)?ערך'
    r')\s+'
    r'([^;\]]+?)(?=\s*(?:;|$))'
)

# ביטויי "אחרי-שם" שצריך לחתוך מסוף שם הערך
TRAILING_PHRASES = re.compile(
    r'\s*(?:'
    r'בהערה\s+שם|בהערה|שם\s+בפירוש[^,]*|בפירוש\s+הראשון|'
    r'שם\s+מבואר[^,]*|שם\s+יש\s+ערך[^,]*|שם\s+בה?ע[ר][ך][^,]*|'
    r'\.[^.]*$'
    r')\s*$'
)

# מילים שאם זה כל השם - להתעלם (לא הפניה לערך)
IGNORE_REFS = {'שם', 'שם שם', 'לעיל', 'לקמן', 'להלן'}

def normalize_term(s):
    """נירמול לצורך השוואת שמות ערכים: ללא תגיות, ללא ניקוד/טעמים, ללא גרשיים, רווחים מאוחדים."""
    s = HTML_TAG.sub('', s)
    s = re.sub(r'[֑-ׇ]', '', s)  # ניקוד וטעמי מקרא
    s = s.replace('"', '').replace('״', '').replace("'", '').replace('׳', '').replace('`', '')
    s = re.sub(r'\s+', ' ', s).strip()
    s = s.strip('.,;:')
    return s

def trim_trailing(s):
    """חותך ביטויי 'בהערה שם', '. שם...' וכד' מסוף השם."""
    prev = None
    while prev != s:
        prev = s
        s = TRAILING_PHRASES.sub('', s).strip(' .,;:')
    return s

def lookup(ref_name, term_index, term_index_norm):
    """
    מנסה למצוא ערך מתאים. סדר העדיפויות:
    1. התאמה מדויקת
    2. התאמה אחרי חיתוך ביטויי-זנב
    3. השם הוא prefix מדויק של ערך קיים (עם '–' או רווח אחרי)
    4. ערך קיים הוא prefix של השם (זה פחות בטוח אבל עוזר לשמות מורחבים)
    """
    if not ref_name or ref_name in IGNORE_REFS:
        return None

    # 1
    tid = term_index.get(ref_name)
    if tid:
        return tid

    # 2
    trimmed = trim_trailing(ref_name)
    if trimmed and trimmed != ref_name:
        tid = term_index.get(trimmed)
        if tid:
            return tid
        ref_name = trimmed

    if ref_name in IGNORE_REFS:
        return None

    # 3 — ההפניה היא תחילית של ערך קיים (= ההפניה קצרה מהערך)
    # נחפש ערכים שמתחילים ב-"<ref> – " או "<ref> "
    candidates = []
    for k, v in term_index.items():
        if k == ref_name:
            return v
        if k.startswith(ref_name + ' – ') or k.startswith(ref_name + ' -'):
            candidates.append((len(k), v))
    if len(candidates) == 1:
        return candidates[0][1]
    if candidates:
        # בוחר את הקצר ביותר (הכי קרוב לשם המבוקש)
        candidates.sort()
        return candidates[0][1]

    # 4 — ערך קיים הוא תחילית של ההפניה (ההפניה ארוכה יותר ומפרטת)
    candidates = []
    for k, v in term_index.items():
        if ref_name.startswith(k + ' – ') or ref_name.startswith(k + ' -') or ref_name.startswith(k + '.'):
            candidates.append((-len(k), v))  # שלילי כדי להעדיף את הארוך ביותר
    if candidates:
        candidates.sort()
        return candidates[0][1]

    return None

UNDERLINE = re.compile(r'<u\b[^>]*>(.*?)</u>', re.DOTALL)
UNDERLINE_MERGE = re.compile(r'</u>\s*<u\b[^>]*>')

# רגקס שמאתר תבנית [...] בתחילת הטקסט, גם אם עטופה ב-spans חיצוניים/פנימיים
LEADING_BRACKET = re.compile(
    r'^\s*'
    r'((?:<span\b[^>]*>\s*)*)'                 # פתיחות span חיצוניות (אופציונלי)
    r'\['
    r'((?:[^\[\]]|<[^>]+>)*?)'                 # תוכן הסוגריים, יכול להכיל spans פנימיים
    r'\]'
    r'((?:\s*</span>)*)'                        # סגירות span חיצוניות
    r'[\s.,;:]*'
)

# רגקס לזיהוי ציטוטים תחומים בגרשיים: ": "...long content..."" ארוך מ-60 תווים.
# מטפל בגרשיים פנימיים בתוך קיצורים עבריים (כמו הוי"ה, אדה"ר):
# בקיצורים אלה הגרשיים מוקפות באותיות, לא ברווחים. לכן:
# - "פותחות" של ציטוט: לפני הגרשיים יש רווח/נקודתיים/פתיחת-תג
# - "סוגרות" של ציטוט: אחרי הגרשיים יש סימן פיסוק/רווח/סגירת-תג
# - גרשיים בקיצור (כמו ה-" באמצע "הא"ס") נבלעות בתוכן (לפני: אות, אחרי: אות)
QUOTE_INLINE = re.compile(
    r'(?<=[\s:>])'                  # לפני הגרשיים: רווח / נקודתיים / סגירת-תג HTML
    r'"'
    r'((?:[^"]|"(?![\s.,;:<]|$))+?)'  # תוכן: לא-גרשיים, או גרשיים שאחריה כל דבר חוץ מפיסוק (כלומר באמצע מילה / בתוך attribute HTML / קיצור עברי)
    r'"'
    r'(?=[\s.,;:<]|$)',              # אחרי הגרשיים: פיסוק / רווח / פתיחת-תג / סוף
    re.DOTALL
)
QUOTE_MIN_WORDS = 30  # סף מינימלי במספר מילים בתוך הציטוט (לפי plain text)

def wrap_long_quotes(html):
    """עוטף ציטוטים ארוכים '"..."' ב-<span class="quote"> אם בתוכם לפחות 30 מילים."""
    if not html or '"' not in html:
        return html

    def repl(m):
        content = m.group(1)
        # אם התוכן כבר עטוף ב-quote - אל תכפיל
        if 'class="quote"' in content:
            return m.group(0)
        # ספירת מילים ב-plain text (תוכן ללא תגיות HTML)
        plain = HTML_TAG.sub(' ', content)
        word_count = len([w for w in plain.split() if w.strip()])
        if word_count < QUOTE_MIN_WORDS:
            return m.group(0)
        return f'<span class="quote">"{content}"</span>'

    return QUOTE_INLINE.sub(repl, html)

def strip_leading_reference(html):
    """
    אם טקסט ההגדרה מתחיל ב-[ראה ערך X] או [עיין ערך X] (גם אם עטוף ב-<span>),
    מסיר את הסוגריים מהטקסט (ההפניה כבר נמצאת ב-related).
    """
    if not html:
        return html
    m = LEADING_BRACKET.match(html)
    if not m:
        return html
    inner_plain = HTML_TAG.sub('', m.group(2))
    # רק אם זו אכן הפניה (מכילה "ראה ערך" או "עיין ערך")
    if not re.search(r'(?:ראה|עיין)\s*[^.]*?\s*ערך', inner_plain):
        return html
    rest = html[m.end():].lstrip()
    return rest

def lookup_strict(ref_name, term_index):
    """התאמה מדויקת בלבד — לאיתותים פחות אמינים כמו קו תחתון."""
    if not ref_name or ref_name in IGNORE_REFS:
        return None
    return term_index.get(ref_name)

def extract_references(text, term_index, current_id):
    """
    מאתר תבניות [ראה ערך X] (התאמה גמישה) ועוד טקסטים בקו תחתון <u>X</u> שמתאימים בדיוק לשם ערך.
    מחזיר רשימת IDs ייחודיים של ערכים שאליהם יש הפניה (לא כולל הערך הנוכחי עצמו).
    """
    if not text:
        return []

    # --- (1) הפניות [ראה ערך X] ---
    plain = HTML_TAG.sub('', text)
    plain = re.sub(r'\s+', ' ', plain)

    found = []
    for bracket_content in BRACKET_REF.findall(plain):
        for chunk in re.split(r';', bracket_content):
            for m in TRIGGER.finditer(chunk):
                ref_name = normalize_term(m.group(1))
                tid = lookup(ref_name, term_index, None)
                if tid and tid != current_id and tid not in found:
                    found.append(tid)

    # --- (2) טקסטים עם קו תחתון <u>...</u> ---
    # מאחד <u>X</u><u>Y</u> רצופים לרוץ אחד (לפי הדוגמאות, Word מפצל לרצים נפרדים)
    merged = UNDERLINE_MERGE.sub('', text)
    for m in UNDERLINE.finditer(merged):
        content = m.group(1)
        # אם זה ארוך מדי - כנראה לא שם ערך אלא ציטוט/הדגשה ארוכה
        if len(content) > 80:
            continue
        ref = normalize_term(content)
        # סינון של "מקפים" וכד'
        if not ref or len(ref) < 2 or ref in {'–', '-', '—', '...'}:
            continue
        tid = lookup_strict(ref, term_index)
        if tid and tid != current_id and tid not in found:
            found.append(tid)

    return found

# ====================================================================
# ---------- מזהים יציבים בין עדכוני וורד ----------
# ====================================================================
# בעבר המזהה היה מספר סידורי לפי מקום במסמך, ולכן הוספת ערך אחד באמצע
# הזיזה את כל המזהים אחריו — וכל סימניה או קישור ששותף הצביע פתאום על
# ערך אחר. כאן המזהה נקבע לפי *שם הערך* דרך מפה שנשמרת בריפו.
ID_MAP_PATH = os.path.join(os.path.dirname(__file__), "id-map.json")

def _norm_key(term):
    """מפתח זיהוי לערך: שם מנורמל, עמיד לשינויי רווחים/ניקוד/פיסוק."""
    k = re.sub(r'[֑-ׇ]', '', term or '')
    k = re.sub(r'[^\w\s\u0590-\u05ff]', ' ', k)
    return re.sub(r'\s+', ' ', k).strip().lower()

def load_id_map():
    if not os.path.exists(ID_MAP_PATH):
        return {"next": 1, "byTerm": {}}
    with open(ID_MAP_PATH, encoding="utf-8") as f:
        m = json.load(f)
    m.setdefault("next", 1)
    m.setdefault("byTerm", {})
    return m

def _content_sig(first_def):
    """חתימת תוכן של ערך: תחילת ההגדרה הראשונה, אותיות בלבד."""
    txt, _src = split_source(first_def or "")
    txt = HTML_TAG.sub('', txt or "")
    return re.sub(r'[^0-9A-Za-z֐-׿]+', '', txt)[:120]


def _retired_pool(by_term, live_keys):
    """
    ערכים שהיו באתר בריצה הקודמת ושמם אינו מופיע עוד בוורד — מועמדים ל'שינוי שם'.
    קוראים אותם מ-entries/<id>.json, שעדיין מכיל את הפלט של הריצה הקודמת.
    """
    ent_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'entries')
    live_ids = {by_term[k] for k in live_keys if k in by_term}
    pool, pooled = [], set()
    for key, eid in by_term.items():
        if key in live_keys or eid in live_ids or eid in pooled:
            continue
        pooled.add(eid)
        path = os.path.join(ent_dir, eid + '.json')
        if not os.path.exists(path):
            continue                      # נעלם כבר לפני כמה ריצות — אין עם מה להשוות
        try:
            with open(path, encoding='utf-8') as f:
                old = json.load(f)
        except (OSError, ValueError):
            continue
        defs = old.get("definitions") or []
        pool.append({"key": key, "id": eid, "term": old.get("term", ""),
                     "fold": _R.fold_key(old.get("term", "")),
                     "sig": _content_sig(defs[0].get("text", "") if defs else "")})
    return pool


def _find_rename(term, first_def, pool):
    """
    האם הערך ה'חדש' הזה הוא בעצם ערך קיים ששמו שונה? מחזיר רשומה מה-pool או None.
    מקבלים רק זיהוי חד-משמעי:
      1. אותו שם אחרי קיפול פיסוק/רווחים/ו' החיבור
      2. אותה הגדרה ראשונה (התוכן לא השתנה, רק הכותרת)
      3. שם אחד הוא הרחבה של השני — ורק אם יש מועמד יחיד כזה
    """
    fold = _R.fold_key(term)
    sig = _content_sig(first_def)
    strong = [p for p in pool if (fold and p["fold"] == fold) or (len(sig) >= 40 and p["sig"] == sig)]
    if len(strong) == 1:
        return strong[0]
    if strong:
        return None
    ext = [p for p in pool if fold and p["fold"] and
           (p["fold"].startswith(fold + ' ') or fold.startswith(p["fold"] + ' '))]
    return ext[0] if len(ext) == 1 else None


def assign_stable_ids(raw_sections):
    """
    ממפה כל ערך למזהה קבוע. מחזיר (id_map, stats).
    ערך שכבר קיבל מזהה בעבר — שומר אותו. ערך ששמו שונה בוורד (אבל הוא אותו ערך)
    יורש את המזהה הישן, כדי שסימניות וקישורים לא יישברו. ערך חדש באמת מקבל את
    המספר הפנוי הבא. מספר של ערך שנמחק לא ממוחזר לעולם.
    """
    m = load_id_map()
    by_term = m["byTerm"]
    used = set(by_term.values())
    kept = added = 0
    occ = {}
    todo = []                 # (key, term)
    for section in raw_sections:
        for term in section["terms"]:
            base = _norm_key(term["term"])
            if not base:
                continue
            # שמות שחוזרים כשני ערכים נפרדים — ממספרים אותם
            occ[base] = occ.get(base, 0) + 1
            key = base if occ[base] == 1 else f"{base}#{occ[base]}"
            todo.append((key, term))
    seen_keys = {k for k, _ in todo}
    pool = _retired_pool(by_term, seen_keys)
    renamed = []
    for key, term in todo:
        if key in by_term:
            kept += 1
            continue
        defs = term.get("definition") or []
        hit = _find_rename(term["term"], defs[0] if defs else "", pool)
        if hit:
            pool.remove(hit)
            del by_term[hit["key"]]            # המפתח הישן עובר, לא משתכפל
            by_term[key] = hit["id"]
            renamed.append((hit["term"], term["term"], hit["id"]))
            continue
        while f"t_{m['next']}" in used:
            m["next"] += 1
        by_term[key] = f"t_{m['next']}"
        used.add(by_term[key])
        m["next"] += 1
        added += 1
    retired = [k for k in by_term if k not in seen_keys]
    return m, {"kept": kept, "added": added, "retired": len(retired),
               "renamed": renamed, "gone": [p["term"] for p in pool]}

_id_map, _id_stats = assign_stable_ids(raw["sections"])
_ID_BY_TERM = _id_map["byTerm"]

_id_occ = {}
def stable_id(term_text, fallback):
    """נקרא פעם אחת לכל ערך, בסדר המסמך — כמו assign_stable_ids."""
    base = _norm_key(term_text)
    if not base:
        return fallback
    _id_occ[base] = _id_occ.get(base, 0) + 1
    key = base if _id_occ[base] == 1 else f"{base}#{_id_occ[base]}"
    return _ID_BY_TERM.get(key, fallback)

# ---------- המרה (שלב 1: בניית מבנה ואינדקס) ----------
out = {
    "title": "מילון מונחים בפנימיות התורה",
    "subtitle": 'על פי תורת הרב ראובן ששון שליט"א',
    "topics": []
}

stats = {"topics": 0, "entries": 0, "definitions": 0, "with_source": 0,
         "refs_found": 0, "entries_with_refs": 0, "inline_quotes_wrapped": 0}

# אינדקס: שם ערך מנורמל -> id
term_index = {}

for section in raw["sections"]:
    # שינוי שם המדור הכללי (גם תאימות לאחור עם data.js ישן)
    section_name = section["name"]
    if section_name == "שונות":
        section_name = "ערכים כלליים"
    topic = {
        "id": section["id"],
        "title": section_name,
        "subtitle": "",
        "entries": []
    }
    for term in section["terms"]:
        entry = {
            "id": stable_id(term["term"], term["id"]),
            "term": term["term"],
            "definitions": [],
            "related": []
        }
        for definition in term["definition"]:
            text, source = split_source(definition)
            # עטיפת ציטוטים ארוכים תחומי גרשיים ב-<span class="quote">
            wrapped = wrap_long_quotes(text)
            if wrapped != text:
                stats["inline_quotes_wrapped"] += wrapped.count('<span class="quote">') - text.count('<span class="quote">')
                text = wrapped
            entry["definitions"].append({"text": text, "source": source})
            stats["definitions"] += 1
            if source:
                stats["with_source"] += 1
        topic["entries"].append(entry)
        stats["entries"] += 1

        # אינדקס לחיפוש הפניות (לפי שם הערך המנורמל)
        norm = normalize_term(term["term"])
        if norm:
            # אם יש כפילויות, נשמור רק את הראשון
            term_index.setdefault(norm, entry["id"])

    out["topics"].append(topic)
    stats["topics"] += 1

# ---------- שלב 2: סריקת הפניות ומילוי related ----------
# פותר ההפניות המקיף (refs.py) רץ *בנוסף* לזה הישן, ואיחוד התוצאות.
# כך אפשר רק להרוויח קישורים, לא לאבד. הישן קורא רק [...]; החדש קורא גם
# הפניות שאינן בסוגריים, ומטפל בדו-משמעות של המקף בשם הערך.
_all_terms = [e["term"] for t in out["topics"] for e in t["entries"]]
_ref_index = _R.build_index(_all_terms)
_ref_keys = sorted(_ref_index.keys(), key=len, reverse=True)
_name_to_id = {}
for t in out["topics"]:
    for e in t["entries"]:
        _name_to_id.setdefault(e["term"], e["id"])

_stats_new = 0
for topic in out["topics"]:
    for entry in topic["entries"]:
        refs = []
        for d in entry["definitions"]:
            for rid in extract_references(d["text"], term_index, entry["id"]):
                if rid not in refs:
                    refs.append(rid)
        before = len(refs)
        for d in entry["definitions"]:
            for nm in _R.find_references(d["text"], _ref_index, _ref_keys, entry["term"]):
                rid = _name_to_id.get(nm)
                if rid and rid != entry["id"] and rid not in refs:
                    refs.append(rid)
        _stats_new += len(refs) - before
        entry["related"] = refs
        if refs:
            stats["entries_with_refs"] += 1
            stats["refs_found"] += len(refs)

print(f"OK: הפניות — {_stats_new} קישורים נוספים שהפותר הישן פספס")

# ====================================================================
# ---------- סיווג לנושאים לפי ה'מפתח' שבראש קובץ הוורד ----------
# ====================================================================
# הערכים עצמם נשארים רשימה אחת (מקור אמת יחיד: כותרות H2). המפתח רק *מצביע*
# עליהם: מדור -> כותרת-על -> שמות ערכים, וערך יכול להופיע בכמה כותרות-על.
# שם במפתח מותאם לערך בשלוש דרגות, כי המפתח נכתב ביד ואינו זהה תו-בתו:
#   1. שם מנורמל זהה   2. מפתח מקופל זהה (רווחים, פיסוק, ו' החיבור)
#   3. השם במפתח הוא תחילית של שם ערך אחד ויחיד (או להיפך)
_flat = [e for t in out["topics"] for e in t["entries"]]
_fold_to_id = {}
for _e in _flat:
    _fold_to_id.setdefault(_R.fold_key(_e["term"]), _e["id"])
_fold_keys = list(_fold_to_id.keys())

def _resolve_index_name(name):
    tid = term_index.get(normalize_term(name))
    if tid:
        return tid
    fk = _R.fold_key(name)
    if not fk:
        return None
    if fk in _fold_to_id:
        return _fold_to_id[fk]
    longer = [k for k in _fold_keys if k.startswith(fk + ' ')]
    if len(longer) == 1:
        return _fold_to_id[longer[0]]
    shorter = [k for k in _fold_keys if fk.startswith(k + ' ')]
    if shorter:
        return _fold_to_id[max(shorter, key=len)]
    return None

def _topic_ids(titles):
    """מזהה קבוע לכל נושא (k_N), נשמר ב-id-map.json כדי שלשוניות וקישורים
    שמורים לא יצביעו על נושא אחר אחרי עדכון וורד."""
    by = _id_map.setdefault("byTopic", {})
    nxt = _id_map.setdefault("nextTopic", 1)
    used = set(by.values())
    res = []
    for t in titles:
        key = _norm_key(t)
        if key not in by:
            while f"k_{nxt}" in used:
                nxt += 1
            by[key] = f"k_{nxt}"
            used.add(by[key])
            nxt += 1
        res.append(by[key])
    _id_map["nextTopic"] = nxt
    return res

_sections, _topics_view, _primary = [], [], {}
_unresolved, _classified = [], set()
_UNSORTED_SECTION = "ערכים נוספים"
_UNSORTED_TOPIC = "ערכים שטרם שובצו במפתח"

_index = raw.get("index") or []
if _index:
    _titles = [g["name"] for s in _index for g in s["groups"]]
    _tids = dict(zip(_titles, _topic_ids(_titles)))
    for _si, _sec in enumerate(_index):
        _sections.append({"title": _sec["name"], "topics": []})
        for _g in _sec["groups"]:
            _ids = []
            for _name in _g["terms"]:
                _eid = _resolve_index_name(_name)
                if not _eid:
                    _unresolved.append((_g["name"], _name))
                    continue
                if _eid not in _ids:
                    _ids.append(_eid)
                _classified.add(_eid)
                _primary.setdefault(_eid, _g["name"])
            _topics_view.append({"id": _tids[_g["name"]], "title": _g["name"],
                                 "section": _si, "ids": _ids})
            _sections[_si]["topics"].append(_tids[_g["name"]])
    _left = [e for e in _flat if e["id"] not in _classified]
    if _left:
        _tid = _topic_ids([_UNSORTED_TOPIC])[0]
        _sections.append({"title": _UNSORTED_SECTION, "topics": [_tid], "auto": True})
        _topics_view.append({"id": _tid, "title": _UNSORTED_TOPIC,
                             "section": len(_sections) - 1,
                             "ids": [e["id"] for e in _left]})
        for e in _left:
            _primary[e["id"]] = _UNSORTED_TOPIC
    print(f"OK: מפתח — {len(_index)} מדורים, {len(_titles)} נושאים, "
          f"{len(_classified)}/{len(_flat)} ערכים משובצים")
    if _left:
        print(f"  NOTE: {len(_left)} ערכים קיימים במילון אך אינם מופיעים במפתח "
              f"(מוצגים תחת '{_UNSORTED_TOPIC}'):")
        for e in _left:
            print(f"     · {e['term']}")
    if _unresolved:
        print(f"  NOTE: {len(_unresolved)} שורות במפתח לא נמצא להן ערך (H2) מתאים:")
        for _g, _n in _unresolved:
            print(f"     · [{_g}] {_n}")
else:
    # אין מפתח בוורד — מדור אחד עם כל הערכים, כמו שהיה לפני הסיווג
    _tid = _topic_ids(["ערכים כלליים"])[0]
    _sections.append({"title": "", "topics": [_tid]})
    _topics_view.append({"id": _tid, "title": "ערכים כלליים", "section": 0,
                         "ids": [e["id"] for e in _flat]})
    for e in _flat:
        _primary[e["id"]] = "ערכים כלליים"
_topic_id_by_title = {t["title"]: t["id"] for t in _topics_view}

# הערה: data.json הוסר ב-Phase 1 (lazy loading). הערכים נשמרים ב-entries/<id>.json
# (in-memory הדאטה ב-`out` עדיין משמש להלן ליצירת terms.json + search-index.json + entries/*)

# ---------- שמירת מפת המזהים (חובה ל-commit יחד עם שאר הפלטים) ----------
with open(ID_MAP_PATH, "w", encoding="utf-8") as f:
    json.dump(_id_map, f, ensure_ascii=False, indent=1, sort_keys=True)
print(f"OK: id-map.json ({_id_stats['kept']} ids kept, {_id_stats['added']} new, "
      f"{_id_stats['retired']} retired)")
if _id_stats['renamed']:
    print(f"  NOTE: {len(_id_stats['renamed'])} ערכים שינו שם — המזהה נשמר (סימניות וקישורים ימשיכו לעבוד):")
    for _old, _new, _eid in _id_stats['renamed']:
        print(f"     · {_old}  →  {_new}")
if _id_stats['gone']:
    print(f"  NOTE: {len(_id_stats['gone'])} ערכים נעלמו מהוורד — המזהים שלהם לא ימוחזרו:")
    for _t in _id_stats['gone']:
        print(f"     · {_t}")

# ====================================================================
# ---------- search-index.json (פורמט חדש — מודול משותף) ----------
# ====================================================================
# הנרמול/הטוקניזציה לחיפוש קורים ב-JS בלבד (מקור אמת יחיד).
# כאן נכתב רק טקסט נקי מלא לכל הגדרה. אותן פונקציות משמשות גם את
# rebuild_index_from_entries.py, כדי שהפורמט לא ייפרד לשני מימושים.
from datetime import datetime as _dt
_VERSION = _dt.now().strftime('%Y-%m-%d-%H%M%S')

from build_search_index import build_payload, build_terms_v2, write_json

_payload = build_payload(out["topics"], _VERSION, primary=_primary,
                         titles=[t["title"] for t in _topics_view])

# ── בקרת שפיות: ריצה שהפיקה אפס ערכים/הגדרות לא תדרוס את הפלט הקיים ──
_n_entries = len(_payload["entries"])
_n_defs    = sum(len(e["d"]) for e in _payload["entries"])
if _n_entries == 0 or _n_defs == 0:
    raise SystemExit(
        f"ABORT: ההמרה הפיקה {_n_entries} ערכים ו-{_n_defs} הגדרות. "
        "הפלט הקיים לא נדרס. בדוק את קובץ ה-Word לפני ריצה חוזרת."
    )
if _n_entries < 400:
    print(f"WARNING: רק {_n_entries} ערכים (צפוי ~650). ודא שקובץ ה-Word שלם.")

SEARCH_INDEX_JSON = os.path.join(os.path.dirname(os.path.dirname(__file__)), "search-index.json")
write_json(SEARCH_INDEX_JSON, _payload)
print(f"OK: search-index.json ({_n_entries} entries, {_n_defs} definitions)")

# ---------- entries/<id>.json (Lazy loading — קובץ קטן לכל ערך) ----------
ENTRIES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'entries')
os.makedirs(ENTRIES_DIR, exist_ok=True)

# נקה קבצי entries ישנים (במקרה שערך נמחק מהוורד)
for _f in os.listdir(ENTRIES_DIR):
    if _f.endswith('.json'):
        try:
            os.remove(os.path.join(ENTRIES_DIR, _f))
        except OSError:
            pass

# כתוב קובץ נפרד לכל ערך
_entry_count = 0
for topic in out["topics"]:
    for entry in topic["entries"]:
        entry_data = {
            "id":         entry["id"],
            "term":       entry["term"],
            "topicId":    _topic_id_by_title.get(_primary.get(entry["id"], ""), topic["id"]),
            "topicTitle": _primary.get(entry["id"], topic["title"]),
            "definitions": entry["definitions"],
            "related":    entry.get("related", []),
        }
        path = os.path.join(ENTRIES_DIR, f"{entry['id']}.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(entry_data, f, ensure_ascii=False, separators=(',', ':'))
        _entry_count += 1
print(f"OK: entries/*.json ({_entry_count} files)")

# ---------- terms.json (קל — רק שמות ערכים לסרגל) ----------
TERMS_JSON = os.path.join(os.path.dirname(os.path.dirname(__file__)), "terms.json")
write_json(TERMS_JSON, build_terms_v2(out["title"], out["subtitle"], _flat,
                                      _sections, _topics_view))
print("OK: terms.json")

# ---------- עדכון גרסת Service Worker + SEARCH_URL ----------
_ts = _VERSION   # אותה גרסה שנכתבה לתוך search-index.json

sw_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sw.js')
if os.path.exists(sw_path):
    with open(sw_path, 'r', encoding='utf-8') as f:
        sw = f.read()
    sw_new = re.sub(r"const CACHE_VERSION\s*=\s*'[^']*'",
                    f"const CACHE_VERSION = '{_ts}'", sw)
    if sw_new != sw:
        with open(sw_path, 'w', encoding='utf-8') as f:
            f.write(sw_new)
        print(f"Updated sw.js CACHE_VERSION: {_ts}")

milon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'milon.html')
if os.path.exists(milon_path):
    with open(milon_path, 'r', encoding='utf-8') as f:
        milon = f.read()
    milon_new = re.sub(r'(search-index\.json\?v=)[^"]*',
                       f'\\g<1>{_ts}', milon)
    if milon_new != milon:
        with open(milon_path, 'w', encoding='utf-8') as f:
            f.write(milon_new)
        print(f"Updated milon.html SEARCH_URL: ?v={_ts}")

print(f"OK: terms.json + entries/ ({_entry_count} files)")
print(f"  Topics: {stats['topics']}")
print(f"  Entries: {stats['entries']}")
print(f"  Definitions: {stats['definitions']}")
_pct = (stats['with_source']*100//stats['definitions']) if stats['definitions'] else 0
print(f"  With source: {stats['with_source']} ({_pct}%)")
print(f"  Without source: {stats['definitions'] - stats['with_source']}")
print(f"  Entries with related refs: {stats['entries_with_refs']}")
print(f"  Total references resolved: {stats['refs_found']}")
print(f"  Inline quotes wrapped: {stats['inline_quotes_wrapped']}")

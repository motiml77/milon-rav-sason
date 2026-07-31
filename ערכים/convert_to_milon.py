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

def assign_stable_ids(raw_sections):
    """
    ממפה כל ערך למזהה קבוע. מחזיר (id_map, stats).
    ערך שכבר קיבל מזהה בעבר — שומר אותו. ערך חדש מקבל את המספר הפנוי הבא.
    מספר של ערך שנמחק לא ממוחזר לעולם.
    """
    m = load_id_map()
    by_term = m["byTerm"]
    used = set(by_term.values())
    kept = added = 0
    seen_keys = set()
    occ = {}
    for section in raw_sections:
        for term in section["terms"]:
            base = _norm_key(term["term"])
            if not base:
                continue
            # במסמך יש 4 שמות שחוזרים כשני ערכים נפרדים — ממספרים אותם
            occ[base] = occ.get(base, 0) + 1
            key = base if occ[base] == 1 else f"{base}#{occ[base]}"
            seen_keys.add(key)
            if key in by_term:
                kept += 1
            else:
                while f"t_{m['next']}" in used:
                    m["next"] += 1
                by_term[key] = f"t_{m['next']}"
                used.add(by_term[key])
                m["next"] += 1
                added += 1
    retired = [k for k in by_term if k not in seen_keys]
    return m, {"kept": kept, "added": added, "retired": len(retired)}

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

# הערה: data.json הוסר ב-Phase 1 (lazy loading). הערכים נשמרים ב-entries/<id>.json
# (in-memory הדאטה ב-`out` עדיין משמש להלן ליצירת terms.json + search-index.json + entries/*)

# ---------- שמירת מפת המזהים (חובה ל-commit יחד עם שאר הפלטים) ----------
with open(ID_MAP_PATH, "w", encoding="utf-8") as f:
    json.dump(_id_map, f, ensure_ascii=False, indent=1, sort_keys=True)
print(f"OK: id-map.json ({_id_stats['kept']} ids kept, {_id_stats['added']} new, "
      f"{_id_stats['retired']} retired)")
if _id_stats['retired']:
    print(f"  NOTE: {_id_stats['retired']} ערכים נעלמו מהוורד — המזהים שלהם לא ימוחזר")

# ====================================================================
# ---------- search-index.json (פורמט חדש — מודול משותף) ----------
# ====================================================================
# הנרמול/הטוקניזציה לחיפוש קורים ב-JS בלבד (מקור אמת יחיד).
# כאן נכתב רק טקסט נקי מלא לכל הגדרה. אותן פונקציות משמשות גם את
# rebuild_index_from_entries.py, כדי שהפורמט לא ייפרד לשני מימושים.
from datetime import datetime as _dt
_VERSION = _dt.now().strftime('%Y-%m-%d-%H%M%S')

from build_search_index import build_payload, build_terms, write_json

_payload = build_payload(out["topics"], _VERSION)

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
            "topicId":    topic["id"],
            "topicTitle": topic["title"],
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
write_json(TERMS_JSON, build_terms(out["title"], out["subtitle"], out["topics"]))
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

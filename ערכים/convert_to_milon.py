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
    r'(?:וכן|גם)\s+ערך'
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
    topic = {
        "id": section["id"],
        "title": section["name"],
        "subtitle": "",
        "entries": []
    }
    for term in section["terms"]:
        entry = {
            "id": term["id"],
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
            term_index.setdefault(norm, term["id"])

    out["topics"].append(topic)
    stats["topics"] += 1

# ---------- שלב 2: סריקת הפניות ומילוי related ----------
for topic in out["topics"]:
    for entry in topic["entries"]:
        refs = []
        for d in entry["definitions"]:
            for rid in extract_references(d["text"], term_index, entry["id"]):
                if rid not in refs:
                    refs.append(rid)
        entry["related"] = refs
        if refs:
            stats["entries_with_refs"] += 1
            stats["refs_found"] += len(refs)

# ---------- כתיבה ----------
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print(f"OK: {OUTPUT_JSON}")
print(f"  Topics: {stats['topics']}")
print(f"  Entries: {stats['entries']}")
print(f"  Definitions: {stats['definitions']}")
print(f"  With source: {stats['with_source']} ({stats['with_source']*100//stats['definitions']}%)")
print(f"  Without source: {stats['definitions'] - stats['with_source']}")
print(f"  Entries with related refs: {stats['entries_with_refs']}")
print(f"  Total references resolved: {stats['refs_found']}")
print(f"  Inline quotes wrapped: {stats['inline_quotes_wrapped']}")

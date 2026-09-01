# -*- coding: utf-8 -*-
"""
בניית search-index.json + terms.json בפורמט החדש.

שינוי מהפורמט הישן (חשוב):
  לפני:  לכל ערך נשמרו termN + defsN (טקסט מנורמל לחיפוש) + defsP (תצוגה מקדימה
         חתוכה ל-350 תווים) + preview. כלומר הנרמול לחיפוש היה משוכפל בין
         Python ל-JS — וכל הבדל ביניהם יצר באגים שקטים בחיפוש.
  אחרי:  נשמר רק טקסט נקי מלא לכל הגדרה. כל הנרמול והטוקניזציה קורים ב-JS בלבד
         (מקור אמת יחיד), וה-JS בונה אינדקס הפוך בזיכרון.

יתרונות: קובץ קטן משמעותית, אין יותר סטייה בין הנרמולים, ואפשר להפיק
קטע-תצוגה שממורכז סביב ההתאמה במקום 350 התווים הראשונים.

הפונקציות כאן משמשות גם את convert_to_milon.py וגם את
rebuild_index_from_entries.py.
"""
import html
import json
import os
import re

TAG_RE = re.compile(r'<[^>]+>')
WS_RE = re.compile(r'\s+')


def strip_html(s):
    """מסיר תגיות HTML ומפענח ישויות — מחזיר טקסט קריא לתצוגה."""
    if not s:
        return ""
    s = TAG_RE.sub(' ', s)
    s = html.unescape(s)
    return WS_RE.sub(' ', s).strip()


def definition_texts(entry):
    """טקסט נקי לכל הגדרה, כולל ציון המקור (כדי שגם מקור יהיה בר-חיפוש)."""
    out = []
    for d in entry.get("definitions", []):
        txt = strip_html(d.get("text", ""))
        src = strip_html(d.get("source", ""))
        if src:
            txt = (txt + " ✦ " + src).strip()
        out.append(txt)
    return out


def build_payload(topics_list, version):
    """
    topics_list: [{id, title, subtitle, entries:[{id, term, definitions, ...}]}]
    מחזיר את המבנה שנכתב ל-search-index.json.
    """
    topic_titles = []
    entries_out = []
    for topic in topics_list:
        title = topic.get("title", "")
        if title not in topic_titles:
            topic_titles.append(title)
        p = topic_titles.index(title)
        for entry in topic.get("entries", []):
            entries_out.append({
                "i": entry["id"],
                "t": entry["term"],
                "p": p,
                "d": definition_texts(entry),
                # קישורי "ראה ערך" — נחוצים למדור ההקשרי בתוצאות החיפוש,
                # שאחרת היה מחייב טעינת 680 קבצי ערכים.
                "r": [r for r in (entry.get("related") or []) if r],
            })
    return {"v": version, "topics": topic_titles, "entries": entries_out}


def build_terms(title, subtitle, topics_list):
    """
    terms.json — רק מה שדרוש לסרגל הצדדי.
    termN הוסר: ה-JS מנרמל את השמות בעצמו (אותו קוד כמו החיפוש המלא).
    """
    return {
        "title": title,
        "subtitle": subtitle,
        "topics": [
            {
                "id": t["id"],
                "title": t.get("title", ""),
                "subtitle": t.get("subtitle", ""),
                "entries": [{"id": e["id"], "term": e["term"]} for e in t.get("entries", [])],
            }
            for t in topics_list
        ],
    }


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)   # כתיבה אטומית — לא משאיר קובץ חצי-כתוב אם משהו נופל

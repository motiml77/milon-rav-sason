# -*- coding: utf-8 -*-
"""
מייצר מחדש את search-index.json מתוך entries/*.json הקיימים,
בלי להריץ את כל הצינור מקובץ ה-Word.

שימושי כשמשנים רק את פורמט האינדקס / לוגיקת החיפוש ולא את התוכן —
מבטיח שהתוכן נשאר זהה בדיוק למה שכבר נבדק. terms.json (המפתח) לא נכתב
מחדש: הסיווג לנושאים מגיע מהוורד בלבד, דרך update.py.

    python "ערכים/rebuild_index_from_entries.py"
"""
import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_search_index import build_payload, write_json  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRIES_DIR = os.path.join(ROOT, "entries")
TERMS_JSON = os.path.join(ROOT, "terms.json")
SEARCH_JSON = os.path.join(ROOT, "search-index.json")
MILON_HTML = os.path.join(ROOT, "milon.html")
SW_JS = os.path.join(ROOT, "sw.js")


def read_terms():
    """מחזיר (סדר הערכים, {id: נושא ראשי}, סדר הנושאים) — בשני הפורמטים."""
    terms = json.load(open(TERMS_JSON, encoding="utf-8"))
    primary = {}
    if "names" in terms:                       # פורמט המפתח: names + topics[].ids
        order = list(terms["names"].keys())
        for t in terms["topics"]:
            for eid in t.get("ids", []):
                primary.setdefault(eid, t.get("title", ""))
    else:                                      # הפורמט הישן: topics[].entries
        order = []
        for t in terms["topics"]:
            for e in t["entries"]:
                if e["id"] not in primary:
                    order.append(e["id"])
                    primary[e["id"]] = t.get("title", "")
    titles = [t.get("title", "") for t in terms["topics"]]
    return order, primary, titles


def main():
    order, primary, titles = read_terms()

    # סדר הערכים נקבע ע"י terms.json (סדר המילון), לא ע"י סדר הקבצים בתיקייה
    entries, missing = [], []
    for eid in order:
        path = os.path.join(ENTRIES_DIR, eid + ".json")
        if not os.path.exists(path):
            missing.append(eid)
            continue
        full = json.load(open(path, encoding="utf-8"))
        entries.append({
            "id": full["id"],
            "term": full["term"],
            "definitions": full.get("definitions", []),
            "related": full.get("related", []),
        })

    if missing:
        print(f"WARNING: {len(missing)} entries listed in terms.json have no file: {missing[:5]}")

    version = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    payload = build_payload([{"title": "", "entries": entries}], version,
                            primary=primary, titles=titles)

    n_defs = sum(len(e["d"]) for e in payload["entries"])
    if not payload["entries"] or not n_defs:
        sys.exit("ABORT: refusing to write an empty index")

    write_json(SEARCH_JSON, payload)

    # עדכון מספר הגרסה ב-milon.html וב-sw.js
    for path, pattern, repl in (
        (MILON_HTML, r'(search-index\.json\?v=)[^"]*', r'\g<1>' + version),
        (SW_JS, r"const CACHE_VERSION\s*=\s*'[^']*'", f"const CACHE_VERSION = '{version}'"),
    ):
        if not os.path.exists(path):
            continue
        src = open(path, encoding="utf-8").read()
        new = re.sub(pattern, repl, src)
        if new != src:
            open(path, "w", encoding="utf-8", newline="").write(new)
            print(f"  updated version in {os.path.basename(path)}")

    print(f"OK: search-index.json  {len(payload['entries'])} entries, {n_defs} definitions")
    print(f"    version {version}")
    print(f"    size    {os.path.getsize(SEARCH_JSON)/1e6:.2f} MB")


if __name__ == "__main__":
    main()

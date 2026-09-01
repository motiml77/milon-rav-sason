# -*- coding: utf-8 -*-
"""
מייצר מחדש את search-index.json ו-terms.json מתוך entries/*.json הקיימים,
בלי להריץ את כל הצינור מקובץ ה-Word.

שימושי כשמשנים רק את פורמט האינדקס / לוגיקת החיפוש ולא את התוכן —
מבטיח שהתוכן נשאר זהה בדיוק למה שכבר נבדק.

    python "ערכים/rebuild_index_from_entries.py"
"""
import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_search_index import build_payload, build_terms, write_json  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRIES_DIR = os.path.join(ROOT, "entries")
TERMS_JSON = os.path.join(ROOT, "terms.json")
SEARCH_JSON = os.path.join(ROOT, "search-index.json")
MILON_HTML = os.path.join(ROOT, "milon.html")
SW_JS = os.path.join(ROOT, "sw.js")


def main():
    old_terms = json.load(open(TERMS_JSON, encoding="utf-8"))

    # סדר הערכים נקבע ע"י terms.json (סדר המילון), לא ע"י סדר הקבצים בתיקייה
    topics = []
    missing = []
    for t in old_terms["topics"]:
        entries = []
        for e in t["entries"]:
            path = os.path.join(ENTRIES_DIR, e["id"] + ".json")
            if not os.path.exists(path):
                missing.append(e["id"])
                continue
            full = json.load(open(path, encoding="utf-8"))
            entries.append({
                "id": full["id"],
                "term": full["term"],
                "definitions": full.get("definitions", []),
                "related": full.get("related", []),
            })
        topics.append({
            "id": t["id"],
            "title": t.get("title", ""),
            "subtitle": t.get("subtitle", ""),
            "entries": entries,
        })

    if missing:
        print(f"WARNING: {len(missing)} entries listed in terms.json have no file: {missing[:5]}")

    version = datetime.now().strftime("%Y-%m-%d-%H%M%S")

    payload = build_payload(topics, version)
    terms = build_terms(old_terms.get("title", ""), old_terms.get("subtitle", ""), topics)

    n_defs = sum(len(e["d"]) for e in payload["entries"])
    if not payload["entries"] or not n_defs:
        sys.exit("ABORT: refusing to write an empty index")

    write_json(SEARCH_JSON, payload)
    write_json(TERMS_JSON, terms)

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
            open(path, "w", encoding="utf-8").write(new)
            print(f"  updated version in {os.path.basename(path)}")

    print(f"OK: search-index.json  {len(payload['entries'])} entries, {n_defs} definitions")
    print(f"OK: terms.json         {sum(len(t['entries']) for t in terms['topics'])} entries")
    print(f"    version {version}")
    print(f"    size    {os.path.getsize(SEARCH_JSON)/1e6:.2f} MB")


if __name__ == "__main__":
    main()

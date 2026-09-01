# -*- coding: utf-8 -*-
"""
עדכון האתר מקובץ ה-Word — פקודה אחת שבודקת את עצמה.

    python "ערכים/update.py"

מה זה עושה, בסדר הזה:
  1. docx  ->  data.js                       (convert_docx_hierarchical)
  2. data.js -> search-index/terms/entries   (convert_to_milon, מזהים יציבים)
  3. מודד את איכות החיפוש מול ערכת הבקרה, ו**נכשל בקול** אם היא נסוגה
  4. מדפיס בדיוק מה להעלות ל-git

אם שלב 3 נכשל — אל תעשה push. משהו בתוכן או בקוד שבר את החיפוש,
וההרצה הזאת בדיוק חסכה לך גילוי של זה מהמשתמשים.
"""
import os
import re
import shutil
import subprocess
import sys

# קונסולת Windows בעברית היא cp1255 ולא יודעת להדפיס תווי מסגרת ו-Unicode.
# בלי זה הסקריפט קורס על print בלבד, עוד לפני שעשה משהו.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

# ציון מינימלי מתקבל. אם שינית את הדירוג בכוונה לטובה — עדכן את המספר.
MIN_SCORE = 97.0

def say(msg):
    print(msg, flush=True)

def die(msg):
    say('')
    say('=' * 64)
    say('נכשל: ' + msg)
    say('=' * 64)
    sys.exit(1)


def find_docx():
    cands = [f for f in os.listdir(HERE)
             if f.lower().endswith('.docx') and not f.startswith('~$')]
    if not cands:
        die('לא נמצא קובץ .docx בתיקיית "ערכים".')
    if len(cands) > 1:
        say('  ! נמצאו כמה קבצי docx, נבחר: ' + cands[0])
    return os.path.join(HERE, cands[0])


def backup_outputs():
    """גיבוי הפלטים כדי שנוכל לשחזר אם המדידה נכשלת."""
    bak = os.path.join(HERE, '.update-backup')
    if os.path.isdir(bak):
        shutil.rmtree(bak)
    os.makedirs(bak)
    for name in ('search-index.json', 'terms.json'):
        p = os.path.join(ROOT, name)
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(bak, name))
    ent = os.path.join(ROOT, 'entries')
    if os.path.isdir(ent):
        shutil.copytree(ent, os.path.join(bak, 'entries'))
    for name in ('id-map.json',):
        p = os.path.join(HERE, name)
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(bak, name))
    return bak


def restore_outputs(bak):
    """משחזר את הפלט הקודם ואז מנקה את הגיבוי — אחרת נשארת תיקייה של ~5MB."""
    for name in ('search-index.json', 'terms.json'):
        src = os.path.join(bak, name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(ROOT, name))
    src_ent = os.path.join(bak, 'entries')
    if os.path.isdir(src_ent):
        dst = os.path.join(ROOT, 'entries')
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        shutil.copytree(src_ent, dst)
    src_map = os.path.join(bak, 'id-map.json')
    if os.path.exists(src_map):
        shutil.copy2(src_map, os.path.join(HERE, 'id-map.json'))
    shutil.rmtree(bak, ignore_errors=True)


def main():
    say('')
    say('── 1/4  קריאת קובץ ה-Word ──')
    docx = find_docx()
    say('   ' + os.path.basename(docx))
    bak = backup_outputs()

    import convert_docx_hierarchical as cdh
    cwd = os.getcwd()
    os.chdir(HERE)
    try:
        data = cdh.convert_docx_to_hierarchical(docx)
        cdh.save_to_js(data, 'data.js')
    finally:
        os.chdir(cwd)

    say('')
    say('── 2/4  בניית פלטי האתר ──')
    os.chdir(HERE)
    try:
        # ריצה כתהליך נפרד: הסקריפט הוא module-level ורץ פעם אחת בלבד לתהליך
        r = subprocess.run([sys.executable, 'convert_to_milon.py'],
                           capture_output=True, text=True, encoding='utf-8',
                           env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    finally:
        os.chdir(cwd)
    say(r.stdout.rstrip())
    if r.returncode != 0:
        say(r.stderr.rstrip())
        restore_outputs(bak)
        die('בניית הפלטים נכשלה. הפלט הקודם שוחזר.')

    n_new = re.search(r'id-map\.json \((\d+) ids kept, (\d+) new, (\d+) retired\)', r.stdout)
    if n_new:
        kept, new, retired = n_new.groups()
        say('')
        say(f'   מזהים: {kept} נשמרו, {new} חדשים, {retired} נעלמו מהוורד')
        if int(retired):
            say('   ! ערך שנעלם — מזההו לא ימוחזר, כך שקישורים ישנים לא יצביעו על ערך אחר')

    say('')
    say('── 3/4  מדידת איכות החיפוש ──')
    ev = subprocess.run(['node', os.path.join('ערכים', 'eval', 'run-eval.mjs')],
                        cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    say(ev.stdout.rstrip() or ev.stderr.rstrip())
    if ev.returncode != 0 and 'SCORE' not in (ev.stdout or ''):
        restore_outputs(bak)
        die('הרצת המדידה נכשלה (מותקן node?). הפלט הקודם שוחזר.')
    m = re.search(r'SCORE = ([\d.]+)', ev.stdout or '')
    if not m:
        restore_outputs(bak)
        die('לא הצלחתי לקרוא את הציון. הפלט הקודם שוחזר.')
    score = float(m.group(1))
    if score < MIN_SCORE:
        restore_outputs(bak)
        die(f'איכות החיפוש ירדה ל-{score:.2f} (מינימום {MIN_SCORE}).\n'
            f'הפלט הקודם שוחזר — האתר לא נפגע.\n'
            f'אם שמות ערכים שונו בוורד, הרץ:  node "ערכים/eval/make-golden.cjs"\n'
            f'ואז בדוק שהציפיות עדיין נכונות לפני ניסיון חוזר.')
    say('')
    say(f'   ✓ ציון {score:.2f} (מינימום {MIN_SCORE})')

    shutil.rmtree(bak, ignore_errors=True)
    say('')
    say('── 4/4  מוכן להעלאה ──')
    say('')
    say('  git add search-index.json terms.json entries/ sw.js milon.html "ערכים/id-map.json"')
    say('  git commit -m "עדכון תוכן מהוורד"')
    say('  git push')
    say('')
    say('  Vercel יפרוס אוטומטית תוך ~30 שניות.')
    say('')


if __name__ == '__main__':
    main()

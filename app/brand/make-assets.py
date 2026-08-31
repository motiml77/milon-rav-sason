# -*- coding: utf-8 -*-
"""
מייצר את מקורות האייקון ומסך הפתיחה מתוך הלוגו של המוסדות.

הרקע נבנה מרצועת העץ הנקייה שמעל הקשת (בלי אותיות), מרוצף בשיקוף
כדי שלא ייראו תפרים, ומותאם בגוון לשולי הסמל — כך אין הפרש בהירות
בין הסמל לשוליים, וגם אין "רפאים" של אותיות ברקע.
"""
import os
from PIL import Image, ImageFilter, ImageDraw, ImageStat

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
src = Image.open(os.path.join(ROOT, 'assets', 'logo-mlh.png')).convert('RGB')
W, H = src.size

STRIP = src.crop((0, 0, W, 76))          # עץ נקי מעל הקשת

def wood(size, match_to):
    """מרצף את רצועת העץ בשיקוף, ומתאים את גוונה לתמונת הייחוס."""
    t = STRIP
    row = Image.new('RGB', (t.width * 2, t.height))
    row.paste(t, (0, 0))
    row.paste(t.transpose(Image.FLIP_LEFT_RIGHT), (t.width, 0))
    blk = Image.new('RGB', (row.width, row.height * 2))
    blk.paste(row, (0, 0))
    blk.paste(row.transpose(Image.FLIP_TOP_BOTTOM), (0, row.height))
    out = Image.new('RGB', (size, size))
    for y in range(0, size, blk.height):
        for x in range(0, size, blk.width):
            out.paste(blk, (x, y))
    out = out.filter(ImageFilter.GaussianBlur(1.0))
    # התאמת גוון: מזיזים את הממוצע של הרקע לממוצע שולי הסמל
    want = ImageStat.Stat(match_to).mean
    have = ImageStat.Stat(out).mean
    return Image.merge('RGB', [
        ch.point(lambda v, i=i: max(0, min(255, int(v + want[i] - have[i]))))
        for i, ch in enumerate(out.split())
    ])

def feathered(bg, fg, feather):
    """מדביק fg במרכז bg עם שוליים מטושטשים — בלי קו הפרדה חד."""
    mask = Image.new('L', fg.size, 0)
    ImageDraw.Draw(mask).rectangle(
        [feather, feather, fg.width - feather, fg.height - feather], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(feather * 0.55))
    out = bg.copy()
    out.paste(fg, ((bg.width - fg.width) // 2, (bg.height - fg.height) // 2), mask)
    return out

# ── האייקון: הסמל בלבד (הכיתוב הקטן לא נקרא בגודל אייקון) ──
emblem = src.crop((0, 20, W, 646))
border = emblem.crop((0, 0, emblem.width, 60))      # שולי הסמל = יעד ההתאמה

ICON = 1024
tw = int(ICON * 0.62)      # אזור בטוח לאייקון אדפטיבי
em = emblem.resize((tw, int(emblem.height * tw / emblem.width)), Image.LANCZOS)
feathered(wood(ICON, border), em, 24).save(os.path.join(HERE, 'icon.png'))

# ── מסך פתיחה: הלוגו על רקע אחיד בצבע המותג ──
# גרדיאנט על פני 2732px ולוגו גדול דחסו גרוע: 26 גרסאות הצפיפות
# שקלו 8MB. רקע אחיד (זהה ל-backgroundColor שבקונפיג, כך שאין קפיצה
# בין מסך הפתיחה של המערכת לזה של האפליקציה) + לוגו קטן יותר —
# אותה תוצאה חזותית בשבריר הנפח.
SPL = 2732
splash = Image.new('RGB', (SPL, SPL), (0x4a, 0x2f, 0x17))
th = int(SPL * 0.20)
lg = src.resize((int(src.width * th / src.height), th), Image.LANCZOS)
splash.paste(lg, ((SPL - lg.width) // 2, (SPL - lg.height) // 2))
splash.save(os.path.join(HERE, 'splash.png'))
splash.save(os.path.join(HERE, 'splash-dark.png'))

for f in ('icon.png', 'splash.png'):
    p = os.path.join(HERE, f)
    print(f'{f}: {Image.open(p).size}  {os.path.getsize(p)/1024:.0f} KB')

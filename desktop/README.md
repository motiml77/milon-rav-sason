# תוכנת הדסקטופ (Windows)

עוטפת את אותו `milon.html` של האתר — מקור אמת יחיד. עדכון וורד מעדכן
את האתר, את אפליקציית האנדרואיד ואת התוכנה הזאת.

## בנייה

```bash
cd desktop
npm install --ignore-scripts     # Electron יורד בנפרד, ראה למטה
npm run dist
```

התוצאה: `desktop/release/MilonRavSason-Setup.exe`

## שתי מגבלות סביבה, ואיך עוקפים אותן

**1. הורדת Electron חנוקה כאן** (‎~3KB/s). לכן ההתקנה היא
`--ignore-scripts`, והבינארי נלקח מעותק קיים במחשב:

```bash
cp -r "<פרויקט אחר>/node_modules/electron/dist" node_modules/electron/dist
printf 'electron.exe' > node_modules/electron/path.txt   # בלי שורה חדשה!
```

`electronDist` ב-package.json מפנה לשם, כדי ש-electron-builder לא ינסה להוריד.

**2. חילוץ winCodeSign נכשל** — הארכיון מכיל symlinks של macOS, ו-Windows
דורש הרשאת מנהל או Developer Mode כדי ליצור אותם. לכן
`signAndEditExecutable: false`, והאייקון נצרב ל-exe ידנית:

```bash
# מספר גרסת המטמון משתנה בין התקנות — למצוא אותו, לא לקבע אותו
RC=$(find "$LOCALAPPDATA/electron-builder/Cache/winCodeSign" -name rcedit-x64.exe | head -1)
"$RC" release/win-unpacked/MilonRavSason.exe --set-icon build/icon.ico \
  --set-version-string "ProductName" "מילון פנימיות התורה" \
  --set-version-string "FileDescription" "מילון פנימיות התורה" \
  --set-file-version "1.0.0" --set-product-version "1.0.0"
./node_modules/.bin/electron-builder.cmd --win nsis --prepackaged release/win-unpacked
```

אם תפעיל Developer Mode ב-Windows, אפשר להחזיר `signAndEditExecutable: true`
ולהריץ פשוט `npm run dist`.

## בדיקה בלי לפתוח את החלון

```bash
MILON_SHOT=out.png ./release/win-unpacked/MilonRavSason.exe          # צילום
MILON_QUERY='אור אין סוף' ./release/win-unpacked/MilonRavSason.exe   # חיפוש
```

## למה פרוטוקול משלנו

`milon.html` טוען נתונים ב-`fetch` עם נתיבים יחסיים. תחת `file://` הדפדפן
חוסם fetch, ולכן `main.cjs` רושם סכמה `milon://` שמגישה את `www/` כמקור
רגיל. זה גם מה שמאפשר לקרוא מתוך `app.asar` אחרי אריזה.

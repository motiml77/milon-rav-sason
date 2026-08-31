// בונה את תיקיית www לאפליקציה מתוך אותם קבצים שמזינים את האתר.
// מקור אמת יחיד: אין עותק שני של milon.html או של התוכן.
import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const WWW = path.join(import.meta.dirname, 'www');

fs.rmSync(WWW, { recursive: true, force: true });
fs.mkdirSync(WWW, { recursive: true });

// milon.html -> index.html (Capacitor טוען index.html)
let html = fs.readFileSync(path.join(ROOT, 'milon.html'), 'utf8');
fs.writeFileSync(path.join(WWW, 'index.html'), html, 'utf8');

// נתונים — נארזים לתוך ה-APK כדי שהאפליקציה תעבוד לגמרי אופליין
let bytes = 0;
for (const f of ['terms.json', 'search-index.json']) {
  fs.copyFileSync(path.join(ROOT, f), path.join(WWW, f));
  bytes += fs.statSync(path.join(WWW, f)).size;
}
fs.mkdirSync(path.join(WWW, 'entries'));
let n = 0;
for (const f of fs.readdirSync(path.join(ROOT, 'entries'))) {
  if (!f.endsWith('.json')) continue;
  fs.copyFileSync(path.join(ROOT, 'entries', f), path.join(WWW, 'entries', f));
  bytes += fs.statSync(path.join(WWW, 'entries', f)).size;
  n++;
}
fs.mkdirSync(path.join(WWW, 'assets'));
for (const f of fs.readdirSync(path.join(ROOT, 'assets'))) {
  fs.copyFileSync(path.join(ROOT, 'assets', f), path.join(WWW, 'assets', f));
  bytes += fs.statSync(path.join(WWW, 'assets', f)).size;
}

console.log(`www built: index.html + terms/search-index + ${n} entries + assets`);
console.log(`bundled data: ${(bytes / 1e6).toFixed(2)} MB`);

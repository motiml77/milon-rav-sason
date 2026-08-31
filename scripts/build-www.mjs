// בונה תיקיית www מתוך אותם קבצים שמזינים את האתר.
// משותף לאפליקציית אנדרואיד (app/) ולתוכנת הדסקטופ (desktop/) —
// מקור אמת יחיד, בלי עותק שני של milon.html או של התוכן.
//
//   node scripts/build-www.mjs <outDir>
import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const out = process.argv[2];
if (!out) { console.error('usage: build-www.mjs <outDir>'); process.exit(1); }
const WWW = path.resolve(out);

fs.rmSync(WWW, { recursive: true, force: true });
fs.mkdirSync(WWW, { recursive: true });

// milon.html -> index.html
fs.copyFileSync(path.join(ROOT, 'milon.html'), path.join(WWW, 'index.html'));

let bytes = 0, n = 0;
const take = (rel, dstRel = rel) => {
  const dst = path.join(WWW, dstRel);
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  fs.copyFileSync(path.join(ROOT, rel), dst);
  bytes += fs.statSync(dst).size;
};

for (const f of ['terms.json', 'search-index.json']) take(f);
for (const f of fs.readdirSync(path.join(ROOT, 'entries'))) {
  if (f.endsWith('.json')) { take(path.join('entries', f)); n++; }
}
for (const f of fs.readdirSync(path.join(ROOT, 'assets'))) take(path.join('assets', f));

console.log(`www -> ${path.relative(ROOT, WWW)}: index.html + ${n} entries + data/assets`);
console.log(`bundled: ${(bytes / 1e6).toFixed(2)} MB`);

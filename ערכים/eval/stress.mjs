// -*- coding: utf-8 -*-
// בדיקת עומס לחיפוש: אלפי שאילתות שנגזרות אוטומטית מהמילון עצמו.
//
// ערכת הבקרה (golden.json) קטנה ונכתבה ביד — היא שומרת על מה שכבר עובד, אבל
// כשהיא מגיעה ל-100 היא כבר לא מודדת כלום. כאן כל ערך במילון נבחן מכמה כיוונים,
// והאמת נקבעת מכנית (מי באמת מכיל את הצירוף), כך שאפשר לראות *איפה* החיפוש חלש.
//
//   node "ערכים/eval/stress.mjs"                 # טבלת סיכום
//   node "ערכים/eval/stress.mjs" --fails 15      # + דוגמאות כישלון לכל סוג
//   node "ערכים/eval/stress.mjs" --save base     # שמירה להשוואה
//   node "ערכים/eval/stress.mjs" --diff base     # מה השתפר / נשבר מול השמירה
import fs from 'node:fs';
import path from 'node:path';
import url from 'node:url';
import vm from 'node:vm';

const __dirname = path.dirname(url.fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..', '..');
const argv = process.argv.slice(2);
const val = f => { const i = argv.indexOf(f); return i >= 0 ? argv[i + 1] : null; };
const HTML = val('--html') || path.join(ROOT, 'milon.html');

const html = fs.readFileSync(HTML, 'utf8');
const code = html.match(/<script>([\s\S]*)<\/script>\s*<\/body>/)[1];

const mkEl = id => ({ id, value:'', textContent:'', innerHTML:'', scrollTop:0, offsetWidth:1,
  style:{setProperty(){},removeProperty(){},cssText:''}, dataset:{},
  classList:{_s:new Set(),add(...c){c.forEach(x=>this._s.add(x))},remove(...c){c.forEach(x=>this._s.delete(x))},
    toggle(c,f){const on=f===undefined?!this._s.has(c):!!f;on?this._s.add(c):this._s.delete(c);return on;},
    contains(c){return this._s.has(c)}},
  addEventListener(){}, removeEventListener(){}, setAttribute(){}, getAttribute(){return null},
  removeAttribute(){}, appendChild(){}, removeChild(){}, replaceChild(){}, insertBefore(){},
  querySelector(){return null}, querySelectorAll(){return []},
  getBoundingClientRect(){return{top:0,left:0,right:0,bottom:0,width:0,height:0}},
  scrollIntoView(){}, focus(){}, blur(){}, click(){}, closest(){return null}, contains(){return false},
  cloneNode(){return mkEl(id)}, remove(){} });
const els = new Map();
const sandbox = {
  document:{ body:mkEl('body'), documentElement:mkEl('html'),
    getElementById:id=>{ if(!els.has(id)) els.set(id, mkEl(id)); return els.get(id); },
    querySelector:()=>null, querySelectorAll:()=>[], createElement:t=>mkEl('c:'+t),
    createTextNode:t=>({textContent:t}), createDocumentFragment:()=>mkEl('frag'),
    createTreeWalker:()=>({nextNode:()=>null}), addEventListener(){}, removeEventListener(){} },
  localStorage:(()=>{const m=new Map();return{getItem:k=>m.has(k)?m.get(k):null,
    setItem:(k,v)=>m.set(k,String(v)),removeItem:k=>m.delete(k)}})(),
  console:{log(){},warn(){},error(){},info(){}},
  window:null, navigator:{serviceWorker:{register:()=>Promise.resolve()}},
  matchMedia:()=>({matches:false,addEventListener(){},removeEventListener(){},addListener(){}}),
  requestAnimationFrame:f=>setTimeout(f,0), requestIdleCallback:undefined,
  setTimeout, clearTimeout, setInterval, clearInterval, performance, indexedDB:undefined,
  getComputedStyle:()=>({getPropertyValue:()=>'340px'}),
  Set,Map,Promise,JSON,Math,Object,Array,String,Number,RegExp,Error,
  Float64Array,Float32Array,Uint8Array,Uint16Array,Uint32Array,Int32Array,
  addEventListener(){}, removeEventListener(){}, dispatchEvent(){return true},
  innerWidth:1280, innerHeight:800, scrollTo(){}, history:{state:null,pushState(){},replaceState(){}},
  Event:class{constructor(t){this.type=t}},
  fetch: async u => {
    const c = String(u).split('?')[0].replace(/^\//,'');
    const p = path.join(ROOT, c);
    if(!fs.existsSync(p)) return {ok:false,status:404,json:async()=>{throw new Error('404')},text:async()=>''};
    const t = fs.readFileSync(p,'utf8');
    return {ok:true,status:200,json:async()=>JSON.parse(t),text:async()=>t};
  },
};
sandbox.window = sandbox; sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(code, sandbox, {filename:'milon.js'});
await new Promise(r => setTimeout(r, 400));
const tBuild0 = performance.now();
await sandbox.ensureSearchIndex().catch(() => {});
await new Promise(r => setTimeout(r, 400));
if (!vm.runInContext('!!searchIx', sandbox)) { console.error('index failed to build'); process.exit(1); }

// ─────────────────────────────────────────────────────────────────────────
// כל מה שמכאן רץ *בתוך* ההקשר של האתר, מול הפונקציות האמיתיות שלו.
// ─────────────────────────────────────────────────────────────────────────
function core(){
  const E = searchData.entries, N = E.length;
  const STOP = new Set(['של','את','הוא','היא','זה','זו','על','אל','כי','אמ','לא','גמ','או','כמו','אשר','עמ','אבל','רק','כל','יש','בו','בה','מה','מי','כנ','אנ','המ','הנ','שמ','עד','כד','וכו','ראה','ערכ']);
  let seed = 12345;
  const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;

  const tTok = E.map(e => tokenize(e.t));
  const dTok = E.map(e => (e.d || []).map(x => tokenize(x)));
  const titleDf = new Map();
  for(const toks of tTok) for(const w of new Set(toks)) titleDf.set(w, (titleDf.get(w) || 0) + 1);

  const hasSeq = (toks, seq) => {
    outer: for(let i = 0; i + seq.length <= toks.length; i++){
      for(let k = 0; k < seq.length; k++) if(toks[i + k] !== seq[k]) continue outer;
      return true;
    }
    return false;
  };
  const run = q => {
    const t0 = performance.now();
    const r = runEngine(searchIx, q, true);
    return { ei: r.results.map(x => x.ei), dt: performance.now() - t0, note: r.note };
  };
  const cases = [];
  const add = (kind, q, target, ok, extra) => cases.push(Object.assign({ kind, q, target: E[target].t, ok }, extra || {}));

  // 1. שם הערך המלא → חייב להיות ראשון (או בין הזהים לו)
  for(let i = 0; i < N; i++){
    const key = tTok[i].join(' ');
    const twins = tTok.filter(t => t.join(' ') === key).length;
    const r = run(E[i].t);
    const rk = r.ei.indexOf(i);
    add('שם מלא', E[i].t, i, rk >= 0 && rk < twins, { rank: rk, dt: r.dt });
  }
  // 2. ראש הערך (מה שלפני המקף) → כל מי שהראש בכותרתו צריך לקדום לכל השאר
  for(let i = 0; i < N; i++){
    const head = E[i].t.split(/\s[–—-]\s/)[0];
    if(head === E[i].t) continue;
    const hs = tokenize(head);
    if(!hs.length || hs.every(w => STOP.has(w))) continue;
    const group = [];
    for(let j = 0; j < N; j++) if(hasSeq(tTok[j], hs)) group.push(j);
    const r = run(head);
    const rk = r.ei.indexOf(i);
    add('ראש הערך', head, i, rk >= 0 && rk < group.length, { rank: rk, group: group.length, dt: r.dt });
  }
  // 3. שתי מילים מהכותרת (לא צמודות, עד 4 מילים ביניהן)
  for(let i = 0; i < N; i++){
    const t = tTok[i];
    const idx = [];
    for(let k = 0; k < t.length; k++) if(t[k].length >= 3 && !STOP.has(t[k])) idx.push(k);
    let a = -1, b = -1;
    for(let x = 0; x < idx.length && a < 0; x++) for(let y = idx.length - 1; y > x; y--){
      const gap = idx[y] - idx[x];
      if(gap >= 2 && gap <= 5 && t[idx[x]] !== t[idx[y]]){ a = idx[x]; b = idx[y]; break; }
    }
    if(a < 0) continue;
    const w1 = t[a], w2 = t[b];
    let group = 0;
    for(let j = 0; j < N; j++){
      const tj = tTok[j]; let ok = false;
      for(let p = 0; p < tj.length && !ok; p++) if(tj[p] === w1)
        for(let q = p + 1; q < tj.length && q - p <= 6; q++) if(tj[q] === w2){ ok = true; break; }
      if(ok) group++;
    }
    const q = w1 + ' ' + w2;
    const r = run(q);
    const rk = r.ei.indexOf(i);
    add('שתי מילים מהכותרת', q, i, rk >= 0 && rk < Math.max(group, 3), { rank: rk, group, dt: r.dt });
  }
  // 4. צירוף של שלוש מילים מתוך גוף הערך → מי שמכיל את הצירוף המדויק צריך להיות בראש
  for(let i = 0; i < N; i += 2){
    const defs = dTok[i];
    if(!defs.length) continue;
    let tries = 0, done = false;
    while(tries++ < 12 && !done){
      const d = defs[Math.floor(rnd() * defs.length)];
      if(d.length < 12) continue;
      const p = 3 + Math.floor(rnd() * (d.length - 8));
      const seq = d.slice(p, p + 3);
      if(seq.some(w => w.length < 3 || STOP.has(w) || /^[0-9a-z]+$/.test(w))) continue;
      const holders = new Set();
      for(let j = 0; j < N; j++){
        if(hasSeq(tTok[j], seq)){ holders.add(j); continue; }
        for(const dj of dTok[j]) if(hasSeq(dj, seq)){ holders.add(j); break; }
      }
      if(holders.size > 12) continue;          // צירוף שגור מדי — לא מבחן
      const q = seq.join(' ');
      const r = run(q);
      const top = r.ei.slice(0, holders.size);
      let hit = 0; for(const x of top) if(holders.has(x)) hit++;
      const rk = r.ei.indexOf(i);
      add('צירוף מהתוכן', q, i, hit === holders.size, { rank: rk, group: holders.size, hit, dt: r.dt });
      done = true;
    }
  }
  // 5. שגיאת הקלדה: אות אחת חסרה / מוחלפת במילה ייחודית מהכותרת
  const HEB = 'אבגדהוזחטיכלמנסעפצקרשת';
  for(let i = 0; i < N; i++){
    const cand = tTok[i].filter(w => w.length >= 5 && (titleDf.get(w) || 0) <= 2 && /^[א-ת]+$/.test(w));
    if(!cand.length) continue;
    const w = cand[0];
    const pos = 1 + Math.floor(rnd() * (w.length - 2));
    const sub = HEB[Math.floor(rnd() * HEB.length)];
    const variants = [w.slice(0, pos) + w.slice(pos + 1), w.slice(0, pos) + (sub === w[pos] ? 'ק' : sub) + w.slice(pos + 1)];
    const v = variants[i % 2];
    if(searchIx.vocab.has(v)) continue;        // יצא במקרה מילה אמיתית — לא שגיאה
    const rest = tTok[i].filter(x => x !== w && x.length >= 3 && !STOP.has(x)).slice(0, 1);
    const q = rest.length ? (tTok[i].indexOf(rest[0]) < tTok[i].indexOf(w) ? rest[0] + ' ' + v : v + ' ' + rest[0]) : v;
    const r = run(q);
    const rk = r.ei.indexOf(i);
    add(i % 2 ? 'שגיאת הקלדה (אות מוחלפת)' : 'שגיאת הקלדה (אות חסרה)', q, i, rk >= 0 && rk < 5, { rank: rk, dt: r.dt });
  }
  // 6. כתיב מלא/חסר: משמיטים י/ו פנימית ממילה ייחודית בכותרת
  for(let i = 0; i < N; i++){
    const cand = tTok[i].filter(w => w.length >= 4 && (titleDf.get(w) || 0) <= 3 && /[יו]/.test(w.slice(1, -1)));
    if(!cand.length) continue;
    const w = cand[0];
    const inner = w.slice(1, -1), at = inner.search(/[יו]/);
    const v = w[0] + inner.slice(0, at) + inner.slice(at + 1) + w[w.length - 1];
    if(v.length < 3) continue;
    let group = 0;
    for(let j = 0; j < N; j++) if(tTok[j].indexOf(w) >= 0) group++;
    const r = run(v);
    const rk = r.ei.indexOf(i);
    add('כתיב חסר', v, i, rk >= 0 && rk < Math.max(group + 2, 5), { rank: rk, group, dt: r.dt, orig: w });
  }
  // 7. מילה מהכותרת עם אות שימוש שהמשתמש הוסיף (ה/ב/ל/ו/מ/ש)
  const PRE = ['ה','ב','ל','ו','מ','ש'];
  for(let i = 0; i < N; i++){
    const cand = tTok[i].filter(w => w.length >= 4 && (titleDf.get(w) || 0) <= 3 && /^[א-ת]+$/.test(w));
    if(!cand.length) continue;
    const w = cand[0];
    const v = PRE[i % PRE.length] + w;
    if(searchIx.vocab.has(v) && (titleDf.get(v) || 0) > 0) continue;
    let group = 0;
    for(let j = 0; j < N; j++) if(tTok[j].indexOf(w) >= 0) group++;
    const r = run(v);
    const rk = r.ei.indexOf(i);
    add('אות שימוש נוספת', v, i, rk >= 0 && rk < Math.max(group + 2, 5), { rank: rk, group, dt: r.dt, orig: w });
  }
  return JSON.stringify(cases);
}

const cases = JSON.parse(vm.runInContext('(' + core.toString() + ')()', sandbox, { filename: 'stress-core' }));

// ── סיכום ──
const kinds = [...new Set(cases.map(c => c.kind))];
const pct = (a, b) => b ? (100 * a / b).toFixed(1) + '%' : '—';
const q = (arr, p) => { const s = arr.slice().sort((x, y) => x - y); return s.length ? s[Math.min(s.length - 1, Math.floor(p * s.length))] : 0; };
const summary = {};
console.log('══ STRESS ══  ' + cases.length + ' שאילתות שנגזרו מהמילון');
console.log('סוג'.padEnd(30) + 'n'.padStart(6) + 'עבר'.padStart(8) + 'חציון ms'.padStart(11) + 'p95 ms'.padStart(9) + 'max ms'.padStart(9));
let allOk = 0;
for (const k of kinds) {
  const cs = cases.filter(c => c.kind === k), ok = cs.filter(c => c.ok).length, dts = cs.map(c => c.dt);
  allOk += ok;
  summary[k] = { n: cs.length, ok };
  console.log(k.padEnd(30) + String(cs.length).padStart(6) + pct(ok, cs.length).padStart(8) +
    q(dts, 0.5).toFixed(2).padStart(11) + q(dts, 0.95).toFixed(2).padStart(9) + Math.max(...dts).toFixed(2).padStart(9));
}
const dtsAll = cases.map(c => c.dt);
console.log('-'.repeat(73));
console.log('סה"כ'.padEnd(30) + String(cases.length).padStart(6) + pct(allOk, cases.length).padStart(8) +
  q(dtsAll, 0.5).toFixed(2).padStart(11) + q(dtsAll, 0.95).toFixed(2).padStart(9) + Math.max(...dtsAll).toFixed(2).padStart(9));
console.log('STRESS = ' + (100 * allOk / cases.length).toFixed(2));

const nf = +(val('--fails') || 0);
if (nf) for (const k of kinds) {
  const bad = cases.filter(c => c.kind === k && !c.ok);
  if (!bad.length) continue;
  console.log('\n── ' + k + ' — ' + bad.length + ' כישלונות ──');
  for (const c of bad.slice(0, nf))
    console.log('   "' + c.q + '"  →  ' + c.target + '   [מקום ' + (c.rank < 0 ? 'לא נמצא' : c.rank + 1) +
      (c.group !== undefined ? ', קבוצה ' + c.group : '') + (c.orig ? ', מקור: ' + c.orig : '') + ']');
}

const snapDir = path.join(__dirname, 'snapshots');
if (val('--save')) {
  fs.mkdirSync(snapDir, { recursive: true });
  fs.writeFileSync(path.join(snapDir, 'stress-' + val('--save') + '.json'),
    JSON.stringify(cases.map(c => ({ kind: c.kind, q: c.q, target: c.target, ok: c.ok, rank: c.rank }))));
  console.log('\nsaved snapshot: stress-' + val('--save'));
}
if (val('--diff')) {
  const f = path.join(snapDir, 'stress-' + val('--diff') + '.json');
  if (fs.existsSync(f)) {
    const old = new Map(JSON.parse(fs.readFileSync(f, 'utf8')).map(c => [c.kind + '|' + c.q + '|' + c.target, c]));
    let better = [], worse = [];
    for (const c of cases) {
      const o = old.get(c.kind + '|' + c.q + '|' + c.target);
      if (!o) continue;
      if (c.ok && !o.ok) better.push(c); else if (!c.ok && o.ok) worse.push(c);
    }
    console.log('\nמול "' + val('--diff') + '":  ' + better.length + ' תוקנו, ' + worse.length + ' נשברו');
    for (const c of worse.slice(0, 25)) console.log('   ✗ [' + c.kind + '] "' + c.q + '" → ' + c.target + '  (מקום ' + (c.rank < 0 ? '—' : c.rank + 1) + ')');
  } else console.log('\n(no snapshot named ' + val('--diff') + ')');
}

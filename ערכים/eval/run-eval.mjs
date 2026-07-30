// -*- coding: utf-8 -*-
// מריץ את מנוע החיפוש האמיתי מתוך milon.html מול golden.json ומדפיס ציון יחיד.
// אין צורך בדפדפן — ה-script מורץ ב-vm עם DOM מדומה.
//
//   node "ערכים/eval/run-eval.mjs"
//   node "ערכים/eval/run-eval.mjs" --verbose      # פירוט לכל שאילתה
//   node "ערכים/eval/run-eval.mjs" --save base    # שמור תוצאה להשוואה
//   node "ערכים/eval/run-eval.mjs" --diff base    # השווה מול תוצאה שמורה
import fs from 'node:fs';
import path from 'node:path';
import url from 'node:url';
import vm from 'node:vm';

const __dirname = path.dirname(url.fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..', '..');
const argv = process.argv.slice(2);
const has = f => argv.includes(f);
const val = f => { const i = argv.indexOf(f); return i >= 0 ? argv[i + 1] : null; };

const golden = JSON.parse(fs.readFileSync(path.join(__dirname, 'golden.json'), 'utf8'));
const html = fs.readFileSync(path.join(ROOT, 'milon.html'), 'utf8');
const code = html.match(/<script>([\s\S]*)<\/script>\s*<\/body>/)[1];

// ── DOM מדומה מינימלי ──
const mkEl = id => ({ id, value:'', textContent:'', innerHTML:'', scrollTop:0, offsetWidth:1,
  style:{setProperty(){},removeProperty(){},cssText:''}, dataset:{},
  classList:{_s:new Set(),add(...c){c.forEach(x=>this._s.add(x))},remove(...c){c.forEach(x=>this._s.delete(x))},
    toggle(c,f){const on=f===undefined?!this._s.has(c):!!f;on?this._s.add(c):this._s.delete(c);return on;},
    contains(c){return this._s.has(c)}},
  addEventListener(){}, removeEventListener(){}, setAttribute(){}, getAttribute(){return null},
  removeAttribute(){}, appendChild(){}, removeChild(){}, replaceChild(){}, insertBefore(){},
  querySelector(){return null}, querySelectorAll(){return []},
  getBoundingClientRect(){return{top:0,left:0,right:0,bottom:0,width:0,height:0}},
  scrollIntoView(){}, focus(){}, closest(){return null}, contains(){return false},
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
  Float64Array,Uint8Array,Uint32Array,Int32Array,
  addEventListener(){}, removeEventListener(){}, dispatchEvent(){return true},
  innerWidth:1280, innerHeight:800, scrollTo(){}, history:{pushState(){},replaceState(){}},
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
await sandbox.ensureSearchIndex().catch(() => {});
await new Promise(r => setTimeout(r, 400));
const P = e => vm.runInContext(e, sandbox, {filename:'probe'});
if (!P('!!searchIx')) { console.error('index failed to build'); process.exit(1); }

const rank = (q) => JSON.parse(P(
  `(()=>{const t0=performance.now();const r=runEngine(searchIx,${JSON.stringify(q)},true);
    const dt=performance.now()-t0;
    return JSON.stringify({ids:r.results.slice(0,20).map(x=>searchData.entries[x.ei].i),
      titles:r.results.slice(0,5).map(x=>searchData.entries[x.ei].t),
      n:r.results.length, dt});})()`));

// ── metrics ──
const K = 10;
function evalOne(g){
  const r = rank(g.query);
  const exp = new Set(g.expected);
  let firstHit = -1;
  for (let i = 0; i < r.ids.length; i++) if (exp.has(r.ids[i])) { firstHit = i; break; }
  const rr = firstHit >= 0 ? 1 / (firstHit + 1) : 0;
  // nDCG@10 with binary gains
  let dcg = 0;
  for (let i = 0; i < Math.min(K, r.ids.length); i++) if (exp.has(r.ids[i])) dcg += 1 / Math.log2(i + 2);
  let idcg = 0;
  for (let i = 0; i < Math.min(K, exp.size); i++) idcg += 1 / Math.log2(i + 2);
  return { ...g, rankPos: firstHit, rr, s1: firstHit === 0, s3: firstHit >= 0 && firstHit < 3,
           s10: firstHit >= 0 && firstHit < 10, ndcg: idcg ? dcg / idcg : 0,
           n: r.n, dt: r.dt, top: r.titles };
}

const results = golden.queries.map(evalOne);
const groups = {};
for (const r of results) (groups[r.intent] = groups[r.intent] || []).push(r);

const agg = rs => ({
  n: rs.length,
  s1: rs.filter(r => r.s1).length / rs.length,
  s3: rs.filter(r => r.s3).length / rs.length,
  s10: rs.filter(r => r.s10).length / rs.length,
  mrr: rs.reduce((a, r) => a + r.rr, 0) / rs.length,
  ndcg: rs.reduce((a, r) => a + r.ndcg, 0) / rs.length,
});
const pc = x => (x * 100).toFixed(1).padStart(5) + '%';

console.log('══ SEARCH QUALITY ══  index ' + P('searchData.v'));
console.log('intent          n   S@1     S@3     S@10    MRR     nDCG@10');
const order = ['known-item', 'head-term', 'phrase', 'abbrev', 'typo'];
for (const k of order){
  if (!groups[k]) continue;
  const a = agg(groups[k]);
  console.log(`${k.padEnd(14)} ${String(a.n).padStart(2)}  ${pc(a.s1)}  ${pc(a.s3)}  ${pc(a.s10)}  ${pc(a.mrr)}  ${pc(a.ndcg)}`);
}
// overall excludes 'typo' (aspirational) so the headline number is not misleading
const core = results.filter(r => r.intent !== 'typo');   // typo is aspirational
const A = agg(core), All = agg(results);
console.log('-'.repeat(62));
console.log(`${'CORE (no typo)'.padEnd(14)} ${String(A.n).padStart(2)}  ${pc(A.s1)}  ${pc(A.s3)}  ${pc(A.s10)}  ${pc(A.mrr)}  ${pc(A.ndcg)}`);
console.log(`${'ALL'.padEnd(14)} ${String(All.n).padStart(2)}  ${pc(All.s1)}  ${pc(All.s3)}  ${pc(All.s10)}  ${pc(All.mrr)}  ${pc(All.ndcg)}`);
const dts = results.map(r => r.dt).sort((a,b)=>a-b);
console.log(`\nlatency: median ${dts[Math.floor(dts.length/2)].toFixed(2)} ms, max ${dts[dts.length-1].toFixed(2)} ms`);
console.log(`SCORE = ${(A.mrr * 100).toFixed(2)}  (core MRR x100 — the single number to move)`);

// ── איכות קטע התצוגה ──
// באג שהיה: makeSnippet התמרכז על ההתאמה הראשונה של *מילה אחת*, ולכן בשאילתה
// רבת-מילים הקטע יכול היה להציג מופע מקרי בלי ההתאמה האמיתית. נמדד כאן כדי
// שלא יחזור.
const multi = golden.queries.filter(g => g.query.trim().split(/\s+/).length > 1);
let snipOk = 0, snipTot = 0;
const snipBad = [];
for (const g of multi){
  const rep = JSON.parse(P(`(()=>{
    const r = runEngine(searchIx, ${JSON.stringify(g.query)}, true);
    const mt = collectMatchTokens(searchIx, r.resolved);
    const out = [];
    for (const x of r.results.slice(0, 5)){
      const e = searchData.entries[x.ei];
      const bd = bestDefinitionFor(searchIx, x.ei, r.resolved);
      if (bd.defIdx < 0) continue;
      const sn = makeSnippet(e.d[bd.defIdx], mt, 300);
      const snToks = new Set(tokenize(sn));
      let cov = 0;
      for (const rr of r.resolved){
        let hit = false;
        for (const id of rr.qmap.keys()) if (snToks.has(searchIx.vocabList[id])) { hit = true; break; }
        if (hit) cov++;
      }
      // האם ההגדרה עצמה מכילה את כל המילים? אם כן, הקטע חייב להראות אותן
      const dToks = new Set(tokenize(e.d[bd.defIdx]));
      let dcov = 0;
      for (const rr of r.resolved){
        let hit = false;
        for (const id of rr.qmap.keys()) if (dToks.has(searchIx.vocabList[id])) { hit = true; break; }
        if (hit) dcov++;
      }
      out.push({ t: e.t, cov, dcov, n: r.resolved.length });
    }
    return JSON.stringify(out);
  })()`));
  for (const x of rep){
    if (x.dcov < x.n) continue;          // ההגדרה לא מכילה הכל — לא דורשים מהקטע
    snipTot++;
    if (x.cov === x.n) snipOk++;
    else snipBad.push(`"${g.query}" -> ${x.t.slice(0,40)} (הקטע הראה ${x.cov}/${x.n} מילים)`);
  }
}
if (snipTot){
  console.log(`
snippet quality: ${snipOk}/${snipTot} snippets show every query word that their definition contains` +
              ` (${(snipOk*100/snipTot).toFixed(0)}%)`);
  if (snipBad.length){
    console.log('  misleading snippets:');
    snipBad.slice(0, 8).forEach(b => console.log('    ! ' + b));
  }
}

const failures = results.filter(r => !r.s3);
if (failures.length){
  console.log(`\n── ${failures.length} queries with no expected hit in top 3 ──`);
  for (const f of failures){
    console.log(`  [${f.intent}] "${f.query}"  -> rank ${f.rankPos < 0 ? 'MISS' : f.rankPos + 1}  (${f.n} results)`);
    console.log(`        want: ${f.expectedTitles[0]}`);
    console.log(`        got : ${f.top.slice(0,3).join('  |  ') || '(nothing)'}`);
  }
}
if (has('--verbose')){
  console.log('\n── all queries ──');
  for (const r of results)
    console.log(`  ${(r.rankPos<0?'MISS':'#'+(r.rankPos+1)).padStart(5)}  [${r.intent}] "${r.query}"`);
}

const snapDir = path.join(__dirname, 'snapshots');
if (val('--save')){
  fs.mkdirSync(snapDir, { recursive: true });
  const f = path.join(snapDir, val('--save') + '.json');
  fs.writeFileSync(f, JSON.stringify({ score: A.mrr, agg: A,
    perQuery: results.map(r => ({ q: r.query, rank: r.rankPos })) }, null, 2), 'utf8');
  console.log(`\nsaved snapshot -> ${path.basename(f)}`);
}
if (val('--diff')){
  const f = path.join(snapDir, val('--diff') + '.json');
  if (!fs.existsSync(f)) { console.log(`\nno snapshot "${val('--diff')}"`); process.exit(0); }
  const base = JSON.parse(fs.readFileSync(f, 'utf8'));
  const prev = new Map(base.perQuery.map(x => [x.q, x.rank]));
  console.log(`\n── diff vs "${val('--diff')}" ──  score ${(base.score*100).toFixed(2)} -> ${(A.mrr*100).toFixed(2)}`);
  let better = 0, worse = 0;
  for (const r of results){
    if (!prev.has(r.query)) continue;
    const p = prev.get(r.query);
    if (p === r.rankPos) continue;
    const gain = (p < 0 ? 999 : p) - (r.rankPos < 0 ? 999 : r.rankPos);
    if (gain > 0) better++; else worse++;
    console.log(`  ${gain > 0 ? '+' : '-'} "${r.query}": ${p < 0 ? 'MISS' : '#'+(p+1)} -> ${r.rankPos < 0 ? 'MISS' : '#'+(r.rankPos+1)}`);
  }
  console.log(`  ${better} improved, ${worse} regressed`);
}

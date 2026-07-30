// -*- coding: utf-8 -*-
// מייצר golden.json — סט שאילתות בקרה לבדיקת איכות החיפוש.
// כל ציפייה מאומתת מול הקורפוס האמיתי, כדי שלא ייכנסו ציפיות שגויות.
//
//   node "ערכים/eval/make-golden.cjs"
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const idx = JSON.parse(fs.readFileSync(path.join(ROOT, 'search-index.json'), 'utf8'));
const E = idx.entries;
const byId = new Map(E.map(e => [e.i, e]));
const idOfTitle = t => (E.find(e => e.t === t) || {}).i;

// ── known-item: המשתמש יודע את שם הערך ורוצה אותו ──
const KNOWN = [
  ['נרנח"י', 'נרנח"י'],
  ['נרנחי', 'נרנח"י'],                       // בלי גרשיים — חייב לעבוד
  ['הבלא דגרמי', 'הבלא דגרמי'],
  ['רשימו', 'רשימו'],
  ['החלל הפנוי והקו', 'החלל הפנוי והקו'],
  ['מלכות אין סוף', 'מלכות אין סוף'],
  ['בעלה דמטרוניתא', 'בעלה דמטרוניתא'],
  ['טלית ציצית', 'טלית, ציצית'],
  ['עבודה צורך גבוה', 'עבודה צורך גבוה'],
  ['פירוד לאה ורחל', 'פירוד לאה ורחל'],
  ['מרכבה לשכינה', 'מרכבה לשכינה'],
  ['ברכת הלבנה', 'ברכת הלבנה'],
  ['שיעור קומת אדם', 'שיעור קומת אדם'],
  ['ממלא גדול מהסובב', 'ממלא גדול מהסובב'],
  ['הנהגת הייחוד', 'הנהגת הייחוד'],
  ['הנהגת המשפט', 'הנהגת המשפט'],
  ['פנימיות וחיצוניות', 'פנימיות וחיצוניות'],
  ['כהן לוי וישראל', 'כהן לוי וישראל'],
  ['סגולה ובחירה', 'סגולה ובחירה'],
  ['שכינה גפן', 'שכינה – גפן'],
  ['נבואה לעומת תושבע', 'נבואה לעומת תושב"ע'],
  ['משה ורשבי', 'משה ורשב"י'],
];

// ── head-term: מילת ראש של משפחת ערכים; מצפים לאחד מבני המשפחה בראש ──
const HEAD = [
  ['נשמה',        ['נשמה – מקור ההשגות של האדם','נשמה – שורש האופי העצמי של כל אחד','נשמה – מקור האמונה','נשמה – עצמותה והתלבשותה ברצון לטוב']],
  ['בריאת העולם', ['בריאת העולם','בריאת העולם – טעמי הבריאה']],
  ['צמצום',       ['צמצום – הכח עומד להוות נפרדים מן האינסוף']],
  ['הרע',         ['הרע – תכלית יצירתו בעולם']],
  ['סדר ההשתלשלות', ['סדר ההשתלשלות – רצון, מחשבה, הרהור, דיבור ומעשה']],
  ['הרצון האלוקי',  ['הרצון האלוקי – כח פועל ומהווה']],
];

// ── misspellings (typo tolerance) ──
const TYPO = [
  ['צימצום', ['צמצום – הכח עומד להוות נפרדים מן האינסוף']],
  ['רשימא',  ['רשימו']],
  ['נשמא',   ['נשמה – מקור ההשגות של האדם','נשמה – מקור האמונה','נשמה – שורש האופי העצמי של כל אחד','נשמה – עצמותה והתלבשותה ברצון לטוב']],
  ['הבלא דגרמא', ['הבלא דגרמי']],
];

// ── abbreviation / acronym resolution (Hebrew gershayim) ──
// המשתמש מקליד קיצור ומצפה לערך הקנוני שלו — או להיפך.
const ABBREV = [
  ['א"א',   ['אריך אנפין']],
  ['אא',     ['אריך אנפין']],
  ['ז"א',   ['זעיר אנפין']],
  ['זא',     ['זעיר אנפין']],
  ['ע"ק',   ['עתיק יומין']],
];

const out = [];
const warn = [];

function push(query, intent, titles, note){
  const ids = [];
  for (const t of titles){
    const id = idOfTitle(t);
    if (!id){ warn.push(`title not found, dropped: "${t}" (query "${query}")`); continue; }
    ids.push(id);
  }
  if (!ids.length){ warn.push(`NO valid expectation for query "${query}" — skipped`); return; }
  out.push({ query, intent, expected: ids, expectedTitles: ids.map(i => byId.get(i).t), note: note || '' });
}

for (const [q, t] of KNOWN) push(q, 'known-item', [t], 'must be rank 1');
for (const [q, ts] of HEAD) push(q, 'head-term', ts, 'any of the family in top 3');
for (const [q, ts] of ABBREV) push(q, 'abbrev', ts, 'acronym must resolve to its canonical entry');
for (const [q, ts] of TYPO) push(q, 'typo', ts, 'currently expected to FAIL — target for fuzzy fallback');

// ── phrase-from-definition: ביטוי אמיתי וייחודי מתוך הגדרה ──
// נבחר ביטויים שמופיעים בערך אחד בלבד, כדי שהציפייה חד-משמעית.
const SOFIT = { 'ך':'כ','ם':'מ','ן':'נ','ף':'פ','ץ':'צ' };
const nrm = s => (s || '').replace(/[֑-ׇ]/g, '').replace(/[ךםןףץ]/g, c => SOFIT[c]).toLowerCase();
const words = s => nrm(s).split(/[^א-ת0-9a-z]+/).filter(Boolean);

const docWords = E.map(e => words(e.d.join(' ')));
function phraseOwners(phrase){
  const pw = words(phrase);
  const owners = [];
  for (let i = 0; i < docWords.length; i++){
    const dw = docWords[i];
    for (let k = 0; k + pw.length <= dw.length; k++){
      let ok = true;
      for (let j = 0; j < pw.length; j++) if (dw[k+j] !== pw[j]){ ok = false; break; }
      if (ok){ owners.push(E[i].i); break; }
    }
  }
  return owners;
}

// שלוף מועמדים: רצפים של 5 מילים מתוך הגדרות, ובחר כאלה שייחודיים לערך אחד
let phraseCount = 0;
for (let i = 0; i < E.length && phraseCount < 8; i += 47){
  const e = E[i];
  const dw = words(e.d[0] || '');
  if (dw.length < 40) continue;
  for (let start = 12; start + 5 < dw.length && phraseCount < 8; start += 17){
    const phrase = dw.slice(start, start + 5).join(' ');
    if (phrase.length < 20) continue;
    const owners = phraseOwners(phrase);
    if (owners.length === 1 && owners[0] === e.i){
      out.push({ query: phrase, intent: 'phrase', expected: [e.i], expectedTitles: [e.t],
                 note: 'unique 5-word phrase from the entry definition' });
      phraseCount++;
      break;
    }
  }
}

const golden = {
  note: 'סט בקרה לאיכות החיפוש. expected = מזהי הערכים שנחשבים תשובה נכונה.',
  generated_from_index_version: idx.v,
  intents: {
    'known-item': 'המשתמש יודע את שם הערך — נמדד Success@1',
    'head-term': 'מילת ראש של משפחת ערכים — נמדד Success@3',
    'phrase':    'ביטוי מתוך הגדרה — נמדד Success@1',
    'abbrev':    'קיצור בגרשיים — נמדד Success@3',
    'typo':      'שגיאת כתיב — נמדד Success@3 (יעד לשיפור עתידי)',
  },
  queries: out,
};

const dst = path.join(__dirname, 'golden.json');
fs.writeFileSync(dst, JSON.stringify(golden, null, 2), 'utf8');
console.log(`wrote ${path.relative(ROOT, dst)} — ${out.length} queries`);
const byIntent = {};
for (const q of out) byIntent[q.intent] = (byIntent[q.intent] || 0) + 1;
console.log('by intent:', JSON.stringify(byIntent));
if (warn.length){ console.log('\nwarnings:'); warn.forEach(w => console.log('  ! ' + w)); }

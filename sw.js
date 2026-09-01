// ─── Service Worker — מילון פנימיות התורה ───
// CACHE_VERSION מתעדכן אוטומטית ע"י convert_to_milon.py בכל הרצת pipeline
const CACHE_VERSION = '2026-09-01-161524';
const CACHE_NAME    = `milon-${CACHE_VERSION}`;

// רק נכסים שאינם משתנים בין גרסאות תוכן. milon.html **לא** נמצא כאן:
// הוא נטען network-first, כדי שתיקוני קוד/עיצוב יגיעו למשתמשים חוזרים מיד.
// milon.html נשמר כאן כגיבוי לא-מקוון בלבד; ב-fetch הוא תמיד network-first,
// כך שעדכוני קוד מגיעים מיד — ובכל זאת יש עמוד לעבוד איתו בלי חיבור.
const PRECACHE_URLS = [
  '/milon.html',
  '/terms.json',
  '/assets/logo-mlh.png',
];

// ── התקנה ──
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME)
      .then(c => c.addAll(PRECACHE_URLS))
      .catch(() => {})                 // כשל בפריקאש לא יבטל את ההתקנה
      .then(() => self.skipWaiting())
  );
});

// ── הפעלה: מחק גרסאות ישנות ──
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// ── אסטרטגיות ──
// network-first: מנסה רשת, נופל לקאש כשאין חיבור (HTML)
async function networkFirst(req, cache){
  try{
    const res = await fetch(req);
    if(res && res.ok) cache.put(req, res.clone());
    return res;
  }catch(err){
    const cached = await cache.match(req);
    if(cached) return cached;
    throw err;
  }
}

// cache-first: נכסים עם גרסה ב-URL (?v=...) או נכסים בינאריים
async function cacheFirst(req, cache){
  const cached = await cache.match(req);
  if(cached) return cached;
  const res = await fetch(req);
  if(res && res.ok) cache.put(req, res.clone());
  return res;
}

// stale-while-revalidate: מגיש מיד מהקאש ומרענן ברקע (JSON בלי גרסה ב-URL)
async function staleWhileRevalidate(req, cache){
  const cached = await cache.match(req);
  const network = fetch(req)
    .then(res => { if(res && res.ok) cache.put(req, res.clone()); return res; })
    .catch(() => null);
  if(cached) return cached;            // הרענון ממשיך ברקע
  const res = await network;
  if(res) return res;
  throw new Error('offline and not cached');
}

self.addEventListener('fetch', e => {
  const req = e.request;
  if(req.method !== 'GET') return;

  const url = new URL(req.url);
  if(url.origin !== self.location.origin) return;   // רק אותו מקור

  // ניווטים (כולל "/" שמנותב ל-milon.html) — תמיד network-first
  if(req.mode === 'navigate'){
    e.respondWith(caches.open(CACHE_NAME).then(c => networkFirst(req, c)));
    return;
  }

  const path = url.pathname;
  if(!/\.(html|json|png|jpg|jpeg|svg|webp|js|css|woff2?)$/.test(path)) return;

  e.respondWith(caches.open(CACHE_NAME).then(c => {
    // HTML — רשת קודם, כדי שעדכוני קוד יגיעו מיד
    if(path.endsWith('.html'))    return networkFirst(req, c);
    // נכסים עם גרסה מפורשת ב-URL — ה-URL עצמו הוא ה"גרסה"
    if(url.searchParams.has('v')) return cacheFirst(req, c);
    // JSON בלי גרסה (terms.json, entries/*.json) — הגש מיד ורענן ברקע
    if(path.endsWith('.json'))    return staleWhileRevalidate(req, c);
    // תמונות/גופנים
    return cacheFirst(req, c);
  }));
});

// ─── Service Worker — מילון פנימיות התורה ───
// CACHE_VERSION מתעדכן אוטומטית ע"י convert_to_milon.py בכל הרצת pipeline
const CACHE_VERSION = '2026-05-08-1301';
const CACHE_NAME    = `milon-${CACHE_VERSION}`;

const PRECACHE_URLS = [
  '/milon.html',
  '/terms.json',
  '/assets/logo-mlh.png',
];

// ── התקנה: שמור את הקבצים הקלים מיד ──
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME)
      .then(c => c.addAll(PRECACHE_URLS))
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

// ── בקשות: cache-first לכל קבצי האתר ──
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // רק בקשות GET לאותו מקור
  if (e.request.method !== 'GET' || !url.pathname.match(/\.(html|json|png|jpg|svg|js|css)$/)) return;

  e.respondWith(
    caches.open(CACHE_NAME).then(async cache => {
      const cached = await cache.match(e.request);
      if (cached) return cached;            // מהמחשב — מיידי

      // לא בקש: הורד ושמור לפעם הבאה
      const res = await fetch(e.request);
      if (res.ok) cache.put(e.request, res.clone());
      return res;
    })
  );
});

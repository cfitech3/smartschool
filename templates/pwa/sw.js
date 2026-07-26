/**
 * SmartSchool — Service Worker v2
 * Stratégie : Cache-first pour assets statiques, Network-first pour pages,
 * Offline fallback pour présences (stockage local → sync au retour réseau).
 */

const CACHE_VERSION   = 'smartschool-v2';
const CACHE_STATIC    = 'smartschool-static-v2';
const CACHE_PAGES     = 'smartschool-pages-v2';
const OFFLINE_URL     = '/offline/';

// Assets statiques à mettre en cache immédiatement
const STATIC_ASSETS = [
  OFFLINE_URL,
  '/static/css/smartschool.css?v=3',
  '/manifest.json',
];

// Pages critiques à mettre en cache (mode offline)
const CRITICAL_PAGES = [
  '/dashboard/',
  '/eleves/presences/',
  '/notes/conduite/',
  '/notes/absences/',
];

// ── Installation ────────────────────────────────────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    Promise.all([
      caches.open(CACHE_STATIC).then(cache => cache.addAll(STATIC_ASSETS)),
    ])
  );
  self.skipWaiting();
});

// ── Activation : nettoyer les anciens caches ─────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(k => k !== CACHE_STATIC && k !== CACHE_PAGES)
          .map(k => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// ── Stratégie de récupération ────────────────────────────────────────────
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Ignorer les requêtes non-GET et cross-origin
  if (request.method !== 'GET') return;
  if (url.origin !== self.location.origin) return;
  // Ignorer admin Django et API
  if (url.pathname.startsWith('/admin/')) return;

  // Assets statiques : Cache-first
  if (url.pathname.startsWith('/static/') || url.pathname === '/manifest.json') {
    event.respondWith(
      caches.match(request).then(cached => cached || fetch(request).then(response => {
        const clone = response.clone();
        caches.open(CACHE_STATIC).then(cache => cache.put(request, clone));
        return response;
      }))
    );
    return;
  }

  // Pages HTML : Network-first avec fallback cache puis offline
  if (request.mode === 'navigate' ||
      (request.headers.get('accept') || '').includes('text/html')) {
    event.respondWith(
      fetch(request)
        .then(response => {
          // Mettre en cache les pages critiques
          if (CRITICAL_PAGES.some(p => url.pathname.startsWith(p))) {
            const clone = response.clone();
            caches.open(CACHE_PAGES).then(cache => cache.put(request, clone));
          }
          return response;
        })
        .catch(async () => {
          // Pas de réseau → chercher dans le cache
          const cached = await caches.match(request);
          if (cached) return cached;
          // Dernière chance : page offline
          return caches.match(OFFLINE_URL);
        })
    );
    return;
  }

  // Autres requêtes : Network-first simple
  event.respondWith(
    fetch(request).catch(() => caches.match(request))
  );
});

// ── Background Sync : sync des présences offline ─────────────────────────
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-presences') {
    event.waitUntil(syncPresences());
  }
});

async function syncPresences() {
  try {
    // Lire les présences en attente depuis IndexedDB
    const db = await openDB();
    const pending = await getAllPending(db);
    for (const item of pending) {
      try {
        const res = await fetch(item.url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': item.csrf },
          body: item.body,
        });
        if (res.ok) await deletePending(db, item.id);
      } catch (_) { /* Sera retenté au prochain sync */ }
    }
  } catch (_) {}
}

// ── IndexedDB helpers ────────────────────────────────────────────────────
function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('smartschool-offline', 1);
    req.onupgradeneeded = e => e.target.result.createObjectStore('presences', { keyPath: 'id', autoIncrement: true });
    req.onsuccess = e => resolve(e.target.result);
    req.onerror   = e => reject(e);
  });
}
function getAllPending(db) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction('presences', 'readonly');
    const req = tx.objectStore('presences').getAll();
    req.onsuccess = e => resolve(e.target.result);
    req.onerror   = e => reject(e);
  });
}
function deletePending(db, id) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction('presences', 'readwrite');
    const req = tx.objectStore('presences').delete(id);
    req.onsuccess = () => resolve();
    req.onerror   = e => reject(e);
  });
}

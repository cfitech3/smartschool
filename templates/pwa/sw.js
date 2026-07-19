const CACHE_NAME = 'smartschool-v1';
const OFFLINE_URL = '/offline/';

const ASSETS_TO_CACHE = [
  OFFLINE_URL,
  '/static/css/bootstrap.min.css',
  // On ajoute ici les autres assets statiques essentiels plus tard
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Mise en cache des assets hors-ligne');
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
  // Force le service worker à s'activer immédiatement
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('[SW] Suppression de l\'ancien cache', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // On ne gère que les requêtes GET (pas les requêtes POST comme les formulaires)
  if (event.request.method !== 'GET') return;

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Optionnel : on pourrait mettre en cache à la volée ici
        return response;
      })
      .catch(async () => {
        // En cas d'erreur réseau (hors-ligne)
        const cache = await caches.open(CACHE_NAME);
        
        // Si c'recherche une image ou un style en cache
        const cachedResponse = await cache.match(event.request);
        if (cachedResponse) {
          return cachedResponse;
        }
        
        // Si c'est une page HTML (navigation), on renvoie la page offline
        if (event.request.mode === 'navigate' || 
           (event.request.headers.get('accept') && event.request.headers.get('accept').includes('text/html'))) {
          return cache.match(OFFLINE_URL);
        }
        
        // Sinon, on laisse échouer silencieusement
        return new Response('', { status: 408, headers: { 'Content-Type': 'text/plain' } });
      })
  );
});

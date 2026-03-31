const CACHE_NAME = "siopa-mobile-v1";

function getScopePath() {
  const scopeUrl = new URL(self.registration.scope);
  return scopeUrl.pathname.endsWith("/") ? scopeUrl.pathname.slice(0, -1) : scopeUrl.pathname;
}

function getCoreAssets() {
  const base = getScopePath();
  return [`${base}/`, `${base}/static/annotation.html`, `${base}/manifest.webmanifest`, `${base}/icon.svg`];
}

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(getCoreAssets())));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;

  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      const networkFetch = fetch(event.request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return response;
        })
        .catch(() => cachedResponse || caches.match(`${getScopePath()}/`));

      return cachedResponse || networkFetch;
    })
  );
});

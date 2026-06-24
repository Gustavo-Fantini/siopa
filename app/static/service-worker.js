const CACHE_NAME = "siopa-shell-v2";

function getBasePath() {
    const scopeUrl = new URL(self.registration.scope);
    return scopeUrl.pathname.endsWith("/") ? scopeUrl.pathname.slice(0, -1) : scopeUrl.pathname;
}

function withBase(path) {
    const basePath = getBasePath();
    if (path === "/") {
        return `${basePath}/`;
    }

    return `${basePath}${path}`;
}

function getCoreAssets() {
    return [
        "/",
        "/static/app.css",
        "/static/app.js",
        "/static/annotation.html",
        "/manifest.webmanifest",
        "/icon.svg",
    ].map(withBase);
}

self.addEventListener("install", (event) => {
    event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(getCoreAssets())));
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
        )
    );
    self.clients.claim();
});

self.addEventListener("fetch", (event) => {
    if (event.request.method !== "GET") {
        return;
    }

    const requestUrl = new URL(event.request.url);
    if (requestUrl.origin !== self.location.origin || requestUrl.pathname.includes("/api/")) {
        return;
    }

    if (event.request.mode === "navigate") {
        event.respondWith(
            fetch(event.request).catch(() => caches.match(withBase("/")))
        );
        return;
    }

    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            if (cachedResponse) {
                return cachedResponse;
            }

            return fetch(event.request).then((response) => {
                const responseClone = response.clone();
                caches.open(CACHE_NAME).then((cache) => cache.put(event.request, responseClone));
                return response;
            });
        })
    );
});

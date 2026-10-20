"use strict";
const CACHE_NAME = "siopa-offline-v3-1";
const base = new URL("./", self.registration.scope);
const coreAssets = ["", "static/app.css", "static/app.js", "static/offline-store.js", "static/analysis-engine.js", "static/analysis-worker.js", "static/crops.json", "manifest.webmanifest", "icon.svg"].map(path => new URL(path, base).href);
self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(coreAssets)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith("siopa-") && key !== CACHE_NAME).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener("message", event => {
  if (event.data?.type !== "CHECK_OFFLINE" || !event.ports?.[0]) return;
  event.waitUntil(caches.open(CACHE_NAME).then(async cache => {
    const available = await Promise.all(coreAssets.map(url => cache.match(url)));
    event.ports[0].postMessage({ ready: available.every(Boolean), version: CACHE_NAME });
  }));
});
self.addEventListener("fetch", event => {
  const request = event.request, url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== base.origin || url.pathname.includes("/api/")) return;
  const appNavigation = request.mode === "navigate" && [base.pathname, `${base.pathname}index.html`].includes(url.pathname);
  if (appNavigation) { event.respondWith(caches.open(CACHE_NAME).then(async cache => (await cache.match(base.href)) || fetch(request))); return; }
  if (coreAssets.includes(url.href)) event.respondWith(caches.open(CACHE_NAME).then(async cache => (await cache.match(request)) || fetch(request)));
});

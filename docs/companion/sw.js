'use strict';
// Cache only application shell. Photos, camera frames and exported files are NEVER cached.
const CACHE = 'hex-mobile-companion-v9-1';
const APP = ['./', './index.html', './app.js', './style.css', './icon.svg',
             './manifest.webmanifest'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(APP)));
  self.skipWaiting();
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(
    keys.filter(k => k.startsWith('hex-mobile-companion-') && k !== CACHE)
      .map(k => caches.delete(k))
  )).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== self.location.origin ||
      !APP.map(p => new URL(p, self.registration.scope).pathname)
        .includes(url.pathname)) return;
  event.respondWith(caches.match(req).then(hit => hit || fetch(req)));
});
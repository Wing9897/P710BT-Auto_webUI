const CACHE = "p710bt-web-v2";
const ASSETS = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./css/app.css",
  "./js/app.js",
  "./js/label.js",
  "./js/parser.js",
  "./js/printer.js",
  "./js/qr.js",
  "./js/barcode.js",
  "./js/packbits.js",
  "./js/patterns.js",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./sample.csv",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;
  event.respondWith((async () => {
    try {
      const fresh = await fetch(event.request);
      const cache = await caches.open(CACHE);
      cache.put(event.request, fresh.clone());
      return fresh;
    } catch {
      const cached = await caches.match(event.request) || await caches.match("./index.html");
      if (cached) return cached;
      throw new Error("offline");
    }
  })());
});

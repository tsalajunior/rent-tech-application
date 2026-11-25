const CACHE_NAME = "renttech-static-v1";
const CACHE_PREFIX = "renttech-static-";
const OFFLINE_URL = "/static/core/offline.html";
const PRECACHE_URLS = [
    OFFLINE_URL,
    "/static/core/css/output.css",
    "/static/core/images/renttech-icon-192.png",
];

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => cache.addAll(PRECACHE_URLS))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys()
            .then((cacheNames) => Promise.all(
                cacheNames
                    .filter((cacheName) => cacheName.startsWith(CACHE_PREFIX) && cacheName !== CACHE_NAME)
                    .map((cacheName) => caches.delete(cacheName))
            ))
            .then(() => self.clients.claim())
    );
});

self.addEventListener("fetch", (event) => {
    const request = event.request;
    if (request.method !== "GET") {
        return;
    }

    const url = new URL(request.url);
    if (url.origin !== self.location.origin) {
        return;
    }

    if (request.mode === "navigate") {
        event.respondWith(
            fetch(request).catch(async (error) => {
                const offlineResponse = await caches.match(OFFLINE_URL);
                if (offlineResponse) {
                    return offlineResponse;
                }
                throw error;
            })
        );
        return;
    }

    if (
        !url.pathname.startsWith("/static/")
        || !["style", "script", "image", "font"].includes(request.destination)
    ) {
        return;
    }

    event.respondWith((async () => {
        const cache = await caches.open(CACHE_NAME);
        let response;
        try {
            response = await fetch(request);
        } catch (error) {
            const cachedResponse = await cache.match(request);
            if (cachedResponse) {
                return cachedResponse;
            }
            throw error;
        }

        if (response.ok && response.type === "basic") {
            await cache.put(request, response.clone());
        }
        return response;
    })());
});

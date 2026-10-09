// Service worker de EDE Puerta: guarda solo la "carcasa" de la app para que abra sin señal.
// Las llamadas a /puerta/api/ NUNCA se guardan: validar siempre requiere conexión.
const CACHE = 'ede-puerta-v1';
const CARCASA = ['/puerta/', '{{ lib }}', '{{ icono }}', '/puerta/manifest.webmanifest'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(CARCASA)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.pathname.startsWith('/puerta/api/') || url.pathname === '/puerta/admin/') return;
  if (!CARCASA.includes(url.pathname)) return;
  // Red primero (para recibir actualizaciones); si no hay señal, lo guardado.
  e.respondWith(
    fetch(e.request).then((r) => {
      if (r.ok) { const copia = r.clone(); caches.open(CACHE).then((c) => c.put(e.request, copia)); }
      return r;
    }).catch(() => caches.match(e.request))
  );
});

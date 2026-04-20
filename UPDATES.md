# CineMix — Registro de Actualizaciones

> Leer al inicio de cada sesión para contexto inmediato.
> El PRD de referencia está en `PRODUCT.md` (filosofía) y `PRD_CineMix.pdf` (auditoría técnica completa).

---

## Sesión 2026-04-20

### Bugs arreglados (Fase 1 del roadmap)

#### 1. Fix TMDB — `/search/movie` → `/find/{tconst}` (`backend/main.py`)
- **Problema:** La búsqueda por título+año era frágil. Títulos como "It", "Se7en" o caracteres no-ASCII fallaban frecuentemente, dejando películas sin póster ni sinopsis.
- **Solución:** `enrich_tmdb(tconst)` ahora usa `/find/{tconst}?external_source=imdb_id`. Match 1:1 garantizado porque la BD ya almacena el `tconst` de IMDb.
- **Archivos:** `backend/main.py` — función `enrich_tmdb` (línea ~460) + llamada en el endpoint `/api/movies/mix`.

#### 2. Fix Debounce Misfire — sliders ya no auto-disparan el backend (`src/hooks/useMix.js`)
- **Problema:** `useEffect` dependía de `[debouncedSliders, remixKey]`. Mover cualquier slider lanzaba un fetch automático a los 350ms, rompiendo el "ritual" del botón Mezclar (PRD §2.2).
- **Solución:** El efecto ahora solo depende de `[remixKey]`. Los valores de sliders se capturan en un `useRef` que se actualiza silenciosamente en cada render. Al pulsar "Mezclar" se hace snapshot del estado en ese instante.
- **Archivos:** `src/hooks/useMix.js` — eliminado `useDebounce`, añadido `slidersRef`.

#### 3. Fix Poster Leak — preload antes del crossfade (`src/components/PosterBackground.jsx`)
- **Problema:** Al cambiar de película, si el póster de TMDB tardaba en cargar o daba 404, React mostraba un flash del fondo anterior o dejaba el fondo roto.
- **Solución:** Se precarga la imagen con `new Image()`. Solo se llama a `setDisplayed` en `onload`. Si `onerror`, el fondo anterior se mantiene intacto.
- **Archivos:** `src/components/PosterBackground.jsx` — `useEffect` con preloader.

---

## Sesión 2026-04-20 (continuación)

### Fase 1 completada

#### 4. Géneros relacionales (`backend/migrate_genres.py` + `backend/main.py`)
- **Problema:** Géneros almacenados como `"Action,Drama"` forzaban `LIKE '%,Action,%'` — full-table-scan en 144k filas sin índice.
- **Solución:** `migrate_genres.py` crea tabla `movie_genre (tconst, genre_name)` con 111k filas + índices en `genre_name` y `tconst`. `build_query` reemplaza todos los LIKE por subqueries indexadas.
- **Archivos:** `backend/migrate_genres.py` (nuevo), `backend/main.py` — función `build_query`.

#### 5. Analytics endpoint (`backend/main.py` + `src/lib/track.js`)
- **Problema:** `ENDPOINT = null` en track.js — todos los eventos se perdían.
- **Solución:** Endpoint `POST /api/events` en FastAPI que persiste eventos en el log de uvicorn (listo para conectar a PostHog/Mixpanel sin tocar el frontend). `ENDPOINT = '/api/events'` en track.js.
- **Archivos:** `backend/main.py` (endpoint nuevo al final), `src/lib/track.js`.

#### 6. `run_in_threadpool` (`backend/main.py`)
- **Problema:** `sqlite3` nativo en `async def` bloqueaba el event loop de Uvicorn — un request pesado paralizaba todos los demás.
- **Solución:** Todos los `run_query(...)` en endpoints `async def` envueltos con `await run_in_threadpool(run_query, ...)`.
- **Archivos:** `backend/main.py` — endpoints `mix` y `health`.

---

## Estado del backlog (referencia PRD §8)

### Fase 1 — Remediación Crítica ✓ COMPLETA
- [x] Fix integración TMDB (`/find/{tconst}`) — 2026-04-20
- [x] Fix Debounce Misfire (sliders no auto-disparan) — 2026-04-20
- [x] Fix Poster Leak (preload + onError) — 2026-04-20
- [x] Géneros relacionales: tabla `movie_genre` + índices, `build_query` usa subqueries — 2026-04-20
- [x] Analytics: `/api/events` en FastAPI, `ENDPOINT='/api/events'` en `track.js` — 2026-04-20
- [x] `run_in_threadpool` en todos los `run_query` de endpoints async — 2026-04-20

### Fase 2 — SEO y Viralidad
- [ ] Migración a Next.js App Router
- [ ] Rutas `/mezcla/[slug]` con metadatos estáticos
- [ ] Open Graph images dinámicas (`@vercel/og`)
- [ ] Botón Share (Web Share API nativa)

### Fase 3 — Backend escalable
- [ ] PostgreSQL (Supabase / Neon) en lugar de SQLite local
- [ ] Redis (Upstash) para cachear watch providers (TTL 48h)

---

## Deuda técnica conocida (no bloqueante hoy)

| Problema | Impacto | Dónde |
|----------|---------|-------|
| Géneros como string plano `"Action,Drama"` → `LIKE` sin índice | Performance bajo carga alta (50+ RPS) | `backend/main.py` `build_query()` |
| `sqlite3` nativo en `async def` bloquea el event loop | Concurrencia | `backend/main.py` `run_query()` |
| `ENDPOINT = null` en `track.js` | Métricas perdidas | `src/lib/track.js` |

---

## Stack actual

| Capa | Tecnología |
|------|-----------|
| Frontend | React 18 + Vite + Tailwind + Framer Motion |
| Backend | FastAPI + Python + SQLite (144k películas IMDb) |
| Metadatos | TMDB API (póster + sinopsis + watch providers vía JustWatch) |
| Persistencia usuario | localStorage (sin login, por diseño) |
| Analytics | `track.js` implementado pero sin endpoint conectado |
| SEO | Pendiente (requiere Next.js) |

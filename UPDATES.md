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

---

## Sesión 2026-04-20 (auditoría + limpieza)

### Análisis de ingeniería completo
- Añadido `cinemix_analysis.md` — auditoría de 15 fases: mapa del repo, flujo completo del sistema, bugs críticos, arquitectura propuesta, plan de construcción por sprints, prompts listos para usar.

### Limpieza de repo
- **Eliminado** `src/hooks/useDebounce.js` — código muerto desde el fix del Debounce Misfire. No se importaba en ningún archivo.
- **Actualizado** `.gitignore` — añadidos `backend/title.akas.tsv.gz` (~2GB) y `backend/*.log` para que no entren por accidente.

### Bugs críticos — Sprint 0 ✓ COMPLETO

| # | Bug | Archivo | Fix |
|---|-----|---------|-----|
| 1 | **CORS hardcodeado** | `backend/main.py` | `os.getenv("ALLOWED_ORIGINS", ...).split(",")` — 2026-04-20 |
| 2 | **`War` no mapeado** en `IMDB_TO_TMDB_GENRE` | `backend/main.py` | `"War": 10752` — 2026-04-20 |
| 3 | **`yearTo: 2024`** | `src/App.jsx` | `yearTo: new Date().getFullYear()` — 2026-04-20 |
| 4 | **`mixCountRef` no persiste** | `src/hooks/useMix.js` | `localStorage cmx_mix_count` — 2026-04-20 |

---

## Sesión 2026-04-20 (Sprint 0 + fix géneros)

### Sprint 0 completado
Los 4 bugs críticos aplicados y pusheados (ver tabla arriba).

### Fix crítico: géneros del usuario vs Tono (`backend/main.py`)

**Problema:** Al seleccionar géneros en los pads (ej. Mystery + War), `translate_vibes()` añadía silenciosamente el grupo OR del Tono como requisito AND adicional. Con tone=40, la query resultante era `Mystery AND War AND (Drama OR Romance)`, devolviendo películas que casualmente tenían esos tres tags — a menudo con géneros inesperados como Horror.

**Causa raíz:** El Tono siempre añadía `genre_groups` independientemente de si el usuario había elegido géneros o no.

**Solución:**
- Cuando el usuario elige géneros: el Tono solo contribuye a `priority_genres` (sesgo suave 70/30 en `pick_one`) — nunca añade `genre_groups`
- Cuando el usuario NO elige géneros: el Tono sigue añadiendo su grupo OR como antes
- `VibeConstraints`: nuevo campo `user_genres` para separar géneros del usuario de los del Tono
- `relax()`: paso 3 ahora preserva `user_genres` al relajar; paso 4 elimina todo; pasos 5-6 son exclusiones y `max_votes`
- `yearTo` en el endpoint: cap subido de 2026 a 2030

**Archivos:** `backend/main.py` — `VibeConstraints`, `translate_vibes()`, `relax()`

---

## Estado del backlog

### Sprint 0 — Bugs críticos ✓ COMPLETO
- [x] CORS desde ENV (`ALLOWED_ORIGINS`) — 2026-04-20
- [x] `"War": 10752` en `IMDB_TO_TMDB_GENRE` — 2026-04-20
- [x] `yearTo: new Date().getFullYear()` — 2026-04-20
- [x] `mixCountRef` persistente en localStorage — 2026-04-20
- [x] Géneros usuario vs Tono: el Tono ya no sobreescribe la selección del usuario — 2026-04-20

### Sprint 1 — Viralidad
- [ ] Botón Compartir (Web Share API + clipboard fallback)
- [ ] URL de mezcla compartible (`?tone=70&cerebro=30&genres=Thriller,Crime`)
- [ ] Open Graph tags dinámicos por película

### Sprint 2 — Producción real
- [ ] README + `.env.example`
- [ ] Rate limiting (`slowapi`, 20 req/min en `/api/movies/mix`)
- [ ] Redis (Upstash) para cachear TMDB responses (TTL 7 días `enrich_tmdb`, TTL 48h providers)
- [ ] Connection pool SQLite con `threading.local()`

### Sprint 3 — SEO (requiere Next.js)
- [ ] Migración frontend a Next.js App Router
- [ ] Rutas `/mezcla/[slug]` con SSG
- [ ] Sitemap programático

### Sprint 4 — Responsive mobile
- [ ] Panel lateral → bottom sheet en mobile (<768px)
- [ ] `PANEL_W = '40%'` responsivo

---

## Deuda técnica conocida (no bloqueante hoy)

| Problema | Impacto | Dónde |
|----------|---------|-------|
| Sin connection pool SQLite — abre/cierra conexión en cada request | Performance bajo carga | `backend/main.py` `run_query()` |
| `mixCountRef` useRef(0) — se reinicia en cada recarga | Calidad de analytics | `src/hooks/useMix.js` |
| Magic strings de color (`#e8a020`, `#080810`) en 6+ archivos | Mantenibilidad | `src/components/` |
| Sin tests de ningún tipo | Riesgo en refactors | Todo el backend |
| Sin README — proyecto inoperable para colaboradores nuevos | Onboarding | raíz del repo |

---

## Stack actual

| Capa | Tecnología |
|------|-----------|
| Frontend | React 18 + Vite + Tailwind + Framer Motion (SPA, no SSR) |
| Backend | FastAPI + Python + SQLite (144k películas IMDb, Bayesian WR) |
| Metadatos | TMDB API (póster + sinopsis + watch providers vía JustWatch) |
| Persistencia usuario | localStorage (`cmx_*` keys, sin login por diseño) |
| Analytics | `track.js` → `navigator.sendBeacon` → `POST /api/events` (funcional) |
| SEO | Pendiente (requiere migración a Next.js) |

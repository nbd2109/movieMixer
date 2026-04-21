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

### Fix: fallback transparente — "algo parecido" (`backend/main.py` + `MovieDisplay.jsx`)

**Problema:** La función `relax` relajaba constraints silenciosamente y devolvía algo completamente distinto a lo pedido sin decirle nada al usuario. Además, con géneros del usuario seleccionados, un AND sin resultados devolvía 404 directo sin intentar nada más.

**Solución:**
- Géneros del usuario: si AND no encuentra nada y hay múltiples géneros, intenta OR antes de 404. `genre_match = "approximate"`.
- Sin géneros (solo tono): `for step in range(1,8)` limpio en lugar del `while` con bug (ejecutaba la query vacía dos veces). Pasos 1-2 → `"relaxed"`, pasos 3+ → `"approximate"`.
- `MovieDisplay.jsx`: badge ámbar con texto rotatorio cuando `genre_match === "approximate"`: *"Lo más parecido que encontramos"*, *"No es exacto, pero va en esa onda"*, *"La mezcla más cercana disponible"*.

**Archivos:** `backend/main.py` endpoint `/api/movies/mix`, `src/components/MovieDisplay.jsx`

---

### Fix: ruta de plataforma usa Vibe Matrix (`backend/main.py`)

**Problema principal (el caso Carrie):** Con Comedy+Family + plataforma, si no encontraba AND en ES caía directamente a sin-género en ES, devolviendo cualquier film de la plataforma incluyendo Horror. Además el Tono y Cerebro eran completamente ignorados en la ruta de plataforma.

**Causas raíz:**
- `vote_count.gte: 500` y `vote_average.gte: 6.0` siempre fijos — Cerebro sin efecto
- Fallback `géneros(AND) → sin géneros` sin paso OR intermedio
- Géneros del Tono no pasados cuando el usuario no tenía pads activos
- Sin `without_genres` — géneros incompatibles podían aparecer en cualquier fallback
- `sort_by: vote_count.desc` + páginas 1-5 → siempre los mismos 100 films top
- `asyncio` importado dentro de closure; `War` ausente de `_TMDB_GENRE_NAMES`

**Solución completa:**
- `_platform_fetch_page`: nuevo parámetro `genre_filter` (string, coma=AND / pipe=OR), `exclude_filter` → `without_genres`, `min_votes` y `min_rating` escalados por Cerebro (`max(100, min_votes//10)`), `sort_by: popularity.desc`, páginas random 1-15
- `discover_tmdb_by_platform`: nueva firma con `user_genres`, `tone_genres`, `exclude_genres`, `min_votes`, `min_rating`. Devuelve `(resultado, genre_match)`. Secuencia: AND/ES → OR/ES → AND/US → OR/US → sin-género/ES → sin-género/US. Sin-género siempre → `"approximate"`.
- Endpoint: computa `translate_vibes()` también para ruta de plataforma; extrae `tone_genres` del grupo OR del Tono cuando no hay pads; pasa `exclude_genres` → `without_genres` bloquea géneros incompatibles en TODOS los pasos del fallback
- `asyncio` movido a imports de nivel superior; `War: 10752` añadido a `_TMDB_GENRE_NAMES`

**Resultado:** Comedy+Family+Netflix busca `35,10751 AND` → `35|10751 OR` → sin género. Tone=0+plataforma busca `Comedy|Animation|Family` y excluye `Horror,Crime,Thriller,Mystery` en todos los pasos → Carrie imposible.

**Archivos:** `backend/main.py` — `_platform_fetch_page`, `discover_tmdb_by_platform`, endpoint `/api/movies/mix`

---

## Sesión 2026-04-21

### Sprint 1 — Viralidad

#### URL de mezcla compartible (`src/App.jsx`)
- **Problema:** Compartir CineMix con alguien llevaba a la app con sliders en default, sin la configuración que generó la película.
- **Solución:**
  - `parseUrlSliders()`: al montar, lee `?tone=&cerebro=&genres=&yearFrom=&yearTo=&runtime=&platform=` y los aplica como estado inicial. Prioridad: URL > localStorage > `INITIAL_SLIDERS`.
  - `buildShareUrl(s)`: serializa los sliders actuales en query params.
  - `handleRemix()`: llama a `window.history.replaceState(null, '', buildShareUrl(sliders))` antes de disparar el fetch — la URL siempre refleja la mezcla activa.
- **Archivos:** `src/App.jsx`

#### Botón Compartir (`src/components/MovieDisplay.jsx`)
- **Problema:** `share_clicked` definido en `track.js` pero sin llamar — la funcionalidad no existía.
- **Solución:**
  - Botón sutil (↗ Compartir) visible solo cuando hay película, debajo de la fila de metadatos.
  - En móvil (`navigator.share` disponible): Web Share API nativa → abre directamente WhatsApp/iMessage/etc.
  - En desktop: `navigator.clipboard.writeText(url)` + feedback visual "✓ Copiado" durante 2s.
  - Llama a `track(Events.SHARE_CLICKED, { title, platform: 'web_share' | 'clipboard' })`.
- **Archivos:** `src/components/MovieDisplay.jsx`

### Fix: UnboundLocalError `current` (`backend/main.py`)
- **Problema:** `current` solo se definía dentro del `else` del fallback, pero se usaba incondicionalmente en `pick_one(pool, current.priority_genres)` → 500 en el camino feliz (query con resultados).
- **Solución:** `current = constraints` movido al scope principal antes del `if not rows:`.
- **Archivos:** `backend/main.py` línea ~781

### Panel Historial (`src/components/HistorialPanel.jsx`, `src/hooks/useHistory.js`)
- **Cola FIFO de 10 películas** persistente en `localStorage['cmx_history']`, deduplicada por título.
- **Botón "Historial"** con badge contador junto al logo CINEMIX (arriba izquierda).
- Panel slide-in desde la izquierda con tarjetas que incluyen: poster, título, año, rating, duración, géneros, sinopsis (3 líneas), enlace TMDB, logos de plataformas streaming + link JustWatch, fecha.
- Botón "Limpiar" para vaciar el historial.
- **Archivos:** `src/hooks/useHistory.js` (nuevo), `src/components/HistorialPanel.jsx` (nuevo), `src/App.jsx`

### Rate limiting (`backend/main.py`, `backend/requirements.txt`)
- `slowapi==0.1.9` instalado.
- `/api/movies/mix`: **20 req/min** por IP
- `/api/movies/{id}/watch-providers`: **60 req/min** por IP
- `/api/events`: **60 req/min** por IP
- Respuesta 429: `{"error": "too_many_requests", "retry_after": 60}`

### README + `.env.example`
- `README.md`: setup completo (requisitos, orden de scripts de migración, variables de entorno, arquitectura).
- `.env.example`: `TMDB_API_KEY` y `ALLOWED_ORIGINS`.

### ⚠️ Deuda técnica pendiente — inicio de siguiente sesión
- `vite.config.js` apunta a puerto `8003` (parche temporal — zombie en `8001`). Revertir a `8001` tras reiniciar el PC.

---

## Estado del backlog

### Sprint 0 — Bugs críticos ✓ COMPLETO (2026-04-20)

### Sprint 1 — Viralidad ✓ COMPLETO (2026-04-21)
- [x] Botón Compartir (Web Share API + clipboard fallback)
- [x] URL de mezcla compartible (`?tone=70&cerebro=30&genres=Thriller,Crime`)
- [ ] Open Graph tags dinámicos por película (requiere Next.js para SSR real)

### Sprint 1.5 — UX ✓ COMPLETO (2026-04-21)
- [x] Panel Historial — 10 películas FIFO, localStorage, con poster/sinopsis/TMDB/JustWatch
- [x] README + `.env.example`

### Sprint 2 — Producción real (en curso)
- [x] Rate limiting (`slowapi`, 20/60 req/min) — 2026-04-21
- [ ] Connection pool SQLite con `threading.local()`
- [ ] Redis (Upstash) para cachear TMDB responses (TTL 7 días `enrich_tmdb`, TTL 48h providers)

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

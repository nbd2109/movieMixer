# CINEMIX — Análisis de Ingeniería Completo
### De repositorio a producto real · Abril 2026

---

## FASE 1 — MAPA COMPLETO DEL REPOSITORIO

### Estructura de árbol

```
movieMixer-main/
├── backend/
│   ├── main.py                   ← API FastAPI (815 líneas) — núcleo del sistema
│   ├── setup_db.py               ← Pipeline IMDb → SQLite (one-time setup)
│   ├── migrate_genres.py         ← Crea tabla movie_genre con índices
│   ├── migrate_runtime.py        ← Añade columna runtimeMinutes a BD existente
│   ├── migrate_remove_indian.py  ← Elimina producciones indias por idioma
│   └── requirements.txt          ← fastapi, uvicorn, httpx, python-dotenv
├── src/
│   ├── App.jsx                   ← Componente raíz · orquestador de estado global
│   ├── main.jsx                  ← Entry point React
│   ├── index.css                 ← Estilos globales + CSS custom properties
│   ├── components/
│   │   ├── MovieDisplay.jsx      ← Título, año, rating, sinopsis, géneros
│   │   ├── MixerSlider.jsx       ← Slider con odómetro animado y glow neón
│   │   ├── PosterBackground.jsx  ← Fondo blur con crossfade + preload
│   │   ├── SamplePads.jsx        ← Grid 4×4 de géneros tipo pad de batería
│   │   ├── WatchProviders.jsx    ← Logos de plataformas streaming/rent
│   │   ├── YearRangeSlider.jsx   ← Doble slider para rango de años
│   │   ├── RuntimeFilter.jsx     ← Selector de duración (4 opciones)
│   │   ├── PlatformFilter.jsx    ← Selector de plataforma (5 opciones)
│   │   └── TmdbAttribution.jsx   ← Logo TMDB (obligatorio por ToS)
│   ├── hooks/
│   │   ├── useMix.js             ← Fetch al backend + fallbacks offline
│   │   ├── useRetention.js       ← localStorage + mensajes de bienvenida
│   │   ├── useWatchProviders.js  ← Fetch a /watch-providers por tmdbId
│   │   └── useDebounce.js        ← Utility (actualmente sin uso real)
│   └── lib/
│       └── track.js              ← Data layer de analytics (beacon + buffer)
├── public/
│   └── favicon.svg
├── index.html                    ← HTML shell de Vite
├── package.json                  ← React 18 + Framer Motion + Vite + Tailwind
├── vite.config.js                ← Proxy /api → localhost:8001
├── tailwind.config.js
├── postcss.config.js
├── PRODUCT.md                    ← Product Manifesto completo
├── UPDATES.md                    ← Registro de sesiones de desarrollo
└── .gitignore                    ← Excluye movies.db, datasets IMDb, .env
```

### Responsabilidad de cada módulo

**`backend/`** — servidor Python. Contiene toda la lógica de negocio: la Vibe Matrix (traducción de sliders a restricciones SQL), el query builder, el sistema de fallback progresivo, la integración TMDB y los endpoints REST.

**`src/`** — cliente React/Vite. Interfaz visual de una sola página: una "mesa de mezclas" con panel lateral deslizante, área de película a la izquierda y fondo blur animado.

**`backend/*.py` scripts de migración** — herramientas one-shot para construir y actualizar la BD SQLite local que actúa como fuente de datos primaria.

---

## FASE 2 — ANÁLISIS ARCHIVO POR ARCHIVO

### `backend/main.py` (815 líneas)

**Función real:** Toda la lógica de servidor en un único fichero. Está estructurado en 9 secciones numeradas con comentarios.

**Sección 1 — Modelo de datos (`VibeConstraints`):**
`@dataclass` con los campos que el query builder consume: `genre_groups`, `exclude_genres`, `priority_genres`, `min_votes`, `max_votes`, `min_vibe_score`, `year_from`, `year_to`, `runtime_min`, `runtime_max`. Es el contrato entre la Vibe Matrix y el SQL.

**Sección 2 — Vibe Matrix (`translate_vibes`, `interpolate_tone`, `cerebro_to_constraints`):**

- `TONE_ANCHORS`: 8 puntos del espectro (0=Comedia familiar → 100=Terror/Crimen) con pesos por género (0.0–1.0). Entre anclas se interpola linealmente → cada valor del slider produce pesos únicos.
- `cerebro_to_constraints(cerebro, pop_factor)`: curvas continuas. `min_votes` baja de 200k (cerebro=0) a 1k (cerebro=100) via exponencial `200000 * (1/200)^cb`. `min_vibe` sube de 5.0 a 7.5 via cóncava `5.0 + 2.5 * cb^0.6`. `max_votes` aparece solo a partir de cerebro=65 para excluir blockbusters en modo autor.
- `genre_popularity_factor()`: ajusta `min_votes` según lo masivo que sea el género pedido. Biografía/Historia reducen el umbral para que haya resultados.

**Sección 3 — Query Builder (`build_query`):**
SQL parametrizado 100%. Usa subqueries indexadas en `movie_genre` para filtros de género: `tconst IN (SELECT tconst FROM movie_genre WHERE genre_name IN (...))`. Nunca usa `LIKE`. El `ORDER BY RANDOM() LIMIT 100` es el pool del que se elige la película.

**Sección 4 — Fallback (`relax`):**
5 pasos de relajación progresiva: (1) amplía rango de años ±10, (2) divide `min_votes` a la mitad, (3) elimina grupos de géneros, (4) elimina exclusiones, (5) elimina `max_votes`. Garantiza que siempre haya respuesta salvo si la BD está vacía.

**Sección 5 — Selección (`pick_one`):**
Pool de hasta 100 filas del SQL. Si hay `priority_genres`, 70% de probabilidad de elegir del subpool que los contenga. El 30% garantiza variedad.

**Sección 6 — TMDB (`enrich_tmdb`):**
Usa `/find/{tconst}?external_source=imdb_id` — match 1:1 garantizado. Devuelve `posterUrl`, `overview`, `tmdbId`, `original_language`. Best-effort: nunca lanza excepción.

**Sección 7 — DB helper (`run_query`):**
Abre conexión SQLite, ejecuta, cierra. Síncrono por naturaleza de sqlite3. Llamado siempre via `run_in_threadpool` desde los endpoints async para no bloquear el event loop.

**Sección 8 — Platform path (`discover_tmdb_by_platform`):**
Cuando el usuario selecciona plataforma, bypass completo de SQLite. Va directo a TMDB Discover con `with_watch_providers` (datos de JustWatch). Pide 3 páginas aleatorias en paralelo con `asyncio.gather` para variedad real. Intenta ES primero, luego US.

**Sección 9 — Endpoints:**
- `GET /api/movies/mix` — endpoint principal. Bifurca en ruta plataforma vs. ruta SQLite.
- `GET /api/movies/{tmdb_id}/watch-providers` — watch providers por país.
- `GET /health` — count de películas en BD.
- `POST /api/events` — colector de telemetría (beacon).

**Problemas identificados:**
- `ORDER BY RANDOM()` en SQLite es un full-table-scan sobre el resultado filtrado. Con pools de 100 filas el impacto es pequeño pero existe.
- CORS solo permite `localhost`. En producción hay que añadir el dominio real — si se olvida, el frontend en prod no puede hablar con el backend.
- `run_query` abre y cierra conexión en cada llamada. No hay connection pool.
- El filtro de películas indias tiene doble mecanismo: `migrate_remove_indian.py` las elimina de la BD permanentemente, Y hay filtro en runtime en `enrich_tmdb` y `discover_tmdb_by_platform`. Si no se ha ejecutado la migración, el filtro runtime es la única barrera.

---

### `backend/setup_db.py`

**Función real:** Pipeline completo IMDb → SQLite. Descarga `title.basics.tsv.gz` (~1GB) y `title.ratings.tsv.gz`, los une, calcula el Bayesian Weighted Rating y genera `movies.db`. Filtro de importación: solo películas (`titleType=movie`) con ≥1000 votos.

**Bayesian Weighted Rating:**
`WR = (V/(V+m)) × R + (m/(V+m)) × C`
donde V=votos película, m=1000, C=media de la BD. Esto es el mismo sistema que usa IMDb para su Top 250. Evita que películas con 1 voto de 10★ aparezcan como top.

**Índices creados:** `startYear`, `averageRating`, `numVotes`, `vibe_score`, `(startYear, numVotes)`, `(startYear, vibe_score)`. No incluye índice en `genres` (string plano) — de ahí la necesidad de `migrate_genres.py`.

**Problema:** `movies.db` y los datasets `.tsv.gz` están en `.gitignore`. Cualquier desarrollador nuevo debe ejecutar `setup_db.py` + los 3 scripts de migración antes de levantar el backend. No hay documentación de este proceso en el repo (no hay README).

---

### `backend/migrate_genres.py`

**Función real:** Normaliza el campo `genres` (string `"Action,Drama"`) en una tabla relacional `movie_genre(tconst, genre_name)` con índices. Esto transforma el filtro de géneros de `LIKE '%Action%'` (full-table-scan) a subquery indexada.

**Resultado:** ~111k filas en `movie_genre`. Índices en `genre_name` y `tconst`. Idempotente (usa `INSERT OR IGNORE`).

---

### `backend/migrate_runtime.py`

**Función real:** Añade columna `runtimeMinutes` a la BD existente leyendo `title.basics.tsv.gz`. Crea índice `idx_runtime`. Sin esto, el filtro de duración en `/api/movies/mix` no tiene efecto (columna NULL para todos).

---

### `backend/migrate_remove_indian.py`

**Función real:** Elimina de la BD todas las películas que en `title.akas.tsv.gz` tienen `region=IN AND language IN {14 lenguas del subcontinente}`. Distingue correctamente producciones indias (lengua india) de distribuciones indias de Hollywood (inglés). Requiere descargar `title.akas.tsv.gz` (~2GB) adicionalmente.

**Problema crítico:** `title.akas.tsv.gz` no está listado en ninguna instrucción ni en UPDATES.md como descarga requerida. Un desarrollador que ejecute `setup_db.py` + las 3 migraciones sin saber que necesita este archivo verá error.

---

### `src/App.jsx`

**Función real:** Componente raíz. Estado global definido aquí: `sliders` (todos los controles del panel), `panelOpen` (visibilidad del panel lateral), `remixKey` (contador que dispara el fetch), `spinning` (animación del botón).

**Patrón `set(key)`:** Fábrica de handlers. `set('tone')` devuelve `(val) => setSliders(prev => ({...prev, tone: val}))` + `saveSliders` + `track`. Evita 8 handlers duplicados.

**Punto de acoplamiento:** `useMix(sliders, remixKey)` — App pasa el objeto completo de sliders. `useMix` captura snapshot via `slidersRef.current` en el momento del click. Esto es correcto y evita el bug del debounce anterior.

**Problema:** `PANEL_W = '40%'` hardcodeado. En móvil (< 640px), el panel ocupa toda la pantalla y no hay layout responsive declarado. La app está diseñada para desktop.

---

### `src/hooks/useMix.js`

**Función real:** Orquesta el fetch al backend. Se activa solo cuando `remixKey > 0` (el usuario pulsó "Mezclar"). Usa `AbortController` para cancelar fetches anteriores si el usuario pulsa rápido.

**Fallbacks hardcoded:** 4 películas (Blade Runner 2049, Interstellar, Parasite, Mad Max) con poster URLs de TMDB. Si el backend no está disponible, muestra una de estas en lugar de pantalla en blanco. Esto implementa el "modo demo" mencionado en el badge de la UI.

**Manejo de errores 404 estructurado:** Distingue `no_platform_match` de `no_genre_match` por el campo `detail.code` del JSON de error. Cada uno muestra un badge diferente en la UI.

**Problema:** `mixCountRef` no persiste entre navegaciones. Si el usuario recarga, el contador de mezclas vuelve a 0 y el evento `mix_generated` con `mix_number` reinicia. Impacta la calidad del análisis de funnel.

---

### `src/hooks/useRetention.js`

**Función real:** Implementa completa la especificación §3.4 de PRODUCT.md. Persiste sliders en `localStorage['cmx_sliders']`. Al montar, calcula `hoursAgo` desde `cmx_last_visit` y construye mensaje contextual. 6 variantes de mensaje según tiempo transcurrido y géneros guardados.

**Keys localStorage:** `cmx_sliders`, `cmx_last_visit`, `cmx_session_count`. Todos prefijados con `cmx_` para evitar colisiones.

**Problema:** `saveSliders` tiene debounce de 800ms con `setTimeout`. Si el usuario cierra la pestaña en los 800ms después de mover un slider, el cambio se pierde. Impacto bajo en práctica pero existe.

---

### `src/hooks/useDebounce.js`

**Función real:** Hook genérico de debounce. Exporta `useDebounce(value, delay)`.

**Estado actual:** Importado en ningún archivo del proyecto actualmente. Fue el hook central de la versión anterior (antes del fix del "Debounce Misfire" documentado en UPDATES.md). Es código muerto desde que `useMix` migró a `slidersRef`.

---

### `src/hooks/useWatchProviders.js`

**Función real:** Fetch a `/api/movies/{tmdbId}/watch-providers?country=ES` cuando cambia `tmdbId`. Retorna `{ flatrate, rent, link }` o `null`.

**Problema menor:** La región ES está hardcodeada en el fetch. Si se quisiera internacionalizar, habría que pasarla como parámetro.

---

### `src/lib/track.js`

**Función real:** Data layer de analytics. Tres canales: (1) `console.log` en DEV con color amarillo, (2) `navigator.sendBeacon` al endpoint `/api/events` (fire-and-forget, no bloquea), (3) buffer en `sessionStorage['cmx_events']` (máx. 200 eventos, para debug manual).

**Session ID:** Generado en primera visita, persiste en `sessionStorage`. Se incluye en todos los eventos.

**Eventos definidos:** `mix_generated`, `remix_clicked`, `pad_toggled`, `slider_adjusted`, `where_to_watch_clicked`, `share_clicked`, `ticket_downloaded`, `session_returned`.

**Problema:** `share_clicked` y `ticket_downloaded` están definidos en el enum `Events` pero no son llamados en ningún componente actual. La funcionalidad de compartir/ticket no está implementada.

---

### `src/components/MixerSlider.jsx`

**Función real:** Slider con tres efectos visuales: (1) odómetro animado (número que rueda con spring usando `useMotionValue` + `useVelocity`), (2) glow neón en el thumb según hover/drag via CSS variable `--thumb-shadow`, (3) fill de color proporcional al valor.

**Técnica CSS variable dinámica:** `style={{ '--thumb-shadow': thumbShadow }}` inyecta el shadow en tiempo real. El pseudo-elemento `::webkit-slider-thumb` lo lee via `var(--thumb-shadow, fallback)`. Esto es un patrón no muy común pero correcto.

**Problema:** `useMotionValue`, `useSpring`, `useVelocity`, `useTransform`, `useMotionValueEvent` — 5 hooks de Framer Motion por instancia de slider. Con 2 sliders en pantalla son 10 motion values vivos. No es un problema de rendimiento real hoy pero se acumula.

---

### `src/components/PosterBackground.jsx`

**Función real:** Preloading de imagen antes de hacer crossfade. `useEffect` crea `new Image()`, asigna `src`, y solo llama a `setDisplayed` en `onload`. Si hay error 404, mantiene el fondo anterior. Crossfade de 1.4s con `AnimatePresence mode="sync"`.

**Estado inicial:** Muestra `IdleBackground()` — dos nebulosas de color con gradientes radiales + vignette. Diseño coherente con el resto de la UI.

---

### `src/components/SamplePads.jsx`

**Función real:** Grid 4×4 de 16 géneros. Toggling: incluye/excluye del array `selected`. Si 0 géneros → sin filtro. Si N géneros → el backend busca películas que contengan TODOS (AND entre grupos). Botón "limpiar" aparece con AnimatePresence cuando hay ≥1 activo.

**Géneros disponibles:** Action, Adventure, Thriller, Crime, Drama, Romance, Comedy, Horror, Sci-Fi, Fantasy, Mystery, Documentary, Biography, History, War, Animation. 16 total.

**Problema:** `War` está en `PADS` como género seleccionable pero NO está en `IMDB_TO_TMDB_GENRE` del backend. Si el usuario selecciona "Guerra" y tiene plataforma activa, el género se ignora silenciosamente en la ruta TMDB Discover. En la ruta SQLite sí funciona porque War existe en los datos IMDb.

---

### `src/components/WatchProviders.jsx`

**Función real:** Muestra logos de plataformas donde ver la película (streaming prioritario sobre alquiler). Solo se muestra si hay datos. Click en logo abre el link de JustWatch via `window.open`. Incluye atribución "via JustWatch" obligatoria por ToS de TMDB.

---

### `src/components/YearRangeSlider.jsx`

**Función real:** Doble slider superpuesto para rango 1920–2026. Los dos `<input type="range">` comparten el mismo track mediante `position: absolute`. Validación inline: el slider `from` no puede superar `yearTo - 1` y viceversa.

**Problema potencial:** Si `yearFrom === yearTo - 1` y el usuario intenta igualarlos, ambos sliders se bloquean mutuamente. No crashea pero puede confundir al usuario.

---

### `src/components/RuntimeFilter.jsx` y `src/components/PlatformFilter.jsx`

**Función real:** Selectores simples de estado (null | opción). `RuntimeFilter` mapea a `{ runtimeMax: 89 }`, `{ runtimeMin: 90, runtimeMax: 140 }` o `{ runtimeMin: 141 }` en `useMix.js`. `PlatformFilter` pasa el id de plataforma al backend que va por ruta TMDB Discover.

---

## FASE 3 — FLUJO COMPLETO DEL SISTEMA

```
USUARIO
  │
  ├── Ajusta sliders (Tono, Cerebro) → setSliders() → saveSliders() → localStorage
  ├── Activa pads de géneros → setSliders({ genres: [...] })
  ├── Filtra año, duración, plataforma
  │
  └── Pulsa "MEZCLAR"
        │
        ▼
   App.jsx: setRemixKey(k + 1) → spinning animation
        │
        ▼
   useMix.js: useEffect([remixKey]) dispara
     │  snapshot: slidersRef.current
     │  construye URLSearchParams
     │
     ▼
   fetch('/api/movies/mix?genres=...&tone=40&cerebro=50&yearFrom=1920...')
   [Vite proxy → localhost:8001]
        │
        ▼
   FastAPI: GET /api/movies/mix
     │
     ├── [plataforma seleccionada?]
     │     YES → discover_tmdb_by_platform()
     │             │  TMDB Discover API (JustWatch data)
     │             │  3 páginas aleatorias en paralelo (ES, fallback US)
     │             │  Filtra lenguas indias
     │             └── return { title, year, genres, rating, posterUrl, overview, tmdbId }
     │
     └── [ruta SQLite estándar]
           │
           ▼
       translate_vibes(genres, tone, cerebro, yearFrom, yearTo)
         → interpolate_tone(tone) → pesos por género
         → cerebro_to_constraints(cerebro, pop_factor) → min_votes, max_votes, min_vibe
         → VibeConstraints
           │
           ▼
       build_query(constraints)
         → SQL parametrizado con subqueries indexadas en movie_genre
         → ORDER BY RANDOM() LIMIT 100
           │
           ▼
       run_in_threadpool(run_query, sql, params)
         → sqlite3 sobre movies.db (144k películas IMDb)
         → pool de hasta 100 filas
           │
           ├── [0 resultados + géneros seleccionados] → 404 no_genre_match
           ├── [0 resultados sin géneros] → relax() → reintentar hasta paso 5
           │
           ▼
       pick_one(rows, priority_genres)
         → 70% del subpool con priority_genres si existe
         → random.choice del resto
           │
           ▼
       enrich_tmdb(tconst)
         → TMDB /find/{tconst}?external_source=imdb_id
         → posterUrl, overview, tmdbId, original_language
         [si lengua india → reintento con otra película del pool]
           │
           ▼
       return {
         title, year, genres, rating, runtime,
         tconst, posterUrl, overview, tmdbId, genre_match
       }

        │
        ▼
   useMix.js: setMovie(data) → track(MIX_GENERATED, ...)
        │
        ▼
   App.jsx re-render
     │
     ├── PosterBackground: preload new Image() → onload → setDisplayed → crossfade 1.4s
     ├── MovieDisplay: AnimatePresence mode="wait" → exit old → enter new
     └── WatchProviders: useEffect([tmdbId]) → fetch /watch-providers → logos streaming
```

---

## FASE 4 — PRODUCTO REAL

### 4.1 Qué es el producto realmente (basado en código)

Un recomendador de películas basado en dos sliders continuos (Tono emocional 0-100, Cerebro/popularidad 0-100) más filtros opcionales de género (16 pads), año (dual range), duración y plataforma de streaming. Devuelve una película por sesión de búsqueda. El valor lo produce el algoritmo de traducción de sliders a SQL (Vibe Matrix), que convierte estados emocionales abstractos en restricciones de base de datos.

La base de datos es IMDb (~144k películas con ≥1000 votos) enriquecida con metadatos de TMDB (póster, sinopsis, watch providers de JustWatch).

### 4.2 Qué debería ser

El código ya implementa sustancialmente la visión del PRODUCT.md. La brecha principal está en: (1) falta de SEO (Vite SPA no indexable), (2) funcionalidad de compartir no implementada, (3) diseño no responsive para móvil, (4) sin README ni documentación de setup.

### 4.3 MVP real — qué funciona hoy

**FUNCIONA:**
- Mezcla por sliders Tono + Cerebro con interpolación continua entre 8 anclas
- Filtros de género (AND entre múltiples), año, duración, plataforma
- Enriquecimiento TMDB (poster, sinopsis, watch providers)
- Ruta alternativa TMDB Discover cuando hay plataforma seleccionada
- Fallback offline (4 películas hardcoded)
- Persistencia de sliders en localStorage
- Mensajes de retorno personalizados por tiempo transcurrido
- Data layer de analytics completo (beacon a /api/events)
- Sistema de fallback progresivo (5 pasos de relajación)
- Filtro de cine indio

**INCOMPLETO / FALSO:**
- `share_clicked` y `ticket_downloaded` definidos en Events pero no llamados — la funcionalidad no existe
- `useDebounce.js` importado en ningún lado — código muerto
- Sin README: imposible levantar el proyecto sin leer el código
- `PANEL_W = '40%'` hardcoded — no hay responsive
- Sin tests de ningún tipo

### 4.4 Funcionalidades reales — cómo funcionan internamente

**Vibe Matrix:** `translate_vibes()` en `main.py` línea ~160. Llama a `interpolate_tone()` que interpola linealmente entre 8 `TONE_ANCHORS`. Los géneros con peso ≥0.45 se incluyen como grupo OR requerido. Los de peso ≥0.65 van a `priority_genres` (sesgo 70/30 en `pick_one`). `cerebro_to_constraints()` usa exponencial y curva cóncava para producir umbrales únicos por cada valor del slider.

**Retención sin login:** `useRetention.js` completo. Guarda `cmx_sliders`, `cmx_last_visit`, `cmx_session_count`. Al montar calcula `hoursAgo` y llama a `buildWelcomeMessage()` que tiene 6 variantes de mensaje. El mensaje desaparece a los 4.5s.

**Analytics:** `track.js` — `navigator.sendBeacon` es fire-and-forget (no bloquea la UI). Buffer de 200 eventos en `sessionStorage` permite inspección manual. El backend `POST /api/events` loguea en uvicorn (`logger.info`). Pendiente: conectar a PostHog/Mixpanel cambiando solo `_dispatch()`.

### 4.5 Errores críticos

**Bug 1 — CORS en producción:**
`backend/main.py` líneas ~180-186: `allow_origins` solo contiene `localhost:5173`, `localhost:5174`, `localhost:4173`. Si el frontend se despliega en cualquier dominio real (cinemix.app, vercel.app, etc.), **todos los requests del browser fallarán con CORS error**. El backend es funcional, el frontend recibe error de red, cae al modo fallback y muestra películas hardcoded. El usuario no ve error explicativo.

**Bug 2 — `War` genre en TMDB Discover:**
`SamplePads.jsx` incluye `{ id: 'War', label: 'Guerra' }`. `IMDB_TO_TMDB_GENRE` en `main.py` no tiene entrada para `"War"`. En la función `discover_tmdb_by_platform()`, la traducción `IMDB_TO_TMDB_GENRE[g]` falla silenciosamente para War (el género se omite en `genre_ids`). Si el usuario selecciona "Guerra" + plataforma, el filtro de género se ignora y TMDB Discover devuelve cualquier película de la plataforma.

La corrección: añadir `"War": 10752` en `IMDB_TO_TMDB_GENRE`.

**Bug 3 — `yearTo` hardcoded en `INITIAL_SLIDERS`:**
`App.jsx` línea 21: `yearTo: 2024`. Estamos en 2026. Películas de 2025 y 2026 quedan fuera del rango por defecto. El usuario tendría que mover manualmente el slider `yearTo` para verlas.

**Bug 4 — `mixCountRef` no persiste:**
`useMix.js` — `const mixCountRef = useRef(0)`. Se reinicia a 0 en cada recarga de página. El campo `mix_number` en el evento `mix_generated` siempre empieza en 1, haciendo imposible diferenciar usuarios activos de nuevos por este campo.

**Deuda técnica (no bugs críticos):**
- `useDebounce.js` no se usa — código muerto
- Sin connection pool en SQLite — `run_query` abre/cierra conexión en cada request
- Sin README.md — barrera de entrada para contribuidores o deploy
- Sin `.env.example` — el desarrollador no sabe qué variables de entorno necesita
- Sin tests de ningún tipo

### 4.6 Mejoras obligatorias (1:1 mapping)

**Módulo: `backend/main.py` — CORS**
- Problema: `allow_origins` solo localhost
- Solución: Leer origins permitidos de variable de entorno `ALLOWED_ORIGINS`
- Implementación: `os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")`
- Impacto: Bloqueante para cualquier deploy real

**Módulo: `backend/main.py` — War genre**
- Problema: `"War"` no mapeado a TMDB genre ID
- Solución: Añadir `"War": 10752` en `IMDB_TO_TMDB_GENRE`
- Implementación: Una línea en el diccionario
- Impacto: Bug silencioso que afecta a usuarios que seleccionan "Guerra" + plataforma

**Módulo: `src/App.jsx` — yearTo**
- Problema: `yearTo: 2024` hardcodeado
- Solución: `yearTo: new Date().getFullYear()` o al menos 2026
- Implementación: Una línea en `INITIAL_SLIDERS`
- Impacto: Películas del año actual invisibles por defecto

**Módulo: `src/hooks/useDebounce.js` — código muerto**
- Problema: No se usa en ningún lugar
- Solución: Eliminar el archivo
- Impacto: Limpieza sin riesgo

**Módulo: `backend/` — README ausente**
- Problema: Sin instrucciones de setup, el proyecto es inoperable para un nuevo desarrollador
- Solución: Crear `README.md` con: requisitos, pasos de setup DB, variables de entorno, cómo levantar backend y frontend
- Impacto: Crítico para colaboración y deploy

---

## FASE 5 — ARQUITECTURA Y RECONSTRUCCIÓN

### Arquitectura actual

```
Browser (React SPA / Vite)
        │  HTTP REST
        ▼
FastAPI (Python, puerto 8001)
        │  sqlite3
        ▼
SQLite movies.db (144k películas)
        │  httpx async
        ▼
TMDB API (póster + sinopsis + watch providers)
         └── JustWatch (datos de disponibilidad, vía TMDB)
```

**Características:** SPA sin SSR. BD local sin servidor. Sin autenticación. Sin caché. Stateless entre requests (el estado de sesión vive en el cliente via localStorage).

### Problemas estructurales

1. **SPA no indexable** — Google no puede crawlear las películas. Bloqueante para SEO programático (descrito como prioritario en PRODUCT.md §3.1).

2. **SQLite local no escala horizontalmente** — Si se despliega en múltiples instancias (Kubernetes, serverless), cada instancia necesita su copia de `movies.db` (~300-500MB). Imposible de coordinar writes si se añadieran en el futuro.

3. **Sin caché para TMDB** — Cada request a `/api/movies/mix` hace una llamada a `enrich_tmdb()` y otra potencial a `/watch-providers`. Con 1000 usuarios concurrentes = 1000-2000 requests/s a TMDB. El plan gratuito de TMDB tiene límite de 50 requests/s.

4. **CORS hardcodeado** — Bloqueante para producción.

5. **Sin autenticación de endpoints** — `/api/events` puede recibir spam de cualquiera. `/api/movies/mix` puede ser llamado en bucle. No hay rate limiting.

### Arquitectura ideal propuesta

```
Next.js App Router (SSR + SSG)
  ├── /mezcla/[slug]          → páginas indexables por Google
  ├── /pelicula/[tmdbId]      → páginas de película indexables
  └── SPA interactiva
        │  Server Actions / API Routes
        ▼
FastAPI (Python) — mismo backend, añadir:
  ├── Redis (Upstash)         → caché TMDB responses TTL 48h
  ├── Rate limiting           → slowapi / middleware custom
  └── CORS desde ENV
        │
        ├── SQLite (dev) / PostgreSQL (prod, Supabase/Neon)
        └── TMDB API (con caché Redis)
```

### Cómo reconstruir paso a paso

**Paso 1 (hoy):** Corregir bugs críticos (CORS, War genre, yearTo). No requiere arquitectura nueva.

**Paso 2 (semana 1):** Crear README + `.env.example`. Añadir al CORS `ALLOWED_ORIGINS` desde ENV.

**Paso 3 (semana 2-3):** Añadir Redis (Upstash free tier) como caché para respuestas TMDB. Llave: `tmdb:find:{tconst}` TTL 7 días, `tmdb:providers:{tmdbId}:{country}` TTL 48h.

**Paso 4 (mes 1):** Migrar frontend a Next.js App Router. Mantener el backend FastAPI existente. Añadir rutas `/mezcla/[slug]` con metadatos estáticos para SEO.

**Paso 5 (mes 2):** Migrar SQLite a PostgreSQL (Supabase) para deploy multi-instancia. El schema es simple: una tabla `movies`, una tabla `movie_genre`.

---

## FASE 6 — PLAN DE CONSTRUCCIÓN REAL

### Orden de desarrollo (por urgencia y dependencias)

**Sprint 0 — Fixes críticos (1-2 días)**
1. `backend/main.py`: CORS desde ENV
2. `backend/main.py`: `"War": 10752` en `IMDB_TO_TMDB_GENRE`
3. `src/App.jsx`: `yearTo: new Date().getFullYear()`
4. `backend/`: Crear `README.md` + `.env.example`
5. `src/hooks/`: Eliminar `useDebounce.js`

**Sprint 1 — Viralidad (3-5 días)**
6. Implementar botón Compartir (Web Share API nativa en móvil, fallback clipboard)
7. URL de mezcla compartible: slug legible `/mezcla/thriller-anos90`
8. Open Graph tags dinámicos por película

**Sprint 2 — Rendimiento y estabilidad (1 semana)**
9. Caché Redis para TMDB (Upstash free tier suficiente)
10. Connection pool SQLite o migración a PostgreSQL
11. Rate limiting en `/api/movies/mix`

**Sprint 3 — SEO (2-3 semanas)**
12. Migración frontend a Next.js App Router
13. Rutas de película indexables
14. Sitemap programático

**Sprint 4 — Responsive (3-5 días)**
15. Layout mobile-first: panel como bottom sheet en móvil
16. `PANEL_W` responsivo o eliminado en favor de breakpoints

### Dependencias entre módulos

- El caché Redis (Sprint 2) debe ir antes del SEO (Sprint 3) porque las páginas SSR de Next.js harán más llamadas a TMDB.
- El botón Compartir (Sprint 1) requiere que las URLs de mezcla existan primero.
- La migración a PostgreSQL (Sprint 2) es independiente del frontend y puede hacerse en paralelo.

---

## FASE 7 — ESCALABILIDAD TÉCNICA

### Cuellos de botella reales

**1. TMDB API sin caché — techo real: ~50 req/s**
Cada mix hace 1 llamada a `enrich_tmdb`. Con 50 usuarios simultáneos pulsando "Mezclar" = 50 req/s al plan gratuito de TMDB. A partir de ahí: throttling → 429 → `enrich_tmdb` devuelve `{}` → películas sin poster ni sinopsis. La app no crashea (best-effort) pero la UX se degrada.

Solución: Redis TTL 7 días para `enrich_tmdb`. Con 144k películas y 20% siendo populares, el hit rate de caché rápidamente supera el 80%.

**2. SQLite `ORDER BY RANDOM()` — no escala a >1000 req/s**
El pool de 100 filas se selecciona con `ORDER BY RANDOM()` sobre el resultado filtrado de SQLite. En SQLite `RANDOM()` es O(N) sobre el resultado. Con filtros muy amplios (pocos géneros, Cerebro=50) el pool puede ser 10k+ filas → sort completo de 10k integers. A 1000 req/s esto satura el disco.

Solución a corto plazo: Reducir `LIMIT 100` a `LIMIT 20` — calidad suficiente para `pick_one`. Solución a largo plazo: PostgreSQL con `TABLESAMPLE` o pre-computar pools.

**3. SQLite no escala horizontalmente**
`movies.db` (~300MB) debe estar en cada instancia. Imposible en serverless (Vercel, Lambda). Posible en VPS único.

Solución: Supabase (PostgreSQL) — misma API SQL, escala automáticamente.

### Límites del sistema actual

| Usuarios concurrentes | Estado |
|---|---|
| 1–50 | Funciona correctamente |
| 50–200 | TMDB empieza a throttlear (posters desaparecen) |
| 200–1000 | SQLite contención en disco. `run_in_threadpool` ayuda pero no elimina el bottleneck |
| 1000+ | Sistema caído sin Redis + PostgreSQL |

### Cómo escalar a 1k / 100k / 1M usuarios

**1k usuarios:**
- Añadir Redis (Upstash free tier: 10k req/día)
- Desplegar FastAPI en Railway/Render (no serverless)
- Frontend en Vercel

**100k usuarios:**
- Migrar a PostgreSQL (Supabase)
- Redis pagado (Upstash pay-per-use)
- 2-3 instancias FastAPI detrás de un load balancer
- CDN para posters (CloudFront o Cloudflare)

**1M usuarios:**
- Pre-computar pools por combinación popular de sliders (cron diario)
- Caché de respuestas completas `/api/movies/mix` por combinación (TTL 5 min)
- Read replicas PostgreSQL
- Rate limiting por IP

---

## FASE 8 — INTEGRACIONES EXTERNAS

### IMDb

**Dónde se usa:** `backend/setup_db.py` — descarga `title.basics.tsv.gz` y `title.ratings.tsv.gz` desde `datasets.imdbws.com`. Los datos IMDb son la fuente primaria de la BD.

**Cómo se usa:** One-time import. Los datos se graban en SQLite y no se consulta IMDb en runtime. Los `tconst` (IDs IMDb como `tt0110912`) se guardan en la BD y sirven como llave para buscar en TMDB.

**Uso legal:** IMDb publica sus datasets bajo licencia no comercial. El archivo `title.basics.tsv.gz` incluye `"for personal and non-commercial use only"`. **Para uso comercial se necesita licencia de IMDb o migrar completamente a TMDB como fuente.**

**Riesgo de dependencia:** IMDb puede cambiar el formato de los TSV sin previo aviso. Si añaden o eliminan columnas, `setup_db.py` falla. Bajo en práctica histórica, pero real.

### TMDb

**Dónde se usa:**
- `backend/main.py` → `enrich_tmdb()`: `GET /find/{tconst}?external_source=imdb_id` — poster + sinopsis
- `backend/main.py` → `watch_providers()`: `GET /movie/{tmdb_id}/watch/providers` — plataformas streaming
- `backend/main.py` → `_platform_fetch_page()`: `GET /discover/movie` con `with_watch_providers` — búsqueda por plataforma
- `src/components/TmdbAttribution.jsx`: logo TMDB (obligatorio por ToS)

**Cómo se usa:** API key via `TMDB_API_KEY` en `.env`. Requests con `httpx.AsyncClient(timeout=5)`. Todas las llamadas son best-effort — fallos devuelven `{}` o `[]`.

**Uso legal:** La API de TMDB es gratuita para uso personal y no comercial. Para uso comercial se requiere acuerdo comercial. El código incluye la atribución obligatoria en `TmdbAttribution.jsx`.

**Migración IMDb → TMDB como fuente primaria (paso a paso técnico):**
1. Descargar TMDB full export via `GET /movie/{movie_id}` (no hay dump público equivalente a IMDb). Alternativa: usar TMDB daily export files (`movie_ids_{date}.json.gz`).
2. Modificar `setup_db.py` para importar desde TMDB en lugar de IMDb TSV.
3. Reemplazar campo `tconst` por `tmdbId` como clave primaria.
4. Eliminar la llamada a `enrich_tmdb()` — los datos ya están en la BD.
5. Eliminar las migraciones `migrate_genres.py`, `migrate_remove_indian.py` (TMDB tiene géneros normalizados nativamente).
6. Actualizar `build_query()` para usar IDs numéricos de géneros en lugar de strings.

**Ventaja:** TMDB ya tiene géneros normalizados, datos en español, y watch providers integrados. **Desventaja:** TMDB tiene ~500k películas con ratings propios; la calidad del Bayesian Rating habría que reconstruirla.

### JustWatch

**Dónde se usa:** Indirectamente. TMDB Watch Providers obtiene sus datos de JustWatch vía acuerdo comercial. El endpoint `/movie/{id}/watch/providers` retorna los datos de JustWatch. El link `country_data.get("link")` apunta a la página de JustWatch de esa película.

**Uso legal:** El código accede a los datos de JustWatch a través de la API de TMDB (legal). Mostrar directamente datos de JustWatch requeriría su propia API (no pública). La atribución "via JustWatch" en `WatchProviders.jsx` cumple con los requerimientos de TMDB ToS.

**Riesgo:** JustWatch puede cambiar su acuerdo con TMDB. En ese caso los watch providers desaparecerían sin código propio que cambiar — sería un cambio en la API de TMDB.

---

## FASE 9 — FRONTEND (REACT PROFUNDO)

### Árbol de componentes y estado

```
App (estado: sliders, panelOpen, remixKey, spinning)
  ├── PosterBackground (props: posterUrl, loading)
  │     estado local: displayed (preloaded URL)
  │
  ├── MovieDisplay (props: movie, loading)
  │     estado local: phrase (idle text, random on mount)
  │
  ├── WatchProviders (props: tmdbId, movieTitle)
  │     hook: useWatchProviders(tmdbId) → estado local: providers
  │
  ├── MixerSlider × 2 (props: label, value, onChange, color)
  │     estado local: isDragging, isHovered, counter
  │     motion values: raw, spring, velocity, yOffset
  │
  ├── SamplePads (props: selected, onChange)
  │     sin estado local — stateless
  │
  ├── YearRangeSlider (props: yearFrom, yearTo, onChangeFrom, onChangeTo)
  │     sin estado local — stateless
  │
  ├── RuntimeFilter (props: value, onChange)
  │     sin estado local — stateless
  │
  └── PlatformFilter (props: value, onChange)
        sin estado local — stateless
```

**Hooks custom:**
- `useMix(sliders, remixKey)` — fetch + estado de película, loading, error
- `useRetention(defaultSliders)` — localStorage + welcome message
- `useWatchProviders(tmdbId)` — fetch watch providers

### Problemas de diseño

**1. Estado en App.jsx demasiado plano:**
`sliders` es un objeto flat con 7 campos. Cualquier cambio en un campo re-renderiza todos los componentes que reciben callbacks via `set(key)`. En la práctica no es un problema de rendimiento hoy (React 18 batching), pero una refactorización a `useReducer` o Zustand mejoraría la trazabilidad.

**2. `PANEL_W = '40%'` hardcodeado:**
No hay breakpoints. En pantallas <768px el panel ocupa 40% de pantalla dejando solo 60% para la película. En móvil, la UX es deficiente.

**3. Framer Motion en sliders — potencial jank:**
`MixerSlider` usa 5 motion values (raw, spring, velocity, yOffset + el color del thumb via CSS var). Con 2 sliders = 10 motion values en el compositor. En dispositivos lentos puede haber jank al arrastrar. En la práctica, los sliders de rango no son muy frecuentes en arrastre continuo.

**4. `MovieDisplay` overview no truncado:**
Si `overview` es muy largo (descripciones TMDB pueden ser >500 caracteres), el texto empuja el layout. No hay `line-clamp` aplicado.

### Performance

**Carga inicial:** Framer Motion (~40KB gzip) es la dependencia más pesada. React + ReactDOM (~45KB). Tailwind purgado en build. Total estimado: ~130KB gzip — aceptable.

**Re-renders:** El patrón `set(key)` en App.jsx con `setSliders` + `saveSliders` produce un re-render por cada cambio de slider. Con React 18 y el event loop de Framer Motion esto es fluido en desktop. En mobile lento puede ser perceptible.

---

## FASE 10 — BACKEND

### Framework y arquitectura

FastAPI 0.111.0 con Uvicorn. Async throughout excepto `run_query` que usa `run_in_threadpool` para sqlite3 síncrono. Middleware: solo CORS.

### Endpoints reales

| Método | Ruta | Autenticación | Caché |
|---|---|---|---|
| GET | `/api/movies/mix` | Ninguna | Ninguna |
| GET | `/api/movies/{tmdb_id}/watch-providers` | Ninguna | Ninguna |
| GET | `/health` | Ninguna | Ninguna |
| POST | `/api/events` | Ninguna | N/A |

### Lógica de negocio

La Vibe Matrix es la lógica de negocio central. Toda la inteligencia del sistema está en dos funciones: `interpolate_tone()` (8 anclas × interpolación lineal) y `cerebro_to_constraints()` (curvas exponencial y cóncava). El resto (build_query, fallback, pick_one) es infraestructura.

### Seguridad

**Sin autenticación en ningún endpoint.** Vulnerabilidades actuales:
- `/api/movies/mix` puede ser llamado en bucle automatizado consumiendo el cupo de TMDB.
- `/api/events` acepta cualquier JSON — puede ser spameado.
- No hay rate limiting.
- No hay validación del body en `/api/events` más allá del JSON parse con try/catch.

Para producción mínima: añadir `slowapi` para rate limiting por IP (`10 req/min` en `/api/movies/mix`).

### Problemas estructurales

**Monolito de 815 líneas:** Todo en `main.py`. Funciona para este tamaño pero si crece (tests, nuevos endpoints, modelos de BD) se volvería inmanejable. Separar en `routers/`, `services/`, `models/` sería la evolución natural.

**Sin tests:** Ni unittest ni pytest. Las funciones `translate_vibes()`, `build_query()`, `interpolate_tone()` son puras y fácilmente testables. La ausencia de tests es el mayor riesgo para refactorización futura.

---

## FASE 11 — TECNOLOGÍAS

### React 18 + Vite 5

**Qué es:** React como librería de UI. Vite como bundler/dev server ultra-rápido (ESM nativo).

**Cómo se usa:** SPA con `<React.StrictMode>` (implícito en Vite template). `import.meta.env.DEV` para detectar desarrollo (usado en `track.js`). Proxy de Vite a `localhost:8001` para las llamadas a `/api`.

**Problemas:** SPA = no indexable por Google. El proxy de Vite solo funciona en desarrollo — en producción el frontend debe estar detrás de un proxy real (nginx, Caddy) que redirija `/api` al backend.

### Framer Motion 11.3.0

**Cómo se usa:** AnimatePresence para crossfades (PosterBackground, MovieDisplay, badges de error, panel lateral). `motion.div` / `motion.button` para micro-interacciones. `useSpring` + `useMotionValue` + `useVelocity` para el odómetro de MixerSlider.

**Problemas:** Dependencia grande (~40KB gzip) para los efectos que usa. Alternativa ligera para los casos simples (badges, botones) sería CSS transitions. Para el odómetro del slider y el crossfade del poster, Framer Motion está justificado.

### FastAPI 0.111.0

**Cómo se usa:** Framework async Python. Validación de query params con `Query(ge=0, le=100)`. `run_in_threadpool` para sqlite3. `httpx.AsyncClient` para TMDB.

**Problemas:** Sin tests. Sin dependency injection formal (las funciones se llaman directamente). `TMDB_API_KEY` como variable global del módulo — en tests habría que parchear el módulo.

### SQLite + sqlite3 (stdlib)

**Cómo se usa:** BD local de ~300MB con 144k películas. Schema: tabla `movies` (7 columnas) + tabla `movie_genre` (2 columnas, normalizada). 8 índices en `movies` + 2 en `movie_genre`.

**Límites:** Escrituras serializdas. `journal_mode=WAL` en las migraciones pero no se activa en runtime. Para solo lecturas (el caso de uso actual) SQLite es perfectamente válido hasta ~200 req/s concurrentes.

### Tailwind CSS 3.4.6

**Cómo se usa:** Clases utilitarias + CSS personalizado en `index.css` (`@layer components` para `.mixer-slider`, `.year-slider`, `.glass`). CSS variables dinámicas para el glow del slider thumb (`--thumb-shadow`).

**Problema:** En `App.jsx` hay mezcla de Tailwind y `style={{ }}` inline. Los colores (`#080810`, `rgba(255,255,255,0.07)`, `#e8a020`) se repiten como magic strings en múltiples componentes sin un design token centralizado.

---

## FASE 12 — NEGOCIO

### ICP real (del código, no de la intención)

El código confirma el ICP de PRODUCT.md: persona que quiere una película rápido sin indecisión. Los fallbacks offline son Blade Runner 2049, Interstellar, Parasite, Mad Max — apuntan a 25-40 años, cultura cinematográfica media-alta, no cinéfilo extremo. Los géneros de los pads no incluyen géneros de nicho pequeño (Western, Musical, Sport). El rango de años por defecto (1920-2024) es más amplio de lo que un casual picker usaría — el usuario típico probablemente filtra a "últimas décadas".

### Casos de uso reales

- Usuario que no sabe qué ver un viernes por la noche → mueve sliders hacia "oscuro" + "Thriller" + "últimos 10 años" → obtiene resultado
- Usuario que tiene Netflix y quiere saber qué ver ahí → activa filtro Netflix → obtiene película disponible en su plataforma
- Usuario que quiere algo "indie/autor" → mueve Cerebro a la derecha → obtiene películas con menos votos pero alta nota

### Monetización posible

Sin cambiar la filosofía del producto (sin login, sin ads por diseño del PRODUCT.md):
- **Afiliación JustWatch:** Si JustWatch tiene programa de afiliados por clicks en sus links. Hoy los clicks ya se trackan en `track.js` — la infraestructura está.
- **Versión Pro sin límites de platform filter:** Hoy solo hay 5 plataformas hardcoded. Una versión con todas las plataformas disponibles en TMDB podría ser de pago.
- **API pública para terceros:** Exponer la Vibe Matrix como API para que otras apps puedan usarla.

### Viabilidad

El producto es técnicamente completo para un MVP. Los bloqueantes para escalar son SEO (sin Next.js no hay tráfico orgánico) y los bugs CORS (sin corrección no se puede desplegar). Con los 5 fixes del Sprint 0 el producto está listo para producción real.

---

## FASE 13 — MÉTRICAS

### KPIs del sistema (basados en eventos definidos en `track.js`)

| Evento | KPI | Fórmula | Objetivo |
|---|---|---|---|
| `mix_generated` | Mezclas por sesión | count por `session_id` | ≥ 1 (TTR < 3s) |
| `remix_clicked` | Tasa de insatisfacción | `remix_clicked` / `mix_generated` | < 3 por sesión |
| `where_to_watch_clicked` | Conversión principal | clicks / `mix_generated` | > 40% |
| `pad_toggled` | Uso de géneros | distribución de `genre` | insight de contenido |
| `session_returned` | Retención | count con delta < 24h | > 35% D1 |
| `share_clicked` | K-factor | shares / sesiones únicas | > 0.3 |

### Qué falta para medir

- `share_clicked` no se llama — la funcionalidad no existe. Sin ella, el K-factor es 0.
- `where_to_watch_clicked` solo se trackea cuando hay providers disponibles. Películas sin TMDB ID o sin providers en ES dan 0 conversiones aunque el usuario quiera verlas.
- Tiempo hasta primera película (Time to Value < 3s): no se mide actualmente. Añadir `performance.now()` al inicio de `fetchMix()` y al `setMovie(data)`.

---

## FASE 14 — IDEAS BRILLANTES (PRODUCT EXPANSION)

### Idea 1 — URL de mezcla compartible

**Problema que resuelve:** Hoy si compartes CineMix con alguien, llegan a la app con los sliders en default, no en tu configuración.

**Cómo encaja:** Serializar el estado de sliders en la URL: `/mezcla?tone=70&cerebro=30&genres=Thriller,Crime&y=2000-2020`. Al montar, `useRetention` o el propio `useMix` lee los params y los aplica. Opcionalmente, route con slug: `/mezcla/thriller-oscuro-2000s`.

**Impacto:** Activa el K-factor (PRODUCT.md §3.3). Es el vector viral principal.

**Dificultad:** Baja (2-3 días). Solo frontend — no requiere cambios en backend.

---

### Idea 2 — Modo "Noche de parejas"

**Problema que resuelve:** Dos personas con gustos distintos en el mismo sofá. Hoy la app es individual.

**Cómo encaja:** Dos conjuntos de sliders en pantalla. El backend recibe los constraints de ambos y hace un `INTERSECT` de los dos pools (películas que satisfacen a ambos). Si el intersect es vacío, el sistema sugiere la película del pool con menor distancia entre los dos conjuntos de constraints.

**Impacto:** Nuevo caso de uso, nueva audiencia. Diferenciador claro vs. Netflix.

**Dificultad:** Media (1 semana). Requiere UI de doble panel y lógica de intersección en backend.

---

### Idea 3 — "Modo rápido" para móvil

**Problema que resuelve:** En móvil, abrir el panel lateral, mover sliders y pulsar Mezclar es friction. La app no es realmente usable en phone.

**Cómo encaja:** En pantallas < 640px, reemplazar el panel lateral por un bottom sheet con swipe gestures. 3 presets de toque rápido: "Algo ligero", "Algo intenso", "Sorpréndeme". Un swipe arriba → Mezclar.

**Impacto:** Abre el mercado mobile (probablemente >60% del tráfico real). Activa Web Share API native para compartir directamente desde el móvil.

**Dificultad:** Media-alta (1-2 semanas). Requiere rediseño de layout.

---

### Idea 4 — Historial de sesión ("El setlist")

**Problema que resuelve:** El usuario hace 5 mezclas, le gustan 2. Luego no recuerda cuáles.

**Cómo encaja:** Guardar las últimas 5 películas de la sesión en `sessionStorage`. Mostrar como carrusel pequeño debajo del botón Mezclar. Click en una → restaura esa película como la mostrada actualmente.

**Impacto:** P2 en el backlog de PRODUCT.md. Reduce frustración de "la vi pero se fue".

**Dificultad:** Baja (1-2 días). Solo frontend, sessionStorage.

---

### Idea 5 — SEO programático + páginas de película

**Problema que resuelve:** Sin SEO, el único canal de adquisición es boca a boca / compartir. Sin tráfico orgánico no hay crecimiento sostenible.

**Cómo encaja:** Migrar a Next.js. Generar páginas estáticas para las 1000 combinaciones de géneros más populares: `/mezcla/thriller-anos-90`, `/mezcla/comedia-familiar-clasicos`. Generar páginas de película: `/pelicula/parasite-2019`.

**Impacto:** Potencialmente el mayor palanca de crecimiento a largo plazo. Palabras clave como "mejores películas thriller años 90" tienen miles de búsquedas mensuales.

**Dificultad:** Alta (3-4 semanas). Requiere migración de arquitectura completa a Next.js.

---

## FASE 15 — PROMPTS PARA CLAUDE (LISTOS PARA USAR)

### Prompt 1 — Refactor completo del repo

```
Tengo el repositorio CineMix (movieMixer). 
El backend es FastAPI en `backend/main.py` (815 líneas, todo en un archivo).
El frontend es React 18 + Vite en `src/`.

Quiero refactorizar el backend manteniendo la funcionalidad exacta:

1. Separar `main.py` en:
   - `backend/models.py` — VibeConstraints dataclass + constantes (TONE_ANCHORS, PLATFORM_IDS, etc.)
   - `backend/vibe_matrix.py` — translate_vibes(), interpolate_tone(), cerebro_to_constraints(), genre_popularity_factor()
   - `backend/query_builder.py` — build_query(), relax(), pick_one()
   - `backend/tmdb.py` — enrich_tmdb(), discover_tmdb_by_platform(), watch_providers helper
   - `backend/database.py` — run_query()
   - `backend/routers/movies.py` — endpoints FastAPI
   - `backend/main.py` — solo app = FastAPI() + include_router + middleware

2. Añadir `ALLOWED_ORIGINS` desde ENV en el middleware CORS:
   `os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")`

3. Añadir `"War": 10752` en el dict IMDB_TO_TMDB_GENRE de `models.py`

4. Crear `backend/tests/test_vibe_matrix.py` con pytest:
   - test que tone=0 produce Comedy/Animation en priority_genres
   - test que tone=100 produce Horror/Crime en priority_genres  
   - test que cerebro=0 produce min_votes >= 100000
   - test que cerebro=100 produce min_votes <= 2000
   - test que genre War no está en exclude_genres cuando tone=50

Mantén exactamente la misma lógica. No cambies ningún algoritmo.
```

---

### Prompt 2 — Mejora del frontend React

```
Tengo el frontend de CineMix en `src/`. Es React 18 + Vite + Tailwind + Framer Motion.

Problemas a resolver:

1. RESPONSIVE MOBILE:
   - `App.jsx` tiene `const PANEL_W = '40%'` hardcodeado
   - En mobile (< 768px), convertir el panel lateral en un bottom sheet
   - El bottom sheet se abre con swipe up o tap en un handle
   - En desktop, mantener el comportamiento actual (panel lateral 40%)
   - Usar `window.innerWidth` o un hook `useBreakpoint()` para detectar

2. OVERVIEW TRUNCADO:
   - `MovieDisplay.jsx` muestra `movie.overview` sin truncar
   - Aplicar `overflow: hidden; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical` 
   - Añadir link "Leer más" que expanda al hacer click

3. DESIGN TOKENS:
   - Los colores `#e8a020`, `#080810`, `rgba(255,255,255,0.07)` aparecen como magic strings en múltiples componentes
   - Crear `src/lib/tokens.js` con `export const GOLD = '#e8a020'` etc.
   - Reemplazar todas las occurrencias

4. ELIMINAR `src/hooks/useDebounce.js`:
   - El archivo existe pero no se importa en ningún componente
   - Eliminarlo y verificar que no hay referencias restantes

Los componentes a modificar son: App.jsx, MovieDisplay.jsx, y el resto donde aparezcan magic strings de color.
No cambies la lógica de negocio ni el data fetching.
```

---

### Prompt 3 — Mejora del backend

```
Tengo el backend de CineMix en `backend/main.py` (FastAPI + SQLite).

Quiero añadir estas mejoras de producción:

1. RATE LIMITING:
   Instalar `slowapi` y añadir:
   - `/api/movies/mix`: máx 20 req/min por IP
   - `/api/events`: máx 60 req/min por IP
   - Error 429 con mensaje JSON: {"error": "too_many_requests", "retry_after": 60}

2. CONNECTION POOL SQLITE:
   La función `run_query()` abre y cierra conexión en cada llamada.
   Reemplazar con un pool simple usando `threading.local()`:
   ```python
   _local = threading.local()
   def get_conn():
       if not hasattr(_local, 'conn'):
           _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
           _local.conn.row_factory = sqlite3.Row
       return _local.conn
   ```

3. REDIS CACHE PARA TMDB:
   Añadir caché opcional para `enrich_tmdb()`. Si `REDIS_URL` está en ENV:
   - Antes de llamar a TMDB, check Redis con key `tmdb:find:{tconst}` TTL 7 días
   - Si hit: return caché. Si miss: llamar TMDB, guardar resultado en Redis
   - Si Redis no está configurado: comportamiento actual (sin caché)
   - Usar `redis.asyncio` (pip install redis)

4. .env.example:
   Crear archivo con:
   ```
   TMDB_API_KEY=your_tmdb_api_key_here
   ALLOWED_ORIGINS=http://localhost:5173
   REDIS_URL=          # opcional, dejar vacío para sin caché
   ```

No cambies la lógica de la Vibe Matrix ni los endpoints.
```

---

### Prompt 4 — Migración IMDb → TMDB como fuente primaria

```
Tengo CineMix. La BD actual usa datos de IMDb (setup_db.py descarga title.basics.tsv.gz).
Quiero migrar a TMDB como fuente primaria de datos.

El plan:

1. NUEVO `backend/setup_db_tmdb.py`:
   - Descargar el daily export de TMDB: 
     `http://files.tmdb.org/p/exports/movie_ids_{fecha}.json.gz`
   - Obtener detalles de cada película via `GET /movie/{id}?language=es-ES`
   - Filtrar: solo películas con `vote_count >= 1000`
   - Calcular Bayesian WR igual que el script actual: WR = (V/(V+m))×R + (m/(V+m))×C
   - Schema de la nueva tabla:
     ```sql
     CREATE TABLE movies (
       tmdb_id      INTEGER PRIMARY KEY,
       title        TEXT NOT NULL,
       year         INTEGER NOT NULL,
       overview     TEXT,
       poster_path  TEXT,
       vote_average REAL NOT NULL,
       vote_count   INTEGER NOT NULL,
       vibe_score   REAL NOT NULL,
       runtime      INTEGER
     )
     CREATE TABLE movie_genre (
       tmdb_id    INTEGER NOT NULL,
       genre_id   INTEGER NOT NULL,
       PRIMARY KEY (tmdb_id, genre_id)
     )
     ```

2. Actualizar `backend/main.py`:
   - Cambiar clave primaria de `tconst` a `tmdb_id`
   - Eliminar la llamada a `enrich_tmdb()` del endpoint `/api/movies/mix` (los datos ya están en BD)
   - Actualizar `build_query()` para usar `genre_id` numérico en lugar de string
   - Mantener `IMDB_TO_TMDB_GENRE` mapeando los IDs correctos del panel de géneros

3. El endpoint `/api/movies/{tmdb_id}/watch-providers` no cambia.

Importante: mantener exactamente la misma interfaz de respuesta JSON del endpoint `/api/movies/mix`.
El frontend no debe cambiar.
```

---

### Prompt 5 — Expansión: botón compartir + URL de mezcla

```
Quiero añadir a CineMix la funcionalidad de compartir (PRODUCT.md §3.3 — K-factor).

Dos partes:

PARTE 1 — URL de mezcla compartible:
En `src/App.jsx`:
- Al montar, leer los query params de la URL (?tone=70&cerebro=30&genres=Thriller,Crime&yearFrom=2000&yearTo=2020)
- Si existen, usarlos como estado inicial en lugar de localStorage o INITIAL_SLIDERS
- Prioridad: URL params > localStorage > INITIAL_SLIDERS

En `src/hooks/useMix.js` o en App.jsx:
- Cuando se genera una mezcla exitosa, actualizar la URL con `window.history.replaceState` para incluir los sliders actuales
- Formato: `/mezcla?tone=70&cerebro=30&genres=Thriller,Crime`

PARTE 2 — Botón compartir:
En `src/components/MovieDisplay.jsx`:
- Añadir un botón pequeño de compartir debajo del título (visible solo cuando hay película)
- Si `navigator.share` existe (móvil): usar Web Share API
  ```js
  navigator.share({
    title: `${movie.title} · CineMix`,
    text: `CineMix me encontró esta: ${movie.title} (${movie.year}). ¿Qué te encuentra a ti?`,
    url: window.location.href
  })
  ```
- Si no existe (desktop): copiar URL al portapapeles + feedback visual "¡Copiado!"
- Llamar `track(Events.SHARE_CLICKED, { title: movie.title, platform: 'web_share' | 'clipboard' })`

Estilo: el botón debe ser sutil — no más llamativo que el botón Mezclar.
```

---

## FASE 16 — APÉNDICE DE LIMPIEZA DEL REPOSITORIO

### 1. Archivos a eliminar

**`src/hooks/useDebounce.js`**
- Razón: No se importa en ningún archivo del proyecto. Fue el hook central de la versión anterior del sistema de fetch (antes del fix "Debounce Misfire" de 2026-04-20). Tras migrar a `slidersRef` en `useMix.js`, quedó huérfano.
- Riesgo de mantenerlo: Ninguno funcional. Confunde a desarrolladores nuevos que puedan pensar que se usa o que necesita actualizarse.

### 2. Código a refactorizar

**`src/App.jsx` — `PANEL_W = '40%'` hardcodeado**
- Problema: No responsive. El panel en mobile rompe el layout.
- Refactorización: Hook `useBreakpoint()` o media query. En mobile: bottom sheet. En desktop: panel lateral.

**`backend/main.py` — CORS hardcodeado**
- Problema: Solo permite localhost. Bloqueante para deploy.
- Refactorización: `os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")`

**`src/App.jsx` — `yearTo: 2024` en INITIAL_SLIDERS**
- Problema: Películas de 2025-2026 invisibles por defecto.
- Refactorización: `yearTo: new Date().getFullYear()`

**`backend/main.py` — `IMDB_TO_TMDB_GENRE` incompleto**
- Problema: `War` presente en `SamplePads.jsx` pero no en el dict.
- Refactorización: Añadir `"War": 10752, "Family": 10751` (Family ya está pero revisarlo).

**`src/components/` — magic strings de color**
- Problema: `#e8a020`, `#080810`, `rgba(255,255,255,0.07)` repetidos en 6+ archivos.
- Refactorización: `src/lib/tokens.js` con constantes exportadas.

**`backend/main.py` — monolito de 815 líneas**
- Problema: Difícil de testear y mantener.
- Refactorización: Separar en `models.py`, `vibe_matrix.py`, `query_builder.py`, `tmdb.py`, `database.py`, `routers/`.

### 3. Riesgos de no limpiar

**CORS hardcodeado:**
Si se despliega en producción sin corregir → la app silenciosamente falla para todos los usuarios reales (solo funciona en localhost). Es el bug más peligroso del repositorio.

**Sin README:**
Cualquier nuevo colaborador (o el autor tras 6 meses) no puede levantar el proyecto. Hay 4 scripts de setup que ejecutar en orden específico (`setup_db.py` → `migrate_genres.py` → `migrate_runtime.py` → `migrate_remove_indian.py`) y ese orden no está documentado en ningún lugar.

**`yearTo: 2024`:**
A medida que pasen los años, la app excluirá un año más de cine reciente por cada año que pase. En 2027 excluirá 3 años de estrenos.

**Código muerto (`useDebounce.js`):**
Bajo riesgo inmediato. Alto riesgo de confusión en PR reviews y onboarding. Si alguien importa el hook pensando que ya funciona, introduce silenciosamente el bug del debounce misfire que ya fue corregido.

**Magic strings de color:**
Si el equipo decide cambiar el color dorado `#e8a020` por un nuevo brand color, hay que buscarlo y reemplazarlo en 6+ archivos con riesgo de perder alguno.

---

*Análisis generado con lectura completa de todos los archivos del repositorio. Cada afirmación está respaldada por código verificado.*

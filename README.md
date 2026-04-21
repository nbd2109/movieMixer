# CineMix

> "No sabe qué ver. Nosotros sí."

Mezclador de películas para la persona que abre Netflix un viernes a las 21:30 y no sabe qué poner. Mueve los sliders, activa géneros, pulsa **Mezclar** — una película, sin más.

---

## Stack

| Capa | Tecnología |
|------|-----------|
| Frontend | React 18 + Vite + Tailwind + Framer Motion |
| Backend | FastAPI + Python + uvicorn |
| Base de datos | SQLite local (144k películas IMDb, Bayesian WR) |
| Metadatos | TMDB API — póster, sinopsis, watch providers (JustWatch) |

---

## Setup

### Requisitos

- Python 3.10+
- Node.js 18+
- Cuenta gratuita en [TMDB](https://www.themoviedb.org/settings/api) para obtener una API key

### 1. Clonar y configurar variables de entorno

```bash
git clone https://github.com/nbd2109/movieMixer.git
cd movieMixer
cp .env.example .env
# Edita .env y pon tu TMDB_API_KEY
```

### 2. Construir la base de datos

Ejecuta los scripts en este orden exacto desde la carpeta `backend/`:

```bash
cd backend
python setup_db.py          # Descarga datos IMDb y crea movies.db (~5 min)
python migrate_genres.py    # Crea tabla movie_genre con índices
python migrate_runtime.py   # Añade columna runtimeMinutes
```

> `setup_db.py` descarga `title.basics.tsv.gz` (~1GB) y `title.ratings.tsv.gz` de IMDb automáticamente.
> `movies.db` resultante pesa ~300MB y está en `.gitignore`.

### 3. Levantar el backend

```bash
cd backend
uvicorn main:app --port 8001 --reload
```

El backend estará en `http://localhost:8001`. Verifica con:

```bash
curl http://localhost:8001/health
# {"status":"ok","movies_in_db":144000}
```

### 4. Levantar el frontend

```bash
# En otra terminal, desde la raíz del proyecto
npm install
npm run dev
```

La app estará en **http://localhost:5173**.

---

## Variables de entorno

Ver `.env.example` para la lista completa.

| Variable | Requerida | Descripción |
|----------|-----------|-------------|
| `TMDB_API_KEY` | Sí | API key de TMDB (gratuita) |
| `ALLOWED_ORIGINS` | No | Origins permitidos en CORS, separados por coma. Default: `http://localhost:5173` |

---

## Arquitectura

```
Browser (React SPA / Vite :5173)
    │  HTTP — proxy Vite → /api
    ▼
FastAPI (Python :8001)
    ├── SQLite movies.db   ← ruta estándar (144k películas IMDb)
    └── TMDB Discover API  ← ruta con plataforma seleccionada
            └── TMDB /find/{tconst}  ← enrich (póster + sinopsis)
```

El algoritmo central (**Vibe Matrix**) traduce los sliders Tono y Cerebro en restricciones SQL:
- `interpolate_tone(0–100)` → pesos por género interpolados entre 8 anclas emocionales
- `cerebro_to_constraints(0–100)` → `min_votes` (exponencial) + `min_vibe_score` (cóncava)
- `relax()` → 5 pasos de fallback progresivo, nunca devuelve vacío

---

## Scripts de migración opcionales

| Script | Cuándo ejecutarlo |
|--------|------------------|
| `migrate_remove_indian.py` | Si quieres filtrar producciones del subcontinente indio. Requiere descargar `title.akas.tsv.gz` (~2GB) adicional de IMDb. |

---

## Producción

Para desplegar en producción:

1. Añade el dominio de tu frontend a `ALLOWED_ORIGINS` en el `.env` del servidor
2. El frontend necesita un proxy real (nginx, Caddy) que redirija `/api` al backend
3. Ver `UPDATES.md` para el roadmap de Redis, rate limiting y migración a Next.js

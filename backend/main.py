"""
CineMixer Backend v2.0 — FastAPI
Arquitectura: SQLite local (IMDb) para selección + TMDB para enriquecimiento.

Flujo por request:
  1. translate_vibes()  — convierte sliders a VibeConstraints
  2. build_query()      — construye SQL parametrizado
  3. Fallback loop      — relaja restricciones si no hay resultados
  4. pick_one()         — elige 1 película aleatoria del pool (con sesgo opcional)
  5. enrich_tmdb()      — añade póster y sinopsis desde TMDB (best-effort)
"""

import bisect
import copy
import os
import random
import sqlite3
from dataclasses import dataclass, field
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE    = "https://api.themoviedb.org/3"
TMDB_IMG     = "https://image.tmdb.org/t/p/original"
DB_PATH      = os.path.join(os.path.dirname(__file__), "movies.db")

# Géneros a excluir siempre (no son películas reales de cine)
ALWAYS_EXCLUDE = ["Adult", "News", "Reality-TV", "Talk-Show", "Game-Show"]

# ── TONE ANCHORS ──────────────────────────────────────────────────────────────
# 8 puntos del espectro emocional, cada uno con afinidades por género (0.0–1.0).
# Entre anclas se interpola linealmente → cada valor del slider es único.
#
#   afinidad >= 0.65  →  género preferido (pool prioritario en pick_one)
#   afinidad >= 0.45  →  incluido en el grupo OR requerido
#   afinidad <= 0.10  →  excluido en los extremos (solo anclas 0 y 100)
#
TONE_ANCHORS: list[tuple[int, dict[str, float]]] = [
    (0,   {'Comedy': 1.0, 'Animation': 0.9, 'Family': 0.8, 'Adventure': 0.2}),
    (15,  {'Comedy': 0.8, 'Adventure': 0.7, 'Family': 0.5, 'Romance': 0.3}),
    (30,  {'Romance': 0.8, 'Comedy': 0.5, 'Drama': 0.3, 'Adventure': 0.3}),
    (45,  {'Drama': 0.8, 'Romance': 0.5, 'Biography': 0.4}),
    (55,  {'Drama': 0.9, 'Biography': 0.4, 'History': 0.4, 'Mystery': 0.3}),
    (70,  {'Thriller': 0.8, 'Crime': 0.7, 'Mystery': 0.5, 'Drama': 0.3}),
    (85,  {'Crime': 0.8, 'Thriller': 0.7, 'Horror': 0.6, 'Mystery': 0.3}),
    (100, {'Horror': 1.0, 'Crime': 0.6, 'Thriller': 0.5}),
]

_TONE_VALUES = [a[0] for a in TONE_ANCHORS]

# Géneros que se excluyen en los extremos absolutos del slider
_TONE_EXCLUDE_LOW  = ['Horror', 'Crime', 'Thriller', 'Mystery']   # tone <= 10
_TONE_EXCLUDE_HIGH = ['Comedy', 'Family', 'Animation', 'Romance'] # tone >= 90


def interpolate_tone(tone: int) -> dict[str, float]:
    """
    Devuelve {genre: weight} para una posición del slider (0–100).
    Interpola linealmente entre las dos anclas más cercanas.
    """
    if tone <= _TONE_VALUES[0]:
        return dict(TONE_ANCHORS[0][1])
    if tone >= _TONE_VALUES[-1]:
        return dict(TONE_ANCHORS[-1][1])

    idx   = bisect.bisect_right(_TONE_VALUES, tone) - 1
    t0, g0 = TONE_ANCHORS[idx]
    t1, g1 = TONE_ANCHORS[idx + 1]
    alpha  = (tone - t0) / (t1 - t0)   # 0.0 → ancla izquierda, 1.0 → ancla derecha

    all_genres = set(g0) | set(g1)
    return {
        g: g0.get(g, 0.0) * (1 - alpha) + g1.get(g, 0.0) * alpha
        for g in all_genres
    }

# Umbrales de Cerebro calibrados contra percentiles reales de la BD:
#   P99  = 187.120 votos  (top 1%   → ~1.800 pelís)
#   P95  =  24.616 votos  (top 5%   → ~7.200 pelís)
#   P90  =   7.717 votos  (top 10%  → ~14.500 pelís)
#   P85  =   3.000 votos  (top 15%  → ~21.700 pelís)
# Cerebro LOW  (0-35):  >= 100.000  → ~2.500 pelís  — blockbusters reales
# Cerebro MID (36-69):  >= 15.000   → ~8.000 pelís  — mainstream de calidad
# Cerebro HIGH (70-100): 3.000–50.000 → ~10.000 pelís — autor/nicho

app = FastAPI(title="CineMixer API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:4173",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════════════════════
# 1. MODELO DE DATOS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class VibeConstraints:
    """
    Restricciones resueltas listas para convertirse en SQL.

    genre_groups   → Lista de grupos de géneros. La película debe coincidir
                     con ≥1 género de CADA grupo (AND entre grupos, OR dentro).
                     Ejemplo: [['Action','Sci-Fi'], ['Drama']] significa
                     (Action OR Sci-Fi) AND (Drama).

    exclude_genres → La película NO debe contener ninguno de estos géneros.
                     Las exclusiones siempre tienen prioridad sobre los grupos.

    priority_genres → Preferencia suave para el selector aleatorio (Cerebro alto).
                      No es un filtro hard — solo sesga la elección 70/30.
    """
    genre_groups:    list[list[str]] = field(default_factory=list)
    exclude_genres:  list[str]       = field(default_factory=list)
    priority_genres: list[str]       = field(default_factory=list)
    min_votes:  int           = 50_000
    max_votes:  Optional[int] = None
    min_rating: float         = 6.5
    year_from:  int           = 1990
    year_to:    int           = 2024


# ══════════════════════════════════════════════════════════════════════════════
# 2. VIBE MATRIX — Traducción de sliders a restricciones
# ══════════════════════════════════════════════════════════════════════════════

def translate_vibes(
    genres: list[str],
    tone: int,
    cerebro: int,
    year_from: int,
    year_to: int,
) -> VibeConstraints:
    """
    Aplica la Vibe Matrix y resuelve colisiones.

    RESOLUCIÓN DE COLISIONES
    ────────────────────────
    Las exclusiones siempre ganan. Si el usuario pide Thriller pero Tono=0
    excluye Thriller, ese género se elimina del grupo. Un grupo que queda
    vacío se descarta en lugar de generar una query imposible.
    """
    c = VibeConstraints(year_from=year_from, year_to=year_to)

    # Excluir siempre géneros no cinematográficos
    c.exclude_genres += ALWAYS_EXCLUDE

    # ── GENEROS SELECCIONADOS POR EL USUARIO ──────────────────────────────────
    # Lógica AND: cada género seleccionado es un grupo propio.
    # La película debe contener TODOS los géneros elegidos.
    # Si no elige ninguno, no se aplica filtro de género.
    for genre in genres:
        c.genre_groups.append([genre])

    # ── SLIDER: TONO — interpolación continua entre 8 anclas ─────────────────
    # Cada posición del slider tiene un mix único de afinidades por género.
    # No hay dead zones: todo el rango 0–100 produce resultados distintos.
    tone_weights = interpolate_tone(tone)

    # Géneros con peso alto → grupo OR requerido (la peli debe tener al menos uno)
    required = [g for g, w in tone_weights.items() if w >= 0.45]
    if required:
        c.genre_groups.append(required)

    # Géneros con peso muy alto → sesgo en pick_one (sin ser requisito hard)
    c.priority_genres += [g for g, w in tone_weights.items() if w >= 0.65]

    # Exclusiones hard solo en los extremos absolutos del slider
    if tone <= 10:
        c.exclude_genres += _TONE_EXCLUDE_LOW
    elif tone >= 90:
        c.exclude_genres += _TONE_EXCLUDE_HIGH

    # ── SLIDER: CEREBRO (calibrado con percentiles reales de la BD) ─────────
    # Distribución real: P50=460 | P90=7.717 | P95=24.616 | P99=187.120 votos
    if cerebro <= 35:
        # Blockbuster: top ~1.7% de la BD por votos, nota permisiva
        # >= 100k votos → ~2.500 peliculas (blockbusters garantizados)
        c.min_votes  = 100_000
        c.max_votes  = None
        c.min_rating = 5.5

    elif cerebro <= 69:
        # Mainstream de calidad: top ~5-6% por votos, nota decente
        # >= 15k votos → ~8.000 peliculas conocidas pero no masivas
        c.min_votes  = 15_000
        c.max_votes  = None
        c.min_rating = 6.5

    else:
        # Cine de autor/nicho: por encima de la media pero sin blockbusters
        # 3.000–50.000 votos → ~10.000 peliculas (top 10-15%, excluye nivel Marvel)
        c.min_votes     = 3_000
        c.max_votes     = 50_000
        c.min_rating    = 7.3
        c.priority_genres = ["Biography", "History", "Drama", "Documentary"]

    # ── RESOLUCIÓN DE COLISIONES ──────────────────────────────────────────────
    # Las exclusiones siempre tienen prioridad absoluta.
    # Cada grupo de géneros pierde las opciones excluidas.
    # Un grupo que queda vacío se descarta (no añade restricción imposible).
    exclude_set = set(c.exclude_genres)
    c.genre_groups = [
        [g for g in group if g not in exclude_set]
        for group in c.genre_groups
        if any(g not in exclude_set for g in group)  # Descartar grupos imposibles
    ]

    return c


# ══════════════════════════════════════════════════════════════════════════════
# 3. QUERY BUILDER — Construcción dinámica de SQL parametrizado
# ══════════════════════════════════════════════════════════════════════════════

def build_query(c: VibeConstraints) -> tuple[str, list]:
    """
    Construye un SELECT parametrizado desde VibeConstraints.
    Usa ',' || genres || ',' para que el LIKE funcione en primer y último género.

    Ejemplo con genre_groups=[['Action','Sci-Fi'], ['Drama']] y exclude=['Horror']:
        WHERE startYear BETWEEN ? AND ?
          AND numVotes >= ?
          AND averageRating >= ?
          AND (',' || genres || ',') NOT LIKE '%,Horror,%'
          AND ((',' || genres || ',') LIKE '%,Action,%' OR (',' || genres || ',') LIKE '%,Sci-Fi,%')
          AND ((',' || genres || ',') LIKE '%,Drama,%')
        LIMIT 50
    """
    clauses: list[str] = []
    params:  list      = []

    # Rango de años
    clauses.append("startYear BETWEEN ? AND ?")
    params += [c.year_from, c.year_to]

    # Votos mínimos
    clauses.append("numVotes >= ?")
    params.append(c.min_votes)

    # Votos máximos (solo Cerebro alto — excluye mega-blockbusters)
    if c.max_votes is not None:
        clauses.append("numVotes <= ?")
        params.append(c.max_votes)

    # Nota mínima
    clauses.append("averageRating >= ?")
    params.append(c.min_rating)

    # Géneros excluidos (la película NO debe contener ninguno)
    for genre in c.exclude_genres:
        clauses.append("(',' || genres || ',') NOT LIKE ?")
        params.append(f"%,{genre},%")

    # Grupos de géneros requeridos (AND entre grupos, OR dentro de cada grupo)
    for group in c.genre_groups:
        sub = " OR ".join(["(',' || genres || ',') LIKE ?" for _ in group])
        clauses.append(f"({sub})")
        params += [f"%,{g},%" for g in group]

    sql = f"""
        SELECT tconst, primaryTitle, startYear, genres, averageRating, numVotes
        FROM movies
        WHERE {' AND '.join(clauses)}
        ORDER BY RANDOM()
        LIMIT 100
    """
    return sql, params


# ══════════════════════════════════════════════════════════════════════════════
# 4. SISTEMA DE FALLBACK — Relajación progresiva de restricciones
# ══════════════════════════════════════════════════════════════════════════════

def relax(c: VibeConstraints, step: int) -> Optional[VibeConstraints]:
    """
    Relaja las restricciones en orden de menor a mayor impacto.
    Devuelve None cuando ya no hay nada más que relajar.

    Orden de relajación:
      Paso 1 → Ampliar rango de años ±10 años (menos impacto en el espíritu de la búsqueda)
      Paso 2 → Reducir numVotes a la mitad (más películas candidatas)
      Paso 3 → Eliminar grupos de géneros requeridos (solo quedan exclusiones)
      Paso 4 → Eliminar exclusiones de géneros (pool máximo)
      Paso 5 → Eliminar límite máximo de votos (si existía para Cerebro alto)
    """
    r = copy.deepcopy(c)

    if step == 1:
        r.year_from = max(1900, r.year_from - 10)
        r.year_to   = min(2025, r.year_to   + 10)
    elif step == 2:
        r.min_votes = max(100, r.min_votes // 2)
    elif step == 3:
        r.genre_groups = []
    elif step == 4:
        r.exclude_genres = []
    elif step == 5:
        r.max_votes = None
    else:
        return None

    return r


# ══════════════════════════════════════════════════════════════════════════════
# 5. SELECCIÓN — Aleatorización con sesgo por priority_genres
# ══════════════════════════════════════════════════════════════════════════════

def pick_one(rows: list[dict], priority_genres: list[str]) -> dict:
    """
    Elige 1 película de un pool de hasta 50.
    Si hay priority_genres (Cerebro alto), 70% de probabilidad de elegir
    una película que los tenga. El 30% restante garantiza variedad.
    """
    if priority_genres:
        priority_pool = [
            r for r in rows
            if any(g in r["genres"] for g in priority_genres)
        ]
        if priority_pool and random.random() < 0.70:
            return random.choice(priority_pool)
    return random.choice(rows)


# ══════════════════════════════════════════════════════════════════════════════
# 6. ENRIQUECIMIENTO TMDB — Póster y sinopsis (best-effort)
# ══════════════════════════════════════════════════════════════════════════════

async def enrich_tmdb(title: str, year: int) -> dict:
    """
    Busca la película en TMDB por título+año para obtener póster y sinopsis.
    Devuelve {} si TMDB no está configurado o falla — nunca lanza excepción.
    """
    if not TMDB_API_KEY:
        return {}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{TMDB_BASE}/search/movie",
                params={
                    "api_key":  TMDB_API_KEY,
                    "query":    title,
                    "year":     year,
                    "language": "es-ES",
                },
            )
        if resp.status_code != 200:
            return {}
        results = resp.json().get("results", [])
        if not results:
            return {}
        hit = results[0]
        poster = hit.get("poster_path")
        return {
            "posterUrl": f"{TMDB_IMG}{poster}" if poster else None,
            "overview":  hit.get("overview", ""),
            "tmdbId":    hit.get("id"),
        }
    except Exception:
        return {}


# ══════════════════════════════════════════════════════════════════════════════
# 7. HELPERS DE BASE DE DATOS
# ══════════════════════════════════════════════════════════════════════════════

def run_query(sql: str, params: list) -> list[dict]:
    if not os.path.exists(DB_PATH):
        raise HTTPException(
            503,
            detail="Base de datos no encontrada. Ejecuta: python setup_db.py",
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# 8. ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/movies/mix")
async def mix(
    genres:   str = Query(""),
    tone:     int = Query(50, ge=0, le=100),
    cerebro:  int = Query(50, ge=0, le=100),
    yearFrom: int = Query(1920, ge=1900, le=2026),
    yearTo:   int = Query(2024, ge=1900, le=2026),
):
    # Parsear géneros (string vacío → lista vacía)
    genre_list = [g.strip() for g in genres.split(",") if g.strip()] if genres else []

    # 1. Traducir sliders → restricciones
    constraints = translate_vibes(genre_list, tone, cerebro, yearFrom, yearTo)

    # 2a. Primer intento: con géneros exactos (AND entre todos los seleccionados)
    sql, params = build_query(constraints)
    rows = run_query(sql, params)
    genre_match = "exact"

    # 2b. Si no hay resultados con géneros exactos y el usuario eligió géneros,
    #     devolver 404 — el frontend mostrará el mensaje de "sin coincidencia"
    if not rows and genre_list:
        raise HTTPException(
            404,
            detail={
                "code": "no_genre_match",
                "message": f"Sin películas con: {', '.join(genre_list)}",
                "genres_requested": genre_list,
            }
        )

    # 2c. Sin géneros seleccionados → fallback progresivo normal
    step    = 0
    current = constraints
    while not rows:
        sql, params = build_query(current)
        rows = run_query(sql, params)
        if not rows:
            step   += 1
            relaxed = relax(current, step)
            if relaxed is None:
                raise HTTPException(500, "Sin resultados tras relajación máxima")
            current = relaxed

    # 3. Elegir 1 película
    movie = pick_one(rows, current.priority_genres)

    # 4. Enriquecer con TMDB (póster + sinopsis) — best-effort
    meta = await enrich_tmdb(movie["primaryTitle"], movie["startYear"])

    genres = [g.strip() for g in movie["genres"].split(",") if g.strip()][:3]

    return {
        "title":    movie["primaryTitle"],
        "year":     movie["startYear"],
        "genres":   genres,
        "rating":   round(float(movie["averageRating"]), 1),
        "tconst":   movie["tconst"],
        # De TMDB (None si no disponible)
        "posterUrl": meta.get("posterUrl"),
        "overview":  meta.get("overview", ""),
        "tmdbId":    meta.get("tmdbId"),
        "genre_match": genre_match,
    }


@app.get("/api/movies/{tmdb_id}/watch-providers")
async def watch_providers(tmdb_id: int, country: str = Query("ES")):
    """
    Devuelve dónde ver la película vía TMDB Watch Providers (datos de JustWatch).
    Intenta el país solicitado; hace fallback a US si no hay datos.
    Devuelve lista vacía (no error) cuando TMDB no está configurado o falla.
    """
    if not TMDB_API_KEY:
        return {"flatrate": [], "rent": [], "link": None}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{TMDB_BASE}/movie/{tmdb_id}/watch/providers",
                params={"api_key": TMDB_API_KEY},
            )
        if resp.status_code != 200:
            return {"flatrate": [], "rent": [], "link": None}

        results = resp.json().get("results", {})
        country_data = results.get(country) or results.get("US") or {}

        def fmt(providers):
            return [
                {
                    "id":   p["provider_id"],
                    "name": p["provider_name"],
                    "logo": f"https://image.tmdb.org/t/p/w45{p['logo_path']}",
                }
                for p in providers
                if p.get("logo_path")
            ][:5]

        return {
            "flatrate": fmt(country_data.get("flatrate", [])),
            "rent":     fmt(country_data.get("rent", [])),
            "link":     country_data.get("link"),
        }
    except Exception:
        return {"flatrate": [], "rent": [], "link": None}


@app.get("/health")
async def health():
    try:
        rows = run_query("SELECT COUNT(*) as cnt FROM movies", [])
        return {"status": "ok", "movies_in_db": rows[0]["cnt"]}
    except HTTPException as e:
        return {"status": "error", "detail": e.detail}

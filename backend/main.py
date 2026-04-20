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

# ── PLATAFORMAS DE STREAMING ──────────────────────────────────────────────────
# IDs de proveedor de JustWatch vía TMDB Watch Providers API.
# Fuente: https://developers.themoviedb.org/3/watch-providers
PLATFORM_IDS: dict[str, int] = {
    "netflix": 8,
    "prime":   119,
    "disney":  337,
    "max":     1899,
    "apple":   350,
}

# Nombres de géneros IMDb → IDs de géneros TMDB
IMDB_TO_TMDB_GENRE: dict[str, int] = {
    "Action":      28,
    "Adventure":   12,
    "Animation":   16,
    "Comedy":      35,
    "Crime":       80,
    "Documentary": 99,
    "Drama":       18,
    "Family":      10751,
    "Fantasy":     14,
    "History":     36,
    "Horror":      27,
    "Mystery":     9648,
    "Romance":     10749,
    "Sci-Fi":      878,
    "Thriller":    53,
    "Biography":   18,   # TMDB no tiene Biography; Drama es la categoría más cercana
}

# Mapa inverso: ID TMDB → nombre legible (para reconstruir géneros en respuesta)
_TMDB_GENRE_NAMES: dict[int, str] = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy",
    80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Family",
    14: "Fantasy", 36: "History", 27: "Horror", 9648: "Mystery",
    10749: "Romance", 878: "Sci-Fi", 53: "Thriller",
}

# Lenguas de producción india
INDIAN_LANGUAGES = {"hi", "ta", "te", "ml", "kn", "bn", "mr", "pa", "gu", "ur"}

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

# ── POPULARIDAD POR GÉNERO ────────────────────────────────────────────────────
# Qué tan masivo es un género en términos de votos (1.0 = máximo mainstream).
# Usado para adaptar los umbrales de Cerebro cuando Tono apunta a géneros de nicho.
_GENRE_POPULARITY: dict[str, float] = {
    'Action':      1.00,
    'Comedy':      1.00,
    'Horror':      0.90,
    'Thriller':    0.90,
    'Sci-Fi':      0.85,
    'Adventure':   0.85,
    'Animation':   0.80,
    'Family':      0.80,
    'Romance':     0.75,
    'Crime':       0.75,
    'Drama':       0.70,
    'Mystery':     0.65,
    'Fantasy':     0.65,
    'Biography':   0.35,
    'History':     0.30,
    'Documentary': 0.25,
}


def genre_popularity_factor(tone_weights: dict[str, float]) -> float:
    """
    Devuelve un factor 0.2–1.0 que refleja lo 'masivo' que es el mix de géneros
    que pide Tono. Géneros de nicho (Biography, History) → factor bajo → Cerebro
    afloja sus umbrales de votos para que sigan existiendo resultados.
    """
    if not tone_weights:
        return 1.0
    total = sum(tone_weights.values())
    if total == 0:
        return 1.0
    weighted = sum(_GENRE_POPULARITY.get(g, 0.6) * w for g, w in tone_weights.items())
    return max(0.20, weighted / total)


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

    genre_groups    → AND entre grupos, OR dentro de cada grupo.
    exclude_genres  → Exclusiones hard. Siempre tienen prioridad.
    priority_genres → Sesgo suave en pick_one() (70/30).
    min_votes       → Umbral mínimo de votos (exponencial continua).
    max_votes       → Techo de votos — excluye blockbusters en modo autor.
    min_vibe_score  → Bayesian Weighted Rating mínimo (curva cóncava continua).
    """
    genre_groups:    list[list[str]] = field(default_factory=list)
    exclude_genres:  list[str]       = field(default_factory=list)
    priority_genres: list[str]       = field(default_factory=list)
    min_votes:       int           = 15_000
    max_votes:       Optional[int] = None
    min_vibe_score:  float         = 6.0
    year_from:       int           = 1990
    year_to:         int           = 2024
    runtime_min:     Optional[int] = None
    runtime_max:     Optional[int] = None


# ══════════════════════════════════════════════════════════════════════════════
# 2. VIBE MATRIX — Traducción de sliders a restricciones
# ══════════════════════════════════════════════════════════════════════════════

def cerebro_to_constraints(cerebro: int, pop_factor: float) -> tuple[int, Optional[int], float]:
    """
    Convierte Cerebro (0–100) a (min_votes, max_votes, min_vibe_score)
    usando curvas continuas moduladas por el factor de popularidad del Tono.

    min_votes   — exponencial 200k → 1k escalada por pop_factor
                  cada punto del slider produce un umbral distinto
    max_votes   — techo exponencial que aparece suavemente a partir de cerebro=65
                  excluye mega-blockbusters en modo autor
    min_vibe    — curva cóncava 5.0 → 7.5 (sube rápido al principio)
                  basada en el Bayesian Weighted Rating precomputado

    Ejemplos con pop_factor=1.0 (géneros masivos como Comedy/Action):
      cerebro=0   → min_votes=200k, max=None,   min_vibe=5.00
      cerebro=25  → min_votes= 60k, max=None,   min_vibe=6.09
      cerebro=50  → min_votes= 14k, max=None,   min_vibe=6.65
      cerebro=75  → min_votes=  6k, max=  92k,  min_vibe=7.15
      cerebro=100 → min_votes=  1k, max=  15k,  min_vibe=7.50

    Con pop_factor=0.35 (géneros de nicho como Biography/History):
      cerebro=0   → min_votes= 70k, max=None,   min_vibe=5.00
      cerebro=50  → min_votes=  5k, max=None,   min_vibe=6.65
      cerebro=100 → min_votes= 350, max= 5.2k,  min_vibe=7.50
    """
    cb = cerebro / 100.0

    # ── Mínimo de votos: exponencial 200k → 1k ───────────────────────────────
    # (1/200)^cb: a cb=0 → 1.0, a cb=1 → 0.005
    base_min = 200_000 * (1 / 200) ** cb
    min_votes = max(300, int(base_min * pop_factor))

    # ── Mínimo vibe_score: curva cóncava 5.0 → 7.5 ───────────────────────────
    # cb^0.6 sube más rápido al principio (más discriminante en el rango bajo)
    min_vibe = 5.0 + 2.5 * (cb ** 0.6)

    # ── Máximo de votos: techo exponencial suave a partir de cerebro=65 ───────
    # Evita blockbusters en modo autor sin corte brusco
    # cerebro=65 → ~300k*pop (sin techo real)
    # cerebro=100 → ~15k*pop (excluye todo lo masivo)
    if cerebro >= 65:
        t = (cerebro - 65) / 35          # 0→1 en el rango 65–100
        max_v = 300_000 * pop_factor * (15_000 / 300_000) ** t
        max_votes: Optional[int] = max(3_000, int(max_v))
    else:
        max_votes = None

    return min_votes, max_votes, min_vibe


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
    tone_weights = interpolate_tone(tone)

    # Géneros con peso alto → grupo OR requerido
    required = [g for g, w in tone_weights.items() if w >= 0.45]
    if required:
        c.genre_groups.append(required)

    # Géneros con peso muy alto → sesgo en pick_one
    c.priority_genres += [g for g, w in tone_weights.items() if w >= 0.65]

    # Exclusiones hard solo en extremos absolutos
    if tone <= 10:
        c.exclude_genres += _TONE_EXCLUDE_LOW
    elif tone >= 90:
        c.exclude_genres += _TONE_EXCLUDE_HIGH

    # ── COMBINACIÓN TONO × CEREBRO — curvas continuas ────────────────────────
    pop = genre_popularity_factor(tone_weights)
    c.min_votes, c.max_votes, c.min_vibe_score = cerebro_to_constraints(cerebro, pop)

    # En modo autor (cerebro alto) se sesgua hacia géneros que tienden a tener
    # alta nota con pocos votos — es donde viven las joyas ocultas.
    if cerebro >= 70:
        c.priority_genres += ["Biography", "History", "Drama", "Documentary"]

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

    # Vibe score mínimo (Bayesian Weighted Rating)
    clauses.append("vibe_score >= ?")
    params.append(c.min_vibe_score)

    # Géneros excluidos (la película NO debe contener ninguno)
    for genre in c.exclude_genres:
        clauses.append("(',' || genres || ',') NOT LIKE ?")
        params.append(f"%,{genre},%")

    # Grupos de géneros requeridos (AND entre grupos, OR dentro de cada grupo)
    for group in c.genre_groups:
        sub = " OR ".join(["(',' || genres || ',') LIKE ?" for _ in group])
        clauses.append(f"({sub})")
        params += [f"%,{g},%" for g in group]

    # Duración (solo cuando el usuario activa el filtro)
    if c.runtime_min is not None:
        clauses.append("runtimeMinutes >= ?")
        params.append(c.runtime_min)
    if c.runtime_max is not None:
        clauses.append("runtimeMinutes <= ?")
        params.append(c.runtime_max)

    sql = f"""
        SELECT tconst, primaryTitle, startYear, genres, averageRating, numVotes, runtimeMinutes
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
        r.year_to   = min(2026, r.year_to   + 10)
    elif step == 2:
        r.min_votes      = max(200, r.min_votes // 2)
        r.min_vibe_score = max(5.0, r.min_vibe_score - 0.5)
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

async def enrich_tmdb(tconst: str) -> dict:
    """
    Resuelve la película en TMDB usando el ID de IMDb (tconst) vía /find.
    Esto garantiza un match 1:1 sin ambigüedad por título o año.
    Devuelve {} si TMDB no está configurado o falla — nunca lanza excepción.
    """
    if not TMDB_API_KEY:
        return {}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{TMDB_BASE}/find/{tconst}",
                params={
                    "api_key":         TMDB_API_KEY,
                    "external_source": "imdb_id",
                    "language":        "es-ES",
                },
            )
        if resp.status_code != 200:
            return {}
        results = resp.json().get("movie_results", [])
        if not results:
            return {}
        hit = results[0]
        poster = hit.get("poster_path")
        return {
            "posterUrl":         f"{TMDB_IMG}{poster}" if poster else None,
            "overview":          hit.get("overview", ""),
            "tmdbId":            hit.get("id"),
            "original_language": hit.get("original_language"),
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
# 8. DESCUBRIMIENTO POR PLATAFORMA — TMDB Discover con datos de JustWatch
# ══════════════════════════════════════════════════════════════════════════════

async def _platform_fetch_page(
    platform_id: int,
    page: int,
    genre_ids: list[str],
    year_from: int,
    year_to: int,
    region: str,
) -> list[dict]:
    """
    Una sola llamada a TMDB Discover filtrada por plataforma.
    Devuelve lista vacía en cualquier error — nunca lanza excepción.
    """
    params: dict = {
        "api_key":              TMDB_API_KEY,
        "watch_region":         region,
        "with_watch_providers": str(platform_id),
        "sort_by":              "vote_count.desc",
        "vote_count.gte":       500,       # umbral bajo — la plataforma ya filtra calidad
        "vote_average.gte":     6.0,
        "primary_release_date.gte": f"{year_from}-01-01",
        "primary_release_date.lte": f"{year_to}-12-31",
        "language":             "es-ES",
        "page":                 page,
    }
    if genre_ids:
        params["with_genres"] = ",".join(genre_ids)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{TMDB_BASE}/discover/movie", params=params)
        if resp.status_code == 200:
            return resp.json().get("results", [])
    except Exception:
        pass
    return []


async def discover_tmdb_by_platform(
    platform_id: int,
    genres: list[str],
    year_from: int,
    year_to: int,
) -> dict | None:
    """
    Devuelve una película aleatoria disponible en la plataforma vía TMDB Discover.
    Los datos de disponibilidad son aportados por JustWatch a través de TMDB.

    Estrategia de búsqueda (de más a menos restrictiva):
      1. Región ES, con géneros, páginas 1–5 (pool de variedad)
      2. Región ES, sin géneros
      3. Región US, con géneros  (fallback regional)
      4. Región US, sin géneros

    Devuelve None si TMDB no está configurado o no encuentra nada.
    """
    if not TMDB_API_KEY:
        return None

    genre_ids = list(dict.fromkeys(
        str(IMDB_TO_TMDB_GENRE[g]) for g in genres if g in IMDB_TO_TMDB_GENRE
    ))

    async def _pool(genre_ids_: list[str], region: str) -> list[dict]:
        # Pedir 3 páginas en paralelo para un pool con variedad real
        pages = random.sample(range(1, 6), min(3, 5))
        import asyncio
        batches = await asyncio.gather(
            *[_platform_fetch_page(platform_id, p, genre_ids_, year_from, year_to, region)
              for p in pages]
        )
        # Aplanar y deduplicar por id
        seen: set[int] = set()
        out: list[dict] = []
        for batch in batches:
            for r in batch:
                if r.get("id") not in seen:
                    seen.add(r["id"])
                    out.append(r)
        return out

    results: list[dict] = []

    for (gids, region) in [
        (genre_ids,  "ES"),
        ([],         "ES"),
        (genre_ids,  "US"),
        ([],         "US"),
    ]:
        results = await _pool(gids, region)
        if results:
            break

    if not results:
        return None

    # Filtrar producciones indias
    valid = [r for r in results if r.get("original_language") not in INDIAN_LANGUAGES]
    if not valid:
        valid = results

    hit = random.choice(valid)

    poster       = hit.get("poster_path")
    release_date = hit.get("release_date", "")
    release_year = int(release_date[:4]) if release_date and len(release_date) >= 4 else None
    genres_out   = [
        _TMDB_GENRE_NAMES[gid]
        for gid in hit.get("genre_ids", [])
        if gid in _TMDB_GENRE_NAMES
    ][:3]

    return {
        "title":     hit.get("title", ""),
        "year":      release_year,
        "genres":    genres_out,
        "rating":    round(float(hit.get("vote_average", 0)), 1),
        "runtime":   None,
        "posterUrl": f"{TMDB_IMG}{poster}" if poster else None,
        "overview":  hit.get("overview", ""),
        "tmdbId":    hit.get("id"),
        "genre_match": "platform",
    }


# ══════════════════════════════════════════════════════════════════════════════
# 9. ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/movies/mix")
async def mix(
    genres:     str            = Query(""),
    tone:       int            = Query(50, ge=0, le=100),
    cerebro:    int            = Query(50, ge=0, le=100),
    yearFrom:   int            = Query(1920, ge=1900, le=2026),
    yearTo:     int            = Query(2024, ge=1900, le=2026),
    runtimeMin: Optional[int]  = Query(None, ge=1),
    runtimeMax: Optional[int]  = Query(None, ge=1),
    platform:   str            = Query(""),
):
    genre_list = [g.strip() for g in genres.split(",") if g.strip()] if genres else []

    # ── RUTA PLATAFORMA — TMDB Discover con datos de JustWatch ───────────────
    if platform and platform in PLATFORM_IDS:
        result = await discover_tmdb_by_platform(
            platform_id = PLATFORM_IDS[platform],
            genres      = genre_list,
            year_from   = yearFrom,
            year_to     = yearTo,
        )
        if result:
            return result
        # No caer al SQLite: una película sin verificación de plataforma sería
        # engañosa para el usuario. Devolver 404 con código específico.
        raise HTTPException(
            404,
            detail={
                "code":     "no_platform_match",
                "platform": platform,
                "message":  f"Sin resultados en {platform} con estos ajustes",
            }
        )

    # ── RUTA SQLite — flujo estándar ──────────────────────────────────────────

    # 1. Traducir sliders → restricciones
    constraints = translate_vibes(genre_list, tone, cerebro, yearFrom, yearTo)
    constraints.runtime_min = runtimeMin
    constraints.runtime_max = runtimeMax

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

    # 3+4. Elegir película y enriquecer; reintentar si TMDB la identifica como india
    pool = list(rows)
    for _ in range(min(10, len(pool))):
        movie = pick_one(pool, current.priority_genres)
        meta  = await enrich_tmdb(movie["tconst"])

        if meta.get("original_language") in INDIAN_LANGUAGES:
            pool = [r for r in pool if r["tconst"] != movie["tconst"]]
            if not pool:
                break
            continue
        break

    movie_genres = [g.strip() for g in movie["genres"].split(",") if g.strip()][:3]

    return {
        "title":    movie["primaryTitle"],
        "year":     movie["startYear"],
        "genres":   movie_genres,
        "rating":   round(float(movie["averageRating"]), 1),
        "runtime":  movie.get("runtimeMinutes"),
        "tconst":   movie["tconst"],
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

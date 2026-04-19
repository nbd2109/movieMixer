"""
CineMixer Backend — FastAPI
Endpoint: GET /api/movies/mix
Traduce los 5 sliders del frontend en una petición a TMDB
y devuelve la película más relevante.
"""

import os
import random
from dotenv import load_dotenv
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG  = "https://image.tmdb.org/t/p/original"

app = FastAPI(title="CineMixer API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ── Mapeo de sliders a géneros TMDB ────────────────────────────────────────────
#
# Adrenalina alta  → Acción (28), Thriller (53)
# Adrenalina baja  → Drama (18), Romance (10749)
# Tensión alta     → Terror (27), Misterio (9648)
# Tensión baja     → Comedia (35), Familiar (10751)
# Cerebro alto     → Historia (36), Documental (99), Crimen (80)
# Cerebro bajo     → Aventura (12), Ciencia ficción (878), Fantasía (14)

ADRENALINE_HIGH = [28, 53]   # Acción, Thriller
ADRENALINE_LOW  = [18, 10749] # Drama, Romance
TENSION_HIGH    = [27, 9648]  # Terror, Misterio
TENSION_LOW     = [35, 10751] # Comedia, Familiar
CEREBRO_HIGH    = [36, 99, 80] # Historia, Documental, Crimen
CEREBRO_LOW     = [12, 878, 14] # Aventura, Sci-Fi, Fantasía


def build_genre_ids(adrenaline: int, tension: int, cerebro: int) -> list[int]:
    """Convierte los 3 sliders en una lista de genre_ids para TMDB."""
    genres: set[int] = set()

    # Adrenalina: >= 60 → acción/thriller, <= 40 → drama/romance, medio → mezcla
    if adrenaline >= 60:
        genres.update(ADRENALINE_HIGH)
    elif adrenaline <= 40:
        genres.update(ADRENALINE_LOW)
    else:
        genres.add(random.choice(ADRENALINE_HIGH + ADRENALINE_LOW))

    # Tensión
    if tension >= 60:
        genres.update(TENSION_HIGH)
    elif tension <= 40:
        genres.update(TENSION_LOW)
    else:
        genres.add(random.choice(TENSION_HIGH + TENSION_LOW))

    # Cerebro: alto → cine de autor/nicho, bajo → blockbuster/mainstream
    if cerebro >= 60:
        genres.update(CEREBRO_HIGH)
    elif cerebro <= 40:
        genres.update(CEREBRO_LOW)

    return list(genres)


def build_sort_by(cerebro: int) -> str:
    """
    Cerebro alto  → ordenar por vote_average (cine valorado, no blockbuster)
    Cerebro bajo  → ordenar por popularity (mainstream)
    """
    if cerebro >= 65:
        return "vote_average.desc"
    return "popularity.desc"


GENRE_NAMES = {
    28: "Acción", 53: "Thriller", 18: "Drama", 10749: "Romance",
    27: "Terror", 9648: "Misterio", 35: "Comedia", 10751: "Familiar",
    36: "Historia", 99: "Documental", 80: "Crimen",
    12: "Aventura", 878: "Sci-Fi", 14: "Fantasía",
}


@app.get("/api/movies/mix")
async def mix(
    adrenaline: int = Query(50, ge=0, le=100),
    tension:    int = Query(50, ge=0, le=100),
    cerebro:    int = Query(50, ge=0, le=100),
    yearFrom:   int = Query(1990, ge=1900, le=2026),
    yearTo:     int = Query(2024, ge=1900, le=2026),
):
    if not TMDB_API_KEY:
        raise HTTPException(500, "TMDB_API_KEY no configurada")

    genre_ids = build_genre_ids(adrenaline, tension, cerebro)
    sort_by   = build_sort_by(cerebro)

    # vote_count mínimo varía con cerebro: cine de autor tolera menos votos
    min_votes = 200 if cerebro >= 65 else 500

    params = {
        "api_key": TMDB_API_KEY,
        "language": "es-ES",
        "sort_by": sort_by,
        "with_genres": "|".join(str(g) for g in genre_ids),
        "primary_release_date.gte": f"{yearFrom}-01-01",
        "primary_release_date.lte": f"{yearTo}-12-31",
        "vote_count.gte": min_votes,
        "page": random.randint(1, 3),  # algo de aleatoriedad en la elección
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{TMDB_BASE}/discover/movie", params=params)

    if resp.status_code != 200:
        raise HTTPException(502, f"TMDB error {resp.status_code}")

    data = resp.json()
    results = data.get("results", [])

    if not results:
        # Fallback: quitar filtro de géneros y volver a intentar
        params.pop("with_genres")
        params["page"] = 1
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{TMDB_BASE}/discover/movie", params=params)
        results = resp.json().get("results", [])

    if not results:
        raise HTTPException(404, "No se encontraron películas con esos parámetros")

    # Elegir una película del top-5 resultados de forma pseudo-aleatoria
    movie = random.choice(results[:5])

    poster_path = movie.get("poster_path")
    poster_url  = f"{TMDB_IMG}{poster_path}" if poster_path else None

    # Traducir genre_ids de la película a nombres
    movie_genres = [
        GENRE_NAMES.get(gid, str(gid))
        for gid in movie.get("genre_ids", [])[:3]
    ]

    return {
        "title":     movie.get("title", "Sin título"),
        "year":      int(movie.get("release_date", "0000")[:4]),
        "overview":  movie.get("overview", ""),
        "posterUrl": poster_url,
        "genres":    movie_genres,
        "rating":    round(movie.get("vote_average", 0), 1),
        "tmdbId":    movie.get("id"),
    }


@app.get("/health")
async def health():
    return {"status": "ok"}

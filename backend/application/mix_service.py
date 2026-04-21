"""
Caso de uso: MixService — orquestador principal de CineMix.

Esta capa coordina el dominio (vibe_matrix, relaxation, selection) con los
puertos (MovieRepository, MovieEnricher, PlatformDiscovery). No contiene
lógica de negocio propia ni conoce FastAPI, SQLite ni TMDB directamente.

El MixService recibe sus dependencias por constructor (Dependency Injection),
lo que lo hace trivialmente testeable con dobles de prueba para los puertos.
"""

import copy
import logging
from typing import Optional

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool

from domain.constants import INDIAN_LANGUAGES, PLATFORM_IDS
from domain.entities import VibeConstraints
from domain.ports.movie_enricher import MovieEnricher, PlatformDiscovery
from domain.ports.movie_repository import MovieRepository
from domain.relaxation import STEP_REASON, relax
from domain.selection import pick_one
from domain.vibe_matrix import translate_vibes

logger = logging.getLogger("cinemix")


class MixService:
    """
    Caso de uso principal: recibe los parámetros del usuario y devuelve
    una película recomendada.

    Flujo completo:
      1. translate_vibes()  — convierte sliders a VibeConstraints (dominio puro)
      2. Ruta plataforma    — TMDB Discover si se pidió una plataforma
      3. Ruta SQLite        — búsqueda principal + fallback progresivo
      4. pick_one()         — elección aleatoria con sesgo
      5. enrich()           — póster y sinopsis desde TMDB (best-effort)
    """

    def __init__(
        self,
        repository: MovieRepository,
        enricher: MovieEnricher,
        platform_discovery: PlatformDiscovery,
    ) -> None:
        self._repo      = repository
        self._enricher  = enricher
        self._discovery = platform_discovery

    async def mix(
        self,
        genres:      list[str],
        tone:        int,
        cerebro:     int,
        min_rating:  float,
        max_rating:  Optional[float],
        year_from:   int,
        year_to:     int,
        runtime_min: Optional[int],
        runtime_max: Optional[int],
        platform:    str,
    ) -> dict:
        # ── RUTA PLATAFORMA — TMDB Discover con datos de JustWatch ───────────
        if platform and platform in PLATFORM_IDS:
            return await self._mix_platform(
                genres, tone, cerebro, min_rating, max_rating,
                year_from, year_to, platform,
            )

        # ── RUTA SQLite — flujo estándar ──────────────────────────────────────
        return await self._mix_sqlite(
            genres, tone, cerebro, min_rating, max_rating,
            year_from, year_to, runtime_min, runtime_max,
        )

    # ── Rutas privadas ────────────────────────────────────────────────────────

    async def _mix_platform(
        self,
        genres:     list[str],
        tone:       int,
        cerebro:    int,
        min_rating: float,
        max_rating: Optional[float],
        year_from:  int,
        year_to:    int,
        platform:   str,
    ) -> dict:
        # Aplicar Vibe Matrix también aquí para que Cerebro y Tono tengan
        # efecto real (umbrales de votos/rating y géneros).
        constraints             = translate_vibes(genres, tone, cerebro, year_from, year_to)
        constraints.min_avg_rating = min_rating
        constraints.max_avg_rating = max_rating

        # Géneros del Tono (OR group) — solo cuando el usuario no eligió pads.
        tone_genres = (
            [g for group in constraints.genre_groups for g in group]
            if not genres and constraints.genre_groups
            else []
        )

        result, _ = await self._discovery.discover_by_platform(
            platform_id    = PLATFORM_IDS[platform],
            user_genres    = genres,
            tone_genres    = tone_genres,
            exclude_genres = constraints.exclude_genres,
            year_from      = year_from,
            year_to        = year_to,
            min_votes      = constraints.min_votes,
            min_rating     = constraints.min_vibe_score,
        )
        if result:
            return result
        raise HTTPException(
            404,
            detail={
                "code":     "no_platform_match",
                "platform": platform,
                "message":  f"Sin resultados en {platform} con estos ajustes",
            },
        )

    async def _mix_sqlite(
        self,
        genres:      list[str],
        tone:        int,
        cerebro:     int,
        min_rating:  float,
        max_rating:  Optional[float],
        year_from:   int,
        year_to:     int,
        runtime_min: Optional[int],
        runtime_max: Optional[int],
    ) -> dict:
        constraints             = translate_vibes(genres, tone, cerebro, year_from, year_to)
        constraints.runtime_min    = runtime_min
        constraints.runtime_max    = runtime_max
        constraints.min_avg_rating = min_rating
        constraints.max_avg_rating = max_rating

        # ── Nota del usuario tiene prioridad sobre vibe_score ────────────────
        # vibe_score >= 6.65 (cerebro=50) actúa como suelo implícito que haría
        # inútil cualquier rango de nota por debajo de 6.5.
        if max_rating is not None:
            constraints.min_vibe_score = min(
                constraints.min_vibe_score, max(4.0, max_rating - 0.5)
            )
        if min_rating > 5.0:
            constraints.min_vibe_score = min(constraints.min_vibe_score, min_rating - 0.1)

        genre_match = "exact"
        relaxed_by: Optional[str] = None

        # Búsqueda principal
        current = constraints
        rows    = await run_in_threadpool(self._repo.find_movies, current)

        if not rows:
            # ── Intento previo con múltiples géneros: OR en vez de AND ───────
            if genres and len(genres) > 1:
                broad              = copy.deepcopy(constraints)
                broad.genre_groups = [genres]   # un solo grupo OR
                rows               = await run_in_threadpool(self._repo.find_movies, broad)
                if rows:
                    genre_match = "approximate"
                    relaxed_by  = "genres"

        if not rows:
            # ── Fallback progresivo — relaja restricciones paso a paso ───────
            for step in range(1, 9):
                relaxed = relax(current, step)
                if relaxed is None:
                    raise HTTPException(500, "Sin resultados tras relajación máxima")
                current = relaxed
                rows    = await run_in_threadpool(self._repo.find_movies, current)
                if rows:
                    relaxed_by  = STEP_REASON[step]
                    genre_match = "approximate" if step >= 3 else "relaxed"
                    break

        # Elegir película y enriquecer; reintentar si TMDB la identifica como india
        pool = list(rows)
        for _ in range(min(10, len(pool))):
            movie = pick_one(pool, current.priority_genres)
            meta  = await self._enricher.enrich(movie["tconst"])

            if meta.get("original_language") in INDIAN_LANGUAGES:
                pool = [r for r in pool if r["tconst"] != movie["tconst"]]
                if not pool:
                    break
                continue
            break

        movie_genres = [g.strip() for g in movie["genres"].split(",") if g.strip()][:3]

        return {
            "title":       movie["primaryTitle"],
            "year":        movie["startYear"],
            "genres":      movie_genres,
            "rating":      round(float(movie["averageRating"]), 1),
            "runtime":     movie.get("runtimeMinutes"),
            "tconst":      movie["tconst"],
            "posterUrl":   meta.get("posterUrl"),
            "overview":    meta.get("overview", ""),
            "tmdbId":      meta.get("tmdbId"),
            "genre_match": genre_match,
            "relaxed_by":  relaxed_by,
        }

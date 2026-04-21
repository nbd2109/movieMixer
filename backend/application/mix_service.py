"""
Caso de uso: MixService — orquestador principal de CineMix.

Esta capa coordina el dominio (vibe_matrix, relaxation, selection) con los
puertos (MovieRepository, MovieEnricher, PlatformDiscovery). No contiene
lógica de negocio propia ni conoce FastAPI, SQLite ni TMDB directamente.
"""

import logging
from typing import Optional

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool

from domain.constants import INDIAN_LANGUAGES, PLATFORM_IDS
from domain.ports.movie_enricher import MovieEnricher, PlatformDiscovery
from domain.ports.movie_repository import MovieRepository
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
         Todos los sliders se aplican: género, tono, cerebro, nota, año, duración.
      3. Ruta SQLite        — búsqueda principal + fallback progresivo
      4. pick_one()         — elección aleatoria con sesgo
      5. enrich()           — póster y sinopsis desde TMDB (best-effort)
    """

    def __init__(
        self,
        repository:         MovieRepository,
        enricher:           MovieEnricher,
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
        if platform and platform in PLATFORM_IDS:
            return await self._mix_platform(
                genres, tone, cerebro, min_rating, max_rating,
                year_from, year_to, runtime_min, runtime_max, platform,  # runtime incluido
            )
        return await self._mix_sqlite(
            genres, tone, cerebro, min_rating, max_rating,
            year_from, year_to, runtime_min, runtime_max,
        )

    # ── Ruta plataforma ───────────────────────────────────────────────────────

    async def _mix_platform(
        self,
        genres:      list[str],
        tone:        int,
        cerebro:     int,
        min_rating:  float,
        max_rating:  Optional[float],
        year_from:   int,
        year_to:     int,
        runtime_min: Optional[int],   # ← bug corregido: antes no llegaba aquí
        runtime_max: Optional[int],   # ← ídem
        platform:    str,
    ) -> dict:
        """
        Usa TMDB Discover con datos de JustWatch para buscar en la plataforma.
        TODOS los sliders se aplican: Vibe Matrix calcula los umbrales, y se
        pasan íntegramente a discover_by_platform.
        """
        constraints = translate_vibes(genres, tone, cerebro, year_from, year_to)

        # Aplicar la misma interacción nota ↔ vibe_score que en la ruta SQLite:
        # si el usuario fija un rango de nota, ajustar el suelo bayesiano para
        # que no colisione con el techo que el usuario ha elegido.
        if max_rating is not None:
            constraints.min_vibe_score = min(
                constraints.min_vibe_score, max(4.0, max_rating - 0.5)
            )
        if min_rating > 5.0:
            constraints.min_vibe_score = min(constraints.min_vibe_score, min_rating - 0.1)

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
            min_avg_rating = max(constraints.min_vibe_score, min_rating),  # el más estricto
            max_avg_rating = max_rating,   # ← bug corregido: antes no se pasaba
            runtime_min    = runtime_min,  # ← bug corregido: antes no se pasaba
            runtime_max    = runtime_max,  # ← ídem
            cerebro        = cerebro,      # controla estrategia sort/páginas en TMDB
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

    # ── Ruta SQLite ───────────────────────────────────────────────────────────

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

        # Nota del usuario tiene prioridad sobre vibe_score.
        # vibe_score (Bayesian WR) actúa como suelo implícito de calidad,
        # pero si el usuario fija un techo de nota más bajo, lo respetamos.
        if max_rating is not None:
            constraints.min_vibe_score = min(
                constraints.min_vibe_score, max(4.0, max_rating - 0.5)
            )
        if min_rating > 5.0:
            constraints.min_vibe_score = min(constraints.min_vibe_score, min_rating - 0.1)

        # Búsqueda — sin fallback, sin relajación. Si no hay resultados, es no hay.
        rows = await run_in_threadpool(self._repo.find_movies, constraints)

        if not rows:
            raise HTTPException(
                404,
                detail={
                    "code":    "no_results",
                    "message": "No hay películas con esos ajustes exactos.",
                },
            )

        # Elegir película y enriquecer; reintentar si TMDB la identifica como india
        pool = list(rows)
        for _ in range(min(10, len(pool))):
            movie = pick_one(pool, constraints.priority_genres)
            meta  = await self._enricher.enrich(movie["tconst"])

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
        }

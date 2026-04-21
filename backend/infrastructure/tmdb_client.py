"""
Adaptador TMDB — implementa MovieEnricher y PlatformDiscovery.

Toda la lógica de HTTP, reintentos, formato de respuesta TMDB y la estrategia
de descubrimiento por plataforma viven aquí. Nada de esto se filtra al dominio.

═══════════════════════════════════════════════════════════════════════════════
CALIBRACIÓN TMDB vs IMDb
═══════════════════════════════════════════════════════════════════════════════

vote_count (TMDB ≈ IMDb / 30–50):
  La plataforma TMDB tiene muchos menos votantes que IMDb para la misma peli.
  · The Dark Knight: IMDb ~2.9M, TMDB ~33k  → ratio ≈ 90x
  · Parasite:        IMDb ~900k, TMDB ~20k  → ratio ≈ 45x
  Usamos VOTE_COUNT_FACTOR = 15 como compromiso conservador.
  Así cerebro=0 (200k IMDb) → 13k TMDB (solo grandes blockbusters)
       cerebro=50 (14k IMDb) → 930 TMDB (mainstream conocido)
       cerebro=100 (1k IMDb) → 67 TMDB (cualquier película catalogada)

vote_average (TMDB ≈ IMDb - 0.2..0.5):
  TMDB tiende a puntuar ligeramente más bajo que IMDb.
  Usamos RATING_OFFSET = 0.3 para ajustar el floor al escalar de IMDb → TMDB.
  El techo (max_avg_rating) se pasa sin ajuste para no cortar pelis
  que el usuario claramente quiere ver.

sort_by según cerebro:
  · cerebro < 40  → popularity.desc  páginas 1–8   (blockbusters actuales)
  · cerebro 40–64 → popularity.desc  páginas 1–15  (mainstream variado)
  · cerebro >= 65 → vote_average.desc páginas 1–25  (calidad sobre popularidad)
  vote_average.desc requiere vote_count.gte suficiente para que el orden
  sea significativo (films con 1 voto y 10.0 no deben aparecer).

═══════════════════════════════════════════════════════════════════════════════
"""

import asyncio
import random
from typing import Optional

import httpx

from domain.constants import IMDB_TO_TMDB_GENRE, INDIAN_LANGUAGES, TMDB_GENRE_NAMES
from domain.ports.movie_enricher import MovieEnricher, PlatformDiscovery

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG  = "https://image.tmdb.org/t/p/original"
TMDB_LOGO = "https://image.tmdb.org/t/p/w45"

# Calibración vote_count: factor para convertir umbral IMDb → umbral TMDB
VOTE_COUNT_FACTOR = 15

# Ajuste de escala de ratings IMDb → TMDB (TMDB puntúa ~0.3 más bajo)
RATING_OFFSET = 0.3

# Estrategia de páginas según cerebro
# (sort_by, page_start, page_end)
_PAGE_STRATEGY: list[tuple[int, str, int, int]] = [
    # (cerebro_max_exclusive, sort_by, page_start, page_end)
    (40,  "popularity.desc",   1,  8),   # blockbusters
    (65,  "popularity.desc",   1, 15),   # mainstream
    (101, "vote_average.desc", 1, 25),   # calidad / autor
]


def _page_strategy(cerebro: int) -> tuple[str, int, int]:
    for max_c, sort_by, p_start, p_end in _PAGE_STRATEGY:
        if cerebro < max_c:
            return sort_by, p_start, p_end
    return "popularity.desc", 1, 15  # fallback (nunca debería llegar aquí)


class TmdbClient(MovieEnricher, PlatformDiscovery):
    """
    Cliente TMDB que implementa tanto MovieEnricher como PlatformDiscovery.
    Un único adaptador para dos puertos distintos (la API física es la misma).

    Si TMDB_API_KEY no está configurada, todos los métodos devuelven respuestas
    vacías — principio de degradación elegante.
    """

    def __init__(self, api_key: Optional[str]) -> None:
        self._api_key = api_key

    # ── MovieEnricher ─────────────────────────────────────────────────────────

    async def enrich(self, tconst: str) -> dict:
        """
        Resuelve la película en TMDB usando su ID de IMDb (tconst) vía /find.
        Garantiza un match 1:1 sin ambigüedad por título o año.
        Devuelve {} si TMDB no está configurado o falla.
        """
        if not self._api_key:
            return {}
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{TMDB_BASE}/find/{tconst}",
                    params={
                        "api_key":         self._api_key,
                        "external_source": "imdb_id",
                        "language":        "es-ES",
                    },
                )
            if resp.status_code != 200:
                return {}
            results = resp.json().get("movie_results", [])
            if not results:
                return {}
            hit    = results[0]
            poster = hit.get("poster_path")
            return {
                "posterUrl":         f"{TMDB_IMG}{poster}" if poster else None,
                "overview":          hit.get("overview", ""),
                "tmdbId":            hit.get("id"),
                "original_language": hit.get("original_language"),
            }
        except Exception:
            return {}

    async def get_watch_providers(self, tmdb_id: int, country: str) -> dict:
        """
        Devuelve dónde ver la película vía TMDB Watch Providers (datos de JustWatch).
        Intenta el país solicitado; hace fallback a US si no hay datos.
        """
        if not self._api_key:
            return {"flatrate": [], "rent": [], "link": None}
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{TMDB_BASE}/movie/{tmdb_id}/watch/providers",
                    params={"api_key": self._api_key},
                )
            if resp.status_code != 200:
                return {"flatrate": [], "rent": [], "link": None}

            results      = resp.json().get("results", {})
            country_data = results.get(country) or results.get("US") or {}

            def _fmt(providers: list) -> list:
                return [
                    {
                        "id":   p["provider_id"],
                        "name": p["provider_name"],
                        "logo": f"{TMDB_LOGO}{p['logo_path']}",
                    }
                    for p in providers
                    if p.get("logo_path")
                ][:5]

            return {
                "flatrate": _fmt(country_data.get("flatrate", [])),
                "rent":     _fmt(country_data.get("rent", [])),
                "link":     country_data.get("link"),
            }
        except Exception:
            return {"flatrate": [], "rent": [], "link": None}

    # ── PlatformDiscovery ─────────────────────────────────────────────────────

    async def discover_by_platform(
        self,
        platform_id:    int,
        user_genres:    list[str],
        tone_genres:    list[str],
        exclude_genres: list[str],
        year_from:      int,
        year_to:        int,
        min_votes:      int,
        min_avg_rating: float,
        max_avg_rating: Optional[float],
        runtime_min:    Optional[int],
        runtime_max:    Optional[int],
        cerebro:        int,
    ) -> tuple[dict | None, str]:
        """
        Busca una película disponible en la plataforma vía TMDB Discover.
        Todos los sliders del usuario se aplican — ninguno se ignora.

        Estrategia de género (de más a menos restrictiva):
          Con géneros de usuario:
            1. AND (todos los géneros) — ES
            2. OR  (algún género)     — ES
            3. AND                    — US
            4. OR                     — US
            5. Sin filtro género      — ES  (genre_match='approximate')
            6. Sin filtro género      — US
          Solo géneros de Tono:
            1. OR — ES
            2. OR — US
            3. Sin filtro — ES / US
          Sin géneros:
            1. Sin filtro — ES / US
        """
        if not self._api_key:
            return None, "exact"

        user_ids    = self._to_tmdb_ids(user_genres)
        tone_ids    = self._to_tmdb_ids(tone_genres)
        exclude_str = ",".join(self._to_tmdb_ids(exclude_genres))

        sort_by, p_start, p_end = _page_strategy(cerebro)

        # vote_count.gte calibrado para TMDB (mucho menos votos que IMDb)
        # floor de 50 para modo nicho/autor
        vote_count_gte = max(50, min_votes // VOTE_COUNT_FACTOR)

        # Para vote_average.desc necesitamos un mínimo de votos suficiente
        # para que el orden sea significativo (evitar films con 1 voto y 10.0)
        if sort_by == "vote_average.desc":
            vote_count_gte = max(vote_count_gte, 200)

        # Secuencia de intentos: (genre_filter, region, genre_match)
        if user_ids:
            and_str  = ",".join(user_ids)   # TMDB: AND — debe tener TODOS
            or_str   = "|".join(user_ids)   # TMDB: OR — basta con UNO
            attempts = [
                (and_str, "ES", "exact"),
                (or_str,  "ES", "approximate"),
                (and_str, "US", "exact"),
                (or_str,  "US", "approximate"),
                ("",      "ES", "approximate"),
                ("",      "US", "approximate"),
            ]
        elif tone_ids:
            or_str   = "|".join(tone_ids)
            attempts = [
                (or_str, "ES", "exact"),
                (or_str, "US", "exact"),
                ("",     "ES", "approximate"),
                ("",     "US", "approximate"),
            ]
        else:
            attempts = [
                ("", "ES", "exact"),
                ("", "US", "exact"),
            ]

        for (genre_filter, region, match_label) in attempts:
            results = await self._pool(
                platform_id    = platform_id,
                genre_filter   = genre_filter,
                exclude_filter = exclude_str,
                year_from      = year_from,
                year_to        = year_to,
                region         = region,
                vote_count_gte = vote_count_gte,
                min_avg_rating = min_avg_rating,
                max_avg_rating = max_avg_rating,
                runtime_min    = runtime_min,
                runtime_max    = runtime_max,
                sort_by        = sort_by,
                page_start     = p_start,
                page_end       = p_end,
            )
            valid = [r for r in results if r.get("original_language") not in INDIAN_LANGUAGES]
            if not valid:
                valid = results  # si solo hay producciones indias, usarlas antes que nada
            if valid:
                return self._format_result(random.choice(valid), match_label), match_label

        return None, "exact"

    # ── Helpers privados ──────────────────────────────────────────────────────

    @staticmethod
    def _to_tmdb_ids(genres: list[str]) -> list[str]:
        """Convierte nombres de género IMDb a IDs de TMDB, ignorando los no mapeados."""
        return list(dict.fromkeys(
            str(IMDB_TO_TMDB_GENRE[g]) for g in genres if g in IMDB_TO_TMDB_GENRE
        ))

    async def _pool(
        self,
        platform_id:    int,
        genre_filter:   str,
        exclude_filter: str,
        year_from:      int,
        year_to:        int,
        region:         str,
        vote_count_gte: int,
        min_avg_rating: float,
        max_avg_rating: Optional[float],
        runtime_min:    Optional[int],
        runtime_max:    Optional[int],
        sort_by:        str,
        page_start:     int,
        page_end:       int,
    ) -> list[dict]:
        """
        Obtiene un pool diverso de películas.
        Estrategia de 3 páginas para maximizar variedad sin penalizar latencia:
          · Página 1 (si page_start=1): resultados más relevantes siempre incluidos
          · +2 páginas aleatorias del rango (page_start, page_end)
        Las 3 fetches van en paralelo con asyncio.gather.
        """
        available = list(range(page_start, page_end + 1))
        if len(available) <= 3:
            pages = available
        else:
            # Siempre incluir page_start (resultados más relevantes del criterio de sort)
            anchor = [page_start]
            rest   = [p for p in available if p != page_start]
            extra  = random.sample(rest, min(2, len(rest)))
            pages  = anchor + extra

        batches = await asyncio.gather(*[
            self._fetch_page(
                platform_id    = platform_id,
                page           = p,
                genre_filter   = genre_filter,
                exclude_filter = exclude_filter,
                year_from      = year_from,
                year_to        = year_to,
                region         = region,
                vote_count_gte = vote_count_gte,
                min_avg_rating = min_avg_rating,
                max_avg_rating = max_avg_rating,
                runtime_min    = runtime_min,
                runtime_max    = runtime_max,
                sort_by        = sort_by,
            )
            for p in pages
        ])

        seen: set[int] = set()
        out:  list[dict] = []
        for batch in batches:
            for r in batch:
                if r.get("id") not in seen:
                    seen.add(r["id"])
                    out.append(r)
        return out

    async def _fetch_page(
        self,
        platform_id:    int,
        page:           int,
        genre_filter:   str,
        exclude_filter: str,
        year_from:      int,
        year_to:        int,
        region:         str,
        vote_count_gte: int,
        min_avg_rating: float,
        max_avg_rating: Optional[float],
        runtime_min:    Optional[int],
        runtime_max:    Optional[int],
        sort_by:        str,
    ) -> list[dict]:
        """
        Una sola llamada a TMDB /discover/movie con todos los filtros aplicados.
        Devuelve [] en cualquier error — nunca lanza excepción.

        Parámetros TMDB utilizados:
          with_watch_providers + watch_region → filtro de plataforma
          with_genres / without_genres        → filtro de género
          vote_count.gte                      → calibrado desde min_votes (/ VOTE_COUNT_FACTOR)
          vote_average.gte / vote_average.lte → nota mínima y máxima del slider Nota
          primary_release_date.gte/lte        → slider Época
          with_runtime.gte / with_runtime.lte → slider Duración
          sort_by                             → popularity.desc (cerebro bajo) o
                                                vote_average.desc (cerebro alto)
        """
        params: dict = {
            "api_key":              self._api_key,
            "watch_region":         region,
            "with_watch_providers": str(platform_id),
            "sort_by":              sort_by,
            "vote_count.gte":       vote_count_gte,
            # Nota mínima: la más alta entre el umbral de calidad del cerebro
            # y la nota explícita del usuario. Ajustamos -RATING_OFFSET para
            # compensar que TMDB tiende a puntuar ~0.3 más bajo que IMDb.
            "vote_average.gte":     max(4.5, round(min_avg_rating - RATING_OFFSET, 1)),
            "primary_release_date.gte": f"{year_from}-01-01",
            "primary_release_date.lte": f"{year_to}-12-31",
            "language":             "es-ES",
            "page":                 page,
        }

        # Nota máxima (techo del slider Nota) — antes completamente ignorado
        if max_avg_rating is not None:
            params["vote_average.lte"] = max_avg_rating

        # Duración — antes completamente ignorado
        if runtime_min is not None:
            params["with_runtime.gte"] = runtime_min
        if runtime_max is not None:
            params["with_runtime.lte"] = runtime_max

        # Géneros
        if genre_filter:
            params["with_genres"] = genre_filter
        if exclude_filter:
            params["without_genres"] = exclude_filter

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{TMDB_BASE}/discover/movie", params=params)
            if resp.status_code == 200:
                return resp.json().get("results", [])
        except Exception:
            pass
        return []

    @staticmethod
    def _format_result(hit: dict, match: str) -> dict:
        poster       = hit.get("poster_path")
        release_date = hit.get("release_date", "")
        release_year = int(release_date[:4]) if release_date and len(release_date) >= 4 else None
        genres_out   = [
            TMDB_GENRE_NAMES[gid]
            for gid in hit.get("genre_ids", [])
            if gid in TMDB_GENRE_NAMES
        ][:3]
        return {
            "title":       hit.get("title", ""),
            "year":        release_year,
            "genres":      genres_out,
            "rating":      round(float(hit.get("vote_average", 0)), 1),
            "runtime":     None,   # TMDB Discover no devuelve runtime en el listado
            "posterUrl":   f"{TMDB_IMG}{poster}" if poster else None,
            "overview":    hit.get("overview", ""),
            "tmdbId":      hit.get("id"),
            "genre_match": match,
        }

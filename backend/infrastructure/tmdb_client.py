"""
Adaptador TMDB — implementa MovieEnricher y PlatformDiscovery.

Toda la lógica de HTTP, reintentos, formato de respuesta TMDB y la estrategia
de descubrimiento por plataforma viven aquí. Nada de esto se filtra al dominio.
"""

import asyncio
import random
from typing import Optional

import httpx

from domain.constants import IMDB_TO_TMDB_GENRE, INDIAN_LANGUAGES, PLATFORM_IDS, TMDB_GENRE_NAMES
from domain.ports.movie_enricher import MovieEnricher, PlatformDiscovery

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG  = "https://image.tmdb.org/t/p/original"
TMDB_LOGO = "https://image.tmdb.org/t/p/w45"


class TmdbClient(MovieEnricher, PlatformDiscovery):
    """
    Cliente TMDB que implementa tanto MovieEnricher como PlatformDiscovery.
    Un único adaptador para dos puertos distintos (la interfaz física es la misma API).

    Si TMDB_API_KEY no está configurada, todos los métodos devuelven respuestas
    vacías en vez de lanzar excepción — principio de degradación elegante.
    """

    def __init__(self, api_key: Optional[str]) -> None:
        self._api_key = api_key

    # ── MovieEnricher ─────────────────────────────────────────────────────────

    async def enrich(self, tconst: str) -> dict:
        """
        Resuelve la película en TMDB usando el ID de IMDb (tconst) vía /find.
        Esto garantiza un match 1:1 sin ambigüedad por título o año.
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
        platform_id: int,
        user_genres: list[str],
        tone_genres: list[str],
        exclude_genres: list[str],
        year_from: int,
        year_to: int,
        min_votes: int,
        min_rating: float,
    ) -> tuple[dict | None, str]:
        """
        Devuelve (película, genre_match) disponible en la plataforma vía TMDB Discover.
        Los datos de disponibilidad son aportados por JustWatch a través de TMDB.

        Jerarquía de género:
          · user_genres: géneros del usuario (AND en TMDB = coma).
          · tone_genres: géneros del tono cuando el usuario no eligió pads (OR = pipe).
          · exclude_genres: géneros excluidos por Tono extremo → without_genres en TMDB.

        Estrategia de búsqueda (de más a menos restrictiva):
          Con géneros de usuario:
            1. AND en ES  (deben tener TODOS los géneros pedidos)
            2. OR  en ES  (basta con UNO — "algo parecido")
            3. AND en US
            4. OR  en US
            5. Sin filtro en ES  (fallback de último recurso)
            6. Sin filtro en US
          Sin géneros de usuario pero con géneros de Tono:
            1. OR en ES  (los géneros del Tono son OR por naturaleza)
            2. OR en US
            3. Sin filtro en ES
            4. Sin filtro en US
          Sin ningún género:
            1. Sin filtro en ES
            2. Sin filtro en US
        """
        if not self._api_key:
            return None, "exact"

        user_ids    = self._to_tmdb_ids(user_genres)
        tone_ids    = self._to_tmdb_ids(tone_genres)
        exclude_str = ",".join(self._to_tmdb_ids(exclude_genres))

        # Secuencia de intentos: (genre_filter, region, genre_match)
        if user_ids:
            and_str  = ",".join(user_ids)   # TMDB: deben tener TODOS
            or_str   = "|".join(user_ids)   # TMDB: basta con UNO
            attempts = [
                (and_str, "ES", "exact"),
                (or_str,  "ES", "approximate"),
                (and_str, "US", "exact"),
                (or_str,  "US", "approximate"),
                ("",      "ES", "approximate"),
                ("",      "US", "approximate"),
            ]
        elif tone_ids:
            or_str   = "|".join(tone_ids)   # Tono: OR por naturaleza
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
                platform_id, genre_filter, exclude_str,
                year_from, year_to, region, min_votes, min_rating,
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
        platform_id: int,
        genre_filter: str,
        exclude_filter: str,
        year_from: int,
        year_to: int,
        region: str,
        min_votes: int,
        min_rating: float,
    ) -> list[dict]:
        """3 páginas aleatorias de 1–15 → pool de hasta 60 films con variedad real."""
        pages = random.sample(range(1, 16), 3)
        batches = await asyncio.gather(*[
            self._fetch_page(
                platform_id, p, genre_filter, exclude_filter,
                year_from, year_to, region, min_votes, min_rating,
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
        platform_id: int,
        page: int,
        genre_filter: str,
        exclude_filter: str,
        year_from: int,
        year_to: int,
        region: str,
        min_votes: int,
        min_rating: float,
    ) -> list[dict]:
        """Una sola llamada a TMDB Discover. Devuelve [] en cualquier error."""
        params: dict = {
            "api_key":              self._api_key,
            "watch_region":         region,
            "with_watch_providers": str(platform_id),
            "sort_by":              "popularity.desc",
            "vote_count.gte":       max(100, min_votes // 10),
            "vote_average.gte":     max(5.0, min_rating - 1.0),
            "primary_release_date.gte": f"{year_from}-01-01",
            "primary_release_date.lte": f"{year_to}-12-31",
            "language":             "es-ES",
            "page":                 page,
        }
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
            "runtime":     None,
            "posterUrl":   f"{TMDB_IMG}{poster}" if poster else None,
            "overview":    hit.get("overview", ""),
            "tmdbId":      hit.get("id"),
            "genre_match": match,
        }

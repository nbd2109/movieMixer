"""
Puertos (Ports) para enriquecimiento de datos externos y descubrimiento
por plataforma de streaming.

Separar MovieEnricher de PlatformDiscovery respeta ISP: el endpoint
/watch-providers no necesita saber nada de discover_by_platform.
"""

from abc import ABC, abstractmethod
from typing import Optional


class MovieEnricher(ABC):
    """
    Contrato para enriquecer una película con metadatos externos
    (póster, sinopsis, TMDB ID) a partir de su ID de IMDb.
    """

    @abstractmethod
    async def enrich(self, tconst: str) -> dict:
        """
        Resuelve la película externamente usando su tconst (ID IMDb).
        Devuelve dict con: posterUrl, overview, tmdbId, original_language.
        Nunca lanza excepción — devuelve {} en cualquier error.
        """
        ...

    @abstractmethod
    async def get_watch_providers(self, tmdb_id: int, country: str) -> dict:
        """
        Devuelve dónde ver la película (datos JustWatch vía TMDB).
        Estructura: {"flatrate": [...], "rent": [...], "link": str|None}.
        Nunca lanza — devuelve listas vacías en cualquier error.
        """
        ...


class PlatformDiscovery(ABC):
    """
    Contrato para descubrir películas disponibles en una plataforma de streaming.
    Todos los parámetros de búsqueda se pasan explícitamente para que el
    adaptador los aplique completamente — ningún slider se ignora.
    """

    @abstractmethod
    async def discover_by_platform(
        self,
        platform_id:    int,
        user_genres:    list[str],
        tone_genres:    list[str],
        exclude_genres: list[str],
        year_from:      int,
        year_to:        int,
        min_votes:      int,
        min_avg_rating: float,          # nota mínima (IMDb scale)
        max_avg_rating: Optional[float], # nota máxima (IMDb scale); None = sin techo
        runtime_min:    Optional[int],  # duración mínima en minutos
        runtime_max:    Optional[int],  # duración máxima en minutos
        cerebro:        int,            # 0–100; controla estrategia de ordenación/páginas
    ) -> tuple[dict | None, str]:
        """
        Busca una película disponible en la plataforma dada.
        Devuelve (película_formateada, genre_match) o (None, "exact").
        genre_match: "exact" | "approximate"
        """
        ...

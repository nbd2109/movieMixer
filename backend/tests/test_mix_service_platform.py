"""
Tests de integración ligera del MixService — ruta plataforma.

Verifican que TODOS los sliders llegan correctamente a PlatformDiscovery
sin necesitar backend real ni TMDB. Usa un doble de prueba (stub) del puerto
para capturar exactamente qué parámetros recibe.

Esto demuestra el valor de la Arquitectura Hexagonal: podemos probar la capa
de aplicación de forma aislada, sustituyendo infraestructura por stubs.
"""

import asyncio
import pytest
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

from application.mix_service import MixService
from domain.ports.movie_enricher import MovieEnricher, PlatformDiscovery
from domain.ports.movie_repository import MovieRepository


# ── Stubs mínimos ─────────────────────────────────────────────────────────────

class StubRepository(MovieRepository):
    def find_movies(self, constraints):
        return []
    def count_all(self):
        return 0


class StubEnricher(MovieEnricher):
    async def enrich(self, tconst):
        return {}
    async def get_watch_providers(self, tmdb_id, country):
        return {"flatrate": [], "rent": [], "link": None}


class CapturingDiscovery(PlatformDiscovery):
    """Captura los kwargs de la última llamada a discover_by_platform."""
    def __init__(self):
        self.last_call: dict = {}

    async def discover_by_platform(
        self,
        platform_id, user_genres, tone_genres, exclude_genres,
        year_from, year_to, min_votes, min_avg_rating, max_avg_rating,
        runtime_min, runtime_max, cerebro,
    ) -> tuple[dict | None, str]:
        self.last_call = dict(
            platform_id    = platform_id,
            user_genres    = user_genres,
            tone_genres    = tone_genres,
            exclude_genres = exclude_genres,
            year_from      = year_from,
            year_to        = year_to,
            min_votes      = min_votes,
            min_avg_rating = min_avg_rating,
            max_avg_rating = max_avg_rating,
            runtime_min    = runtime_min,
            runtime_max    = runtime_max,
            cerebro        = cerebro,
        )
        # Simula resultado vacío → el servicio lanzará 404 (esperado en estos tests)
        return None, "exact"


def _make_service():
    discovery = CapturingDiscovery()
    service   = MixService(
        repository         = StubRepository(),
        enricher           = StubEnricher(),
        platform_discovery = discovery,
    )
    return service, discovery


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestPlatformSliderPassthrough:
    """Verifica que cada slider llega íntegramente a PlatformDiscovery."""

    def test_runtime_min_reaches_discovery(self):
        """
        Slider Duración (corta, <90 min) debe llegar como runtime_min=None, runtime_max=89.
        Antes de la corrección, runtime era completamente ignorado en la ruta plataforma.
        """
        service, discovery = _make_service()
        try:
            _run(service.mix(
                genres=[], tone=50, cerebro=50, min_rating=5.0, max_rating=None,
                year_from=1920, year_to=2026,
                runtime_min=None, runtime_max=89,   # película corta
                platform="netflix",
            ))
        except Exception:
            pass  # 404 esperado — el stub devuelve None

        assert discovery.last_call.get("runtime_max") == 89, (
            "runtime_max no llegó a PlatformDiscovery"
        )
        assert discovery.last_call.get("runtime_min") is None

    def test_runtime_long_reaches_discovery(self):
        """Duración larga (>141 min) debe llegar como runtime_min=141."""
        service, discovery = _make_service()
        try:
            _run(service.mix(
                genres=[], tone=50, cerebro=50, min_rating=5.0, max_rating=None,
                year_from=1920, year_to=2026,
                runtime_min=141, runtime_max=None,   # película larga
                platform="prime",
            ))
        except Exception:
            pass
        assert discovery.last_call.get("runtime_min") == 141

    def test_max_avg_rating_reaches_discovery(self):
        """
        Techo del slider Nota debe llegar como max_avg_rating.
        Antes de la corrección, max_avg_rating era ignorado en la ruta plataforma.
        """
        service, discovery = _make_service()
        try:
            _run(service.mix(
                genres=[], tone=50, cerebro=50, min_rating=6.0, max_rating=7.5,
                year_from=1990, year_to=2024,
                runtime_min=None, runtime_max=None,
                platform="netflix",
            ))
        except Exception:
            pass
        assert discovery.last_call.get("max_avg_rating") == 7.5, (
            "max_avg_rating no llegó a PlatformDiscovery"
        )

    def test_min_avg_rating_reaches_discovery(self):
        """Suelo de nota explícito del usuario debe estar en min_avg_rating."""
        service, discovery = _make_service()
        try:
            _run(service.mix(
                genres=[], tone=50, cerebro=50, min_rating=7.0, max_rating=None,
                year_from=1990, year_to=2024,
                runtime_min=None, runtime_max=None,
                platform="disney",
            ))
        except Exception:
            pass
        # min_avg_rating = max(cerebro_vibe_floor, user_min=7.0)
        # cerebro=50 → min_vibe ≈ 6.65, so max(6.65, 7.0) = 7.0
        assert discovery.last_call.get("min_avg_rating") >= 7.0, (
            "min_avg_rating del slider nota no llegó correctamente"
        )

    def test_cerebro_reaches_discovery(self):
        """Cerebro debe llegar a PlatformDiscovery para controlar sort/páginas."""
        service, discovery = _make_service()
        try:
            _run(service.mix(
                genres=[], tone=50, cerebro=80, min_rating=5.0, max_rating=None,
                year_from=1990, year_to=2024,
                runtime_min=None, runtime_max=None,
                platform="max",
            ))
        except Exception:
            pass
        assert discovery.last_call.get("cerebro") == 80

    def test_year_range_reaches_discovery(self):
        """Slider Época debe llegar íntegramente."""
        service, discovery = _make_service()
        try:
            _run(service.mix(
                genres=[], tone=50, cerebro=50, min_rating=5.0, max_rating=None,
                year_from=1970, year_to=1990,
                runtime_min=None, runtime_max=None,
                platform="apple",
            ))
        except Exception:
            pass
        assert discovery.last_call.get("year_from") == 1970
        assert discovery.last_call.get("year_to")   == 1990

    def test_genres_reach_discovery(self):
        """Los géneros del pad deben llegar como user_genres."""
        service, discovery = _make_service()
        try:
            _run(service.mix(
                genres=["Action", "Thriller"], tone=70, cerebro=50,
                min_rating=5.0, max_rating=None,
                year_from=1990, year_to=2026,
                runtime_min=None, runtime_max=None,
                platform="netflix",
            ))
        except Exception:
            pass
        assert "Action" in discovery.last_call.get("user_genres", [])
        assert "Thriller" in discovery.last_call.get("user_genres", [])

    def test_tone_excludes_reach_discovery_at_extreme(self):
        """
        Con tone=0 (extremo cómico), Horror/Crime/Thriller/Mystery deben estar
        en exclude_genres pasados a PlatformDiscovery.
        """
        service, discovery = _make_service()
        try:
            _run(service.mix(
                genres=[], tone=0, cerebro=50, min_rating=5.0, max_rating=None,
                year_from=1990, year_to=2026,
                runtime_min=None, runtime_max=None,
                platform="netflix",
            ))
        except Exception:
            pass
        excl = discovery.last_call.get("exclude_genres", [])
        assert "Horror" in excl, "Horror debería excluirse con tone=0"
        assert "Crime" in excl,  "Crime debería excluirse con tone=0"

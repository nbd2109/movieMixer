"""
Router /api/movies — endpoints de recomendación y watch-providers.

Los routers son deliberadamente delgados: validan la entrada (Query params),
llaman al servicio de aplicación y devuelven la respuesta. Sin lógica de negocio.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from application.mix_service import MixService

router  = APIRouter(prefix="/api/movies")
limiter = Limiter(key_func=get_remote_address)


# ── Dependency injection ──────────────────────────────────────────────────────
# El servicio se inyecta desde el estado de la app (configurado en main.py).
# Esto permite sustituir MixService por un doble en tests de integración.

def _get_mix_service(request: Request) -> MixService:
    return request.app.state.mix_service


def _get_tmdb_client(request: Request):
    return request.app.state.tmdb_client


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/mix")
@limiter.limit("20/minute")
async def mix(
    request:    Request,
    genres:     str            = Query(""),
    tone:       int            = Query(50, ge=0, le=100),
    cerebro:    int            = Query(50, ge=0, le=100),
    minRating:  float          = Query(5.0, ge=5.0, le=10.0),
    maxRating:  Optional[float] = Query(None, ge=5.0, le=10.0),
    yearFrom:   int            = Query(1920, ge=1900, le=2030),
    yearTo:     int            = Query(2026, ge=1900, le=2030),
    runtimeMin: Optional[int]  = Query(None, ge=1),
    runtimeMax: Optional[int]  = Query(None, ge=1),
    platform:   str            = Query(""),
    service:    MixService     = Depends(_get_mix_service),
):
    genre_list = [g.strip() for g in genres.split(",") if g.strip()] if genres else []

    return await service.mix(
        genres      = genre_list,
        tone        = tone,
        cerebro     = cerebro,
        min_rating  = minRating,
        max_rating  = maxRating,
        year_from   = yearFrom,
        year_to     = yearTo,
        runtime_min = runtimeMin,
        runtime_max = runtimeMax,
        platform    = platform,
    )


@router.get("/{tmdb_id}/watch-providers")
@limiter.limit("60/minute")
async def watch_providers(
    request:    Request,
    tmdb_id:    int,
    country:    str = Query("ES"),
    tmdb_client = Depends(_get_tmdb_client),
):
    """
    Devuelve dónde ver la película vía TMDB Watch Providers (datos de JustWatch).
    Devuelve listas vacías (no error) cuando TMDB no está configurado o falla.
    """
    return await tmdb_client.get_watch_providers(tmdb_id, country)

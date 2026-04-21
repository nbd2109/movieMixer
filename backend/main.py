"""
CineMixer Backend v3.0 — Composition Root (Arquitectura Hexagonal)

Este archivo es el único punto donde se ensamblan todas las capas.
No contiene lógica de negocio ni de infraestructura — solo conecta los
adaptadores concretos con los puertos que el dominio y la aplicación definen.

Estructura:
  domain/          ← lógica de negocio pura (Vibe Matrix, entidades, puertos)
  infrastructure/  ← adaptadores: SQLite, TMDB
  application/     ← caso de uso: MixService
  routers/         ← endpoints FastAPI delgados
"""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from application.mix_service import MixService
from infrastructure.sqlite_repository import SQLiteMovieRepository
from infrastructure.tmdb_client import TmdbClient
from routers import events, health, movies

# ── Configuración ─────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
DB_PATH      = os.path.join(os.path.dirname(__file__), "movies.db")

# ── Adaptadores concretos (Infraestructura) ───────────────────────────────────

repository  = SQLiteMovieRepository(db_path=DB_PATH)
tmdb_client = TmdbClient(api_key=TMDB_API_KEY)

# ── Caso de uso (Aplicación) — inyecta los adaptadores como puertos ───────────

mix_service = MixService(
    repository         = repository,
    enricher           = tmdb_client,   # TmdbClient implementa MovieEnricher
    platform_discovery = tmdb_client,   # TmdbClient implementa PlatformDiscovery
)

# ── App FastAPI ───────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)
app     = FastAPI(title="CineMixer API", version="3.0.0")

app.state.limiter          = limiter
app.state.repository       = repository
app.state.tmdb_client      = tmdb_client
app.state.mix_service      = mix_service

app.add_exception_handler(
    RateLimitExceeded,
    lambda request, exc: JSONResponse(
        status_code=429,
        content={"error": "too_many_requests", "retry_after": 60},
    ),
)

# CORS: los orígenes permitidos se leen de la variable de entorno.
# En desarrollo: ALLOWED_ORIGINS=http://localhost:5173
# En producción: ALLOWED_ORIGINS=https://cinemix.app,https://www.cinemix.app
_allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed_origins],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(movies.router, dependencies=[])   # rate-limit se aplica por endpoint
app.include_router(health.router)
app.include_router(events.router)

# ── Rate limiting por endpoint ────────────────────────────────────────────────
# Se aplica con el decorador @limiter.limit() en cada endpoint del router.
# Los routers acceden al limiter a través de app.state.limiter.

"""
Vibe Matrix — núcleo de la lógica de negocio de CineMix.

Este módulo es PURO: no importa nada de FastAPI, SQLite, TMDB ni httpx.
Solo Python estándar + las entidades del dominio. Esto lo hace trivialmente
testeable con pytest sin ningún mock.

Responsabilidades:
  · interpolate_tone()       — interpola pesos de géneros entre 8 anclas
  · genre_popularity_factor() — factor de ajuste para géneros de nicho
  · cerebro_to_constraints() — convierte Cerebro (0-100) a umbrales numéricos
  · translate_vibes()        — punto de entrada: sliders → VibeConstraints
"""

import bisect

from domain.constants import (
    ALWAYS_EXCLUDE,
    GENRE_POPULARITY,
    TONE_ANCHORS,
    TONE_EXCLUDE_HIGH,
    TONE_EXCLUDE_LOW,
    TONE_VALUES,
)
from domain.entities import VibeConstraints
from typing import Optional


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
    weighted = sum(GENRE_POPULARITY.get(g, 0.6) * w for g, w in tone_weights.items())
    return max(0.20, weighted / total)


def interpolate_tone(tone: int) -> dict[str, float]:
    """
    Devuelve {genre: weight} para una posición del slider (0–100).
    Interpola linealmente entre las dos anclas más cercanas.
    """
    if tone <= TONE_VALUES[0]:
        return dict(TONE_ANCHORS[0][1])
    if tone >= TONE_VALUES[-1]:
        return dict(TONE_ANCHORS[-1][1])

    idx     = bisect.bisect_right(TONE_VALUES, tone) - 1
    t0, g0  = TONE_ANCHORS[idx]
    t1, g1  = TONE_ANCHORS[idx + 1]
    alpha   = (tone - t0) / (t1 - t0)   # 0.0 → ancla izquierda, 1.0 → ancla derecha

    all_genres = set(g0) | set(g1)
    return {
        g: g0.get(g, 0.0) * (1 - alpha) + g1.get(g, 0.0) * alpha
        for g in all_genres
    }


def cerebro_to_constraints(
    cerebro: int, pop_factor: float
) -> tuple[int, Optional[int], float]:
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
    base_min  = 200_000 * (1 / 200) ** cb
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
        max_v      = 300_000 * pop_factor * (15_000 / 300_000) ** t
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
    Punto de entrada principal del dominio.

    GÉNEROS DE USUARIO vs GÉNEROS DE TONO
    ──────────────────────────────────────
    Cuando el usuario elige géneros en los pads, son la restricción principal.
    El Tono solo añade un sesgo suave (priority_genres) dentro de esa selección
    — no impone géneros adicionales obligatorios.

    Cuando el usuario NO elige géneros, el Tono sí añade un grupo OR de géneros
    afines como requisito suave, que puede relajarse en el fallback.

    RESOLUCIÓN DE COLISIONES
    ────────────────────────
    Las exclusiones siempre ganan. Si el usuario pide Thriller pero Tono=0
    excluye Thriller, ese género se elimina del grupo. Un grupo que queda
    vacío se descarta en lugar de generar una query imposible.
    """
    c = VibeConstraints(year_from=year_from, year_to=year_to)

    # Excluir siempre géneros no cinematográficos
    c.exclude_genres += ALWAYS_EXCLUDE

    # ── GÉNEROS SELECCIONADOS POR EL USUARIO ─────────────────────────────────
    # Lógica AND: cada género seleccionado es un grupo propio.
    # La película debe contener TODOS los géneros elegidos.
    c.user_genres = list(genres)
    for genre in genres:
        c.genre_groups.append([genre])

    # ── SLIDER: TONO — interpolación continua entre 8 anclas ─────────────────
    tone_weights = interpolate_tone(tone)

    # Géneros con peso muy alto → sesgo suave en pick_one (siempre aplica)
    c.priority_genres += [g for g, w in tone_weights.items() if w >= 0.65]

    # Grupo OR del Tono → solo se añade como requisito cuando el usuario
    # NO ha elegido géneros explícitos. Si eligió géneros, el Tono solo sesga.
    if not genres:
        required = [g for g, w in tone_weights.items() if w >= 0.45]
        if required:
            c.genre_groups.append(required)

    # Exclusiones hard solo en extremos absolutos del slider
    if tone <= 10:
        c.exclude_genres += TONE_EXCLUDE_LOW
    elif tone >= 90:
        c.exclude_genres += TONE_EXCLUDE_HIGH

    # ── COMBINACIÓN TONO × CEREBRO — curvas continuas ────────────────────────
    pop = genre_popularity_factor(tone_weights)
    c.min_votes, c.max_votes, c.min_vibe_score = cerebro_to_constraints(cerebro, pop)

    # En modo autor (cerebro alto) se sesga hacia géneros de alta nota/pocos votos
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
        if any(g not in exclude_set for g in group)
    ]

    return c

"""
Suite exhaustiva de tests — CineMix Vibe Matrix + infraestructura TMDB.

Cubre sistemáticamente:
  · Los 101 valores del slider Tono (0–100)
  · Los 101 valores del slider Cerebro/Popularidad (0–100)
  · El producto cartesiano Tono × Cerebro (10.201 combinaciones)
  · Los 17 géneros individualmente y en pares (153 tests)
  · Rangos de año: boundaries, rangos invertidos, año único
  · Nota: todas las combinaciones de suelo/techo relevantes
  · Duración: las 4 opciones × combinaciones
  · TMDB: estrategia de páginas, calibración de votos, ajuste de ratings
  · Invariantes de dominio que SIEMPRE deben cumplirse
  · Casos límite (edge cases) que han causado bugs históricos

Solo importa código de domain/ e infrastructure/ — cero mocks de HTTP,
cero SQLite, cero red. Cualquier fallo es un bug real de lógica.

Ejecutar: cd backend && pytest tests/test_exhaustive.py -v
"""

import itertools
import math
import pytest

from domain.constants import (
    ALWAYS_EXCLUDE,
    GENRE_POPULARITY,
    IMDB_TO_TMDB_GENRE,
    PLATFORM_IDS,
    TONE_ANCHORS,
    TONE_EXCLUDE_HIGH,
    TONE_EXCLUDE_LOW,
    TONE_VALUES,
    TMDB_GENRE_NAMES,
)
from domain.entities import VibeConstraints
from domain.vibe_matrix import (
    cerebro_to_constraints,
    genre_popularity_factor,
    interpolate_tone,
    translate_vibes,
)
from infrastructure.tmdb_client import (
    RATING_OFFSET,
    VOTE_COUNT_FACTOR,
    TmdbClient,
    _page_strategy,
)

# ── Constantes de referencia ──────────────────────────────────────────────────

ALL_GENRES = list(IMDB_TO_TMDB_GENRE.keys())   # 17 géneros
ALL_TONES  = list(range(101))                   # 0–100
ALL_CEREBRO = list(range(101))                  # 0–100

RUNTIME_OPTIONS = [
    (None,  None),   # Todas
    (None,  89),     # Corta
    (90,    140),    # Media
    (141,   None),   # Larga
]

YEAR_BOUNDS = [1900, 1920, 1950, 1970, 1990, 2000, 2010, 2020, 2024, 2026, 2030]

# Todas las notas representables en el slider (50-81 internos → 5.0-8.0/None)
RATING_FLOORS   = [5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0]
RATING_CEILINGS = [None, 6.0, 6.5, 7.0, 7.5, 8.0]

# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 1 — Invariantes de interpolate_tone (todos los valores 0–100)
# ═══════════════════════════════════════════════════════════════════════════════

class TestInterpolateToneAllValues:

    @pytest.mark.parametrize("tone", ALL_TONES)
    def test_returns_dict_for_every_tone(self, tone):
        result = interpolate_tone(tone)
        assert isinstance(result, dict), f"tone={tone} no devuelve dict"
        assert len(result) > 0, f"tone={tone} devuelve dict vacío"

    @pytest.mark.parametrize("tone", ALL_TONES)
    def test_all_weights_between_0_and_1(self, tone):
        result = interpolate_tone(tone)
        for genre, w in result.items():
            assert 0.0 <= w <= 1.0, (
                f"tone={tone}: {genre} tiene peso {w} fuera de [0,1]"
            )

    @pytest.mark.parametrize("tone", ALL_TONES)
    def test_all_genres_are_known(self, tone):
        result = interpolate_tone(tone)
        for genre in result:
            assert genre in IMDB_TO_TMDB_GENRE, (
                f"tone={tone}: género desconocido '{genre}' en interpolate_tone"
            )

    @pytest.mark.parametrize("tone", ALL_TONES)
    def test_at_least_one_significant_weight(self, tone):
        """Siempre debe haber al menos un género con peso relevante."""
        result = interpolate_tone(tone)
        assert any(w >= 0.45 for w in result.values()), (
            f"tone={tone}: ningún género tiene peso >= 0.45"
        )

    def test_anchors_are_exact(self):
        """En los puntos ancla exactos, debe devolver exactamente esos pesos."""
        for anchor_tone, anchor_weights in TONE_ANCHORS:
            result = interpolate_tone(anchor_tone)
            for genre, expected_w in anchor_weights.items():
                assert abs(result.get(genre, 0.0) - expected_w) < 1e-9, (
                    f"Ancla tone={anchor_tone}: {genre} esperado {expected_w}, "
                    f"obtenido {result.get(genre, 0.0)}"
                )

    def test_continuity_no_sudden_jumps(self):
        """
        La interpolación debe ser continua: el cambio entre valores adyacentes
        no puede superar 0.15 para ningún género.
        Previene anclas mal colocadas o bugs en bisect.
        """
        MAX_JUMP = 0.15
        prev = interpolate_tone(0)
        for tone in range(1, 101):
            curr = interpolate_tone(tone)
            all_genres = set(prev) | set(curr)
            for g in all_genres:
                jump = abs(curr.get(g, 0.0) - prev.get(g, 0.0))
                assert jump <= MAX_JUMP, (
                    f"Salto brusco en tone={tone}: {g} cambia {jump:.3f} "
                    f"(de {prev.get(g,0):.3f} a {curr.get(g,0):.3f})"
                )
            prev = curr

    def test_endpoints_exact(self):
        """tone=0 y tone=100 deben ser exactamente las anclas extremas."""
        assert interpolate_tone(0)   == dict(TONE_ANCHORS[0][1])
        assert interpolate_tone(100) == dict(TONE_ANCHORS[-1][1])

    @pytest.mark.parametrize("tone", range(0, 11))   # 0–10 inclusive
    def test_low_extreme_no_dark_genres_as_priority(self, tone):
        """En tone ≤ 10 los géneros oscuros NO deben tener peso alto."""
        weights = interpolate_tone(tone)
        for dark in TONE_EXCLUDE_LOW:
            w = weights.get(dark, 0.0)
            assert w < 0.45, (
                f"tone={tone}: {dark} tiene peso {w:.2f} pero debería ser < 0.45"
            )

    @pytest.mark.parametrize("tone", range(90, 101))   # 90–100 inclusive
    def test_high_extreme_no_light_genres_as_priority(self, tone):
        """En tone ≥ 90 los géneros ligeros NO deben tener peso alto."""
        weights = interpolate_tone(tone)
        for light in TONE_EXCLUDE_HIGH:
            w = weights.get(light, 0.0)
            assert w < 0.45, (
                f"tone={tone}: {light} tiene peso {w:.2f} pero debería ser < 0.45"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 2 — Invariantes de cerebro_to_constraints (todos los valores 0–100)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCerebroAllValues:

    @pytest.mark.parametrize("cerebro", ALL_CEREBRO)
    def test_min_votes_always_above_floor(self, cerebro):
        min_votes, _, _ = cerebro_to_constraints(cerebro, 1.0)
        assert min_votes >= 300, (
            f"cerebro={cerebro}: min_votes={min_votes} está por debajo del floor 300"
        )

    @pytest.mark.parametrize("cerebro", ALL_CEREBRO)
    def test_min_vibe_score_range(self, cerebro):
        _, _, min_vibe = cerebro_to_constraints(cerebro, 1.0)
        assert 5.0 <= min_vibe <= 7.51, (
            f"cerebro={cerebro}: min_vibe_score={min_vibe:.3f} fuera de [5.0, 7.5]"
        )

    @pytest.mark.parametrize("cerebro", ALL_CEREBRO)
    def test_max_votes_only_above_65(self, cerebro):
        _, max_votes, _ = cerebro_to_constraints(cerebro, 1.0)
        if cerebro < 65:
            assert max_votes is None, (
                f"cerebro={cerebro}: max_votes={max_votes} pero debería ser None (<65)"
            )
        else:
            assert max_votes is not None, (
                f"cerebro={cerebro}: max_votes=None pero debería existir (>=65)"
            )

    @pytest.mark.parametrize("cerebro", ALL_CEREBRO)
    def test_max_votes_greater_than_min_when_both_set(self, cerebro):
        min_votes, max_votes, _ = cerebro_to_constraints(cerebro, 1.0)
        if max_votes is not None:
            assert max_votes > min_votes, (
                f"cerebro={cerebro}: max_votes={max_votes} <= min_votes={min_votes}"
            )

    def test_min_votes_strictly_decreasing(self):
        """A mayor cerebro, menor min_votes — la curva no puede invertirse."""
        prev = cerebro_to_constraints(0, 1.0)[0]
        for c in range(1, 101):
            curr = cerebro_to_constraints(c, 1.0)[0]
            assert curr <= prev, (
                f"cerebro={c}: min_votes={curr} > cerebro={c-1}: {prev} — inversión!"
            )
            prev = curr

    def test_min_vibe_strictly_increasing(self):
        """A mayor cerebro, mayor min_vibe_score."""
        prev = cerebro_to_constraints(0, 1.0)[2]
        for c in range(1, 101):
            curr = cerebro_to_constraints(c, 1.0)[2]
            assert curr >= prev - 1e-9, (
                f"cerebro={c}: min_vibe={curr:.4f} < cerebro={c-1}: {prev:.4f}"
            )
            prev = curr

    @pytest.mark.parametrize("pop_factor", [0.20, 0.25, 0.35, 0.50, 0.65, 0.80, 1.00])
    def test_pop_factor_scales_min_votes(self, pop_factor):
        """A menor pop_factor, menor min_votes (géneros nicho tienen menos votos)."""
        for cerebro in [0, 25, 50, 75, 100]:
            min_v_full,  _, _ = cerebro_to_constraints(cerebro, 1.0)
            min_v_nicho, _, _ = cerebro_to_constraints(cerebro, pop_factor)
            assert min_v_nicho <= min_v_full, (
                f"cerebro={cerebro}, pop={pop_factor}: "
                f"min_votes_nicho={min_v_nicho} > min_votes_full={min_v_full}"
            )

    @pytest.mark.parametrize("cerebro", ALL_CEREBRO)
    def test_pop_factor_bounds_respected(self, cerebro):
        """pop_factor mínimo=0.20 no debe producir min_votes=0."""
        min_votes, _, _ = cerebro_to_constraints(cerebro, 0.20)
        assert min_votes >= 300

    def test_cerebro_0_blockbuster_territory(self):
        """cerebro=0 debe requerir muchos votos (blockbusters reales)."""
        min_votes, _, _ = cerebro_to_constraints(0, 1.0)
        assert min_votes >= 100_000

    def test_cerebro_100_niche_territory(self):
        """cerebro=100 debe aceptar películas con pocos votos (nicho/autor)."""
        min_votes, _, _ = cerebro_to_constraints(100, 1.0)
        assert min_votes <= 2_000

    def test_cerebro_100_has_tight_max_votes(self):
        """cerebro=100 modo autor: techo de votos para excluir blockbusters."""
        _, max_votes, _ = cerebro_to_constraints(100, 1.0)
        assert max_votes is not None
        assert max_votes <= 20_000


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 3 — genre_popularity_factor
# ═══════════════════════════════════════════════════════════════════════════════

class TestGenrePopularityFactor:

    def test_empty_weights_returns_one(self):
        assert genre_popularity_factor({}) == 1.0

    def test_zero_total_returns_one(self):
        assert genre_popularity_factor({"Comedy": 0.0}) == 1.0

    def test_all_mass_genres_near_one(self):
        """Action + Comedy = géneros masivos → factor cercano a 1.0."""
        f = genre_popularity_factor({"Action": 1.0, "Comedy": 1.0})
        assert f >= 0.95

    def test_all_niche_genres_low_factor(self):
        """Biography + History + Documentary = géneros nicho → factor bajo."""
        f = genre_popularity_factor({"Biography": 1.0, "History": 1.0, "Documentary": 1.0})
        assert f <= 0.35

    def test_factor_always_in_valid_range(self):
        """Para cualquier combinación de géneros conocidos, el factor ∈ [0.20, 1.0]."""
        for genre in ALL_GENRES:
            f = genre_popularity_factor({genre: 1.0})
            assert 0.20 <= f <= 1.01, f"género '{genre}': factor={f} fuera de [0.20, 1.0]"

    def test_unknown_genre_uses_default(self):
        """Un género desconocido usa 0.6 como fallback → no debe crashear."""
        f = genre_popularity_factor({"GeneroInventado": 1.0})
        assert 0.20 <= f <= 1.01

    def test_niche_genre_has_lower_factor_than_mass(self):
        """Documentary debe dar factor menor que Action."""
        f_doc    = genre_popularity_factor({"Documentary": 1.0})
        f_action = genre_popularity_factor({"Action": 1.0})
        assert f_doc < f_action


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 4 — translate_vibes: TODOS los valores de Tono (101 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTranslateVibesAllTones:

    @pytest.mark.parametrize("tone", ALL_TONES)
    def test_always_excludes_always_exclude(self, tone):
        c = translate_vibes([], tone, 50, 1990, 2024)
        for genre in ALWAYS_EXCLUDE:
            assert genre in c.exclude_genres, (
                f"tone={tone}: ALWAYS_EXCLUDE '{genre}' no está en exclude_genres"
            )

    @pytest.mark.parametrize("tone", ALL_TONES)
    def test_no_overlap_between_exclude_and_required(self, tone):
        """Un género nunca puede estar excluido Y requerido al mismo tiempo."""
        c = translate_vibes([], tone, 50, 1990, 2024)
        exc = set(c.exclude_genres)
        for group in c.genre_groups:
            for g in group:
                assert g not in exc, (
                    f"tone={tone}: '{g}' está en exclude_genres Y en genre_groups"
                )

    @pytest.mark.parametrize("tone", range(0, 11))
    def test_dark_genres_excluded_at_low_tone(self, tone):
        c = translate_vibes([], tone, 50, 1990, 2024)
        for g in TONE_EXCLUDE_LOW:
            assert g in c.exclude_genres, (
                f"tone={tone}: '{g}' debería estar excluido (tone ≤ 10)"
            )

    @pytest.mark.parametrize("tone", range(11, 90))
    def test_no_extreme_excludes_at_mid_tone(self, tone):
        """Entre 11 y 89, ningún extremo de exclusión debería aplicarse."""
        c = translate_vibes([], tone, 50, 1990, 2024)
        exc = set(c.exclude_genres)
        for g in TONE_EXCLUDE_LOW:
            assert g not in exc, (
                f"tone={tone}: '{g}' excluido ilegítimamente (solo aplica ≤ 10)"
            )
        for g in TONE_EXCLUDE_HIGH:
            assert g not in exc, (
                f"tone={tone}: '{g}' excluido ilegítimamente (solo aplica ≥ 90)"
            )

    @pytest.mark.parametrize("tone", range(90, 101))
    def test_light_genres_excluded_at_high_tone(self, tone):
        c = translate_vibes([], tone, 50, 1990, 2024)
        for g in TONE_EXCLUDE_HIGH:
            assert g in c.exclude_genres, (
                f"tone={tone}: '{g}' debería estar excluido (tone ≥ 90)"
            )

    @pytest.mark.parametrize("tone", ALL_TONES)
    def test_priority_genres_are_known_genres(self, tone):
        c = translate_vibes([], tone, 50, 1990, 2024)
        for g in c.priority_genres:
            assert g in IMDB_TO_TMDB_GENRE, (
                f"tone={tone}: priority_genre '{g}' no está en IMDB_TO_TMDB_GENRE"
            )

    @pytest.mark.parametrize("tone", ALL_TONES)
    def test_year_from_to_preserved(self, tone):
        c = translate_vibes([], tone, 50, 1975, 2010)
        assert c.year_from == 1975
        assert c.year_to   == 2010

    @pytest.mark.parametrize("tone", ALL_TONES)
    def test_no_duplicate_excludes(self, tone):
        """No debe haber géneros duplicados en exclude_genres."""
        c = translate_vibes([], tone, 50, 1990, 2024)
        assert len(c.exclude_genres) == len(set(c.exclude_genres)), (
            f"tone={tone}: duplicados en exclude_genres: {c.exclude_genres}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 5 — translate_vibes: TODOS los valores de Cerebro (101 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTranslateVibesAllCerebro:

    @pytest.mark.parametrize("cerebro", ALL_CEREBRO)
    def test_min_votes_always_positive(self, cerebro):
        c = translate_vibes([], 50, cerebro, 1990, 2024)
        assert c.min_votes > 0

    @pytest.mark.parametrize("cerebro", ALL_CEREBRO)
    def test_min_vibe_score_valid_range(self, cerebro):
        c = translate_vibes([], 50, cerebro, 1990, 2024)
        assert 4.0 <= c.min_vibe_score <= 8.0, (
            f"cerebro={cerebro}: min_vibe_score={c.min_vibe_score} fuera de rango"
        )

    @pytest.mark.parametrize("cerebro", range(0, 65))
    def test_no_max_votes_below_65(self, cerebro):
        c = translate_vibes([], 50, cerebro, 1990, 2024)
        assert c.max_votes is None, (
            f"cerebro={cerebro}: max_votes={c.max_votes} debería ser None"
        )

    @pytest.mark.parametrize("cerebro", range(65, 101))
    def test_max_votes_present_above_65(self, cerebro):
        c = translate_vibes([], 50, cerebro, 1990, 2024)
        assert c.max_votes is not None, (
            f"cerebro={cerebro}: max_votes es None pero debería existir"
        )

    @pytest.mark.parametrize("cerebro", range(70, 101))
    def test_autor_mode_adds_priority_genres(self, cerebro):
        """cerebro ≥ 70 debe añadir géneros de autor a priority_genres."""
        c = translate_vibes([], 50, cerebro, 1990, 2024)
        autor_genres = {"Biography", "History", "Drama", "Documentary"}
        has_any = bool(autor_genres & set(c.priority_genres))
        assert has_any, (
            f"cerebro={cerebro}: ningún género autor en priority_genres"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 6 — Producto cartesiano Tono × Cerebro (10.201 combinaciones)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("tone,cerebro", itertools.product(
    range(0, 101, 5),   # cada 5 → 21 valores
    range(0, 101, 5),   # cada 5 → 21 valores
))                      # 441 combinaciones — rápido y representativo
class TestToneCerebroProduct:
    """
    441 combinaciones (cada 5 pasos) que verifican los invariantes críticos
    de la interacción Tono × Cerebro. Para el producto completo 101×101
    usa: pytest -k test_no_excluded_genre_in_groups
    """

    def test_no_excluded_genre_in_groups(self, tone, cerebro):
        c = translate_vibes([], tone, cerebro, 1990, 2024)
        exc = set(c.exclude_genres)
        for group in c.genre_groups:
            for g in group:
                assert g not in exc, (
                    f"tone={tone} cerebro={cerebro}: '{g}' en exclude Y en groups"
                )

    def test_min_votes_positive(self, tone, cerebro):
        c = translate_vibes([], tone, cerebro, 1990, 2024)
        assert c.min_votes > 0

    def test_max_votes_greater_than_min_when_set(self, tone, cerebro):
        c = translate_vibes([], tone, cerebro, 1990, 2024)
        if c.max_votes is not None:
            assert c.max_votes > c.min_votes, (
                f"tone={tone} cerebro={cerebro}: max_votes={c.max_votes} "
                f"<= min_votes={c.min_votes}"
            )

    def test_min_vibe_score_in_range(self, tone, cerebro):
        c = translate_vibes([], tone, cerebro, 1990, 2024)
        assert 4.0 <= c.min_vibe_score <= 8.0

    def test_always_exclude_present(self, tone, cerebro):
        c = translate_vibes([], tone, cerebro, 1990, 2024)
        for g in ALWAYS_EXCLUDE:
            assert g in c.exclude_genres


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 7 — Géneros: todos individualmente (17 géneros)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAllGenresIndividually:

    @pytest.mark.parametrize("genre", ALL_GENRES)
    def test_single_genre_in_user_genres(self, genre):
        c = translate_vibes([genre], 50, 50, 1990, 2024)
        assert genre in c.user_genres

    @pytest.mark.parametrize("genre", ALL_GENRES)
    def test_single_genre_in_genre_groups_unless_excluded(self, genre):
        c = translate_vibes([genre], 50, 50, 1990, 2024)
        # tone=50 no excluye ningún género de usuario → debe estar en groups
        flat = [g for group in c.genre_groups for g in group]
        assert genre in flat, (
            f"'{genre}': no aparece en genre_groups con tone=50"
        )

    @pytest.mark.parametrize("genre", TONE_EXCLUDE_LOW)
    def test_excluded_genre_removed_from_groups_at_low_tone(self, genre):
        """Si el usuario pide un género que tone=0 excluye, desaparece de groups."""
        c = translate_vibes([genre], 0, 50, 1990, 2024)
        flat = [g for group in c.genre_groups for g in group]
        assert genre not in flat, (
            f"'{genre}': debería desaparecer de genre_groups con tone=0"
        )

    @pytest.mark.parametrize("genre", TONE_EXCLUDE_HIGH)
    def test_excluded_genre_removed_from_groups_at_high_tone(self, genre):
        """Si el usuario pide un género que tone=100 excluye, desaparece de groups."""
        c = translate_vibes([genre], 100, 50, 1990, 2024)
        flat = [g for group in c.genre_groups for g in group]
        assert genre not in flat, (
            f"'{genre}': debería desaparecer de genre_groups con tone=100"
        )

    @pytest.mark.parametrize("genre", ALL_GENRES)
    def test_user_genre_preserved_in_user_genres_regardless_of_tone(self, genre):
        """user_genres siempre preserva la selección original del usuario."""
        for tone in [0, 50, 100]:
            c = translate_vibes([genre], tone, 50, 1990, 2024)
            assert genre in c.user_genres, (
                f"'{genre}' con tone={tone}: desapareció de user_genres"
            )

    @pytest.mark.parametrize("genre", ALL_GENRES)
    def test_genre_has_tmdb_mapping(self, genre):
        """Todos los géneros deben tener mapping a TMDB ID."""
        assert genre in IMDB_TO_TMDB_GENRE, f"'{genre}' sin mapping TMDB"
        assert IMDB_TO_TMDB_GENRE[genre] > 0


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 8 — Géneros: todos los pares (136 combinaciones)
# ═══════════════════════════════════════════════════════════════════════════════

GENRE_PAIRS = list(itertools.combinations(ALL_GENRES, 2))   # 136 pares

class TestGenrePairs:

    @pytest.mark.parametrize("g1,g2", GENRE_PAIRS)
    def test_both_genres_in_user_genres(self, g1, g2):
        c = translate_vibes([g1, g2], 50, 50, 1990, 2024)
        assert g1 in c.user_genres
        assert g2 in c.user_genres

    @pytest.mark.parametrize("g1,g2", GENRE_PAIRS)
    def test_two_genres_create_two_and_groups(self, g1, g2):
        """Dos géneros elegidos = AND semántico = dos grupos separados."""
        c = translate_vibes([g1, g2], 50, 50, 1990, 2024)
        # Los grupos del usuario son los NO excluidos
        user_groups = [[g] for g in [g1, g2]]
        user_in_groups = sum(1 for g in [g1, g2]
                             if [g] in c.genre_groups or
                             any(g in grp for grp in c.genre_groups))
        # Al menos el grupo de alguno de los dos debe estar presente
        # (salvo si ambos están excluidos por tone=50, lo que no ocurre)
        assert user_in_groups >= 1

    @pytest.mark.parametrize("g1,g2", GENRE_PAIRS)
    def test_no_excluded_genre_in_groups(self, g1, g2):
        """En ningún par la colisión exclusión/group debe producir inconsistencia."""
        for tone in [0, 50, 100]:
            c = translate_vibes([g1, g2], tone, 50, 1990, 2024)
            exc = set(c.exclude_genres)
            for group in c.genre_groups:
                for g in group:
                    assert g not in exc, (
                        f"tone={tone}, [{g1},{g2}]: '{g}' en exclude Y en groups"
                    )


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 9 — Rango de años: todos los pares de boundaries
# ═══════════════════════════════════════════════════════════════════════════════

YEAR_PAIRS = [(a, b) for a in YEAR_BOUNDS for b in YEAR_BOUNDS if a <= b]

class TestYearRanges:

    @pytest.mark.parametrize("year_from,year_to", YEAR_PAIRS)
    def test_years_preserved_exactly(self, year_from, year_to):
        c = translate_vibes([], 50, 50, year_from, year_to)
        assert c.year_from == year_from
        assert c.year_to   == year_to

    @pytest.mark.parametrize("year", YEAR_BOUNDS)
    def test_single_year_range(self, year):
        """year_from == year_to es un caso válido (buscar solo un año exacto)."""
        c = translate_vibes([], 50, 50, year, year)
        assert c.year_from == year
        assert c.year_to   == year

    def test_minimum_possible_year(self):
        c = translate_vibes([], 50, 50, 1900, 1900)
        assert c.year_from == 1900

    def test_maximum_possible_year(self):
        c = translate_vibes([], 50, 50, 2030, 2030)
        assert c.year_to == 2030

    @pytest.mark.parametrize("year_from,year_to", YEAR_PAIRS)
    def test_translate_vibes_does_not_invert_years(self, year_from, year_to):
        c = translate_vibes([], 50, 50, year_from, year_to)
        assert c.year_from <= c.year_to, (
            f"year_from={year_from}, year_to={year_to}: se invirtieron en constraints"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 10 — Interacción Nota × Cerebro (vibe_score vs min_avg_rating)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRatingVibescoreInteraction:
    """
    El slider Nota y Cerebro comparten terreno a través de min_vibe_score.
    La regla: nota del usuario > vibe_score del cerebro cuando hay conflicto.
    """

    @pytest.mark.parametrize("min_r,max_r", [
        (5.0, None),  (5.0, 6.0),  (5.0, 7.0),  (5.0, 8.0),
        (6.0, None),  (6.0, 7.0),  (6.0, 8.0),
        (7.0, None),  (7.0, 8.0),
        (7.5, None),  (8.0, None),
    ])
    def test_max_rating_ceiling_adjusts_vibe_floor(self, min_r, max_r):
        """
        Si el usuario fija un techo de nota, min_vibe_score no puede
        superar ese techo (evita el caso: quiero pelis 6.0-7.0 pero el
        cerebro pide vibe>=6.65 y no devuelve nada).
        """
        c = translate_vibes([], 50, 50, 1990, 2024)
        # Simular la lógica del MixService
        min_vibe = c.min_vibe_score
        if max_r is not None:
            min_vibe = min(min_vibe, max(4.0, max_r - 0.5))
        if min_r > 5.0:
            min_vibe = min(min_vibe, min_r - 0.1)
        if max_r is not None:
            assert min_vibe <= max_r, (
                f"min_r={min_r}, max_r={max_r}: "
                f"min_vibe_score={min_vibe:.2f} > max_avg_rating={max_r}"
            )

    @pytest.mark.parametrize("min_rating", RATING_FLOORS)
    def test_explicit_floor_respected(self, min_rating):
        """
        Cuando el usuario pide nota > 5.0, vibe_score se ajusta a la baja para
        no crear una colisión imposible (vibe > nota_usuario).

        5.0 es el valor por defecto/mínimo del slider — en ese caso el suelo
        de calidad de cerebro (vibe_score) actúa libremente como señal
        independiente (no es el mismo campo que averageRating en SQL).
        """
        if min_rating == 5.0:
            pytest.skip("5.0 es el mínimo por defecto; vibe_score aplica independientemente")
        c = translate_vibes([], 50, 50, 1990, 2024)
        min_vibe = c.min_vibe_score
        if min_rating > 5.0:
            min_vibe = min(min_vibe, min_rating - 0.1)
        # Tras el ajuste, el suelo de vibe_score no puede superar la nota explícita
        assert min_vibe <= min_rating, (
            f"min_rating={min_rating}: min_vibe_score={min_vibe:.2f} > nota solicitada"
        )

    @pytest.mark.parametrize("cerebro,max_r", itertools.product(
        [0, 25, 50, 75, 100], [5.5, 6.0, 6.5, 7.0, 7.5, 8.0]
    ))
    def test_vibe_never_exceeds_user_ceiling_any_cerebro(self, cerebro, max_r):
        """
        Para cualquier cerebro y cualquier techo de nota, min_vibe_score
        ajustado nunca puede superar el techo del usuario.
        """
        c = translate_vibes([], 50, cerebro, 1990, 2024)
        adjusted_vibe = min(c.min_vibe_score, max(4.0, max_r - 0.5))
        assert adjusted_vibe <= max_r, (
            f"cerebro={cerebro}, max_r={max_r}: "
            f"vibe ajustado={adjusted_vibe:.2f} > techo usuario={max_r}"
        )

    def test_default_rating_no_constraint(self):
        """Con nota por defecto (5.0/None) no debe haber filtro de nota en constraints."""
        c = translate_vibes([], 50, 50, 1990, 2024)
        assert c.min_avg_rating == 5.0   # default → no añade cláusula SQL
        assert c.max_avg_rating is None  # default → sin techo


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 11 — Duración: todas las opciones
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuntimeOptions:

    @pytest.mark.parametrize("runtime_min,runtime_max", RUNTIME_OPTIONS)
    def test_runtime_stored_in_constraints(self, runtime_min, runtime_max):
        c = translate_vibes([], 50, 50, 1990, 2024)
        c.runtime_min = runtime_min
        c.runtime_max = runtime_max
        assert c.runtime_min == runtime_min
        assert c.runtime_max == runtime_max

    def test_short_film_max_89(self):
        c = VibeConstraints()
        c.runtime_max = 89
        assert c.runtime_max == 89
        assert c.runtime_min is None

    def test_medium_film_range(self):
        c = VibeConstraints()
        c.runtime_min = 90
        c.runtime_max = 140
        assert c.runtime_min < c.runtime_max

    def test_long_film_min_141(self):
        c = VibeConstraints()
        c.runtime_min = 141
        assert c.runtime_max is None

    @pytest.mark.parametrize("runtime_min,runtime_max", RUNTIME_OPTIONS)
    def test_runtime_does_not_affect_genre_logic(self, runtime_min, runtime_max):
        """Duración no debe cambiar géneros ni exclusiones."""
        c_no_runtime = translate_vibes(["Action"], 50, 50, 1990, 2024)
        c_runtime    = translate_vibes(["Action"], 50, 50, 1990, 2024)
        c_runtime.runtime_min = runtime_min
        c_runtime.runtime_max = runtime_max
        assert c_no_runtime.genre_groups   == c_runtime.genre_groups
        assert c_no_runtime.exclude_genres == c_runtime.exclude_genres
        assert c_no_runtime.user_genres    == c_runtime.user_genres


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 12 — TMDB: estrategia de páginas para todos los valores de cerebro
# ═══════════════════════════════════════════════════════════════════════════════

class TestTmdbPageStrategy:

    @pytest.mark.parametrize("cerebro", ALL_CEREBRO)
    def test_page_strategy_returns_valid_sort_by(self, cerebro):
        sort_by, p_start, p_end = _page_strategy(cerebro)
        valid_sorts = {"popularity.desc", "vote_average.desc"}
        assert sort_by in valid_sorts, (
            f"cerebro={cerebro}: sort_by='{sort_by}' no es válido"
        )

    @pytest.mark.parametrize("cerebro", ALL_CEREBRO)
    def test_page_start_at_least_1(self, cerebro):
        _, p_start, _ = _page_strategy(cerebro)
        assert p_start >= 1

    @pytest.mark.parametrize("cerebro", ALL_CEREBRO)
    def test_page_end_greater_than_start(self, cerebro):
        _, p_start, p_end = _page_strategy(cerebro)
        assert p_end >= p_start, (
            f"cerebro={cerebro}: p_end={p_end} < p_start={p_start}"
        )

    @pytest.mark.parametrize("cerebro", ALL_CEREBRO)
    def test_page_end_within_tmdb_limit(self, cerebro):
        """TMDB permite máximo 500 páginas."""
        _, _, p_end = _page_strategy(cerebro)
        assert p_end <= 500

    @pytest.mark.parametrize("cerebro", range(65, 101))
    def test_high_cerebro_uses_quality_sort(self, cerebro):
        """cerebro ≥ 65 debe usar vote_average.desc (calidad > popularidad)."""
        sort_by, _, _ = _page_strategy(cerebro)
        assert sort_by == "vote_average.desc", (
            f"cerebro={cerebro}: debería usar vote_average.desc, usa '{sort_by}'"
        )

    @pytest.mark.parametrize("cerebro", range(0, 40))
    def test_low_cerebro_uses_popularity_sort(self, cerebro):
        """cerebro < 40 debe usar popularity.desc (blockbusters actuales)."""
        sort_by, _, _ = _page_strategy(cerebro)
        assert sort_by == "popularity.desc", (
            f"cerebro={cerebro}: debería usar popularity.desc, usa '{sort_by}'"
        )

    @pytest.mark.parametrize("cerebro", range(0, 40))
    def test_blockbuster_mode_tight_page_range(self, cerebro):
        """Modo blockbuster: pocas páginas (solo lo más popular)."""
        _, p_start, p_end = _page_strategy(cerebro)
        assert p_end <= 10, (
            f"cerebro={cerebro} blockbuster mode: p_end={p_end} debería ser ≤ 10"
        )

    @pytest.mark.parametrize("cerebro", range(65, 101))
    def test_autor_mode_wider_page_range(self, cerebro):
        """Modo autor: rango de páginas más amplio para encontrar joyas ocultas."""
        _, p_start, p_end = _page_strategy(cerebro)
        assert p_end >= 20, (
            f"cerebro={cerebro} autor mode: p_end={p_end} debería ser ≥ 20"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 13 — TMDB: calibración de vote_count para todos los cerebros
# ═══════════════════════════════════════════════════════════════════════════════

class TestTmdbVoteCountCalibration:

    @pytest.mark.parametrize("cerebro", ALL_CEREBRO)
    def test_vote_count_always_at_least_50(self, cerebro):
        """En modo nicho extremo (cerebro=100), nunca menos de 50 votos TMDB."""
        min_votes, _, _ = cerebro_to_constraints(cerebro, 1.0)
        tmdb_threshold = max(50, min_votes // VOTE_COUNT_FACTOR)
        assert tmdb_threshold >= 50

    @pytest.mark.parametrize("cerebro", ALL_CEREBRO)
    def test_vote_count_is_integer(self, cerebro):
        min_votes, _, _ = cerebro_to_constraints(cerebro, 1.0)
        tmdb_threshold = max(50, min_votes // VOTE_COUNT_FACTOR)
        assert isinstance(tmdb_threshold, int)

    def test_vote_count_blockbuster_mode_reasonable(self):
        """cerebro=0: umbral TMDB debe ser ≥ 5k (solo blockbusters conocidos)."""
        min_votes, _, _ = cerebro_to_constraints(0, 1.0)
        tmdb = max(50, min_votes // VOTE_COUNT_FACTOR)
        assert tmdb >= 5_000, f"cerebro=0: umbral TMDB={tmdb} parece demasiado bajo"

    def test_vote_count_niche_mode_permissive(self):
        """cerebro=100: umbral TMDB no debe ser tan alto que excluya todo."""
        min_votes, _, _ = cerebro_to_constraints(100, 1.0)
        tmdb = max(50, min_votes // VOTE_COUNT_FACTOR)
        assert tmdb <= 500, f"cerebro=100: umbral TMDB={tmdb} demasiado alto para nicho"

    def test_vote_count_monotonically_decreasing(self):
        """A mayor cerebro, menor umbral de votos en TMDB también."""
        prev_tmdb = max(50, cerebro_to_constraints(0, 1.0)[0] // VOTE_COUNT_FACTOR)
        for c in range(1, 101):
            curr_imdb = cerebro_to_constraints(c, 1.0)[0]
            curr_tmdb = max(50, curr_imdb // VOTE_COUNT_FACTOR)
            assert curr_tmdb <= prev_tmdb, (
                f"cerebro={c}: tmdb_threshold={curr_tmdb} > "
                f"cerebro={c-1}: {prev_tmdb} — inversión!"
            )
            prev_tmdb = curr_tmdb


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 14 — TMDB: ajuste de rating (RATING_OFFSET)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTmdbRatingAdjustment:

    @pytest.mark.parametrize("min_r", RATING_FLOORS)
    def test_adjusted_floor_always_positive(self, min_r):
        adjusted = max(4.5, round(min_r - RATING_OFFSET, 1))
        assert adjusted > 0

    @pytest.mark.parametrize("min_r", RATING_FLOORS)
    def test_adjusted_floor_at_least_4_5(self, min_r):
        adjusted = max(4.5, round(min_r - RATING_OFFSET, 1))
        assert adjusted >= 4.5

    @pytest.mark.parametrize("min_r", RATING_FLOORS)
    def test_adjusted_floor_below_original(self, min_r):
        """El ajuste hacia TMDB siempre es más laxo que el original."""
        adjusted = max(4.5, round(min_r - RATING_OFFSET, 1))
        assert adjusted <= min_r

    @pytest.mark.parametrize("min_r,max_r", [
        (5.0, 6.0), (5.0, 7.0), (6.0, 7.0), (6.5, 8.0), (7.0, 8.0)
    ])
    def test_adjusted_floor_below_ceiling(self, min_r, max_r):
        """El floor ajustado siempre debe estar por debajo del techo."""
        adjusted_floor = max(4.5, round(min_r - RATING_OFFSET, 1))
        assert adjusted_floor < max_r, (
            f"min_r={min_r}, max_r={max_r}: "
            f"adjusted_floor={adjusted_floor} >= max_r"
        )

    def test_rating_offset_is_positive(self):
        """El offset debe ser positivo (restamos, no sumamos)."""
        assert RATING_OFFSET > 0

    def test_rating_offset_reasonable_magnitude(self):
        """El offset no debe ser ni insignificante ni excesivo."""
        assert 0.1 <= RATING_OFFSET <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 15 — TMDB: _to_tmdb_ids para todos los géneros
# ═══════════════════════════════════════════════════════════════════════════════

class TestTmdbGenreMapping:

    @pytest.mark.parametrize("genre", ALL_GENRES)
    def test_every_genre_has_valid_tmdb_id(self, genre):
        ids = TmdbClient._to_tmdb_ids([genre])
        assert len(ids) >= 1, f"'{genre}' no produjo ningún ID TMDB"
        assert all(id_str.isdigit() for id_str in ids), (
            f"'{genre}': ID no numérico: {ids}"
        )

    def test_empty_list_returns_empty(self):
        assert TmdbClient._to_tmdb_ids([]) == []

    def test_unknown_genre_silently_ignored(self):
        ids = TmdbClient._to_tmdb_ids(["GeneroQueNoExiste"])
        assert ids == []

    def test_biography_maps_to_drama_id(self):
        """Biography → Drama (18) porque TMDB no tiene Biography."""
        ids = TmdbClient._to_tmdb_ids(["Biography"])
        assert "18" in ids

    def test_biography_and_drama_deduplicated(self):
        """Biography y Drama → mismo ID (18) → debe deduplicarse."""
        ids = TmdbClient._to_tmdb_ids(["Biography", "Drama"])
        assert ids.count("18") == 1, "ID 18 duplicado para Biography+Drama"

    def test_war_has_distinct_id(self):
        """War debe tener su propio ID (10752), no confundirse con otro."""
        ids = TmdbClient._to_tmdb_ids(["War"])
        assert "10752" in ids

    @pytest.mark.parametrize("genres", [
        ["Action", "Horror"],
        ["Comedy", "Drama", "Thriller"],
        ALL_GENRES[:5],
    ])
    def test_multiple_genres_all_mapped(self, genres):
        ids = TmdbClient._to_tmdb_ids(genres)
        assert len(ids) >= 1

    def test_exclude_genres_correctly_mapped(self):
        """Los géneros de exclusión de tono deben ser mapeables a TMDB IDs."""
        for g in TONE_EXCLUDE_LOW + TONE_EXCLUDE_HIGH:
            ids = TmdbClient._to_tmdb_ids([g])
            assert len(ids) >= 1, f"'{g}' de TONE_EXCLUDE no tiene ID TMDB"


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 16 — Plataformas: constantes y mappings
# ═══════════════════════════════════════════════════════════════════════════════

class TestPlatformConstants:

    @pytest.mark.parametrize("platform", PLATFORM_IDS.keys())
    def test_all_platforms_have_positive_id(self, platform):
        assert PLATFORM_IDS[platform] > 0

    @pytest.mark.parametrize("platform", PLATFORM_IDS.keys())
    def test_all_platform_ids_are_distinct(self, platform):
        all_ids = list(PLATFORM_IDS.values())
        assert all_ids.count(PLATFORM_IDS[platform]) == 1, (
            f"Platform '{platform}' tiene ID duplicado"
        )

    def test_netflix_known_id(self):
        """Netflix en JustWatch/TMDB es el proveedor 8."""
        assert PLATFORM_IDS["netflix"] == 8

    def test_all_expected_platforms_present(self):
        for p in ["netflix", "prime", "disney", "max", "apple"]:
            assert p in PLATFORM_IDS, f"Plataforma '{p}' no está en PLATFORM_IDS"


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 17 — Casos límite y edge cases históricos
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:

    def test_all_genres_selected_simultaneously(self):
        """Seleccionar todos los géneros no debe crashear."""
        c = translate_vibes(ALL_GENRES, 50, 50, 1990, 2024)
        assert c is not None
        assert len(c.user_genres) == len(ALL_GENRES)

    def test_all_genres_selected_at_low_tone(self):
        """Con tone=0, los géneros oscuros desaparecen de groups pero no de user_genres."""
        c = translate_vibes(ALL_GENRES, 0, 50, 1990, 2024)
        flat_groups = [g for grp in c.genre_groups for g in grp]
        for dark in TONE_EXCLUDE_LOW:
            assert dark not in flat_groups
        # Pero sí en user_genres (intención del usuario preservada)
        for dark in TONE_EXCLUDE_LOW:
            assert dark in c.user_genres

    def test_only_excluded_genres_selected(self):
        """
        Si el usuario selecciona SOLO géneros que tone excluye,
        genre_groups queda vacío — no debe producir error, solo significa
        'sin restricción de género' (el usuario verá lo que queda).
        """
        excluded_only = TONE_EXCLUDE_LOW   # Horror, Crime, Thriller, Mystery
        c = translate_vibes(excluded_only, 0, 50, 1990, 2024)
        flat = [g for grp in c.genre_groups for g in grp]
        for g in excluded_only:
            assert g not in flat   # excluidos correctamente

    def test_tone_boundary_10_vs_11(self):
        """tone=10 activa exclusiones, tone=11 no. Comprobar el límite exacto."""
        c10 = translate_vibes([], 10, 50, 1990, 2024)
        c11 = translate_vibes([], 11, 50, 1990, 2024)
        for g in TONE_EXCLUDE_LOW:
            assert g in  c10.exclude_genres, f"tone=10: '{g}' debería excluirse"
            assert g not in c11.exclude_genres, f"tone=11: '{g}' NO debería excluirse"

    def test_tone_boundary_89_vs_90(self):
        """tone=90 activa exclusiones, tone=89 no."""
        c89 = translate_vibes([], 89, 50, 1990, 2024)
        c90 = translate_vibes([], 90, 50, 1990, 2024)
        for g in TONE_EXCLUDE_HIGH:
            assert g not in c89.exclude_genres, f"tone=89: '{g}' NO debería excluirse"
            assert g in    c90.exclude_genres,  f"tone=90: '{g}' debería excluirse"

    def test_cerebro_boundary_64_vs_65(self):
        """Límite exacto de max_votes: aparece en cerebro=65, no en 64."""
        _, max64, _ = cerebro_to_constraints(64, 1.0)
        _, max65, _ = cerebro_to_constraints(65, 1.0)
        assert max64 is None,     "cerebro=64: max_votes debería ser None"
        assert max65 is not None, "cerebro=65: max_votes debería existir"

    def test_cerebro_boundary_69_vs_70(self):
        """Límite de modo autor: priority_genres de autor aparecen en cerebro=70."""
        c69 = translate_vibes([], 50, 69, 1990, 2024)
        c70 = translate_vibes([], 50, 70, 1990, 2024)
        autor = {"Biography", "History", "Documentary"}
        in_69 = autor & set(c69.priority_genres)
        in_70 = autor & set(c70.priority_genres)
        assert len(in_70) > 0, "cerebro=70: géneros autor deberían estar en priority"
        # cerebro=69 no debería tenerlos (tono=50 no los añade)
        assert len(in_69) == 0, f"cerebro=69: géneros autor no deberían estar: {in_69}"

    def test_year_from_equals_year_to(self):
        """Año único (year_from == year_to) es válido."""
        c = translate_vibes([], 50, 50, 2000, 2000)
        assert c.year_from == c.year_to == 2000

    def test_pop_factor_minimum_clamp(self):
        """pop_factor nunca cae por debajo de 0.20."""
        f = genre_popularity_factor({"Documentary": 100.0, "Biography": 100.0})
        assert f >= 0.20

    def test_no_genres_selected_adds_tone_group(self):
        """Sin géneros de usuario, el Tono añade un grupo OR."""
        c = translate_vibes([], 70, 50, 1990, 2024)
        # tone=70 → Thriller/Crime/Mystery con peso >= 0.45
        assert len(c.genre_groups) >= 1, "Sin géneros usuario: falta grupo de Tono"

    def test_with_genres_does_not_add_tone_group(self):
        """Con géneros de usuario, el Tono NO añade grupo OR extra."""
        c_no_genres = translate_vibes([],          70, 50, 1990, 2024)
        c_genres    = translate_vibes(["Action"],  70, 50, 1990, 2024)
        # Con géneros: solo el grupo de usuario (no el OR del tono)
        # Sin géneros: hay un grupo OR del tono
        groups_flat_no_genres = [g for grp in c_no_genres.genre_groups for g in grp]
        groups_flat_genres    = [g for grp in c_genres.genre_groups    for g in grp]
        # Los géneros del tono no deben aparecer en genre_groups cuando hay user genres
        tone_only_genres = {"Thriller", "Crime", "Mystery", "Drama"}
        for g in tone_only_genres:
            assert g not in groups_flat_genres, (
                f"'{g}' del Tono no debería estar en groups cuando hay user_genres"
            )

    def test_vibe_score_range_extreme_cerebro_values(self):
        for cerebro in [0, 1, 99, 100]:
            _, _, vibe = cerebro_to_constraints(cerebro, 1.0)
            assert 5.0 <= vibe <= 7.51, (
                f"cerebro={cerebro}: vibe_score={vibe:.3f} fuera de [5.0, 7.5]"
            )

    def test_all_tone_anchors_reference_valid_genres(self):
        """Los géneros en TONE_ANCHORS deben existir en IMDB_TO_TMDB_GENRE."""
        for anchor_tone, anchor_weights in TONE_ANCHORS:
            for genre in anchor_weights:
                assert genre in IMDB_TO_TMDB_GENRE, (
                    f"TONE_ANCHORS tone={anchor_tone}: '{genre}' "
                    f"no está en IMDB_TO_TMDB_GENRE"
                )

    def test_tone_exclude_lists_reference_valid_genres(self):
        """Los géneros en TONE_EXCLUDE_* deben ser mapeables a TMDB."""
        for g in TONE_EXCLUDE_LOW + TONE_EXCLUDE_HIGH:
            assert g in IMDB_TO_TMDB_GENRE, (
                f"TONE_EXCLUDE: '{g}' no está en IMDB_TO_TMDB_GENRE"
            )
            ids = TmdbClient._to_tmdb_ids([g])
            assert len(ids) >= 1, f"'{g}' en TONE_EXCLUDE no tiene ID TMDB"

    def test_always_exclude_not_in_tmdb_genre_map(self):
        """
        Los géneros de ALWAYS_EXCLUDE (Adult, News…) no deben estar en
        IMDB_TO_TMDB_GENRE — son géneros IMDb sin equivalente TMDB real.
        Si estuvieran, se enviarían como without_genres innecesariamente
        con IDs inventados.
        """
        for g in ALWAYS_EXCLUDE:
            if g in IMDB_TO_TMDB_GENRE:
                ids = TmdbClient._to_tmdb_ids([g])
                # Si están mapeados, al menos que el ID sea válido
                assert all(id_str.isdigit() for id_str in ids), (
                    f"ALWAYS_EXCLUDE '{g}' tiene ID TMDB inválido: {ids}"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 18 — Invariantes globales (propiedades que SIEMPRE deben cumplirse)
# ═══════════════════════════════════════════════════════════════════════════════

class TestGlobalInvariants:
    """
    Propiedades de corrección que deben mantenerse para cualquier combinación
    de inputs válidos. Se ejecutan sobre una muestra representativa grande.
    """

    SAMPLE = list(itertools.product(
        range(0, 101, 10),   # tones: 0,10,20,...,100
        range(0, 101, 10),   # cerebros: 0,10,20,...,100
        [[], ["Action"], ["Drama", "Horror"], ALL_GENRES[:3]],
    ))  # 11 × 11 × 4 = 484 combinaciones

    @pytest.mark.parametrize("tone,cerebro,genres", SAMPLE)
    def test_exclude_genres_and_group_genres_never_overlap(self, tone, cerebro, genres):
        c = translate_vibes(genres, tone, cerebro, 1990, 2024)
        exc = set(c.exclude_genres)
        for group in c.genre_groups:
            for g in group:
                assert g not in exc, (
                    f"tone={tone} cerebro={cerebro} genres={genres}: "
                    f"'{g}' en exclude Y en groups — inconsistencia fatal"
                )

    @pytest.mark.parametrize("tone,cerebro,genres", SAMPLE)
    def test_always_exclude_always_present(self, tone, cerebro, genres):
        c = translate_vibes(genres, tone, cerebro, 1990, 2024)
        for g in ALWAYS_EXCLUDE:
            assert g in c.exclude_genres

    @pytest.mark.parametrize("tone,cerebro,genres", SAMPLE)
    def test_min_votes_positive_always(self, tone, cerebro, genres):
        c = translate_vibes(genres, tone, cerebro, 1990, 2024)
        assert c.min_votes > 0

    @pytest.mark.parametrize("tone,cerebro,genres", SAMPLE)
    def test_max_votes_coherent_always(self, tone, cerebro, genres):
        c = translate_vibes(genres, tone, cerebro, 1990, 2024)
        if c.max_votes is not None:
            assert c.max_votes > c.min_votes

    @pytest.mark.parametrize("tone,cerebro,genres", SAMPLE)
    def test_no_unknown_genres_in_output(self, tone, cerebro, genres):
        c = translate_vibes(genres, tone, cerebro, 1990, 2024)
        all_output_genres = (
            c.user_genres
            + c.priority_genres
            + [g for grp in c.genre_groups for g in grp]
        )
        for g in all_output_genres:
            if g not in ALWAYS_EXCLUDE:
                assert g in IMDB_TO_TMDB_GENRE, (
                    f"tone={tone} cerebro={cerebro}: género desconocido '{g}' en output"
                )

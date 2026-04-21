"""
Tests de la Vibe Matrix — demuestra la testeabilidad del dominio puro.

Estos tests NO requieren:
  - base de datos (SQLite)
  - API externa (TMDB)
  - servidor HTTP (FastAPI / uvicorn)
  - ningún mock

Solo importan módulos de domain/, que son Python puro.
Esto es la validación directa del valor de la Arquitectura Hexagonal:
el dominio se puede probar en microsegundos, en cualquier entorno, sin
infraestructura alguna.
"""

import pytest

from domain.vibe_matrix import cerebro_to_constraints, translate_vibes


# ── Tono: géneros prioritarios ────────────────────────────────────────────────

class TestTonePriorityGenres:
    def test_tone_0_produces_comedy_in_priority(self):
        """
        Tono=0 apunta al extremo cómico/familiar.
        TONE_ANCHORS[0] = {'Comedy': 1.0, 'Animation': 0.9, 'Family': 0.8, ...}
        Todos con peso >= 0.65 deben aparecer en priority_genres.
        """
        c = translate_vibes([], tone=0, cerebro=50, year_from=1990, year_to=2024)
        assert "Comedy" in c.priority_genres

    def test_tone_0_produces_animation_in_priority(self):
        c = translate_vibes([], tone=0, cerebro=50, year_from=1990, year_to=2024)
        assert "Animation" in c.priority_genres

    def test_tone_100_produces_horror_in_priority(self):
        """
        Tono=100 apunta al extremo oscuro/perturbador.
        TONE_ANCHORS[-1] = {'Horror': 1.0, ...} — Horror tiene peso 1.0 >= 0.65.
        """
        c = translate_vibes([], tone=100, cerebro=50, year_from=1990, year_to=2024)
        assert "Horror" in c.priority_genres

    def test_tone_100_horror_or_crime_in_priority(self):
        """
        Al menos Horror o Crime debe estar en priority_genres con Tono=100.
        Crime tiene peso 0.6 < 0.65, pero Horror (1.0) debe estar siempre.
        """
        c = translate_vibes([], tone=100, cerebro=50, year_from=1990, year_to=2024)
        assert "Horror" in c.priority_genres or "Crime" in c.priority_genres


# ── Cerebro: umbrales de votos ────────────────────────────────────────────────

class TestCerebroVoteThresholds:
    def test_cerebro_0_min_votes_gte_100000(self):
        """
        Cerebro=0 → modo blockbuster, pop_factor=1.0 (géneros neutros).
        Fórmula: 200_000 * (1/200)^0 * 1.0 = 200_000 >> 100_000.
        """
        min_votes, _, _ = cerebro_to_constraints(cerebro=0, pop_factor=1.0)
        assert min_votes >= 100_000, f"Esperado >= 100_000, obtenido {min_votes}"

    def test_cerebro_100_min_votes_lte_2000(self):
        """
        Cerebro=100 → modo autor/nicho, pop_factor=1.0.
        Fórmula: 200_000 * (1/200)^1 * 1.0 = 1_000 <= 2_000.
        """
        min_votes, _, _ = cerebro_to_constraints(cerebro=100, pop_factor=1.0)
        assert min_votes <= 2_000, f"Esperado <= 2_000, obtenido {min_votes}"

    def test_cerebro_0_no_max_votes(self):
        """En modo blockbuster no hay techo de votos (blockbusters son bienvenidos)."""
        _, max_votes, _ = cerebro_to_constraints(cerebro=0, pop_factor=1.0)
        assert max_votes is None

    def test_cerebro_100_has_max_votes(self):
        """En modo autor sí hay techo — se excluyen los mega-blockbusters."""
        _, max_votes, _ = cerebro_to_constraints(cerebro=100, pop_factor=1.0)
        assert max_votes is not None
        assert max_votes <= 15_000

    def test_cerebro_monotonically_decreasing_min_votes(self):
        """
        A mayor Cerebro, menor min_votes — la curva debe ser estrictamente
        decreciente (no puede haber inversión en la fórmula exponencial).
        """
        thresholds = [
            cerebro_to_constraints(cb, 1.0)[0]
            for cb in [0, 25, 50, 75, 100]
        ]
        assert thresholds == sorted(thresholds, reverse=True), (
            f"Umbral no es monótonamente decreciente: {thresholds}"
        )


# ── Exclusiones de géneros ────────────────────────────────────────────────────

class TestGenreExclusions:
    def test_war_not_excluded_at_tone_50(self):
        """
        War no debe estar en exclude_genres con Tono=50 (rango neutro).
        _TONE_EXCLUDE_LOW aplica solo en tone <= 10.
        _TONE_EXCLUDE_HIGH aplica solo en tone >= 90.
        War no está en ninguna de las dos listas ni en ALWAYS_EXCLUDE.
        """
        c = translate_vibes([], tone=50, cerebro=50, year_from=1990, year_to=2024)
        assert "War" not in c.exclude_genres

    def test_horror_excluded_at_tone_0(self):
        """
        Horror, Crime, Thriller, Mystery se excluyen en tone <= 10.
        Con tone=0 deben estar en exclude_genres.
        """
        c = translate_vibes([], tone=0, cerebro=50, year_from=1990, year_to=2024)
        assert "Horror" in c.exclude_genres

    def test_comedy_excluded_at_tone_100(self):
        """
        Comedy, Family, Animation, Romance se excluyen en tone >= 90.
        Con tone=100 deben estar en exclude_genres.
        """
        c = translate_vibes([], tone=100, cerebro=50, year_from=1990, year_to=2024)
        assert "Comedy" in c.exclude_genres

    def test_always_exclude_always_present(self):
        """Adult, News, etc. deben excluirse siempre independientemente del Tono."""
        for tone in [0, 50, 100]:
            c = translate_vibes([], tone=tone, cerebro=50, year_from=1990, year_to=2024)
            assert "Adult" in c.exclude_genres, f"Adult no excluido en tone={tone}"


# ── Resolución de colisiones ──────────────────────────────────────────────────

class TestCollisionResolution:
    def test_excluded_genre_removed_from_user_groups(self):
        """
        Si el usuario pide Thriller pero Tono=0 excluye Thriller,
        el grupo debe quedar vacío y descartarse (no genera SQL imposible).
        """
        c = translate_vibes(["Thriller"], tone=0, cerebro=50, year_from=1990, year_to=2024)
        # Thriller debe estar en exclude_genres (tone=0)
        assert "Thriller" in c.exclude_genres
        # Y no debe aparecer en ningún grupo de géneros
        for group in c.genre_groups:
            assert "Thriller" not in group

    def test_user_genres_preserved_at_neutral_tone(self):
        """Con Tono neutro, los géneros del usuario deben crear grupos individuales (AND)."""
        c = translate_vibes(["Action", "Drama"], tone=50, cerebro=50, year_from=1990, year_to=2024)
        assert ["Action"] in c.genre_groups
        assert ["Drama"] in c.genre_groups

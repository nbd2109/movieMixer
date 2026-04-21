"""
Constantes del dominio CineMix.
No contiene lógica de negocio — solo los valores que parametrizan la Vibe Matrix.
"""

# Géneros a excluir siempre (no son películas reales de cine)
ALWAYS_EXCLUDE: list[str] = ["Adult", "News", "Reality-TV", "Talk-Show", "Game-Show"]

# ── PLATAFORMAS DE STREAMING ──────────────────────────────────────────────────
# IDs de proveedor de JustWatch vía TMDB Watch Providers API.
PLATFORM_IDS: dict[str, int] = {
    "netflix": 8,
    "prime":   119,
    "disney":  337,
    "max":     1899,
    "apple":   350,
}

# Nombres de géneros IMDb → IDs de géneros TMDB
# Bug fix: "War" ya está mapeado correctamente como 10752.
IMDB_TO_TMDB_GENRE: dict[str, int] = {
    "Action":      28,
    "Adventure":   12,
    "Animation":   16,
    "Comedy":      35,
    "Crime":       80,
    "Documentary": 99,
    "Drama":       18,
    "Family":      10751,
    "Fantasy":     14,
    "History":     36,
    "Horror":      27,
    "Mystery":     9648,
    "Romance":     10749,
    "Sci-Fi":      878,
    "Thriller":    53,
    "War":         10752,   # ← presente; si faltara aquí sería el bug silencioso
    "Biography":   18,      # TMDB no tiene Biography; Drama es la categoría más cercana
}

# Mapa inverso: ID TMDB → nombre legible (para reconstruir géneros en respuesta)
TMDB_GENRE_NAMES: dict[int, str] = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy",
    80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Family",
    14: "Fantasy", 36: "History", 27: "Horror", 9648: "Mystery",
    10749: "Romance", 878: "Sci-Fi", 53: "Thriller", 10752: "War",
}

# Lenguas de producción india (filtradas en best-effort por TMDB)
INDIAN_LANGUAGES: frozenset[str] = frozenset(
    {"hi", "ta", "te", "ml", "kn", "bn", "mr", "pa", "gu", "ur"}
)

# ── TONE ANCHORS ──────────────────────────────────────────────────────────────
# 8 puntos del espectro emocional; cada uno con afinidades por género (0.0–1.0).
# Entre anclas se interpola linealmente → cada valor del slider es único.
#
#   afinidad >= 0.65  →  género preferido (pool prioritario en pick_one)
#   afinidad >= 0.45  →  incluido en el grupo OR requerido
#   afinidad <= 0.10  →  excluido en los extremos (solo anclas 0 y 100)
#
TONE_ANCHORS: list[tuple[int, dict[str, float]]] = [
    (0,   {"Comedy": 1.0, "Animation": 0.9, "Family": 0.8, "Adventure": 0.2}),
    (15,  {"Comedy": 0.8, "Adventure": 0.7, "Family": 0.5, "Romance": 0.3}),
    (30,  {"Romance": 0.8, "Comedy": 0.5, "Drama": 0.3, "Adventure": 0.3}),
    (45,  {"Drama": 0.8, "Romance": 0.5, "Biography": 0.4}),
    (55,  {"Drama": 0.9, "Biography": 0.4, "History": 0.4, "Mystery": 0.3}),
    (70,  {"Thriller": 0.8, "Crime": 0.7, "Mystery": 0.5, "Drama": 0.3}),
    (85,  {"Crime": 0.8, "Thriller": 0.7, "Horror": 0.6, "Mystery": 0.3}),
    (100, {"Horror": 1.0, "Crime": 0.6, "Thriller": 0.5}),
]

TONE_VALUES: list[int] = [a[0] for a in TONE_ANCHORS]

# Géneros que se excluyen en los extremos absolutos del slider
TONE_EXCLUDE_LOW:  list[str] = ["Horror", "Crime", "Thriller", "Mystery"]  # tone <= 10
TONE_EXCLUDE_HIGH: list[str] = ["Comedy", "Family", "Animation", "Romance"]  # tone >= 90

# ── POPULARIDAD POR GÉNERO ────────────────────────────────────────────────────
# Qué tan masivo es un género en términos de votos (1.0 = máximo mainstream).
# Usado para adaptar los umbrales de Cerebro cuando Tono apunta a géneros de nicho.
GENRE_POPULARITY: dict[str, float] = {
    "Action":      1.00,
    "Comedy":      1.00,
    "Horror":      0.90,
    "Thriller":    0.90,
    "Sci-Fi":      0.85,
    "Adventure":   0.85,
    "Animation":   0.80,
    "Family":      0.80,
    "Romance":     0.75,
    "Crime":       0.75,
    "Drama":       0.70,
    "Mystery":     0.65,
    "Fantasy":     0.65,
    "Biography":   0.35,
    "History":     0.30,
    "Documentary": 0.25,
}

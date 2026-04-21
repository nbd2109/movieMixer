"""
Entidades del dominio CineMix.

VibeConstraints es el objeto central ("Aggregate") que encapsula todas las
restricciones resueltas a partir de los sliders del usuario. Es inmutable desde
el punto de vista del dominio: una vez construido por translate_vibes() representa
un estado concreto de la búsqueda.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VibeConstraints:
    """
    Restricciones resueltas listas para convertirse en una consulta de persistencia.

    user_genres     → Géneros que eligió el usuario en los pads (guardados aparte
                      para que el fallback pueda preservarlos más tiempo).
    genre_groups    → AND entre grupos, OR dentro de cada grupo.
                      Cuando el usuario elige géneros, cada uno es un grupo propio.
                      Cuando NO elige ninguno, el Tono añade un grupo OR de géneros afines.
    exclude_genres  → Exclusiones hard. Siempre tienen prioridad sobre genre_groups.
    priority_genres → Sesgo suave en pick_one() (70/30).
    min_votes       → Umbral mínimo de votos (exponencial continua).
    max_votes       → Techo de votos — excluye blockbusters en modo autor.
    min_vibe_score  → Bayesian Weighted Rating mínimo (curva cóncava continua).
    min_avg_rating  → Nota IMDb mínima elegida por el usuario.
    max_avg_rating  → Nota IMDb máxima elegida por el usuario.
    """
    user_genres:     list[str]        = field(default_factory=list)
    genre_groups:    list[list[str]]  = field(default_factory=list)
    exclude_genres:  list[str]        = field(default_factory=list)
    priority_genres: list[str]        = field(default_factory=list)
    min_votes:       int              = 15_000
    max_votes:       Optional[int]    = None
    min_vibe_score:  float            = 6.0
    min_avg_rating:  float            = 5.0
    max_avg_rating:  Optional[float]  = None
    year_from:       int              = 1990
    year_to:         int              = 2024
    runtime_min:     Optional[int]    = None
    runtime_max:     Optional[int]    = None

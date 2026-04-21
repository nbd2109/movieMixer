"""
Sistema de fallback — relajación progresiva de restricciones.

Separado de vibe_matrix.py porque es una estrategia de recuperación de errores,
no lógica de construcción de restricciones. Mantiene el principio de
responsabilidad única dentro del dominio.
"""

import copy
from typing import Optional

from domain.entities import VibeConstraints


STEP_REASON: dict[int, str] = {
    1: "epoch",       # ampliar años
    2: "popularity",  # bajar umbral votos/vibe
    3: "tone",        # quitar géneros del tono
    4: "genres",      # quitar géneros del usuario
    5: "tone",        # quitar exclusiones de tono
    6: "popularity",  # quitar límite máx votos
    7: "rating",      # quitar filtro de nota
    8: "runtime",     # quitar filtro de duración
}


def relax(c: VibeConstraints, step: int) -> Optional[VibeConstraints]:
    """
    Relaja las restricciones en orden de menor a mayor impacto.
    Devuelve None cuando ya no hay nada más que relajar.

    Orden de relajación:
      Paso 1 → Ampliar rango de años ±10 años
      Paso 2 → Reducir numVotes a la mitad y bajar min_vibe
      Paso 3 → Eliminar el grupo OR del Tono; conservar géneros del usuario
      Paso 4 → Eliminar también los géneros del usuario (pool sin filtro de género)
      Paso 5 → Eliminar exclusiones de géneros
      Paso 6 → Eliminar límite máximo de votos (Cerebro alto)
      Paso 7 → Eliminar filtro de nota (min/max rating)
      Paso 8 → Eliminar filtro de duración
    """
    r = copy.deepcopy(c)

    if step == 1:
        r.year_from = max(1900, r.year_from - 10)
        r.year_to   = min(2030, r.year_to   + 10)
    elif step == 2:
        r.min_votes      = max(200, r.min_votes // 2)
        r.min_vibe_score = max(5.0, r.min_vibe_score - 0.5)
    elif step == 3:
        # Conservar solo los grupos del usuario (descartar el grupo OR del Tono)
        r.genre_groups = [[g] for g in r.user_genres]
    elif step == 4:
        # Ahora sí eliminar todo filtro de género
        r.genre_groups = []
        r.user_genres  = []
    elif step == 5:
        r.exclude_genres = []
    elif step == 6:
        r.max_votes = None
    elif step == 7:
        r.min_avg_rating = 5.0
        r.max_avg_rating = None
    elif step == 8:
        r.runtime_min = None
        r.runtime_max = None
    else:
        return None

    return r

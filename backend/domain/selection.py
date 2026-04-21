"""
Lógica de selección aleatoria con sesgo por priority_genres.
Módulo puro: sin IO, sin dependencias externas.
"""

import random


def pick_one(rows: list[dict], priority_genres: list[str]) -> dict:
    """
    Elige 1 película de un pool de hasta 100 candidatas.

    Si hay priority_genres (definidos por Tono o Cerebro alto), hay un 70% de
    probabilidad de elegir una película que los contenga. El 30% restante
    garantiza variedad y evita que el resultado sea siempre predecible.

    Requiere que cada elemento de `rows` tenga un campo 'genres' (string CSV).
    """
    if priority_genres:
        priority_pool = [
            r for r in rows
            if any(g in r["genres"] for g in priority_genres)
        ]
        if priority_pool and random.random() < 0.70:
            return random.choice(priority_pool)
    return random.choice(rows)

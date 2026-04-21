"""
Adaptador SQLite — implementa MovieRepository.

build_query() vive AQUÍ, no en el dominio. Es un detalle de implementación de
cómo SQLite traduce VibeConstraints a SQL parametrizado. El dominio no sabe nada
de SQL; solo conoce la especificación (VibeConstraints) y el contrato (MovieRepository).
"""

import os
import sqlite3

from fastapi import HTTPException

from domain.entities import VibeConstraints
from domain.ports.movie_repository import MovieRepository


class SQLiteMovieRepository(MovieRepository):
    """
    Repositorio basado en SQLite local (archivo movies.db).
    Usa la tabla `movie_genre` (índice en genre_name) para evitar
    full-table-scan con LIKE. Cada condición de género es una subquery indexada.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    # ── Puerto público ────────────────────────────────────────────────────────

    def find_movies(self, constraints: VibeConstraints) -> list[dict]:
        sql, params = self._build_query(constraints)
        return self._execute(sql, params)

    def count_all(self) -> int:
        rows = self._execute("SELECT COUNT(*) as cnt FROM movies", [])
        return rows[0]["cnt"] if rows else 0

    # ── Detalle privado de implementación ────────────────────────────────────

    def _build_query(self, c: VibeConstraints) -> tuple[str, list]:
        """
        Construye un SELECT parametrizado desde VibeConstraints.

        Ejemplo con genre_groups=[['Action','Sci-Fi'], ['Drama']] y exclude=['Horror']:
            WHERE startYear BETWEEN ? AND ?
              AND numVotes >= ?
              AND vibe_score >= ?
              AND tconst NOT IN (SELECT tconst FROM movie_genre WHERE genre_name = 'Horror')
              AND tconst IN (SELECT tconst FROM movie_genre WHERE genre_name IN ('Action','Sci-Fi'))
              AND tconst IN (SELECT tconst FROM movie_genre WHERE genre_name IN ('Drama'))
            LIMIT 100
        """
        clauses: list[str] = []
        params:  list      = []

        # Rango de años
        clauses.append("startYear BETWEEN ? AND ?")
        params += [c.year_from, c.year_to]

        # Votos mínimos
        clauses.append("numVotes >= ?")
        params.append(c.min_votes)

        # Votos máximos (solo Cerebro alto — excluye mega-blockbusters)
        if c.max_votes is not None:
            clauses.append("numVotes <= ?")
            params.append(c.max_votes)

        # Vibe score mínimo (Bayesian Weighted Rating)
        clauses.append("vibe_score >= ?")
        params.append(c.min_vibe_score)

        # Rango de nota elegido por el usuario (averageRating IMDb)
        if c.min_avg_rating > 5.0:
            clauses.append("averageRating >= ?")
            params.append(c.min_avg_rating)
        if c.max_avg_rating is not None:
            clauses.append("averageRating <= ?")
            params.append(c.max_avg_rating)

        # Géneros excluidos — subquery indexada por genre_name
        for genre in c.exclude_genres:
            clauses.append(
                "tconst NOT IN (SELECT tconst FROM movie_genre WHERE genre_name = ?)"
            )
            params.append(genre)

        # Grupos de géneros requeridos — OR dentro del grupo, AND entre grupos
        for group in c.genre_groups:
            placeholders = ",".join(["?" for _ in group])
            clauses.append(
                f"tconst IN (SELECT tconst FROM movie_genre WHERE genre_name IN ({placeholders}))"
            )
            params += group

        # Duración (solo cuando el usuario activa el filtro)
        if c.runtime_min is not None:
            clauses.append("runtimeMinutes >= ?")
            params.append(c.runtime_min)
        if c.runtime_max is not None:
            clauses.append("runtimeMinutes <= ?")
            params.append(c.runtime_max)

        sql = f"""
            SELECT tconst, primaryTitle, startYear, genres, averageRating, numVotes, runtimeMinutes
            FROM movies
            WHERE {' AND '.join(clauses)}
            ORDER BY RANDOM()
            LIMIT 100
        """
        return sql, params

    def _execute(self, sql: str, params: list) -> list[dict]:
        if not os.path.exists(self._db_path):
            raise HTTPException(
                503,
                detail="Base de datos no encontrada. Ejecuta: python setup_db.py",
            )
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

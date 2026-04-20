"""
migrate_genres.py — Fase 1 Remediación Crítica

Crea la tabla movie_genre (tconst, genre_name) desde el campo genres existente.
Añade índices para eliminar los full-table-scan de LIKE en build_query.

Uso: python migrate_genres.py
Seguro de relanzar: usa CREATE TABLE IF NOT EXISTS + INSERT OR IGNORE.
"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "movies.db")


def migrate():
    if not os.path.exists(DB_PATH):
        print("ERROR: movies.db no encontrada. Ejecuta setup_db.py primero.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")   # no bloquear lecturas durante la migración
    conn.execute("PRAGMA synchronous=NORMAL")

    print("Creando tabla movie_genre...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS movie_genre (
            tconst     TEXT NOT NULL,
            genre_name TEXT NOT NULL,
            PRIMARY KEY (tconst, genre_name)
        )
    """)

    print("Poblando movie_genre desde movies.genres...")
    rows = conn.execute("SELECT tconst, genres FROM movies WHERE genres IS NOT NULL").fetchall()
    batch = []
    for tconst, genres_str in rows:
        for genre in genres_str.split(","):
            g = genre.strip()
            if g:
                batch.append((tconst, g))

    conn.executemany("INSERT OR IGNORE INTO movie_genre (tconst, genre_name) VALUES (?, ?)", batch)
    print(f"  {len(batch):,} filas insertadas")

    print("Creando índices...")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mg_genre ON movie_genre (genre_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mg_tconst ON movie_genre (tconst)")

    conn.commit()
    conn.close()
    print("Migración completada.")


if __name__ == "__main__":
    migrate()

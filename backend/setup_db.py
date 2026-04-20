"""
setup_db.py — Pipeline IMDb → SQLite (one-time setup)

Descarga title.basics.tsv.gz y title.ratings.tsv.gz de IMDb,
los une y genera movies.db listo para el Vibe Matrix.

Uso:
    python setup_db.py
"""

import csv
import gzip
import os
import sqlite3
import urllib.request

# ── Config ────────────────────────────────────────────────────────────────────
HERE         = os.path.dirname(__file__)
DB_PATH      = os.path.join(HERE, "movies.db")
BASICS_GZ    = os.path.join(HERE, "title.basics.tsv.gz")
RATINGS_GZ   = os.path.join(HERE, "title.ratings.tsv.gz")
BASICS_URL   = "https://datasets.imdbws.com/title.basics.tsv.gz"
RATINGS_URL  = "https://datasets.imdbws.com/title.ratings.tsv.gz"
MIN_VOTES    = 1_000  # Filtro en importación — solo películas con audiencia real


# ── Helpers ───────────────────────────────────────────────────────────────────

def _progress(url: str, block_num: int, block_size: int, total_size: int) -> None:
    downloaded = block_num * block_size
    if total_size > 0:
        pct = min(downloaded / total_size * 100, 100)
        print(f"\r  {os.path.basename(url)}: {pct:.1f}%", end="", flush=True)


def download(url: str, dest: str) -> None:
    if os.path.exists(dest):
        print(f"  Cached: {os.path.basename(dest)}")
        return
    print(f"  Descargando {url} ...")
    urllib.request.urlretrieve(url, dest, reporthook=lambda b, bs, ts: _progress(url, b, bs, ts))
    print()


def load_ratings(path: str) -> dict[str, tuple[float, int]]:
    """tconst → (averageRating, numVotes). Solo incluye títulos con MIN_VOTES."""
    ratings: dict[str, tuple[float, int]] = {}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            try:
                votes = int(row["numVotes"])
                if votes >= MIN_VOTES:
                    ratings[row["tconst"]] = (float(row["averageRating"]), votes)
            except (ValueError, KeyError):
                pass
    print(f"  Ratings cargados: {len(ratings):,}")
    return ratings


def build_db(basics_path: str, ratings: dict, db_path: str) -> None:
    # ── Bayesian Weighted Rating ──────────────────────────────────────────────
    # WR = (V / (V + m)) × R  +  (m / (V + m)) × C
    #   V = votos de la película
    #   m = umbral de confianza (MIN_VOTES — mismo que el filtro de importación)
    #   R = rating de la película
    #   C = rating medio de todas las películas filtradas
    #
    # Efecto: una peli con 7.5★ y 200 votos → WR ≈ 6.86 (casi la media)
    #         una peli con 7.5★ y 50k votos → WR ≈ 7.48 (casi su rating real)
    # Cuantos más votos, más se puede confiar en la nota.
    all_ratings = [r for r, _ in ratings.values()]
    C = sum(all_ratings) / len(all_ratings)   # media real de la BD filtrada
    m = float(MIN_VOTES)                       # constante de confianza
    print(f"  Rating medio de la BD: {C:.3f}  |  Constante Bayesiana m={int(m)}")

    conn = sqlite3.connect(db_path)

    conn.executescript("""
        DROP TABLE IF EXISTS movies;
        CREATE TABLE movies (
            tconst        TEXT PRIMARY KEY,
            primaryTitle  TEXT NOT NULL,
            startYear     INTEGER NOT NULL,
            genres        TEXT    NOT NULL DEFAULT '',
            averageRating REAL    NOT NULL,
            numVotes      INTEGER NOT NULL,
            vibe_score    REAL    NOT NULL DEFAULT 0
        );
    """)

    batch: list[tuple] = []
    inserted = 0

    with gzip.open(basics_path, "rt", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row.get("titleType") != "movie":
                continue
            tconst = row["tconst"]
            if tconst not in ratings:
                continue

            raw_year   = row.get("startYear", r"\N")
            raw_genres = row.get("genres",    r"\N")

            if raw_year == r"\N":
                continue

            try:
                year = int(raw_year)
            except ValueError:
                continue

            genres = "" if raw_genres == r"\N" else raw_genres
            avg_rating, num_votes = ratings[tconst]

            V = float(num_votes)
            R = avg_rating
            vibe_score = round((V / (V + m)) * R + (m / (V + m)) * C, 4)

            batch.append((tconst, row["primaryTitle"], year, genres, avg_rating, num_votes, vibe_score))

            if len(batch) >= 10_000:
                conn.executemany("INSERT OR REPLACE INTO movies VALUES (?,?,?,?,?,?,?)", batch)
                inserted += len(batch)
                batch = []
                print(f"\r  Insertadas {inserted:,} películas…", end="", flush=True)

    if batch:
        conn.executemany("INSERT OR REPLACE INTO movies VALUES (?,?,?,?,?,?,?)", batch)
        inserted += len(batch)

    print("\n  Creando indices...")
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_year       ON movies(startYear);
        CREATE INDEX IF NOT EXISTS idx_rating     ON movies(averageRating);
        CREATE INDEX IF NOT EXISTS idx_votes      ON movies(numVotes);
        CREATE INDEX IF NOT EXISTS idx_vibe       ON movies(vibe_score);
        CREATE INDEX IF NOT EXISTS idx_year_votes ON movies(startYear, numVotes);
        CREATE INDEX IF NOT EXISTS idx_year_vibe  ON movies(startYear, vibe_score);
    """)

    conn.commit()
    conn.close()
    print(f"  OK: {inserted:,} peliculas guardadas en {db_path}")


# --- Main ---

if __name__ == "__main__":
    print("Paso 1/3: Descargar datasets IMDb")
    download(BASICS_URL,  BASICS_GZ)
    download(RATINGS_URL, RATINGS_GZ)

    print("Paso 2/3: Cargar ratings")
    ratings = load_ratings(RATINGS_GZ)

    print("Paso 3/3: Construir base de datos")
    build_db(BASICS_GZ, ratings, DB_PATH)

    print("\nBase de datos lista.")

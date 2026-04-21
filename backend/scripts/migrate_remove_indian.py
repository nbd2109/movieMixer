"""
migrate_remove_indian.py — Elimina producciones indias de movies.db.

Lógica: una película es india si en title.akas tiene alguna entrada con
  region=IN  AND  language IN {lenguas del subcontinente indio}

Esto distingue producciones indias (con entrada en hindi/tamil/telugu/…)
de blockbusters de Hollywood distribuidos en India (region=IN pero language=en/NULL).

Uso:
    python migrate_remove_indian.py
"""

import csv
import gzip
import os
import sqlite3

csv.field_size_limit(10_000_000)

SCRIPTS_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(SCRIPTS_DIR)
DB_PATH     = os.path.join(BACKEND_DIR, "movies.db")
AKAS_GZ     = os.path.join(BACKEND_DIR, "data", "title.akas.tsv.gz")

INDIAN_LANGUAGES = {
    "hi",   # Hindi
    "ta",   # Tamil
    "te",   # Telugu
    "ml",   # Malayalam
    "kn",   # Kannada
    "bn",   # Bengalí
    "mr",   # Marathi
    "pa",   # Punjabi
    "gu",   # Gujarati
    "or",   # Odia
    "ur",   # Urdu
    "as",   # Asamés
    "mai",  # Maithili
    "bho",  # Bhojpuri
}


def main():
    if not os.path.exists(DB_PATH):
        print("ERROR: movies.db no encontrada.")
        return
    if not os.path.exists(AKAS_GZ):
        print("ERROR: title.akas.tsv.gz no encontrado.")
        return

    conn = sqlite3.connect(DB_PATH)
    before = conn.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
    print(f"Películas antes: {before:,}")

    existing = set(r[0] for r in conn.execute("SELECT tconst FROM movies").fetchall())
    print(f"  tconsts en BD: {len(existing):,}")

    print("Leyendo title.akas.tsv.gz — region=IN AND language en lenguas indias ...")
    indian: set[str] = set()

    with gzip.open(AKAS_GZ, "rt", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            tconst = row.get("titleId", "")
            if (
                tconst in existing
                and row.get("region") == "IN"
                and row.get("language") in INDIAN_LANGUAGES
            ):
                indian.add(tconst)

    print(f"  Producciones indias encontradas: {len(indian):,}")

    indian_list = list(indian)
    for i in range(0, len(indian_list), 500):
        batch = indian_list[i:i + 500]
        conn.execute(
            f"DELETE FROM movies WHERE tconst IN ({','.join('?' * len(batch))})",
            batch,
        )

    conn.commit()
    after = conn.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
    conn.execute("VACUUM")
    conn.commit()
    conn.close()
    print(f"Películas después: {after:,}  (eliminadas: {before - after:,})")


if __name__ == "__main__":
    main()

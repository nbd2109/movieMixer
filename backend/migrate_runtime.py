"""
migrate_runtime.py — Añade columna runtimeMinutes a movies.db existente.
Lee title.basics.tsv.gz (ya descargado) y actualiza la BD sin re-importar todo.

Uso:
    python migrate_runtime.py
"""

import csv
import gzip
import os
import sqlite3

HERE       = os.path.dirname(__file__)
DB_PATH    = os.path.join(HERE, "movies.db")
BASICS_GZ  = os.path.join(HERE, "title.basics.tsv.gz")


def main():
    if not os.path.exists(DB_PATH):
        print("ERROR: movies.db no encontrada. Ejecuta setup_db.py primero.")
        return
    if not os.path.exists(BASICS_GZ):
        print("ERROR: title.basics.tsv.gz no encontrado.")
        return

    conn = sqlite3.connect(DB_PATH)

    # Añadir columna si no existe
    cols = [r[1] for r in conn.execute("PRAGMA table_info(movies)").fetchall()]
    if "runtimeMinutes" not in cols:
        print("Añadiendo columna runtimeMinutes...")
        conn.execute("ALTER TABLE movies ADD COLUMN runtimeMinutes INTEGER")
        conn.commit()
    else:
        print("Columna runtimeMinutes ya existe, actualizando valores...")

    # Leer runtimes del tsv.gz
    print("Leyendo title.basics.tsv.gz...")
    runtime_map: dict[str, int] = {}
    with gzip.open(BASICS_GZ, "rt", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row.get("titleType") != "movie":
                continue
            raw = row.get("runtimeMinutes", r"\N")
            if raw == r"\N":
                continue
            try:
                runtime_map[row["tconst"]] = int(raw)
            except ValueError:
                pass

    print(f"  Runtimes encontrados: {len(runtime_map):,}")

    # Actualizar en lotes
    batch = [(v, k) for k, v in runtime_map.items()]
    for i in range(0, len(batch), 10_000):
        conn.executemany(
            "UPDATE movies SET runtimeMinutes = ? WHERE tconst = ?",
            batch[i:i+10_000],
        )
        print(f"\r  Actualizadas {min(i+10_000, len(batch)):,} / {len(batch):,}", end="", flush=True)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_runtime ON movies(runtimeMinutes)")
    conn.commit()
    conn.close()
    print("\nMigración completada.")


if __name__ == "__main__":
    main()

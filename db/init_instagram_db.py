import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instagram.db"
SCHEMA_PATH = BASE_DIR / "schema_instagram.sql"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print("[DB] instagram.db initialized")

if __name__ == "__main__":
    init_db()

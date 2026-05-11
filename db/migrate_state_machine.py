import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "session.db"

DDL = """
CREATE TABLE IF NOT EXISTS ig_conversations (
    sender TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    last_message TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ig_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender TEXT NOT NULL,
    action_type TEXT NOT NULL,
    payload TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL,
    processed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_ig_actions_status_created
ON ig_actions(status, created_at);
"""

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(DDL)
    conn.commit()
    conn.close()
    print(f"[DB MIGRATE] OK -> {DB_PATH}")

if __name__ == "__main__":
    main()

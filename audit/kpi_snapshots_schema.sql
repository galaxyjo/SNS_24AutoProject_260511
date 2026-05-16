CREATE TABLE kpi_snapshots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_at TEXT    NOT NULL,
            period      TEXT    NOT NULL,
            kpi_json    TEXT    NOT NULL
        )

CREATE TABLE sqlite_sequence(name,seq)
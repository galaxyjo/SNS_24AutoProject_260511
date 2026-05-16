CREATE TABLE crawl_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            crawled_at    TEXT    NOT NULL,
            target_url    TEXT    NOT NULL DEFAULT '',
            total         INTEGER NOT NULL DEFAULT 0,
            with_image    INTEGER NOT NULL DEFAULT 0,
            without_image INTEGER NOT NULL DEFAULT 0,
            image_rate    REAL    NOT NULL DEFAULT 0.0
        )

CREATE TABLE sqlite_sequence(name,seq)
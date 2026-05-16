CREATE INDEX idx_rq_next   ON retry_tasks(next_retry)

CREATE INDEX idx_rq_status ON retry_tasks(status)

CREATE TABLE retry_tasks (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type    TEXT    NOT NULL,
            payload      TEXT    NOT NULL,
            attempts     INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            next_retry   TEXT    NOT NULL,
            status       TEXT    NOT NULL DEFAULT 'pending',
            last_error   TEXT,
            created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
        )

CREATE TABLE sqlite_sequence(name,seq)
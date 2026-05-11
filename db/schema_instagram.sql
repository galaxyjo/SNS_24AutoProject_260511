-- Instagram Webhook Events (Raw)
CREATE TABLE IF NOT EXISTS ig_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    user_id TEXT,
    content TEXT,
    external_id TEXT UNIQUE,
    raw_payload TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ig_events_user_id
ON ig_events(user_id);

CREATE INDEX IF NOT EXISTS idx_ig_events_event_type
ON ig_events(event_type);

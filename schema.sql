PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS equipment (
    equipment_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS equipment_thresholds (
    equipment_id TEXT PRIMARY KEY,
    max_temperature_c REAL NOT NULL
        CHECK (max_temperature_c > 0),
    max_vibration_mm_s REAL NOT NULL
        CHECK (max_vibration_mm_s > 0),

    FOREIGN KEY (equipment_id)
        REFERENCES equipment(equipment_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sensor_readings (
    reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id TEXT NOT NULL,
    measured_at TEXT NOT NULL,
    temperature_c REAL NOT NULL
        CHECK (temperature_c BETWEEN -100 AND 300),
    vibration_mm_s REAL NOT NULL
        CHECK (vibration_mm_s >= 0),
    rpm INTEGER NOT NULL
        CHECK (rpm >= 0),

    FOREIGN KEY (equipment_id)
        REFERENCES equipment(equipment_id),

    UNIQUE (equipment_id, measured_at)
);

CREATE INDEX IF NOT EXISTS idx_readings_equipment_time
ON sensor_readings (equipment_id, measured_at);

INSERT OR IGNORE INTO equipment_thresholds (
    equipment_id,
    max_temperature_c,
    max_vibration_mm_s
)
SELECT
    equipment_id,
    70.0,
    4.5
FROM equipment;

CREATE TABLE IF NOT EXISTS maintenance_tickets (
    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id TEXT NOT NULL,
    source_alert_timestamp TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'approved', 'closed', 'cancelled')),
    priority TEXT NOT NULL
        CHECK (priority IN ('medium', 'high')),
    title TEXT NOT NULL
        CHECK (LENGTH(TRIM(title)) > 0),
    description TEXT NOT NULL
        CHECK (LENGTH(TRIM(description)) > 0),
    evidence_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (equipment_id)
        REFERENCES equipment(equipment_id),

    UNIQUE (equipment_id, source_alert_timestamp)
);

CREATE INDEX IF NOT EXISTS idx_tickets_equipment_status
ON maintenance_tickets (equipment_id, status);

CREATE TABLE IF NOT EXISTS manual_documents (
    document_id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    page_count INTEGER NOT NULL
        CHECK (page_count > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (equipment_id)
        REFERENCES equipment(equipment_id),

    UNIQUE (equipment_id, sha256)
);

CREATE TABLE IF NOT EXISTS manual_chunks (
    chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    page_number INTEGER NOT NULL
        CHECK (page_number > 0),
    chunk_index INTEGER NOT NULL
        CHECK (chunk_index >= 0),
    content TEXT NOT NULL
        CHECK (LENGTH(TRIM(content)) > 0),
    embedding_json TEXT NOT NULL,

    FOREIGN KEY (document_id)
        REFERENCES manual_documents(document_id)
        ON DELETE CASCADE,

    UNIQUE (document_id, page_number, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_manual_documents_equipment
ON manual_documents (equipment_id);

CREATE INDEX IF NOT EXISTS idx_manual_chunks_document
ON manual_chunks (document_id, page_number, chunk_index);

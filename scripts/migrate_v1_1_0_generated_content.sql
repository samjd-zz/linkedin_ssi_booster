-- Migration: 1.1.0
-- Description: Add generated_content_records table for optional DB indexing
--              of FLUX art-avatar artifacts (local files remain canonical).
-- Applies to: PostgreSQL 16+
-- Safe to run multiple times (all statements are IF NOT EXISTS / ON CONFLICT DO NOTHING).

-- ============================================================================
-- TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS generated_content_records (
    id VARCHAR(255) PRIMARY KEY,                       -- request_id from flux_capacitor
    run_id VARCHAR(255) NOT NULL,
    candidate_id VARCHAR(255) REFERENCES candidate_records (candidate_id) ON DELETE SET NULL,

-- Content classification
source_mode VARCHAR(50) NOT NULL, -- schedule | curate | console
channel VARCHAR(50),
ssi_component VARCHAR(100),

-- Source linkage
source_url TEXT, source_title TEXT,

-- Local artifact paths (canonical store — these files are the source of truth)
story_path TEXT,
story_metadata_path TEXT,
image_path TEXT,
image_metadata_path TEXT,

-- Render outcome
render_status VARCHAR(50) NOT NULL, -- rendered | deferred | text_only | failed
save_status VARCHAR(50) NOT NULL DEFAULT 'saved', -- saved | failed | skipped

-- Style / prompt traceability
style_preset VARCHAR(100),
prompt_text TEXT,
evidence_ids JSONB DEFAULT '[]',

-- Timing telemetry
queue_wait_seconds FLOAT DEFAULT 0.0,
    render_duration_seconds FLOAT DEFAULT 0.0,

    generated_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_generated_content_run ON generated_content_records (run_id);

CREATE INDEX IF NOT EXISTS idx_generated_content_candidate ON generated_content_records (candidate_id);

CREATE INDEX IF NOT EXISTS idx_generated_content_mode ON generated_content_records (source_mode, channel);

CREATE INDEX IF NOT EXISTS idx_generated_content_status ON generated_content_records (render_status);

-- ============================================================================
-- SCHEMA VERSION BUMP
-- ============================================================================

INSERT INTO
    schema_migrations (version, description)
VALUES (
        '1.1.0',
        'Add generated_content_records table for FLUX art-avatar artifact indexing'
    )
ON CONFLICT (version) DO NOTHING;
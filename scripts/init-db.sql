-- LinkedIn SSI Booster Database Schema
-- Created: 2026-05-16
-- PostgreSQL 16+ with JSONB support

-- ============================================================================
-- PERSONA GRAPH & AVATAR STATE
-- ============================================================================

CREATE TABLE IF NOT EXISTS persona_graph (
    id SERIAL PRIMARY KEY,
    schema_version VARCHAR(10) NOT NULL,
    person JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS projects (
    id VARCHAR(255) PRIMARY KEY,
    persona_graph_id INTEGER REFERENCES persona_graph (id) ON DELETE CASCADE,
    name VARCHAR(500) NOT NULL,
    company_id VARCHAR(255) NOT NULL,
    years VARCHAR(50),
    details TEXT,
    skills JSONB DEFAULT '[]',
    aliases JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_projects_company ON projects (company_id);

CREATE TABLE IF NOT EXISTS companies (
    id VARCHAR(255) PRIMARY KEY,
    persona_graph_id INTEGER REFERENCES persona_graph (id) ON DELETE CASCADE,
    name VARCHAR(500) NOT NULL,
    aliases JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS skills (
    id VARCHAR(255) PRIMARY KEY,
    persona_graph_id INTEGER REFERENCES persona_graph (id) ON DELETE CASCADE,
    name VARCHAR(500) NOT NULL,
    aliases JSONB DEFAULT '[]',
    scope VARCHAR(50) DEFAULT 'domain',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS claims (
    id VARCHAR(255) PRIMARY KEY,
    persona_graph_id INTEGER REFERENCES persona_graph (id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    project_ids JSONB DEFAULT '[]',
    confidence_hint VARCHAR(50) DEFAULT 'medium',
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- DOMAIN KNOWLEDGE
-- ============================================================================

CREATE TABLE IF NOT EXISTS domains (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS domain_facts (
    id VARCHAR(255) PRIMARY KEY,
    domain_id VARCHAR(255) REFERENCES domains (id) ON DELETE CASCADE,
    statement TEXT NOT NULL,
    tags JSONB DEFAULT '[]',
    confidence VARCHAR(50) DEFAULT 'medium',
    scope VARCHAR(100) DEFAULT 'general',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_domain_facts_domain ON domain_facts (domain_id);

CREATE INDEX IF NOT EXISTS idx_domain_facts_tags ON domain_facts USING GIN (tags);

CREATE TABLE IF NOT EXISTS domain_relationships (
    id VARCHAR(255) PRIMARY KEY,
    from_fact_id VARCHAR(255) REFERENCES domain_facts (id) ON DELETE CASCADE,
    to_fact_id VARCHAR(255) REFERENCES domain_facts (id) ON DELETE CASCADE,
    relation_type VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_domain_rel_from ON domain_relationships (from_fact_id);

CREATE INDEX IF NOT EXISTS idx_domain_rel_to ON domain_relationships (to_fact_id);

-- ============================================================================
-- EXTRACTED KNOWLEDGE (NLP Pipeline)
-- ============================================================================

CREATE TABLE IF NOT EXISTS extracted_facts (
    id VARCHAR(255) PRIMARY KEY, -- SHA-256[:12] of source_url + statement
    statement TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_title TEXT,
    extracted_at TIMESTAMP NOT NULL,
    entities JSONB DEFAULT '[]',
    tags JSONB DEFAULT '[]',
    confidence VARCHAR(50) DEFAULT 'medium',
    extraction_method VARCHAR(100) DEFAULT 'spacy_nlp',
    primary_category VARCHAR(255),
    primary_ssi_component VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_extracted_facts_url ON extracted_facts (source_url);

CREATE INDEX IF NOT EXISTS idx_extracted_facts_extracted_at ON extracted_facts (extracted_at);

CREATE INDEX IF NOT EXISTS idx_extracted_facts_tags ON extracted_facts USING GIN (tags);

CREATE INDEX IF NOT EXISTS idx_extracted_facts_entities ON extracted_facts USING GIN (entities);

-- ============================================================================
-- NARRATIVE MEMORY
-- ============================================================================

CREATE TABLE IF NOT EXISTS narrative_memory (
    id SERIAL PRIMARY KEY,
    recent_themes JSONB DEFAULT '[]',
    recent_claims JSONB DEFAULT '[]',
    open_narrative_arcs JSONB DEFAULT '[]',
    last_updated TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- SELECTION LEARNING
-- ============================================================================

CREATE TABLE IF NOT EXISTS candidate_records (
    candidate_id VARCHAR(255) PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    article_url TEXT NOT NULL,
    article_title TEXT,
    article_source VARCHAR(255),
    ssi_component VARCHAR(100),
    channel VARCHAR(50),
    text_hash VARCHAR(64) NOT NULL,
    text_snippet TEXT,
    buffer_id VARCHAR(255),
    route VARCHAR(50),
    selected BOOLEAN,
    selected_at TIMESTAMP,
    run_id VARCHAR(255) NOT NULL,
    themes JSONB DEFAULT '[]',
    sentiment JSONB DEFAULT '{}',
    user_feedback JSONB DEFAULT '{}',
    primary_category VARCHAR(255),
    primary_ssi_component VARCHAR(255),
    category_confidence FLOAT DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_candidates_timestamp ON candidate_records (timestamp);

CREATE INDEX IF NOT EXISTS idx_candidates_article_url ON candidate_records (article_url);

CREATE INDEX IF NOT EXISTS idx_candidates_ssi ON candidate_records (ssi_component);

CREATE INDEX IF NOT EXISTS idx_candidates_channel ON candidate_records (channel);

CREATE INDEX IF NOT EXISTS idx_candidates_selected ON candidate_records (selected);

CREATE TABLE IF NOT EXISTS published_records (
    buffer_id VARCHAR(255) PRIMARY KEY,
    channel VARCHAR(50) NOT NULL,
    text_snippet TEXT,
    published_at TIMESTAMP NOT NULL,
    fetched_at TIMESTAMP NOT NULL,
    candidate_id VARCHAR(255) REFERENCES candidate_records (candidate_id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_published_published_at ON published_records (published_at);

-- ============================================================================
-- LEARNING LOGS
-- ============================================================================

CREATE TABLE IF NOT EXISTS moderation_events (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    channel VARCHAR(50) NOT NULL,
    reason_code VARCHAR(100) NOT NULL,
    decision VARCHAR(50) NOT NULL, -- 'kept' | 'removed'
    sentence_hash VARCHAR(64) NOT NULL,
    article_ref TEXT,
    project_refs JSONB DEFAULT '[]',
    run_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_moderation_timestamp ON moderation_events (timestamp);

CREATE INDEX IF NOT EXISTS idx_moderation_reason ON moderation_events (reason_code);

CREATE INDEX IF NOT EXISTS idx_moderation_decision ON moderation_events (decision);

CREATE TABLE IF NOT EXISTS confidence_decisions (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    channel VARCHAR(50) NOT NULL,
    route VARCHAR(50) NOT NULL,
    policy VARCHAR(100) NOT NULL,
    confidence_score FLOAT NOT NULL,
    confidence_level VARCHAR(50) NOT NULL,
    dominant_signal VARCHAR(100),
    reason TEXT,
    article_ref TEXT,
    run_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_confidence_timestamp ON confidence_decisions (timestamp);

CREATE INDEX IF NOT EXISTS idx_confidence_route ON confidence_decisions (route);

-- ============================================================================
-- TRUTH TRAJECTORIES (Derivative of Truth — Phase 2)
-- ============================================================================

CREATE TABLE IF NOT EXISTS truth_trajectories (
    id SERIAL PRIMARY KEY,
    claim_hash VARCHAR(64) UNIQUE NOT NULL,
    claim_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS truth_trajectory_points (
    id SERIAL PRIMARY KEY,
    trajectory_id INTEGER REFERENCES truth_trajectories (id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL,
    truth_gradient FLOAT NOT NULL CHECK (
        truth_gradient BETWEEN 0 AND 1
    ),
    uncertainty FLOAT NOT NULL CHECK (uncertainty BETWEEN 0 AND 1),
    evidence_count INTEGER NOT NULL,
    flagged BOOLEAN NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trajectory_points_trajectory ON truth_trajectory_points (trajectory_id, timestamp);

-- ============================================================================
-- GENERATED CONTENT RECORDS (local-first artifact index — DB second)
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

CREATE INDEX IF NOT EXISTS idx_generated_content_run ON generated_content_records (run_id);

CREATE INDEX IF NOT EXISTS idx_generated_content_candidate ON generated_content_records (candidate_id);

CREATE INDEX IF NOT EXISTS idx_generated_content_mode ON generated_content_records (source_mode, channel);

CREATE INDEX IF NOT EXISTS idx_generated_content_status ON generated_content_records (render_status);

-- ============================================================================
-- SCHEMA VERSION TRACKING
-- ============================================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(50) PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT NOW(),
    description TEXT
);

INSERT INTO
    schema_migrations (version, description)
VALUES (
        '1.0.0',
        'Initial schema - PostgreSQL migration from JSON/JSONL files'
    )
ON CONFLICT (version) DO NOTHING;
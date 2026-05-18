-- Migration: Add projects.url and claims.links columns
-- Version: 2026-05-18-001
-- Description: Adds optional url and links fields to support complete JSON-to-database mapping

-- Add url column to projects table
ALTER TABLE projects ADD COLUMN IF NOT EXISTS url VARCHAR(1000);

-- Add links column to claims table
ALTER TABLE claims
ADD COLUMN IF NOT EXISTS links JSONB DEFAULT '[]'::jsonb;

-- Add migration record
INSERT INTO
    schema_migrations (
        version,
        description,
        applied_at
    )
VALUES (
        '2026-05-18-001',
        'Add projects.url and claims.links columns for complete JSON mapping',
        NOW()
    )
ON CONFLICT (version) DO NOTHING;
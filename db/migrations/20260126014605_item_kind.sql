-- migrate:up
ALTER TABLE list_items ADD COLUMN kind INTEGER NOT NULL DEFAULT 1;
ALTER TABLE list_items ADD COLUMN metadata_id TEXT;

-- migrate:down
ALTER TABLE list_items DROP COLUMN kind;
ALTER TABLE list_items DROP COLUMN metadata_id;
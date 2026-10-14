-- migrate:up
ALTER TABLE list_items ADD COLUMN available INTEGER NOT NULL DEFAULT 0;

-- migrate:down
ALTER TABLE list_items DROP COLUMN available;
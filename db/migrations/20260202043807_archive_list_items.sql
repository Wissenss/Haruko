-- migrate:up
ALTER TABLE lists ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0;
ALTER TABLE lists ADD COLUMN archived_at TEXT DEFAULT NULL;
ALTER TABLE lists ADD COLUMN created_at TEXT DEFAULT NULL;
ALTER TABLE lists ADD COLUMN updated_at TEXT DEFAULT NULL;

UPDATE lists
SET
  created_at = datetime('now'),
  updated_at = datetime('now')
WHERE created_at IS NULL;

ALTER TABLE list_items ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0;
ALTER TABLE list_items ADD COLUMN archived_at TEXT DEFAULT NULL;
ALTER TABLE list_items ADD COLUMN created_at TEXT DEFAULT NULL;
ALTER TABLE list_items ADD COLUMN updated_at TEXT DEFAULT NULL;

UPDATE list_items
SET
  created_at = datetime('now'),
  updated_at = datetime('now')
WHERE created_at IS NULL;

-- migrate:down
ALTER TABLE lists DROP COLUMN is_archived;
ALTER TABLE lists DROP COLUMN archived_at;
ALTER TABLE lists DROP COLUMN created_at;
ALTER TABLE lists DROP COLUMN updated_at;
ALTER TABLE list_items DROP COLUMN is_archived;
ALTER TABLE list_items DROP COLUMN archived_at;
ALTER TABLE list_items DROP COLUMN created_at;
ALTER TABLE list_items DROP COLUMN updated_at;
-- migrate:up
CREATE TABLE list_item_votes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  list_item_id INTEGER,
  discord_user_id INTEGER,
  discord_guild_id INTEGER,
  web_fingerprint TEXT,
  created_at TEXT,
  vote_value INTEGER,
  FOREIGN KEY (list_item_id) REFERENCES list_items(id)
);

-- migrate:down
DROP TABLE IF EXISTS list_item_votes;
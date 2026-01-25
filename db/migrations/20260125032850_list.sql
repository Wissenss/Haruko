-- migrate:up
CREATE TABLE lists (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  discord_user_id INTEGER,
  discord_guild_id INTEGER,
  name TEXT,
  is_public INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE list_items(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  list_id INTEGER NOT NULL,
  content TEXT,
  score INTEGER,
  position INTEGER,
  FOREIGN KEY (list_id) REFERENCES lists(id)
);

-- migrate:down
DROP TABLE list_items;
DROP TABLE lists;

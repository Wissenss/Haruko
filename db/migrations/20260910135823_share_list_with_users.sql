-- migrate:up

CREATE TABLE list_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    list_id INTEGER NOT NULL,
    discord_user_id INTEGER,
    FOREIGN KEY (list_id) REFERENCES lists(id)
);

-- migrate:down

DROP TABLE IF EXISTS list_users;

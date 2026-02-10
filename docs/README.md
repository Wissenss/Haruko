# Haruko

The Server Humble Assistant.

current production invite link: https://discord.com/oauth2/authorize?client_id=1212204056613888011 

## Discord intents and permissions

The bot requires the following intents to be enabled in applications console:
- members_intent
- message_content_intent

And the following permissions:
- Use Slash Commands
- Send Messages
- Manage Messages
- Read Message History
- View Channels

## For devs

This proyect works with both linux and windows and is written in python 3.13 using the discord.py and sqlite3 libraries.

### Pre Requisites

- python 3.13 or above
- dbmate
- sqlite cli tools

### Setup

#### 0 - create an `.env` file in the root of the proyect like this 
```env
# database
DATABASE_PATH="./forg.sqlite3" 

# dbmate
DATABASE_URL="sqlite:forg.sqlite3"
DBMATE_MIGRATIONS_DIR="./db/migrations/"
DBMATE_SCHEMA_FILE="./db/schema.sql"
DBMATE_MIGRATIONS_TABLE="migrations"

# discord
DISCORD_TOKEN="YOUR DISCORD TOKEN HERE"
```

#### 1 - Create the database schema with dbmate
```cmd
dbmate up
```

#### 2 - Install the python modules
```cmd
pip install -r requirements.txt
```

#### 3 - Run it
```cmd
python forg.py
```

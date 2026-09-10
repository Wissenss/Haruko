import datetime
import sqlite3
from typing import List

import constants
import database

class TListItem:
  def __init__(self):
    self.id : int = 0
    self.list_id : int = 0
    self.content : str = ""
    self.score : int = 0
    self.position : int = 0
    self.kind :  constants.ListItemKind = constants.ListItemKind.NORMAL
    self.metadata_id : str = ""
    self.is_archived : bool = False
    self.archived_at : datetime.datetime = None
    self.created_at : datetime.datetime = None
    self.updated_at : datetime.datetime = None

  def map_from_record(self, record):
    self.id = record[0]
    self.list_id = record[1]
    self.content = record[2]
    self.score = record[3]
    self.position = record[4]
    self.kind = constants.ListItemKind.from_int(record[5])
    self.metadata_id = record[6]
    self.is_archived = record[7] != 0
    self.archived_at = database.parse_db_date(record[8])
    self.created_at = database.parse_db_date(record[9])
    self.updated_at = database.parse_db_date(record[10]) 

class TList:
  def __init__(self):
    self.id : int = 0
    self.discord_user_id : int = 0
    self.discord_guild_id : int = 0
    self.name : str = ""
    self.is_public : bool = False
    self.is_archived : bool = False
    self.created_at : datetime.datetime = None
    self.updated_at : datetime.datetime = None

  def map_from_record(self, record):
    self.id = record[0]
    self.discord_user_id = record[1]
    self.discord_guild_id = record[2]
    self.name = record[3]
    self.is_public = record[4] != 0
    self.is_archived = record[5] != 0
    self.archived_at = database.parse_db_date(record[6])
    self.created_at = database.parse_db_date(record[7])
    self.updated_at = database.parse_db_date(record[8]) 

class TUser:
  def __init__(self):
    self.id : int = 0

class ListRepo:
  def __init__(self):
    pass

  @classmethod
  def get_list_by_id(cls, connection : sqlite3.Connection, id : int) -> TList:
    cur = connection.cursor()

    sql = "SELECT * FROM lists WHERE id = ?;"

    cur.execute(sql, [id])

    record = cur.fetchone()

    if record == None:
      return None 
    
    list : TList = TList()

    list.map_from_record(record)

    return list
  
  @classmethod
  def get_list_item_by_id(cls, connection : sqlite3.Connection, id : int) -> TListItem:
    cur = connection.cursor()

    sql = "SELECT * FROM list_items WHERE id = ?;"
    
    cur.execute(sql, [id])

    record = cur.fetchone()

    if record == None:
      return None
    
    item : TListItem = TListItem()

    item.map_from_record(record)

    return item
  
  @classmethod
  def get_list_items_by_list_id(cls, connection : sqlite3.Connection, list_id : int, include_archived = True) -> List[TListItem]:
    cur = connection.cursor()

    conditions = ""

    if include_archived == False:
      conditions += "AND is_archived == 0"

    sql = f"SELECT * FROM list_items WHERE list_id = ? {conditions} ORDER BY score DESC, position ASC;"

    cur.execute(sql, [list_id])

    records = cur.fetchall()

    items = []

    for r in records:
      i = TListItem()

      i.map_from_record(r)

      items.append(i)

    return items
  
  @classmethod
  def get_public_lists(cls, connection : sqlite3.Connection) -> List[TList]:
    cur = connection.cursor()

    sql = "SELECT * FROM lists WHERE is_public <> 0;"

    cur.execute(sql)

    records = cur.fetchall()

    lists = []

    for r in records:
      l = TList()

      l.map_from_record(r)

      lists.append(l)

    return lists

  @classmethod
  def get_list_users(cls, connection : sqlite3.Connection, list_id : int) -> List[TUser]:
    cur = connection.cursor()

    sql = "SELECT * FROM list_users WHERE list_id = ?"

    cur.execute(sql, [list_id])

    records = cur.fetchall()

    user_list = []

    for r in records:
      user = TUser()

      user.id = r[2]

      user_list.append(user)

    return user_list

  @classmethod
  def append_list_item(cls, connection : sqlite3.Connection, list_id : int, item : TListItem) -> int:
    cur = connection.cursor()

    sql = "SELECT MAX(position) FROM list_items WHERE list_id = ? AND is_archived = 0;"
    
    cur.execute(sql, [list_id])

    row = cur.fetchone()

    if row[0] == None:
      next_position = 1
    else:
      next_position = row[0] + 1

    sql = "INSERT INTO list_items(list_id, content, score, position, kind, metadata_id, is_archived, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, 0, datetime('now'), datetime('now'))"

    cur.execute(sql, [list_id, item.content, item.score, next_position, item.kind.id, item.metadata_id])

    item_id = cur.lastrowid
    
    connection.commit()

    return item_id
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
  def get_list_items_by_list_id(cls, connection : sqlite3.Connection, list_id : int) -> List[TListItem]:
    cur = connection.cursor()

    sql = "SELECT * FROM list_items WHERE list_id = ? ORDER BY position;"

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
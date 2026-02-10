import io
import random

from typing import Literal, Optional
import discord
import discord.ext
import discord.ext.commands
import discord.file

import requests

import constants
import database
import environment
from domain import ListRepo, TList, TListItem

from cogs.customCog import CustomCog

class ListCog(CustomCog):
  def __init__(self, bot):
        super().__init__(bot)

  def __sanitize_list_name(self, list_name : str) -> str:
    return list_name.strip() 

  def __get_list_id_by_name(self, list_name : str, discord_guild_id : int, discord_user_id : int) -> int:
    con = database.ConnectionPool.get()
    cur = con.cursor()
    
    sql = "SELECT l.id FROM lists l LEFT JOIN list_guilds lg ON l.id = lg.list_id WHERE name = ? AND (l.discord_guild_id = ? OR lg.discord_guild_id = ?) AND (l.discord_user_id = ? OR l.is_public = TRUE);"

    cur.execute(sql, [list_name, discord_guild_id, discord_guild_id, discord_user_id])

    row = cur.fetchone() 

    database.ConnectionPool.release(con)

    if row == None:
      return None

    return row[0]

  def __sanitize_item_content(self, item_content : str):
    return item_content.strip()

  def __get_item_id_by_position(self, list_id : int, item_position : int) -> Optional[int]:
    con = database.ConnectionPool.get()
    cur = con.cursor()
    
    sql = "SELECT id FROM list_items WHERE list_id = ? AND position = ?;"

    cur.execute(sql, [list_id, item_position])

    row = cur.fetchone()

    database.ConnectionPool.release(con)
    
    if row == None:
      return None

    return row[0]

  def __order_list_by_position(self, list_id : int):
    con = database.ConnectionPool.get()
    cur = con.cursor()

    sql = "SELECT * FROM list_items WHERE list_id = ? AND is_archived = 0 ORDER BY position;"

    cur.execute(sql, [list_id])

    rows = cur.fetchall()

    i = 0

    for row in rows:
      i += 1

      item = TListItem()
      
      item.map_from_record(row)

      sql = "UPDATE list_items SET position = ?, updated_at = datetieme('now') WHERE id = ?;"

      cur.execute(sql, [i, item.id])
    
      con.commit()

    database.ConnectionPool.release(con)

  def __append_item_to_list(self, list_id, item : TListItem):
    con = database.ConnectionPool.get()
    cur = con.cursor()
    
    # calc next position
    sql = "SELECT MAX(position) FROM list_items WHERE list_id = ? AND is_archived = 0;"

    cur.execute(sql, [list_id])

    row = cur.fetchone()

    if row[0] == None:
      next_position = 1
    else:
      next_position = row[0] + 1

    # add item
    sql = "INSERT INTO list_items(list_id, content, score, position, kind, metadata_id, is_archived, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, 0, datetime('now'), datetime('now'))"

    cur.execute(sql, [list_id, item.content, item.score, next_position, item.kind.id, item.metadata_id])

    item_id = cur.lastrowid
    
    con.commit()

    database.ConnectionPool.release(con)

    return item_id

  async def __list_detail(self, interaction : discord.Interaction, list_name : str):
    em = discord.Embed(title="", description="")

    con = database.ConnectionPool.get()
    cur = con.cursor()

    list_name = self.__sanitize_list_name(list_name)

    list_id = self.__get_list_id_by_name(list_name, interaction.guild.id, interaction.user.id)

    if list_id == None:
      em.description = f"No known list \"{list_name}\""
      return await interaction.response.send_message(embed=em, ephemeral=True)

    # get list info
    sql = "SELECT * FROM lists WHERE id = ?;"

    cur.execute(sql, [list_id])

    list = TList()
    
    list.map_from_record(cur.fetchone()) 
    
    em.set_author(url=f"{environment.WEB_ADDR}/list/{list_id}", name=f"{list_name}")

    if list.discord_guild_id != interaction.guild.id:
      original_guild = await self.bot.fetch_guild(list.discord_guild_id)
      em.set_footer(text=f"shared from {original_guild.name}")

    # add items
    sql = "SELECT * FROM list_items WHERE list_id = ? AND is_archived = 0;"

    cur.execute(sql, [list_id])

    for row in cur.fetchall():
      item = TListItem()
      item.map_from_record(row)
      em.description += f"\n {str(item.position).rjust(4)} - {item.content}"

    return await interaction.response.send_message(embed=em, ephemeral=list.is_public==False)    

  async def __item_detail(self, interaction : discord.Interaction, list_name : str, item_position : int):
    em = discord.Embed(title="", description="")

    # find list id 
    list_id = self.__get_list_id_by_name(list_name, interaction.guild.id, interaction.user.id)

    if list_id == None:
      em.description = f"No known list \"{list_name}\""
      return await interaction.response.send_message(embed=em, ephemeral=True)

    # find item id
    item_id = self.__get_item_id_by_position(list_id, item_position)

    if item_id == None:
      em.description = f"No item with position {item_position} on list \"{list_name}\""
      return await interaction.response.send_message(embed=em, ephemeral=True)
    
    con = database.ConnectionPool.get()
    cur = con.cursor()

    # check if list is public
    sql = "SELECT is_public FROM lists WHERE id = ?"

    cur.execute(sql, [list_id])

    list_is_public = cur.fetchone()[0]

    # show 
    sql = "SELECT * FROM list_items WHERE id = ?;"

    cur.execute(sql, [item_id])

    item = TListItem()
    
    item.map_from_record(cur.fetchone())

    database.ConnectionPool.release(con)

    if item.kind == constants.ListItemKind.MOVIE:
      url = f"https://www.omdbapi.com/?i={item.metadata_id}&apikey={environment.OMDB_KEY}"

      response = requests.get(url)

      if response.status_code == 200:
        data = response.json()
        em.description += f"\n**{item.content}**"
      
        if data['Poster'] != "N/A":
          em.set_image(url=data['Poster'])
        elif data['Plot'] != "N/A":
          em.description += f"\n{data['Plot']}"

        footer_text = ""

        if data['Metascore'] != "N/A":
          footer_text+=f"Metascore: {data['Metascore']}/100"
        elif data['imdbRating'] != "N/A":
          footer_text+=f"IMDB Rating: {data['imdbRating']}/10"
        else:
          footer_text+=f"Unknown Score"

        if data['Runtime'] != "N/A":
          footer_text += f" - Runtime: {data['Runtime']}" 

        em.set_footer(text=footer_text)

      else:
        em.description += "movie matadata could not be obtained for the given resource"
    elif item.kind == constants.ListItemKind.BOOK:
      url = f"https://openlibrary.org/works/{item.metadata_id}.json"

      response = requests.get(url)

      if response.status_code != 200:
        em.description += "book metadata could not be obtained for the given resource"
        return await interaction.response.send_message(embed=em, ephemeral=True)
      
      data = response.json()

      em.title = data["title"]
      em.set_image(url=f"https://covers.openlibrary.org/b/id/{data["covers"][0]}-L.jpg")

    else:
      em.description += f"**{item.content}**"

    return await interaction.response.send_message(embed=em, ephemeral=list_is_public==False)

  @discord.app_commands.command(name="list_new")
  @discord.app_commands.guilds(constants.DEV_GUILD_ID, constants.KUVA_GUILD_ID, constants.THE_SERVER_GUILD_ID, constants.DEV2_GUILD_ID)
  async def list_new(self,  interaction : discord.Interaction, list_name : str):
    em = discord.Embed(title="", description="")
    
    con = database.ConnectionPool.get()
    cur = con.cursor()
    
    # sanitize list name to remove trailing / leadin spaces and invalid chars
    list_name = self.__sanitize_list_name(list_name)

    # check there is no other list already existing with the given name
    list_id = self.__get_list_id_by_name(list_name, interaction.guild.id, interaction.user.id)
    
    if list_id != None:
      database.ConnectionPool.release(con)
      em.description = f"there is already a list with name \"{list_name}\"."
      return await interaction.response.send_message(embed=em, ephemeral=True)
      
    # create new list
    sql = "INSERT INTO lists (discord_user_id, discord_guild_id, name, is_public, is_archived, archived_at, created_at, updated_at) VALUES(?,?,?, 0, 0, NULL, datetime('now'), datetime('now'));"

    cur.execute(sql, [interaction.user.id, interaction.guild.id, list_name])

    con.commit()

    database.ConnectionPool.release(con)

    em.description = f"list \"{list_name}\" has been created"
    return await interaction.response.send_message(embed=em, ephemeral=True)

  @discord.app_commands.command(name="list_delete")
  @discord.app_commands.guilds(constants.DEV_GUILD_ID, constants.KUVA_GUILD_ID, constants.THE_SERVER_GUILD_ID, constants.DEV2_GUILD_ID)
  async def list_delete(self,  interaction : discord.Interaction, list_name : str):
    em = discord.Embed(title="", description="")
    

    list_id = self.__get_list_id_by_name(list_name, interaction.guild.id, interaction.user.id)

    if list_id == None:
      em.description = f"No known list \"{list_name}\""
      return await interaction.response.send_message(embed=em, ephemeral=True)
    
    con = database.ConnectionPool.get()
    cur = con.cursor()
    
    # delete list
    sql = "DELETE FROM lists WHERE id = ?;"

    cur.execute(sql, [list_id])

    con.commit()

    database.ConnectionPool.release(con)

    em.description = f"list \"{list_name}\" has been deleted."
    return await interaction.response.send_message(embed=em, ephemeral=True)

  @discord.app_commands.command(name="list_index")
  @discord.app_commands.guilds(constants.DEV_GUILD_ID, constants.KUVA_GUILD_ID, constants.THE_SERVER_GUILD_ID, constants.DEV2_GUILD_ID, constants.KUVA_GUILD_ID)
  async def list_index(self, interaction : discord.Interaction):
    em = discord.Embed(title="", description="")

    em.description += f"lists of {interaction.user.display_name}:"

    con = database.ConnectionPool.get()
    cur = con.cursor()

    sql = "SELECT l.* FROM lists l LEFT JOIN list_guilds lg ON l.id = lg.list_id WHERE (l.discord_guild_id = ? OR lg.discord_guild_id = ?)  AND (l.discord_user_id = ? OR l.is_public = TRUE) AND is_archived = 0;"

    cur.execute(sql, [interaction.guild.id, interaction.guild.id, interaction.user.id])

    for row in cur.fetchall():
      list = TList()
      
      list.map_from_record(row)

      em.description += f"\n- {list.name}"
    
    return await interaction.response.send_message(embed=em, ephemeral=True)

  @discord.app_commands.command(name="list_is_public")
  @discord.app_commands.guilds(constants.DEV_GUILD_ID, constants.KUVA_GUILD_ID, constants.THE_SERVER_GUILD_ID, constants.DEV2_GUILD_ID, constants.KUVA_GUILD_ID)
  async def list_is_public(self, interaction : discord.Interaction, list_name : str, is_public : bool):
    em = discord.Embed(title="", description="")
    
    # find list id
    list_id = self.__get_list_id_by_name(list_name, interaction.guild.id, interaction.user.id)

    if list_id == None:
      em.description = f"No known list \"{list_name}\""
      return await interaction.response.send_message(embed=em, ephemeral=True)
    
    con = database.ConnectionPool.get()
    cur = con.cursor()

    # set is public
    sql = "UPDATE lists SET is_public = ? WHERE id = ?;"

    cur.execute(sql, [1 if is_public else 0, list_id])

    con.commit()

    database.ConnectionPool.release(con)

    return await self.__list_detail(interaction, list_name)

  @discord.app_commands.command(name="list_detail")
  @discord.app_commands.guilds(constants.DEV_GUILD_ID, constants.KUVA_GUILD_ID, constants.THE_SERVER_GUILD_ID, constants.DEV2_GUILD_ID, constants.KUVA_GUILD_ID)
  async def list_detail(self, interaction : discord.Interaction, list_name : str):
    return await self.__list_detail(interaction, list_name)

  @discord.app_commands.command(name="list_export")
  @discord.app_commands.guilds(constants.DEV_GUILD_ID, constants.KUVA_GUILD_ID, constants.THE_SERVER_GUILD_ID, constants.DEV2_GUILD_ID, constants.KUVA_GUILD_ID)
  async def list_export(self, interaction : discord.Interaction, list_name : str, format : Literal["csv"] = "csv"):
    em = discord.Embed(title="", description="")
    
    list_name = self.__sanitize_list_name(list_name)
    
    # serach list by name
    list_id = self.__get_list_id_by_name(list_name, interaction.guild.id, interaction.user.id)

    if list_id == None:
      em.description = f"No known list \"{list_name}\""
      return await interaction.response.send_message(embed=em, ephemeral=True)
    
    con = database.ConnectionPool.get()
    cur = con.cursor()

    # get list info
    sql = "SELECT * FROM lists WHERE id = ?;"

    cur.execute(sql, [list_id])

    list = TList()
    
    list.map_from_record(cur.fetchone())

    # get list items info
    sql = "SELECT * FROM list_items WHERE list_id = ? ORDER BY position;"

    cur.execute(sql, [list_id])

    rows = cur.fetchall()

    content = "\"position\",\"content\""
    
    if rows != None:
      for row in rows:
        item = TListItem()
        item.map_from_record(row)
        content += f"\n{item.position},\"{item.content}\""

    # create file
    file = discord.file.File(io.StringIO(content))
    
    file.filename = f"{list_name}.{format}"

    return await interaction.response.send_message(file=file, ephemeral=list.is_public==False)

  @discord.app_commands.command(name="list_item")
  @discord.app_commands.guilds(constants.DEV_GUILD_ID, constants.KUVA_GUILD_ID, constants.THE_SERVER_GUILD_ID, constants.DEV2_GUILD_ID, constants.KUVA_GUILD_ID)
  async def list_item(self, interaction : discord.Interaction, list_name : str, item_content : str):
    em = discord.Embed(title="", description="")

    # search list by name    
    list_name = self.__sanitize_list_name(list_name)

    list_id = self.__get_list_id_by_name(list_name, interaction.guild.id, interaction.user.id)

    if list_id == None:
      em.description = f"No known list \"{list_name}\""
      return await interaction.response.send_message(embed=em, ephemeral=True)

    item = TListItem()

    item.content = item_content
    item.score = 0
    item.kind = constants.ListItemKind.NORMAL
    item.metadata_id = ""

    self.__append_item_to_list(list_id, item)

    return await self.__list_detail(interaction, list_name)

  @discord.app_commands.command(name="list_item_content")
  @discord.app_commands.guilds(constants.DEV_GUILD_ID, constants.KUVA_GUILD_ID, constants.THE_SERVER_GUILD_ID, constants.DEV2_GUILD_ID)
  async def list_item_content(self, interaction : discord.Interaction, list_name : str, item_position : int, item_content : str):
    em = discord.Embed(title="", description="")

    item_content = self.__sanitize_item_content(item_content)

    if item_content == "":
      em.description = "content cannot be emtpy."
      return await interaction.response.send_message(embed=em, ephemeral=True)

    con = database.ConnectionPool.get()
    cur = con.cursor()
    
    # find list id 
    list_id = self.__get_list_id_by_name(list_name, interaction.guild.id, interaction.user.id)

    if list_id == None:
      database.ConnectionPool.release(con)
      em.description = f"No known list \"{list_name}\""
      return await interaction.response.send_message(embed=em, ephemeral=True)

    # find item id
    item_id = self.__get_item_id_by_position(list_id, item_position)

    if item_id == None:
      database.ConnectionPool.release(con)
      em.description = f"No item with position {item_position} on list \"{list_name}\""
      return await interaction.response.send_message(embed=em, ephemeral=True)
    
    # update content
    sql = "UPDATE list_items SET content = ?, updated_at = datetime('now') WHERE id = ?;"

    cur.execute(sql, [item_content, item_id])

    con.commit()

    database.ConnectionPool.release(con)

    return await self.__list_detail(interaction, list_name)

  @discord.app_commands.command(name="list_item_identity")
  @discord.app_commands.guilds(constants.DEV_GUILD_ID, constants.KUVA_GUILD_ID, constants.THE_SERVER_GUILD_ID, constants.DEV2_GUILD_ID)
  async def list_item_identity(self, interaction : discord.Interaction, list_name : str, item_position : int, item_kind : Literal[
    constants.ListItemKind.NORMAL.display, # type: ignore  
    constants.ListItemKind.MOVIE.display, # type: ignore
    #constants.ListItemKind.BOOK.display, # type: ignore
    #constants.ListItemKind.GAME.display, # type: ignore
    ], metadata_id : str):
    em = discord.Embed(title="", description="")
    
    # find list id 
    list_id = self.__get_list_id_by_name(list_name, interaction.guild.id, interaction.user.id)

    list_id = self.__get_list_id_by_name(list_name, interaction.guild.id, interaction.user.id)

    if list_id == None:
      em.description = f"No known list \"{list_name}\""
      return await interaction.response.send_message(embed=em, ephemeral=True)

    # find item id
    item_id = self.__get_item_id_by_position(list_id, item_position)

    if item_id == None:
      em.description = f"No item with position {item_position} on list \"{list_name}\""
      return await interaction.response.send_message(embed=em, ephemeral=True)

    con = database.ConnectionPool.get()
    cur = con.cursor()

    sql = "UPDATE list_items SET kind = ?, metadata_id = ?, updated_at = datetime('now') WHERE id = ?;"

    kind_id = constants.ListItemKind.from_str(item_kind)
    kind_id = kind_id.id

    print("kind_id: ", kind_id)
    print("metadata_id: ", metadata_id)
    print("item_id: ", item_id)

    cur.execute(sql, [kind_id, metadata_id, item_id])

    con.commit()

    database.ConnectionPool.release(con)

    return await self.__item_detail(interaction, list_name, item_position)

  @discord.app_commands.command(name="unlist_item")
  @discord.app_commands.guilds(constants.DEV_GUILD_ID, constants.KUVA_GUILD_ID, constants.THE_SERVER_GUILD_ID, constants.DEV2_GUILD_ID, constants.KUVA_GUILD_ID)
  async def unlist_item(self, interaction : discord.Interaction, list_name : str, item_position : int):
    em = discord.Embed(title="", description="")

    # find list id 
    list_id = self.__get_list_id_by_name(list_name, interaction.guild.id, interaction.user.id)

    if list_id == None:
      em.description = f"No known list \"{list_name}\""
      return await interaction.response.send_message(embed=em, ephemeral=True)

    # find item id
    item_id = self.__get_item_id_by_position(list_id, item_position)

    if item_id == None:
      em.description = f"No item with position {item_position} on list \"{list_name}\""
      return await interaction.response.send_message(embed=em, ephemeral=True)

    con = database.ConnectionPool.get()
    cur = con.cursor()

    # delete item
    sql = "DELETE FROM list_items WHERE id = ?;"

    cur.execute(sql, [item_id])

    con.commit()

    database.ConnectionPool.release(con)

    self.__order_list_by_position(list_id)

    return await self.__list_detail(interaction, list_name)

  @discord.app_commands.command(name="list_item_detail")
  @discord.app_commands.guilds(constants.DEV_GUILD_ID, constants.KUVA_GUILD_ID, constants.THE_SERVER_GUILD_ID, constants.DEV2_GUILD_ID, constants.KUVA_GUILD_ID)
  async def list_item_detail(self, interaction : discord.Interaction, list_name : str, item_position : int):
    return await self.__item_detail(interaction, list_name, item_position)

  @discord.app_commands.command(name="list_movie")
  @discord.app_commands.guilds(constants.DEV_GUILD_ID, constants.KUVA_GUILD_ID, constants.THE_SERVER_GUILD_ID, constants.DEV2_GUILD_ID, constants.KUVA_GUILD_ID)
  async def list_movie(self, interaction : discord.Interaction, list_name : str, imdb_id : str):
    em = discord.Embed(title="", description="")
    
    list_id = self.__get_list_id_by_name(list_name, interaction.guild.id, interaction.user.id)

    if list_id == None:
      em.description = f"No known list \"{list_name}\""
      return await interaction.response.send_message(embed=em, ephemeral=True)

    url = f"https://www.omdbapi.com/?i={imdb_id}&apikey={environment.OMDB_KEY}"

    response = requests.get(url)

    if response.status_code != 200:
      em.description += "movie metadata could not be obtained for the given resource"
      return await interaction.response.send_message(embed=em, ephemeral=True)
    
    data = response.json()

    item = TListItem()

    item.content = f"{data['Title']} ({data['Year']})"
    item.score = 0
    item.kind = constants.ListItemKind.MOVIE
    item.metadata_id = imdb_id

    self.__append_item_to_list(list_id, item)
    
    return await self.__list_detail(interaction, list_name)

  @discord.app_commands.command(name="list_random")
  @discord.app_commands.guilds(constants.DEV_GUILD_ID, constants.KUVA_GUILD_ID, constants.THE_SERVER_GUILD_ID, constants.DEV2_GUILD_ID, constants.KUVA_GUILD_ID)
  async def list_random(self, interaction : discord.Interaction, list_name : str):
    em = discord.Embed(title="", description="")
    
    list_id = self.__get_list_id_by_name(list_name, interaction.guild.id, interaction.user.id)

    if list_id == None:
      em.description = f"No known list \"{list_name}\""
      return await interaction.response.send_message(embed=em, ephemeral=True)

    con = database.ConnectionPool.get()
    cur = con.cursor()

    sql = "SELECT id, position FROM list_items WHERE list_id = ?;"

    cur.execute(sql, [list_id])

    items = cur.fetchall()

    if items == None:
      database.ConnectionPool.release(con)
      em.description = f"List \"{list_name}\" has no items"
      return await interaction.response.send_message(embed=em)

    item_id, item_position = random.choice(items)

    database.ConnectionPool.release(con)

    return await self.__item_detail(interaction, list_name, item_position)
  
  @discord.app_commands.command(name="list_book")
  @discord.app_commands.guilds(constants.DEV_GUILD_ID, constants.KUVA_GUILD_ID, constants.THE_SERVER_GUILD_ID, constants.DEV2_GUILD_ID, constants.KUVA_GUILD_ID)
  async def list_book(self, interaction : discord.Interaction, list_name : str, book_id : str):
    em = discord.Embed(title="", description="")
    
    list_id = self.__get_list_id_by_name(list_name, interaction.guild.id, interaction.user.id)

    if list_id == None:
      em.description = f"No known list \"{list_name}\""
      return await interaction.response.send_message(embed=em, ephemeral=True)
    
    url = f"https://openlibrary.org/works/{book_id}.json"
    
    response = requests.get(url)

    if response.status_code != 200:
      em.description += "book metadata could not be obtained for the given resource"
      return await interaction.response.send_message(embed=em, ephemeral=True)
    
    data = response.json()

    item = TListItem()

    item.content = f"{data["title"]}"
    item.score = 0
    item.kind = constants.ListItemKind.BOOK
    item.metadata_id = book_id

    self.__append_item_to_list(list_id, item)
    
    return await self.__list_detail(interaction, list_name)

  @discord.app_commands.command(name="list_item_archive")
  @discord.app_commands.guilds(constants.DEV_GUILD_ID, constants.KUVA_GUILD_ID, constants.THE_SERVER_GUILD_ID, constants.DEV2_GUILD_ID, constants.KUVA_GUILD_ID)
  async def list_item_archive(self, interaction : discord.Interaction, list_name : str, item_position : int):
    em = discord.Embed(title="", description="")

    # find list id 
    list_id = self.__get_list_id_by_name(list_name, interaction.guild.id, interaction.user.id)

    if list_id == None:
      em.description = f"No known list \"{list_name}\""
      return await interaction.response.send_message(embed=em, ephemeral=True)

    # find item id
    item_id = self.__get_item_id_by_position(list_id, item_position)

    if item_id == None:
      em.description = f"No item with position {item_position} on list \"{list_name}\""
      return await interaction.response.send_message(embed=em, ephemeral=True)
    
    # archive
    con = database.create_connection()
    cur = con.cursor()

    sql = "UPDATE list_items SET is_archived = 1, archived_at = datetime('now'), updated_at = datetime('now') position = 0 WHERE id = ?;"

    cur.execute(sql, [item_id])

    con.commit()
    con.close()

    # reorder items
    self.__order_list_by_position(list_id)

    return await self.__list_detail(interaction, list_name)
  
  @discord.app_commands.command(name="list_server_share")
  @discord.app_commands.guilds(constants.DEV_GUILD_ID, constants.KUVA_GUILD_ID, constants.THE_SERVER_GUILD_ID, constants.DEV2_GUILD_ID)
  async def list_item_share(self, interaction : discord.Interaction, list_name : str, shared_discord_guild_id : str):
    em = discord.Embed(title="", description="")

    # find list id 
    list_id = self.__get_list_id_by_name(list_name, interaction.guild.id, interaction.user.id)

    if list_id == None:
      em.description = f"No known list \"{list_name}\""
      return await interaction.response.send_message(embed=em, ephemeral=True)

    # check if the guild id is valid 
    guild = await self.bot.fetch_guild(shared_discord_guild_id)

    if guild == None:
      em.description = f"No known guild with id \"{shared_discord_guild_id}\""
      return await interaction.response.send_message(embed=em, ephemeral=True)

    # check haruko is a member of the server
    if shared_discord_guild_id in self.bot.guilds:
      em.description = f"Haruko is not a member of \"{guild.name}\""
      return await interaction.response.send_message(embed=em, ephemeral=True)

    # check the user is a member of it
    print("guild members: ", [m.id for m in guild.members])
    if interaction.user.id in [m.id for m in guild.members]:
      em.description = f"You are not a member of \"{guild.name}\""
      return await interaction.response.send_message(embed=em, ephemeral=True)

    # if the list is not shared with this server already, share it, otherwhise unshare it
    con = database.ConnectionPool.get()
    cur = con.cursor()

    sql = "SELECT * FROM list_guilds WHERE list_id = ?;"

    cur.execute(sql, [list_id])

    row = cur.fetchone()

    if row == None: 
      em.description = f"{list_name} is now shared with server {guild.name}"

      # check the name is available
      if self.__get_list_id_by_name(list_name, shared_discord_guild_id, interaction.user.id) != None:
        database.ConnectionPool.release(con)
        em.description = f"The name \"{list_name}\" is not available"
        return await interaction.response.send_message(embed=em, ephemeral=True)
      
      sql = "INSERT INTO list_guilds(list_id, discord_user_id, discord_guild_id) VALUES(?, ?, ?);"
      cur.execute(sql, [list_id, interaction.user.id, shared_discord_guild_id])
    
    else:
      em.description = f"{list_name} is no longer shared with server {guild.name}"
      sql = "DELETE FROM list_guilds WHERE list_id=? AND discord_guild_id=?;"
      cur.execute(sql, [list_id, shared_discord_guild_id])

    con.commit()

    database.ConnectionPool.release(con)

    return await interaction.response.send_message(embed=em, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ListCog(bot))
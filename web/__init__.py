from typing import List
import random
from flask import Flask
from flask import g
from flask import render_template
from flask import url_for
from flask import redirect

from werkzeug.middleware.proxy_fix import ProxyFix

import database
import domain
import constants
import environment

import requests_cache

requests_cache.install_cache('requests_cache', expire_after=300)

import requests

app = Flask(__name__)

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1) # In production we pass requests through ngix as a reverse proxy. And a lot of things break... This fixes them!

def get_db():
    if "db" not in g:
      g.db = database.create_connection()

    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

app.teardown_appcontext(close_db)

@app.route("/")
def index():
  return render_template("index.html")

@app.route("/list")
def list_index():
  con = get_db()

  lists : List[domain.TList] = domain.ListRepo.get_public_lists(con)

  return render_template("list_index.html", lists=lists)

@app.route("/list/<int:id>")
def list_detail(id : int):
  con = get_db()
  
  list : domain.TList = domain.ListRepo.get_list_by_id(con, id)

  if list == None:
    return "<p>404: not found</p>"

  if list.is_public == False:
    return "<p>403: forbidden</p>"

  list_items : List[domain.TListItem] = domain.ListRepo.get_list_items_by_list_id(con, list.id)

  return render_template("list_detail.html", list=list, list_items=list_items)

@app.route("/list/<int:list_id>/item/<int:id>")
def list_item_detail(list_id : int, id : int):
  con = get_db()
  
  list : domain.TList = domain.ListRepo.get_list_by_id(con, list_id)

  if list == None:
    return "<p>404: not found</p>"

  if list.is_public == False:
    return "<p>403: forbidden</p>"

  list_item : domain.TListItem = domain.ListRepo.get_list_item_by_id(con, id)

  if list_item == None:
    return "<p>404: not found</p>"
  
  # query metadata (if available)

  metadata = {}

  if list_item.kind == constants.ListItemKind.MOVIE:
    url = f"https://www.omdbapi.com/?i={list_item.metadata_id}&apikey={environment.OMDB_KEY}"

    response = requests.get(url)

    if response.status_code != 200:
      return "<p>502: gateway timeout</p>"

    metadata = response.json()

  return render_template("list_item_detail.html", list=list, list_item=list_item, metadata=metadata)

@app.route("/list/<int:list_id>/item/random")
def list_item_random(list_id : int):
  con = get_db()

  list : domain.TListItem = domain.ListRepo.get_list_by_id(con, list_id)

  if list == None:
    return "<p>404: not found</p>"

  list_items : List[domain.TListItem] = domain.ListRepo.get_list_items_by_list_id(con, list_id, include_archived=False)

  item : domain.TListItem = random.choice(list_items)

  return redirect(url_for('list_item_detail', list_id=list.id, id=item.id))
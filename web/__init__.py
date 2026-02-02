from typing import List
from flask import Flask
from flask import g
from flask import render_template

from werkzeug.middleware.proxy_fix import ProxyFix

import database
import domain
import constants

app = Flask(__name__)

# x_prefix=1 le indica a Flask que confíe en el encabezado X-Forwarded-Prefix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

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
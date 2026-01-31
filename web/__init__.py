from flask import Flask
from flask import g
from flask import render_template

import database

app = Flask(__name__)

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
def hello_world():
  return "<p>hello world!</p>"

@app.route("/list/<int:id>")
def list_detail(id : int):
  con = get_db()
  cur = con.cursor()

  list_title : str = ""
  list_items : list = []

  sql = "SELECT * FROM lists WHERE id = ?;"

  cur.execute(sql, [id])

  row = cur.fetchone()

  if row == None:
    return "<p>404: not found</p>"

  list_title = row[3]

  if row[4] == 0:
    return "<p>403: forbidden</p>"

  sql = "SELECT * FROM list_items WHERE list_id = ? ORDER BY position ASC;"

  cur.execute(sql, [id])

  items_rows = cur.fetchall()

  if items_rows != None:
    for item_row in items_rows:
      list_items.append(item_row[2])

  return render_template("list_detail.html", title=list_title, items=list_items)
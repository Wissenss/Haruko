from typing import List
import io
import random
import re
from flask import Flask, g, render_template, url_for, redirect, request, send_file

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

TMDB_HEADERS = {
    "accept": "application/json",
    "Authorization": f"Bearer {environment.TMDB_KEY}"
}

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

@app.route("/list/<int:list_id>/export")
def list_detail_export(list_id : int):
  con = get_db()

  list : domain.TList = domain.ListRepo.get_list_by_id(con, list_id)

  if list == None:
    return "<p>404: not found</p>"

  if list.is_public == False:
    return "<p>403: forbidden</p>"
  
  list_items : List[domain.TListItem] = domain.ListRepo.get_list_items_by_list_id(con, list.id)

  contents = "index,content,score,created_at,updated_at,is_archived,archived_at"

  for i in list_items:
    contents += f"\n{i.position},\"{i.content}\",{i.score},{i.created_at},{i.updated_at},{i.is_archived},{i.archived_at}"

  file = io.BytesIO(contents.encode("utf-8"))
  file.seek(0)

  return send_file(file, mimetype="text/csv", download_name=f"{list.name}.csv")

@app.route("/api/list/<int:id>")
def api_list_detail():
  pass

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

@app.route("/games/guess-the-movie-plot")
def games_movie_plot():
  
  right_score = int(request.args.get('rs', 0))
  wrong_score = int(request.args.get('ws', 0))
  answer_movie_id = int(request.args.get('ami', 0))

  # get a random movie (if none provided)
  if answer_movie_id == 0:
    response = requests.get(f"https://api.themoviedb.org/3/discover/movie?include_adult=false&include_video=false&language=en-US&page={random.randint(1, 100)}&sort_by=popularity.desc", headers=TMDB_HEADERS)
    
    if response.status_code != 200:
      return "<p>502: gateway timeout</p>"

    data = response.json()

    answer_movie_details = random.choice(data["results"])
  
  else:
    response = requests.get(f"https://api.themoviedb.org/3/movie/{answer_movie_id}", headers=TMDB_HEADERS)

    if response.status_code != 200:
      return "<p>502: gateway timeout</p>"
    
    answer_movie_details = response.json()

  answer_movie_id = answer_movie_details["id"]

  # get other three movies that share similarities 

  response = requests.get(f"https://api.themoviedb.org/3/movie/{answer_movie_details["id"]}/similar", headers=TMDB_HEADERS)
  
  if response.status_code != 200:
    return "<p>502: gateway timeout</p>"

  data = response.json()
  
  results = data["results"]

  choices_movie_details = []

  for c in random.choices(results, k=min(len(results), 10)):
    # cannot have the same id as the answer
    if c["id"] == answer_movie_details["id"]:
      continue

    # cannot have the same title as the answer
    if c["original_title"] == answer_movie_details["original_title"]:
      continue

    # cannot repeat choices
    if c["id"] in [ec["id"] for ec in choices_movie_details]:
      continue

    # image link must be valid - takes a long time... we need a better solution
    # img_path = f"https://image.tmdb.org/t/p/w200/{c['poster_path']}"
    # response = requests.head(img_path, timeout=5)
    # if response.status_code != 200:
    #   continue 
    # if not response.headers["content-type"] in ["image/png", "image/jpeg", "image/jpg"]:
    #   continue

    choices_movie_details.append(c)

    if len(choices_movie_details) == 3:
      break

  choices_movie_details.append(answer_movie_details)

  # if no matches where found, then try again ...
  if len(choices_movie_details) < 2:
    return redirect(url_for("games_movie_plot", rs=right_score, ws=wrong_score))

  random.shuffle(choices_movie_details)

  # censor words from the answer movie title that may appear on the plot text
  overview : str = answer_movie_details["overview"] 

  for tabu_word in answer_movie_details["original_title"].split():
    print("\ntabu_word: ", tabu_word)
    overview = re.sub(tabu_word, "#" * random.randint(4, 10), overview, flags=re.IGNORECASE)
    overview = re.sub("# #", "##", overview, flags=re.IGNORECASE)

  answer_movie_details["overview"] = overview 

  return render_template("guess_the_movie_plot.html", answer_md=answer_movie_details, choices_md=choices_movie_details, right_score=right_score, wrong_score=wrong_score)
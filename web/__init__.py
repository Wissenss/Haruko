from typing import List
import io
import os
import random
import re
from urllib.parse import urljoin, urlencode
from flask import Flask, g, render_template, url_for, redirect, request, send_file, jsonify
from flask_discord import DiscordOAuth2Session, requires_authorization, Unauthorized

from werkzeug.middleware.proxy_fix import ProxyFix

import database
import domain
import constants
import environment

import requests_cache

requests_cache.install_cache('requests_cache', expire_after=300)

import requests

app = Flask(__name__)

app.secret_key = os.urandom(24) 

app.config["DISCORD_CLIENT_ID"] = environment.DISCORD_OAUTH2_CLIENT_ID
app.config["DISCORD_CLIENT_SECRET"] = environment.DISCORD_OAUTH2_CLIENT_SECRET
app.config["DISCORD_REDIRECT_URI"] = environment.DISCORD_OAUTH2_REDIRECT_URI
app.config["DISCORD_REDIRECT_URI_SCOPE"] = ["identify"]

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "true" 

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1) # In production we pass requests through ngix as a reverse proxy. And a lot of things break... This fixes them!

discord = DiscordOAuth2Session(app)

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
  user = None

  if discord.authorized:
    user = discord.fetch_user()
  
  return render_template("index.html", user=user)

@app.route("/list")
def list_index():
  con = get_db()

  lists : List[domain.TList] = domain.ListRepo.get_public_lists(con)

  user = None
  
  if discord.authorized:
    user = discord.fetch_user()
  
  return render_template("list_index.html", lists=lists, user=user)

@app.route("/list/<int:id>")
def list_detail(id : int):
  con = get_db()
  
  list : domain.TList = domain.ListRepo.get_list_by_id(con, id)

  if list == None:
    return "<p>404: not found</p>"

  if list.is_public == False:
    return "<p>403: forbidden</p>"

  list_items : List[domain.TListItem] = domain.ListRepo.get_list_items_by_list_id(con, list.id)

  user = None

  if discord.authorized:
    user = discord.fetch_user()

  return render_template("list_detail.html", list=list, list_items=list_items, user=user)

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
  con = get_db()

  list : domain.TList = domain.ListRepo.get_list_by_id(con, id)

  if list == None:
    return {"error": "not found"}, 404

  if list.is_public == False:
    return {"error": "forbidden"}, 403

  list_items : List[domain.TListItem] = domain.ListRepo.get_list_items_by_list_id(con, list.id)

  return jsonify(list_items)

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

    print(f"url: {url}")

    response = requests.get(url)

    if response.status_code != 200: # not all errors other then 200 will be 502...
      return "<p>502: gateway timeout</p>"

    metadata = response.json()

    # gotta find the id from the stored imdb id

    response = requests.get(f"https://api.themoviedb.org/3/find/{list_item.metadata_id}?external_source=imdb_id&language=en-US", headers=TMDB_HEADERS)

    if response.status_code != 200:
      return f"<p>gateway error {response.status_code}</p>"
    
    # print(f"response id find: {response.json()}")

    tmdb_id = response.json()["movie_results"][0]["id"]

    # once we got it, we can query for the trailer video 

    response = requests.get(f"https://api.themoviedb.org/3/movie/{tmdb_id}/videos", headers=TMDB_HEADERS)

    if response.status_code != 200:
      return f"<p>gateway error {response.status_code}</p>"

    response = response.json()
    
    # print(f"response trailer find: {response}")

    for r in response["results"]:
      if "trailer" in str(r["type"]).lower() and "youtube" in str(r["site"].lower()):
        metadata["trailer_link"] = f"https://youtube.com/embed/{r['key']}?autoplay=1&mute=1"
        break

  print(f"\n\n metadata: {metadata}")

  user = None
  
  if discord.authorized:
    user = discord.fetch_user()

  return render_template("list_item_detail.html", list=list, list_item=list_item, metadata=metadata, user=user)

@app.route("/list/<int:list_id>/item/random")
def list_item_random(list_id : int):
  con = get_db()

  list : domain.TListItem = domain.ListRepo.get_list_by_id(con, list_id)

  if list == None:
    return "<p>404: not found</p>"

  list_items : List[domain.TListItem] = domain.ListRepo.get_list_items_by_list_id(con, list_id, include_archived=False)

  item : domain.TListItem = random.choice(list_items)

  return redirect(url_for('list_item_detail', list_id=list.id, id=item.id))

@app.route("/list/<int:list_id>/item/add")
def list_item_add_movie(list_id : int):
  user = None
  
  if discord.authorized:
    user = discord.fetch_user()
  
  return render_template("list_item_add_movie.html", list_id=list_id, user=user)

@app.route("/api/search/movie", methods=['POST'])
@requires_authorization
def api_search_movie():
  print("search_movie endpoint reached")

  data = request.get_json()

  if not data:
    return jsonify({"error": "Missing request body"}), 400

  query = data.get('query', '')

  url = urljoin("https://api.themoviedb.org", "3/search/movie")

  params = {
    "query": query,
    "include_adult": "true",
    "language": "en-US",
    "page": 1
  }

  url = f"{url}?{urlencode(params)}"

  response = requests.get(url, headers=TMDB_HEADERS)

  return jsonify(response.json()), 200

@app.route("/api/list/item/add", methods=['POST'])
@requires_authorization
def api_list_item_add_movie():
  data = request.get_json()

  list_id = data.get("list_id", 0)
  movie_tmdb_id = data.get("movie_tmdb_id", 0) 

  con = get_db()

  # check list exists

  list_info : domain.TList = domain.ListRepo.get_list_by_id(con, list_id)

  if list_info == None:
    return f"list \"{list_info.name}\" not found", 404

  # check list is allowed for the user

  allowed_user_list : List[domain.TUser] = domain.ListRepo.get_list_users(con, list_id)

  user = discord.fetch_user()

  is_allowed = False

  for au in allowed_user_list:
    if au.id == user.id:
      is_allowed = True
      break

  if is_allowed == False:
    return "Unauthorized", 401

  # add the new item to the list...

  #   go gotta translate the tmdb id to imdb id because that what we store in the db... TODO: refactor to allow for multiple sources of movie metadata

  response = requests.get(f"https://api.themoviedb.org/3/movie/{movie_tmdb_id}/external_ids", headers=TMDB_HEADERS)
  
  if response.status_code != 200:
    return f"gateway error {response.status_code}", 502

  data = response.json()
  print("response: ", data)

  movie_imdb_id = data["imdb_id"]

  #   query the metadata from imdb

  response = requests.get(f"https://www.omdbapi.com/?i={movie_imdb_id}&apikey={environment.OMDB_KEY}")

  if response.status_code != 200:
    return "gateway error, movie metadata could not be obtained for the given resource", 502
  
  response = response.json()

  item = domain.TListItem()

  item.content = f"{response['Title']} ({response['Year']})"
  item.score = 0
  item.kind = constants.ListItemKind.MOVIE
  item.metadata_id = movie_imdb_id
  
  item_id = domain.ListRepo.append_list_item(con, list_id, item)

  return jsonify({item_id: item_id, list_id: list_id}), 200

@app.route("/games/guess-the-movie-plot")
def games_movie_plot():

  user = None

  if discord.authorized:
    user = discord.fetch_user()
  
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
  answer_movie_details["overview_to_read"] = overview.replace('  ', '').replace('##', '').replace('  ', '').replace("##", "").replace('#', ' ... blank! ...').replace('<', '').replace('>', '').replace('&', '').replace("'", '').replace('"', '').replace('`', '')

  return render_template("guess_the_movie_plot.html", answer_md=answer_movie_details, choices_md=choices_movie_details, right_score=right_score, wrong_score=wrong_score, user=user)

@app.route("/contibutors")
def contibutors_list():
  user = None
  
  if discord.authorized:
    user = discord.fetch_user()

  return render_template("contributors.html", user=user)

@app.route("/discord/login")
def login():
    return discord.create_session(scope=["identify"]) 

@app.route("/discord/login/callback")
def callback():
    discord.callback()
    return redirect(url_for("index"))

@app.endpoint(Unauthorized)
def redirect_unauthorized():
    return redirect(url_for("login"))

@app.route("/discord/login/credentials")
def credentials():
    user = discord.fetch_user()
    return user.to_json()

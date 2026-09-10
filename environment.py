import dotenv

environment_vars = dotenv.dotenv_values(".env")

def get_environment_var(name, default = ""):
    if name in environment_vars.keys():
        return environment_vars[name]
    
    return default

DATABASE_PATH = get_environment_var("DATABASE_PATH")
DISCORD_TOKEN = get_environment_var("DISCORD_TOKEN")
DISCORD_OAUTH2_CLIENT_ID = get_environment_var("DISCORD_OAUTH2_CLIENT_ID")
DISCORD_OAUTH2_CLIENT_SECRET = get_environment_var("DISCORD_OAUTH2_CLIENT_SECRET")
DISCORD_OAUTH2_REDIRECT_URI = get_environment_var("DISCORD_OAUTH2_REDIRECT_URI")
DISCORD_OAUTH2_INSECURE_TRANSPORT = get_environment_var("DISCORD_OAUTH2_INSECURE_TRANSPORT")    

OMDB_KEY = get_environment_var("OMDB_KEY")
TMDB_KEY = get_environment_var("TMDB_KEY")
WEB_ADDR = get_environment_var("WEB_ADDR", "http://localhost:5000")

TAKKUN_ADDR = get_environment_var("TAKKUN_ADDR", "http://localhost:5001")
TAKKUN_KEY = get_environment_var("TAKKUN_KEY", "")

if __name__ == "__main__":
    print(environment_vars)
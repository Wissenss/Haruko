import dotenv

environment_vars = dotenv.dotenv_values(".env")

def get_environment_var(name, default = ""):
    if name in environment_vars.keys():
        return environment_vars[name]
    
    return default

DATABASE_PATH = get_environment_var("DATABASE_PATH")
DISCORD_TOKEN = get_environment_var("DISCORD_TOKEN")
OMDB_KEY = get_environment_var("OMDB_KEY")
WEB_ADDR = get_environment_var("WEB_ADDR", "http://localhost:5000")

if __name__ == "__main__":
    print(environment_vars)
import requests
import environment

def get_available_items():
    url = f"http://localhost:8096/items?apikey={environment.JELLY_APIKEY}&recursive=true&fields=ProviderIds"

    response = requests.get(url)

    response_json = response.json()

    items = []

    for rj in response_json["Items"]:
        if "ProviderIds" in rj.keys():
            if "Imdb" in rj["ProviderIds"].keys():
                items.append(rj["ProviderIds"]["Imdb"])

    return items

def update_available_items(available_imdb_ids):
    if len(available_imdb_ids) == 0:
        return
    
    url = f"{environment.WEB_ADDR}/api/items/available?apikey={environment.WEB_APIKEY}"
    
    headers = {"Content-Type": "application/json"}

    data = {
        "items_available": available_imdb_ids
    }

    response = requests.post(url, json=data, headers=headers)

    return response.json()


if __name__ == "__main__":
    
    print(f"Fetching available items...")

    available_imdb_ids = get_available_items()

    print(f"Available items: {len(available_imdb_ids)}")
    print(f"Available items: {available_imdb_ids}")
    
    #available_imdb_ids = ["tt4154756", "tt0137523"]
    #available_imdb_ids = ["tt0137523"]
    
    print(f"Updating available items...")

    result = update_available_items(available_imdb_ids)

    print(f"Result: {result}")
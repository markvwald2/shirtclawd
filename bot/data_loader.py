import requests

DATA_URL = "https://raw.githubusercontent.com/markvwald2/thirdstringshirts/master/data/shirt_inventory.json"

def load_inventory():
    response = requests.get(DATA_URL)
    response.raise_for_status()
    return response.json()
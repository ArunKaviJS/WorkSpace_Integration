import os
import requests
from dotenv import load_dotenv

load_dotenv()

CLICKUP_API_TOKEN = os.getenv("CLICKUP_API_TOKEN")

BASE_URL = "https://api.clickup.com/api/v2"

headers = {
    "Authorization": CLICKUP_API_TOKEN,
    "Content-Type": "application/json"
}


def get_workspaces():
    url = f"{BASE_URL}/team"

    response = requests.get(
        url,
        headers=headers
    )

    response.raise_for_status()

    return response.json()
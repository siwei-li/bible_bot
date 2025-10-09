import os
import requests
import time
from jwt import decode
from dotenv import load_dotenv


load_dotenv()

CLIENT_ID = os.getenv("GLOO_CLIENT_ID")
CLIENT_SECRET = os.getenv("GLOO_CLIENT_SECRET")
TOKEN_URL = "https://platform.ai.gloo.com/oauth2/token"

# - Global token storage
access_token_info = {}


def _get_access_token():
    """Retrieve a new access token from the Gloo AI API."""
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "client_credentials", "scope": "api/access"}

    response = requests.post(
        TOKEN_URL,
        headers=headers,
        data=data,
        auth=(CLIENT_ID, CLIENT_SECRET)
    )
    response.raise_for_status()

    token_data = response.json()
    token_data['expires_at'] = int(time.time()) + token_data['expires_in']

    return token_data


def _is_token_expired(token_info):
    """Check if the token is expired or close to expiring."""
    if not token_info or 'expires_at' not in token_info:
        return True
    return time.time() > (token_info['expires_at'] - 60)


def ensure_valid_token():
    """Ensure we have a valid access token."""
    global access_token_info
    if _is_token_expired(access_token_info):
        print("Getting new access token...")
        access_token_info = _get_access_token()
    return access_token_info['access_token']


def get_auth_headers():
    """Get the Authorization header with the current valid token."""
    token = ensure_valid_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    return headers

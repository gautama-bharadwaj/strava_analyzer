import requests
import json
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TOKEN_FILE = 'strava_tokens.json'
CLIENT_ID = os.getenv('STRAVA_CLIENT_ID')
CLIENT_SECRET = os.getenv('STRAVA_CLIENT_SECRET')

if not CLIENT_ID or not CLIENT_SECRET:
    raise ValueError("STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET must be set in .env file")

def save_tokens(tokens):
    with open(TOKEN_FILE, 'w') as f:
        json.dump(tokens, f)

def load_tokens():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            return json.load(f)
    return None

def get_tokens_with_auth_code(auth_code):
    # Import here to avoid circular imports
    try:
        from strava_rate_limiter import rate_limiter
        rate_limiter.wait_if_needed(is_read_request=False, verbose=True)
    except ImportError:
        pass  # Rate limiter not available, proceed without it

    response = requests.post(
        'https://www.strava.com/oauth/token',
        data={
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'code': auth_code,
            'grant_type': 'authorization_code'
        }
    )
    tokens = response.json()
    save_tokens(tokens)
    return tokens

def refresh_tokens(refresh_token):
    # Import here to avoid circular imports
    try:
        from strava_rate_limiter import rate_limiter
        rate_limiter.wait_if_needed(is_read_request=False, verbose=True)
    except ImportError:
        pass  # Rate limiter not available, proceed without it

    response = requests.post(
        'https://www.strava.com/oauth/token',
        data={
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
    )
    tokens = response.json()
    save_tokens(tokens)
    return tokens

def get_access_token():
    tokens = load_tokens()
    if not tokens:
        raise Exception("No tokens found. Use an auth code to get them first.")

    if tokens['expires_at'] < time.time():
        print("Access token expired. Refreshing...")
        tokens = refresh_tokens(tokens['refresh_token'])

    return tokens['access_token']

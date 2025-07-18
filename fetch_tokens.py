from strava_auth_manager import get_tokens_with_auth_code
import os
from dotenv import load_dotenv

def main():
    """
    Fetch initial Strava tokens using authorization code.
    This should only be run once during initial setup.
    """
    # Load environment variables
    load_dotenv()

    client_id = os.getenv('STRAVA_CLIENT_ID')
    if not client_id:
        print("❌ Error: STRAVA_CLIENT_ID not found in .env file!")
        print("Please create a .env file with your Strava credentials.")
        return

    print("=== Strava Initial Token Setup ===")
    auth_url = f"https://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&redirect_uri=http://localhost&approval_prompt=force&scope=activity:read_all"
    print(f"1. Go to: {auth_url}")
    print("2. Authorize the app and copy the 'code' parameter from the redirect URL")
    print("3. Enter the authorization code below:")

    auth_code = input("\nEnter authorization code: ").strip()

    if not auth_code:
        print("Error: No authorization code provided!")
        return

    try:
        # This will get access + refresh tokens and save them to strava_tokens.json
        get_tokens_with_auth_code(auth_code)
        print("✅ Tokens successfully saved to strava_tokens.json")
        print("You can now run gym_analyzer.py to fetch your activities!")
    except Exception as e:
        print(f"❌ Error getting tokens: {e}")
        print("Please check your authorization code and try again.")

if __name__ == "__main__":
    main()

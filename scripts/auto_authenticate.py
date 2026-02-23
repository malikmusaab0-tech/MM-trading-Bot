import os
import sys
import webbrowser
from kiteconnect import KiteConnect  # make sure kiteconnect is installed

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from utils.auth import generate_access_token_from_request_token


API_KEY = "2kcgsxf407fpuvif"      # read from config/env in your real code


def main():
    print("=== Zerodha Kite Auto Authentication ===")

    # 1) Open Kite login URL in browser
    kite = KiteConnect(api_key=API_KEY)
    login_url = kite.login_url()  # uses your redirect URL set in the console[web:64][web:76]

    print("\nOpening Kite login page in your browser...")
    print(f"If it doesn't open, copy‑paste this URL manually:\n{login_url}\n")

    webbrowser.open(login_url)

    print("1) Log in and complete 2FA in the browser.")
    print("2) After login, check the browser address bar at the redirect URL.")
    print("   It will look like: http://localhost:8501/?request_token=XXXX&action=login")
    print("3) Copy ONLY the value after request_token= and paste it below.\n")

    request_token = input("Paste the request_token here: ").strip()

    if not request_token:
        print("No request_token provided. Exiting.")
        return

    access_token = generate_access_token_from_request_token(request_token)
    print("\nAccess token generated successfully.")
    print(f"Access token: {access_token}")


if __name__ == "__main__":
    main()

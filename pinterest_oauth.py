import os
import sys
import json
import base64
import urllib.parse
import webbrowser
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

class OAuthHandler(BaseHTTPRequestHandler):
    auth_code = None

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        if "code" in params:
            OAuthHandler.auth_code = params["code"][0]
            html = """
            <html>
            <head>
                <title>Authentication Successful</title>
                <style>
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                        background-color: #f7f9fa;
                        color: #1a1a1a;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                    }
                    .card {
                        background: white;
                        padding: 2.5rem;
                        border-radius: 12px;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
                        text-align: center;
                        max-width: 450px;
                    }
                    h1 { color: #e60023; font-size: 24px; margin-bottom: 1rem; }
                    p { color: #5f5f5f; font-size: 16px; line-height: 1.5; }
                    .badge {
                        background-color: #e1f5fe;
                        color: #0288d1;
                        padding: 6px 12px;
                        border-radius: 20px;
                        font-weight: bold;
                        font-size: 14px;
                        display: inline-block;
                        margin-top: 10px;
                    }
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>Pinterest Auth Success!</h1>
                    <p>Authorization code received. You can now close this tab and return to the terminal window to complete the setup.</p>
                    <span class="badge">Code captured successfully</span>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
        else:
            error_msg = params.get("error", ["Unknown error"])[0]
            html = f"""
            <html>
            <body style="font-family: sans-serif; text-align: center; padding-top: 100px;">
                <h1 style="color: #e60023;">Authentication Failed</h1>
                <p>Error: {error_msg}</p>
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))

def run_local_server():
    server_address = ("", 8085)
    httpd = HTTPServer(server_address, OAuthHandler)
    print("Waiting for Pinterest authorization redirect on port 8085...")
    while OAuthHandler.auth_code is None:
        httpd.handle_request()
    return OAuthHandler.auth_code

def exchange_code_for_tokens(client_id, client_secret, auth_code):
    print("Exchanging authorization code for access and refresh tokens...")
    url = "https://api.pinterest.com/v5/oauth/token"
    
    # Basic Authorization Header
    auth_str = f"{client_id}:{client_secret}"
    b64_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
    
    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": "http://localhost:8085"
    }
    
    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error exchanging tokens: Status {response.status_code}")
        print(response.text)
        sys.exit(1)

def main():
    print("==================================================")
    # Configure console for UTF-8 output
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        
    print("     PINTEREST API OAUTH2 AUTHENTICATION TOOL      ")
    print("==================================================")
    
    config = load_config()
    
    # 1. Get Client Credentials
    client_id = config.get("pinterest", {}).get("client_id")
    client_secret = config.get("pinterest", {}).get("client_secret")
    board_id = config.get("pinterest", {}).get("board_id")
    
    print("\n[Step 1] Verify/Enter Pinterest App Credentials")
    if client_id and client_secret:
        print(f"Loaded existing Pinterest credentials from config.json.")
        use_existing = input("Use existing credentials? (y/n, default: y): ").strip().lower() != "n"
    else:
        use_existing = False
        
    if not use_existing:
        client_id = input("Enter Pinterest Client ID: ").strip()
        client_secret = input("Enter Pinterest Client Secret: ").strip()
        if not client_id or not client_secret:
            print("Client ID and Client Secret are required!")
            sys.exit(1)
            
    board_id = input(f"Enter Pinterest Board ID (current: {board_id or 'Not Set'}): ").strip() or board_id
    
    # 2. Start OAuth workflow
    print("\n[Step 2] Authorize application in browser")
    print("IMPORTANT: Ensure you have added 'http://localhost:8085' as a Redirect URI")
    print("in your Pinterest App Settings under developers.pinterest.com.")
    input("\nPress ENTER to open your browser and start authorization...")
    
    scopes = "boards:read,boards:write,pins:read,pins:write"
    auth_url = (
        f"https://www.pinterest.com/oauth/?"
        f"client_id={client_id}&"
        f"redirect_uri=http://localhost:8085&"
        f"response_type=code&"
        f"scope={scopes}"
    )
    
    webbrowser.open(auth_url)
    
    # Run server to capture code
    auth_code = run_local_server()
    
    # 3. Exchange tokens
    tokens = exchange_code_for_tokens(client_id, client_secret, auth_code)
    
    # 4. Save back to config
    if "pinterest" not in config:
        config["pinterest"] = {}
        
    config["pinterest"]["client_id"] = client_id
    config["pinterest"]["client_secret"] = client_secret
    config["pinterest"]["refresh_token"] = tokens.get("refresh_token")
    if board_id:
        config["pinterest"]["board_id"] = board_id
        
    save_config(config)
    print("\n==================================================")
    print("🎉 SUCCESS! Pinterest authentication completed.")
    print("Saved refresh_token and credentials to config.json.")
    print("You can now run the automated Pinterest generator.")
    print("==================================================")

if __name__ == "__main__":
    main()

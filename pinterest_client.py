import os
import json
import base64
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

class PinterestClient:
    def __init__(self, config_path=CONFIG_PATH):
        self.config_path = config_path
        self.config = self.load_config()
        self.pinterest_config = self.config.get("pinterest", {})
        self.client_id = self.pinterest_config.get("client_id")
        self.client_secret = self.pinterest_config.get("client_secret")
        self.refresh_token = self.pinterest_config.get("refresh_token")
        self.board_id = self.pinterest_config.get("board_id")
        self.env = self.pinterest_config.get("environment", "production")
        if self.env == "sandbox":
            self.base_url = "https://api-sandbox.pinterest.com"
        else:
            self.base_url = "https://api.pinterest.com"
        self.access_token = None

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}
        return {}

    def refresh_access_token(self):
        """Refreshes the temporary access token using the long-lived refresh token."""
        if not self.refresh_token:
            raise ValueError(
                "Pinterest credentials missing from config.json. Please run pinterest_oauth.py first."
            )
            
        # If the token is a direct access token (starts with pina_), use it directly without refreshing
        if self.refresh_token.startswith("pina_"):
            print("Using direct Pinterest access token (no refresh needed).")
            self.access_token = self.refresh_token
            return self.access_token
            
        print("Refreshing Pinterest access token...")
        if not self.client_id or not self.client_secret:
            raise ValueError(
                "Pinterest Client ID or Secret missing from config.json."
            )
            
        url = f"{self.base_url}/v5/oauth/token"
        
        # Base64 encoded Basic Auth Header
        auth_str = f"{self.client_id}:{self.client_secret}"
        b64_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
        
        headers = {
            "Authorization": f"Basic {b64_auth}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }
        
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            res_data = response.json()
            self.access_token = res_data.get("access_token")
            # If the response returns a new refresh token, we should update it
            new_refresh = res_data.get("refresh_token")
            if new_refresh and new_refresh != self.refresh_token:
                print("Updating Pinterest refresh token in config...")
                self.refresh_token = new_refresh
                self.config["pinterest"]["refresh_token"] = new_refresh
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(self.config, f, indent=2)
            return self.access_token
        else:
            raise Exception(f"Failed to refresh Pinterest access token: {response.text}")

    def get_headers(self, refresh=False):
        if not self.access_token or refresh:
            self.refresh_access_token()
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    def verify_board(self, board_id=None):
        """Verifies if the specified board exists and is accessible."""
        b_id = board_id or self.board_id
        if not b_id:
            raise ValueError("No board_id provided or configured.")
            
        url = f"{self.base_url}/v5/boards/{b_id}"
        try:
            headers = self.get_headers()
            response = requests.get(url, headers=headers)
            if response.status_code == 401:  # Token expired
                headers = self.get_headers(refresh=True)
                response = requests.get(url, headers=headers)
                
            if response.status_code == 200:
                board_info = response.json()
                print(f"Verified Pinterest Board: '{board_info.get('name')}' (ID: {board_info.get('id')})")
                return True
            else:
                print(f"Board verification failed: {response.text}")
                return False
        except Exception as e:
            print(f"Error verifying Pinterest board: {e}")
            return False

    def create_pin(self, title, description, link, image_url, board_id=None):
        """Creates a Pin on Pinterest using a public image URL."""
        b_id = board_id or self.board_id
        if not b_id:
            raise ValueError("No Pinterest Board ID set. Specify it in config.json or pass it to create_pin.")
            
        url = f"{self.base_url}/v5/pins"
        
        payload = {
            "board_id": b_id,
            "title": title[:100],  # Max 100 characters
            "description": description[:500],  # Max 500 characters
            "link": link,
            "media_source": {
                "source_type": "image_url",
                "url": image_url
            }
        }
        
        headers = self.get_headers()
        print(f"Creating Pin '{payload['title']}' on Board {b_id}...")
        
        response = requests.post(url, headers=headers, json=payload)
        
        # Handle expired token retry
        if response.status_code == 401:
            print("Access token expired during Pin creation, refreshing...")
            headers = self.get_headers(refresh=True)
            response = requests.post(url, headers=headers, json=payload)
            
        if response.status_code == 201:
            pin_data = response.json()
            pin_url = f"https://www.pinterest.com/pin/{pin_data.get('id')}/"
            print(f"Successfully created Pin: {pin_url}")
            return pin_data
        else:
            raise Exception(f"Failed to create Pin: Status {response.status_code} - {response.text}")

    def create_pin_from_file(self, title, description, link, image_path, board_id=None):
        """
        Creates a Pin by sending the image as base64 directly to Pinterest.
        This bypasses all CDN hosting — no external URL required.
        Uses source_type 'image_base64' which Pinterest always accepts.
        """
        b_id = board_id or self.board_id
        if not b_id:
            raise ValueError("No Pinterest Board ID set.")

        # Read and base64-encode the image
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        b64_data = base64.b64encode(image_bytes).decode("utf-8")

        # Determine content type from file extension
        ext = os.path.splitext(image_path)[1].lower()
        content_type_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }
        content_type = content_type_map.get(ext, "image/jpeg")

        url = f"{self.base_url}/v5/pins"
        payload = {
            "board_id": b_id,
            "title": title[:100],
            "description": description[:500],
            "link": link,
            "media_source": {
                "source_type": "image_base64",
                "content_type": content_type,
                "data": b64_data,
            },
        }

        headers = self.get_headers()
        print(f"Creating Pin (base64 upload) '{title[:60]}...' on Board {b_id}...")
        response = requests.post(url, headers=headers, json=payload, timeout=60)

        if response.status_code == 401:
            print("Token expired, refreshing and retrying...")
            headers = self.get_headers(refresh=True)
            response = requests.post(url, headers=headers, json=payload, timeout=60)

        if response.status_code == 201:
            pin_data = response.json()
            pin_url = f"https://www.pinterest.com/pin/{pin_data.get('id')}/"
            print(f"Successfully created Pin (base64): {pin_url}")
            return pin_data
        else:
            raise Exception(f"Failed to create Pin (base64): Status {response.status_code} - {response.text}")


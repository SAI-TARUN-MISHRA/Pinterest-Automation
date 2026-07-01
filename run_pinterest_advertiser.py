import os
import sys
import json
import time
import requests
import datetime
from amazon_scraper import AmazonScraper
from poster_generator import PosterGenerator
from pinterest_client import PinterestClient

# Configure stdout and stderr for UTF-8 to prevent encoding issues on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
QUEUE_PATH = os.path.join(BASE_DIR, "amazon_links.txt")
HISTORY_PATH = os.path.join(BASE_DIR, "amazon_links_history.txt")

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def send_telegram_notification(message, image_url=None):
    config = load_config()
    tele_config = config.get("telegram", {})
    bot_token = tele_config.get("bot_token")
    chat_id = tele_config.get("chat_id")
    
    if not bot_token or not chat_id or "YOUR_TELEGRAM" in bot_token or "YOUR_TELEGRAM" in chat_id:
        return
        
    print("Sending Telegram notification...")
    try:
        if image_url:
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            payload = {
                "chat_id": chat_id,
                "photo": image_url,
                "caption": message,
                "parse_mode": "HTML"
            }
        else:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
        
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code == 200:
            print("Telegram notification sent successfully.")
        else:
            print(f"Telegram API error: {res.text}")
    except Exception as e:
        print(f"Error sending Telegram notification: {e}")

def get_next_link():
    if not os.path.exists(QUEUE_PATH):
        return None, []
        
    with open(QUEUE_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    clean_lines = []
    next_link = None
    
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if next_link is None:
            next_link = stripped
        else:
            clean_lines.append(line) # Keep in queue
            
    # Also preserve comment lines and empty lines for context
    remaining_lines = []
    found_next = False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            remaining_lines.append(line)
        elif not found_next and stripped == next_link:
            found_next = True
            # Skip this line as it is being processed
        else:
            remaining_lines.append(line)
            
    return next_link, remaining_lines

def update_queue(remaining_lines):
    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
        f.writelines(remaining_lines)

def log_to_history(url, pin_url, title):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] URL: {url} | Pin: {pin_url} | Title: {title}\n")

def upload_image_to_tmpfiles(image_path):
    """Uploads a local image to tmpfiles.org and returns the direct download URL."""
    print(f"Uploading local poster {image_path} to tmpfiles.org CDN...")
    url = "https://tmpfiles.org/api/v1/upload"
    
    try:
        with open(image_path, "rb") as f:
            files = {"file": f}
            response = requests.post(url, files=files, timeout=30)
            
        if response.status_code == 200:
            res_data = response.json()
            # Example response: {"status": "success", "data": {"url": "https://tmpfiles.org/12345/image.png"}}
            tmp_url = res_data.get("data", {}).get("url")
            if tmp_url:
                # Convert view URL to direct download URL
                direct_url = tmp_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                print(f"CDN Direct URL: {direct_url}")
                return direct_url
            else:
                raise ValueError(f"Unexpected API response layout: {response.text}")
        else:
            raise Exception(f"CDN Upload failed with status {response.status_code}: {response.text}")
    except Exception as e:
        raise Exception(f"Error uploading image to CDN: {e}")

def get_or_create_board(client, board_name):
    """Checks if a board with the suggested name exists, or creates it."""
    url = f"{client.base_url}/v5/boards"
    headers = client.get_headers()
    
    # 1. Fetch current boards
    boards = []
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            boards = res.json().get("items", [])
            # Try exact match
            for board in boards:
                if board.get("name").lower() == board_name.lower():
                    print(f"Found existing board matching name: '{board.get('name')}' (ID: {board.get('id')})")
                    return board.get("id")
            # Try partial/substring match
            for board in boards:
                b_name_lower = board.get("name").lower()
                suggested_lower = board_name.lower()
                if b_name_lower in suggested_lower or suggested_lower in b_name_lower:
                    print(f"Found partially matching board: '{board.get('name')}' (ID: {board.get('id')})")
                    return board.get("id")
        else:
            print(f"Failed to fetch boards: {res.text}")
    except Exception as e:
        print(f"Error fetching boards: {e}")
        
    # 2. If boards exist, fall back to the first available board instead of failing with write permission
    if boards:
        # Prefer a board that is likely to be about fashion/style
        for board in boards:
            b_name = board.get("name").lower()
            if "outfit" in b_name or "fashion" in b_name or "style" in b_name or "wardrobe" in b_name:
                print(f"Board '{board_name}' not found. Falling back to fashion board: '{board.get('name')}' (ID: {board.get('id')})")
                return board.get("id")
        
        fallback_board = boards[0]
        print(f"Board '{board_name}' not found. Falling back to existing board: '{fallback_board.get('name')}' (ID: {fallback_board.get('id')})")
        return fallback_board.get("id")
        
    # 3. If no boards exist at all, try to create it
    print(f"No boards found. Creating a new public board '{board_name}'...")
    try:
        payload = {
            "name": board_name[:50], # Max 50 chars
            "privacy": "PUBLIC"
        }
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code == 201:
            new_board = res.json()
            print(f"Successfully created board '{new_board.get('name')}' (ID: {new_board.get('id')})")
            return new_board.get("id")
        else:
            print(f"Failed to create board: {res.text}")
    except Exception as e:
        print(f"Error creating board: {e}")
        
    return None

def process_single_url(url, remaining_queue=None, is_manual=False):
    """Processes a single Amazon product URL: scrapes it, generates the poster, and posts to Pinterest."""
    try:
        # 2. Scrape Amazon product details & image
        scraper = AmazonScraper()
        scraped_info = scraper.scrape_product(url)
        
        if not scraped_info["image_path"]:
            print(f"⚠️ Failed to retrieve product image/screenshot for {url}.")
            log_to_history(url, "FAILED - No Image", scraped_info.get("title", "Unknown Product"))
            return False
            
        # 3. Generate copywriting and poster
        generator = PosterGenerator()
        ad_copy, poster_path = generator.process_url(
            scraped_info["image_path"],
            scraped_info["title"],
            scraped_info["details"]
        )
        
        # 4. Upload poster image to temporary CDN
        public_image_url = upload_image_to_tmpfiles(poster_path)
        
        # 5. Connect to Pinterest Client
        pinterest = PinterestClient()
        
        # Determine board ID
        board_id = pinterest.board_id
        if not board_id:
            suggested_board = ad_copy.get("board_name", "Fashion Essentials")
            print(f"No board_id configured. Resolving suggested board name: '{suggested_board}'")
            board_id = get_or_create_board(pinterest, suggested_board)
            
        if not board_id:
            print("❌ No Pinterest Board ID could be resolved or created.")
            log_to_history(url, "FAILED - No Board ID", scraped_info["title"])
            return False
            
        # 6. Publish Pin
        pin_title = ad_copy.get("pin_title", scraped_info["title"])
        pin_desc = ad_copy.get("pin_description", "Premium fashion inspiration. Shop the look now!")
        
        # Ensure affiliate tag is appended/updated in the URL
        config = load_config()
        tag = config.get("amazon_associates_tag", "designforyo0e-21")
        import urllib.parse as urlparse
        from urllib.parse import urlencode, parse_qsl, urlunparse
        try:
            target_url = scraped_info.get("url") or url
            url_parts = list(urlparse.urlparse(target_url))
            query = dict(parse_qsl(url_parts[4]))
            query['tag'] = tag
            url_parts[4] = urlencode(query)
            affiliate_url = urlunparse(url_parts)
            print(f"Ensuring link is configured with tag '{tag}': {affiliate_url}")
        except Exception as e:
            print(f"Warning: Failed to format affiliate URL tag: {e}")
            affiliate_url = url

        pin_data = pinterest.create_pin(
            title=pin_title,
            description=pin_desc,
            link=affiliate_url,
            image_url=public_image_url,
            board_id=board_id
        )
        
        pin_url = f"https://www.pinterest.com/pin/{pin_data.get('id')}/"
        
        # 7. Update queue and log history
        if not is_manual and remaining_queue is not None:
            update_queue(remaining_queue)
        log_to_history(url, pin_url, scraped_info["title"])
        
        # 8. Send success notification
        success_msg = (
            f"🎉 <b>Pinterest Affiliate Pin Created!</b>\n\n"
            f"<b>Product:</b> {scraped_info['title']}\n"
            f"<b>Board ID:</b> {board_id}\n"
            f"<b>Link:</b> <a href='{pin_url}'>View Pin on Pinterest</a>"
        )
        send_telegram_notification(success_msg, public_image_url)
        
        print("\n==================================================")
        print("🚀 RUN COMPLETED SUCCESSFULLY!")
        print(f"Processed: {scraped_info['title']}")
        print(f"Pin URL: {pin_url}")
        print("==================================================")
        return True
        
    except Exception as e:
        print(f"❌ Error processing URL {url}: {e}")
        prod_title = scraped_info.get("title", "Unknown Product") if 'scraped_info' in locals() else "Unknown Product"
        log_to_history(url, f"FAILED - {str(e)[:50]}", prod_title)
        return False

def main(url_arg=None):
    print("==================================================")
    print(f"   STARTING PINTEREST DAILY AFFILIATE GENERATOR   ")
    print(f"   Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("==================================================")
    
    if url_arg:
        print(f"Manual override URL provided: {url_arg}")
        success = process_single_url(url_arg, is_manual=True)
        if not success:
            sys.exit(1)
    else:
        # Loop through queue until we successfully post a pin
        processed_any = False
        while True:
            url, remaining_queue = get_next_link()
            if not url:
                print("Queue is empty. No links to process in amazon_links.txt.")
                break
                
            print(f"Processing URL from queue: {url}")
            success = process_single_url(url, remaining_queue, is_manual=False)
            if success:
                processed_any = True
                break
            else:
                print(f"⚠️ Failed to process URL {url}. Removing from queue and trying next link...")
                update_queue(remaining_queue)
                time.sleep(2)
                
        if not processed_any:
            print("No pins were successfully created in this run (either queue was empty or all items failed).")
            sys.exit(0)

if __name__ == "__main__":
    # Command line argument parser for developer diagnostics
    import argparse
    parser = argparse.ArgumentParser(description="Pinterest Daily Affiliate Pin Generator")
    parser.add_argument("--url", type=str, help="Manually run a single Amazon URL override")
    parser.add_argument("--test-scrape", type=str, help="Test scraping an Amazon URL and download image")
    parser.add_argument("--test-poster", type=str, help="Test generating ad copy and layout from local image")
    
    args = parser.parse_args()
    
    if args.test_scrape:
        scraper = AmazonScraper()
        res = scraper.scrape_product(args.test_scrape)
        print(f"Scrape completed. Title: {res['title']}, Image: {res['image_path']}")
        sys.exit(0)
        
    if args.test_poster:
        generator = PosterGenerator()
        ad_copy, poster = generator.process_url(args.test_poster, "Test Fashion Outfit", "Luxury fabric, elegant fitting, comfortable sleeves.")
        print(f"Poster completed. Output: {poster}")
        sys.exit(0)
        
    # Standard run
    main(args.url)

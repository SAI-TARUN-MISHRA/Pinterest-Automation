import os
import sys
import json
import time
import requests
import datetime
import subprocess
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

# Minimum queue size before auto-refill is triggered
MIN_QUEUE_SIZE = 10
AUTO_REFILL_COUNT = 15

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

# ─────────────────────────────────────────────────────────────────────────────
# Telegram notifications
# ─────────────────────────────────────────────────────────────────────────────
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
            payload = {"chat_id": chat_id, "photo": image_url, "caption": message, "parse_mode": "HTML"}
        else:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code == 200:
            print("Telegram notification sent successfully.")
        else:
            print(f"Telegram API error: {res.text}")
    except Exception as e:
        print(f"Error sending Telegram notification: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# Queue management
# ─────────────────────────────────────────────────────────────────────────────
def count_queue_items():
    """Returns the number of valid (non-comment, non-empty) URLs in the queue."""
    if not os.path.exists(QUEUE_PATH):
        return 0
    count = 0
    with open(QUEUE_PATH, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                count += 1
    return count

def get_next_link():
    if not os.path.exists(QUEUE_PATH):
        return None, []
    with open(QUEUE_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
    next_link = None
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            next_link = stripped
            break
    if not next_link:
        return None, lines
    remaining_lines = []
    found_next = False
    for line in lines:
        stripped = line.strip()
        if not found_next and stripped == next_link:
            found_next = True
            continue
        remaining_lines.append(line)
    return next_link, remaining_lines

def update_queue(remaining_lines):
    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
        f.writelines(remaining_lines)

def log_to_history(url, pin_url, title):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] URL: {url} | Pin: {pin_url} | Title: {title}\n")

def auto_refill_queue():
    """Run the Trend Finder inline to top up the queue."""
    print(f"⚠️  Queue has fewer than {MIN_QUEUE_SIZE} items. Auto-refilling...")
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(BASE_DIR, "amazon_trend_finder.py"), "--count", str(AUTO_REFILL_COUNT)],
            timeout=120,
        )
        if result.returncode == 0:
            print(f"✅ Auto-refill done. Queue now has {count_queue_items()} items.")
        else:
            print("⚠️  Auto-refill finished with non-zero exit. Continuing anyway.")
    except subprocess.TimeoutExpired:
        print("⚠️  Auto-refill timed out after 120s. Continuing with available items.")
    except Exception as e:
        print(f"⚠️  Auto-refill failed: {e}. Continuing with available items.")

# ─────────────────────────────────────────────────────────────────────────────
# Multi-CDN image upload with 3 fallbacks
# ─────────────────────────────────────────────────────────────────────────────
def upload_image_to_cdn(image_path):
    """
    Uploads a local image to a public CDN. Tries 3 CDNs in order:
      1. 0x0.st       — primary, permanent URLs
      2. tmpfiles.org  — secondary, 24h CDN
      3. catbox.moe    — tertiary, permanent free hosting
    """
    print(f"Uploading poster to CDN: {image_path}")

    # CDN 1: 0x0.st (permanent, no account needed)
    try:
        with open(image_path, "rb") as f:
            res = requests.post("https://0x0.st", files={"file": f}, timeout=30)
        if res.status_code == 200 and res.text.strip().startswith("https://"):
            url = res.text.strip()
            print(f"✅ CDN 1 (0x0.st): {url}")
            return url
        print(f"CDN 1 (0x0.st) failed: {res.status_code}")
    except Exception as e:
        print(f"CDN 1 (0x0.st) error: {e}")

    # CDN 2: tmpfiles.org
    try:
        with open(image_path, "rb") as f:
            res = requests.post("https://tmpfiles.org/api/v1/upload", files={"file": f}, timeout=30)
        if res.status_code == 200:
            tmp_url = res.json().get("data", {}).get("url", "")
            if tmp_url:
                direct_url = tmp_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                print(f"✅ CDN 2 (tmpfiles.org): {direct_url}")
                return direct_url
        print(f"CDN 2 (tmpfiles.org) failed: {res.status_code}")
    except Exception as e:
        print(f"CDN 2 (tmpfiles.org) error: {e}")

    # CDN 3: catbox.moe (permanent free hosting)
    try:
        with open(image_path, "rb") as f:
            res = requests.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload"},
                files={"fileToUpload": f},
                timeout=30,
            )
        if res.status_code == 200 and res.text.strip().startswith("https://"):
            url = res.text.strip()
            print(f"✅ CDN 3 (catbox.moe): {url}")
            return url
        print(f"CDN 3 (catbox.moe) failed: {res.status_code}")
    except Exception as e:
        print(f"CDN 3 (catbox.moe) error: {e}")

    raise RuntimeError("All 3 CDN upload attempts failed. Cannot publish pin without a public image URL.")

# ─────────────────────────────────────────────────────────────────────────────
# Retry helper with exponential backoff
# ─────────────────────────────────────────────────────────────────────────────
def retry_with_backoff(fn, retries=3, delays=(5, 15, 45), label="operation"):
    """Calls fn(); retries on exception with exponential backoff delays."""
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if attempt < retries:
                wait = delays[min(attempt - 1, len(delays) - 1)]
                print(f"⚠️  {label} failed (attempt {attempt}/{retries}): {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"❌ {label} failed after {retries} attempts: {e}")
    raise last_exc

# ─────────────────────────────────────────────────────────────────────────────
# Board resolution helper
# ─────────────────────────────────────────────────────────────────────────────
def get_or_create_board(client, board_name):
    url = f"{client.base_url}/v5/boards"
    headers = client.get_headers()
    boards = []
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            boards = res.json().get("items", [])
            for board in boards:
                if board.get("name", "").lower() == board_name.lower():
                    print(f"Found exact board: '{board.get('name')}' (ID: {board.get('id')})")
                    return board.get("id")
            for board in boards:
                b_name = board.get("name", "").lower()
                if b_name in board_name.lower() or board_name.lower() in b_name:
                    print(f"Found partial board: '{board.get('name')}' (ID: {board.get('id')})")
                    return board.get("id")
        else:
            print(f"Failed to fetch boards: {res.text}")
    except Exception as e:
        print(f"Error fetching boards: {e}")

    if boards:
        for board in boards:
            b_name = board.get("name", "").lower()
            if any(kw in b_name for kw in ("outfit", "fashion", "style", "wardrobe", "dress")):
                print(f"Falling back to fashion board: '{board.get('name')}' (ID: {board.get('id')})")
                return board.get("id")
        fallback = boards[0]
        print(f"Falling back to first board: '{fallback.get('name')}' (ID: {fallback.get('id')})")
        return fallback.get("id")

    print(f"Creating board '{board_name}'...")
    try:
        res = requests.post(url, headers=headers, json={"name": board_name[:50], "privacy": "PUBLIC"}, timeout=15)
        if res.status_code == 201:
            new_board = res.json()
            print(f"Created board: '{new_board.get('name')}' (ID: {new_board.get('id')})")
            return new_board.get("id")
        print(f"Board creation failed: {res.text}")
    except Exception as e:
        print(f"Error creating board: {e}")
    return None

# ─────────────────────────────────────────────────────────────────────────────
# Core processing — one URL
# ─────────────────────────────────────────────────────────────────────────────
def process_single_url(url, remaining_queue=None, is_manual=False):
    """
    Scrapes a product, generates a poster, uploads to CDN, posts to Pinterest.
    Returns True on success, False on any unrecoverable failure.
    All network calls use retry_with_backoff for resilience.
    """
    scraped_info = None
    try:
        print(f"\n{'─'*52}")
        print(f"  Processing: {url}")
        print(f"{'─'*52}")

        # Step 1 — Scrape product (with retry)
        scraper = AmazonScraper()
        scraped_info = retry_with_backoff(
            lambda: scraper.scrape_product(url),
            retries=2, delays=(5, 20), label="Amazon scrape"
        )

        if not scraped_info.get("image_path"):
            print(f"⚠️  No product image found. Skipping.")
            log_to_history(url, "FAILED - No Image", scraped_info.get("title", "Unknown"))
            return False

        # Step 2 — Generate poster (with retry)
        generator = PosterGenerator()
        ad_copy, poster_path = retry_with_backoff(
            lambda: generator.process_url(
                scraped_info["image_path"],
                scraped_info["title"],
                scraped_info["details"]
            ),
            retries=2, delays=(5, 15), label="Poster generation"
        )

        # Step 3 — Pinterest client + board resolution
        pinterest = PinterestClient()
        suggested_board = ad_copy.get("board_name", "Fashion Essentials")
        print(f"Resolving board: '{suggested_board}'")
        board_id = get_or_create_board(pinterest, suggested_board)

        if not board_id:
            print("❌ No Pinterest board ID could be resolved.")
            log_to_history(url, "FAILED - No Board ID", scraped_info["title"])
            return False

        # Step 5 — Build affiliate URL with tag
        config = load_config()
        tag = config.get("amazon_associates_tag", "designforyo0e-21")
        import urllib.parse as urlparse
        from urllib.parse import urlencode, parse_qsl, urlunparse
        try:
            target_url = scraped_info.get("url") or url
            url_parts = list(urlparse.urlparse(target_url))
            query = dict(parse_qsl(url_parts[4]))
            query["tag"] = tag
            url_parts[4] = urlencode(query)
            affiliate_url = urlunparse(url_parts)
        except Exception as e:
            print(f"Warning: Could not build affiliate URL: {e}")
            affiliate_url = url

        # Step 6 — Publish Pin (with retry and base64 upload as primary, CDN as fallback)
        pin_title = ad_copy.get("pin_title", scraped_info["title"])
        pin_desc = ad_copy.get("pin_description", "Premium fashion inspiration. Shop the look now!")

        pin_data = None
        public_image_url = None
        try:
            print("Attempting to publish pin using base64 direct image upload...")
            pin_data = retry_with_backoff(
                lambda: pinterest.create_pin_from_file(
                    title=pin_title,
                    description=pin_desc,
                    link=affiliate_url,
                    image_path=poster_path,
                    board_id=board_id,
                ),
                retries=2, delays=(10, 30), label="Pinterest base64 pin creation"
            )
        except Exception as b64_err:
            print(f"⚠️ Direct base64 upload failed: {b64_err}. Falling back to CDN URL method...")
            # Step 6b — Fallback to CDN upload + URL-based pin creation
            public_image_url = retry_with_backoff(
                lambda: upload_image_to_cdn(poster_path),
                retries=2, delays=(5, 15), label="CDN upload fallback"
            )
            pin_data = retry_with_backoff(
                lambda: pinterest.create_pin(
                    title=pin_title,
                    description=pin_desc,
                    link=affiliate_url,
                    image_url=public_image_url,
                    board_id=board_id,
                ),
                retries=2, delays=(10, 30), label="Pinterest URL pin creation"
            )

        pin_url = f"https://www.pinterest.com/pin/{pin_data.get('id')}/"

        # Step 7 — Update queue & history
        if not is_manual and remaining_queue is not None:
            update_queue(remaining_queue)
        log_to_history(url, pin_url, scraped_info["title"])

        # Step 8 — Telegram success notification
        success_msg = (
            f"🎉 <b>Pinterest Pin Published!</b>\n\n"
            f"<b>Product:</b> {scraped_info['title']}\n"
            f"<b>Pin:</b> <a href='{pin_url}'>View on Pinterest</a>"
        )
        send_telegram_notification(success_msg, public_image_url)

        print(f"\n✅ SUCCESS — Pin published: {pin_url}")
        return True

    except Exception as e:
        print(f"❌ process_single_url failed for {url}: {e}")
        title = scraped_info.get("title", "Unknown") if scraped_info else "Unknown"
        log_to_history(url, f"FAILED - {str(e)[:80]}", title)
        return False

# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────
def main(url_arg=None, count=1):
    print("=" * 52)
    print("   PINTEREST AFFILIATE GENERATOR — v3.0   ")
    print(f"   Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 52)

    if url_arg:
        print(f"Manual override URL: {url_arg}")
        success = process_single_url(url_arg, is_manual=True)
        if not success:
            sys.exit(1)
        return

    # Auto-refill queue if running low
    queue_size = count_queue_items()
    print(f"Queue size: {queue_size} items")
    if queue_size < MIN_QUEUE_SIZE:
        auto_refill_queue()

    # Process `count` pins, skipping failures without hard-exiting
    posted = 0
    failed_consecutive = 0
    MAX_CONSECUTIVE_FAILURES = 10

    while posted < count:
        if failed_consecutive >= MAX_CONSECUTIVE_FAILURES:
            msg = f"❌ <b>Generator Halted</b>\n{MAX_CONSECUTIVE_FAILURES} consecutive URL failures. Manual check needed."
            print(msg)
            send_telegram_notification(msg)
            break

        url, remaining_queue = get_next_link()
        if not url:
            print("Queue is empty. No more links to process.")
            break

        print(f"\nProcessing pin {posted + 1}/{count}...")
        success = process_single_url(url, remaining_queue, is_manual=False)

        if success:
            posted += 1
            failed_consecutive = 0
            print(f"🏁 Progress: {posted}/{count} pins published.")
            if posted < count:
                print("Waiting 12 seconds before next pin (API pacing)...")
                time.sleep(12)
        else:
            failed_consecutive += 1
            print(f"⚠️  Removing failed URL from queue (consecutive failures: {failed_consecutive}).")
            update_queue(remaining_queue)
            time.sleep(3)

    if posted == 0:
        print("No pins were successfully published in this run.")
    else:
        print(f"\n{'=' * 52}")
        print(f"   🚀 DONE — {posted}/{count} pins published!   ")
        print(f"{'=' * 52}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Pinterest Daily Affiliate Pin Generator v3.0")
    parser.add_argument("--url", type=str, help="Manually run a single Amazon URL override")
    parser.add_argument("--test-scrape", type=str, help="Test scraping an Amazon URL")
    parser.add_argument("--test-poster", type=str, help="Test generating a poster from a local image")
    parser.add_argument("--count", type=int, default=1, help="Number of successful pins to publish")
    args = parser.parse_args()

    if args.test_scrape:
        scraper = AmazonScraper()
        res = scraper.scrape_product(args.test_scrape)
        print(f"Scrape done. Title: {res['title']}, Image: {res['image_path']}")
        sys.exit(0)

    if args.test_poster:
        generator = PosterGenerator()
        ad_copy, poster = generator.process_url(args.test_poster, "Test Fashion Outfit", "Luxury fabric.")
        print(f"Poster done: {poster}")
        sys.exit(0)

    main(args.url, args.count)

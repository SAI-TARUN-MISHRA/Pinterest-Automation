"""
health_check.py — Weekly system health reporter.
Validates Pinterest token, counts queue items, checks last successful post,
and sends a Telegram status summary.
Run automatically every Sunday by GitHub Actions, or manually at any time.
"""
import os
import sys
import json
import datetime
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
QUEUE_PATH = os.path.join(BASE_DIR, "amazon_links.txt")
HISTORY_PATH = os.path.join(BASE_DIR, "amazon_links_history.txt")


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}


def count_queue():
    if not os.path.exists(QUEUE_PATH):
        return 0
    c = 0
    with open(QUEUE_PATH, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s and not s.startswith("#"):
                c += 1
    return c


def get_last_pin_info():
    """Returns (timestamp_str, title) of the last successful pin from history."""
    if not os.path.exists(HISTORY_PATH):
        return None, None
    last_line = None
    with open(HISTORY_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if "FAILED" not in line and "Pin:" not in line and "URL: " in line:
                last_line = line.strip()
    if not last_line:
        return None, None
    try:
        ts = last_line.split("]")[0].strip("[")
        title_part = last_line.split("Title: ")[-1] if "Title: " in last_line else "Unknown"
        return ts, title_part
    except Exception:
        return None, None


def check_pinterest_token(config):
    """Returns (is_valid: bool, message: str) for the Pinterest token."""
    p_conf = config.get("pinterest", {})
    client_id = p_conf.get("client_id", "")
    client_secret = p_conf.get("client_secret", "")
    refresh_token = p_conf.get("refresh_token", "")

    if not all([client_id, client_secret, refresh_token]):
        return False, "Pinterest credentials not configured"

    # Try to refresh the access token to confirm the refresh_token is still valid
    try:
        token_res = requests.post(
            "https://api.pinterest.com/v5/oauth/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            auth=(client_id, client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        if token_res.status_code == 200:
            data = token_res.json()
            new_token = data.get("access_token")
            if new_token:
                # Verify the token with a simple API call
                verify_res = requests.get(
                    "https://api.pinterest.com/v5/user_account",
                    headers={"Authorization": f"Bearer {new_token}"},
                    timeout=10,
                )
                if verify_res.status_code == 200:
                    username = verify_res.json().get("username", "unknown")
                    return True, f"Token valid. Account: @{username}"
                return False, f"Token refresh OK but verify failed: {verify_res.status_code}"
        return False, f"Token refresh failed: HTTP {token_res.status_code} — {token_res.text[:100]}"
    except Exception as e:
        return False, f"Token check error: {e}"


def send_telegram(config, message):
    tele = config.get("telegram", {})
    bot_token = tele.get("bot_token", "")
    chat_id = tele.get("chat_id", "")
    if not bot_token or not chat_id or "YOUR_" in bot_token:
        print("Telegram not configured. Skipping notification.")
        return
    try:
        res = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=15,
        )
        if res.status_code == 200:
            print("Health report sent to Telegram.")
        else:
            print(f"Telegram error: {res.text}")
    except Exception as e:
        print(f"Telegram failed: {e}")


def main():
    print("=" * 52)
    print("   PINTEREST AUTOMATION — HEALTH CHECK")
    print(f"   {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 52)

    config = load_config()
    issues = []
    info = []

    # 1. Pinterest token check
    print("\n[1] Checking Pinterest token...")
    token_ok, token_msg = check_pinterest_token(config)
    if token_ok:
        print(f"    OK: {token_msg}")
        info.append(f"Pinterest: {token_msg}")
    else:
        print(f"    FAIL: {token_msg}")
        issues.append(f"Pinterest token INVALID: {token_msg}")

    # 2. Queue size check
    print("\n[2] Checking queue size...")
    queue_size = count_queue()
    print(f"    Queue items: {queue_size}")
    if queue_size < 5:
        issues.append(f"Queue is critically low: {queue_size} items")
    else:
        info.append(f"Queue: {queue_size} items ready")

    # 3. Last successful post
    print("\n[3] Checking last successful post...")
    last_ts, last_title = get_last_pin_info()
    if last_ts:
        print(f"    Last post: {last_ts} — {last_title}")
        info.append(f"Last pin: {last_ts}")
        # Check if more than 36 hours ago
        try:
            post_dt = datetime.datetime.strptime(last_ts, "%Y-%m-%d %H:%M:%S")
            hours_ago = (datetime.datetime.now() - post_dt).total_seconds() / 3600
            if hours_ago > 36:
                issues.append(f"Last pin was {hours_ago:.1f} hours ago — posts may have stopped!")
        except Exception:
            pass
    else:
        print("    No successful posts found in history.")
        issues.append("No successful posts found in history file")

    # 4. Build and send health report
    status_emoji = "x" if issues else "ok"
    lines_out = []
    if status_emoji == "ok":
        lines_out.append("<b>Pinterest Automation Health Check</b>")
        lines_out.append("Status: All systems operational")
    else:
        lines_out.append("<b>Pinterest Automation Health Check</b>")
        lines_out.append("<b>WARNING: Issues detected!</b>")
        for issue in issues:
            lines_out.append(f"  - {issue}")
    lines_out.append("")
    for i in info:
        lines_out.append(i)
    lines_out.append(f"Checked at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    report = "\n".join(lines_out)
    print("\n--- HEALTH REPORT ---")
    print(report)
    print("---------------------")

    send_telegram(config, report)

    if issues:
        sys.exit(1)


if __name__ == "__main__":
    main()

import os
import sys
import json
import time
import random
import urllib.parse
import requests
from bs4 import BeautifulSoup

# Configure stdout/stderr for UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
QUEUE_PATH = os.path.join(BASE_DIR, "amazon_links.txt")
HISTORY_PATH = os.path.join(BASE_DIR, "amazon_links_history.txt")
# State file for keyword rotation
KEYWORD_STATE_PATH = os.path.join(BASE_DIR, "last_keyword_index.txt")

# Expanded keyword list — rotated sequentially so each gets used evenly
TREND_KEYWORDS = [
    "women summer linen dress",
    "women bohemian maxi dress",
    "women floral print wrap dress",
    "women casual sundress with pockets",
    "women chic vacation dress",
    "women puff sleeve midi dress",
    "women classic linen blend shirt dress",
    "women tiered ruffle beach dress",
    "women ethnic kurta set",
    "women cotton anarkali kurti",
    "women embroidered salwar suit",
    "women palazzo pants kurti set",
    "women fashion handbag leather",
    "women western flare pants outfit",
    "women co-ord set crop top",
    "women party wear dress evening gown",
]


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def get_next_keyword():
    """Round-robin through TREND_KEYWORDS sequentially using a state file."""
    idx = 0
    if os.path.exists(KEYWORD_STATE_PATH):
        try:
            idx = int(open(KEYWORD_STATE_PATH).read().strip())
        except Exception:
            idx = 0
    keyword = TREND_KEYWORDS[idx % len(TREND_KEYWORDS)]
    next_idx = (idx + 1) % len(TREND_KEYWORDS)
    with open(KEYWORD_STATE_PATH, "w") as f:
        f.write(str(next_idx))
    print(f"Keyword [{idx % len(TREND_KEYWORDS) + 1}/{len(TREND_KEYWORDS)}]: {keyword!r}")
    return keyword


def extract_asin(url):
    """Extracts the 10-char ASIN from an Amazon link."""
    import re
    resolved_url = url
    if "amzn.to" in url:
        try:
            res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True, timeout=10)
            resolved_url = res.url
        except Exception:
            pass
    match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", resolved_url)
    return match.group(1) if match else None


def get_already_processed():
    """Gets ASINs already in queue or history to prevent duplicates."""
    processed = set()
    for path in (QUEUE_PATH, HISTORY_PATH):
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "URL: " in line:
                    parts = line.split("URL: ")
                    if len(parts) > 1:
                        line = parts[1].split(" | ")[0].strip()
                asin = extract_asin(line)
                if asin:
                    processed.add(asin)
    return processed


def search_via_google_translate_proxy(keyword, domain, tag, num_links, already_processed):
    """Primary: Google Translate proxy search (CAPTCHA-proof on cloud IPs)."""
    found = []
    try:
        search_query = keyword.replace(" ", "+")
        target_url = f"https://www.{domain}/s?k={search_query}"
        proxy_url = f"https://translate.google.com/translate?sl=auto&tl=en&u={urllib.parse.quote(target_url)}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        print(f"[Source 1] Google Translate proxy: {proxy_url[:80]}...")
        res = requests.get(proxy_url, headers=headers, timeout=25)
        if res.status_code != 200:
            print(f"  Proxy returned HTTP {res.status_code}")
            return found
        soup = BeautifulSoup(res.text, "html.parser")
        iframe = soup.find("iframe", id="content-frame") or soup.find("iframe", class_="content-frame")
        if iframe and iframe.get("src"):
            iframe_res = requests.get(iframe["src"], headers=headers, timeout=20)
            if iframe_res.status_code == 200:
                soup = BeautifulSoup(iframe_res.text, "html.parser")
        hrefs = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "uddg=" in href:
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                href = qs.get("uddg", [href])[0]
            hrefs.append(href)
        for href in set(hrefs):
            if len(found) >= num_links:
                break
            asin = extract_asin(href)
            if asin and asin not in already_processed:
                aff = f"https://www.{domain}/dp/{asin}/?tag={tag}"
                found.append(aff)
                already_processed.add(asin)
                print(f"  [+] ASIN {asin} -> {aff}")
        print(f"  Source 1 found {len(found)} products.")
    except Exception as e:
        print(f"  Source 1 failed: {e}")
    return found


def search_via_duckduckgo(keyword, domain, tag, num_links, already_processed):
    """Fallback: DuckDuckGo HTML search."""
    found = []
    try:
        query = f"site:{domain}/dp/ {keyword}"
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        print(f"[Source 2] DuckDuckGo HTML search...")
        res = requests.get(url, headers=headers, timeout=20)
        if res.status_code != 200:
            print(f"  DDG returned HTTP {res.status_code}")
            return found
        soup = BeautifulSoup(res.text, "html.parser")
        hrefs = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "uddg=" in href:
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                href = qs.get("uddg", [href])[0]
            if domain in href and ("/dp/" in href or "/gp/product/" in href):
                hrefs.append(href)
        for href in set(hrefs):
            if len(found) >= num_links:
                break
            asin = extract_asin(href)
            if asin and asin not in already_processed:
                aff = f"https://www.{domain}/dp/{asin}/?tag={tag}"
                found.append(aff)
                already_processed.add(asin)
                print(f"  [+] ASIN {asin} -> {aff}")
        print(f"  Source 2 found {len(found)} products.")
    except Exception as e:
        print(f"  Source 2 failed: {e}")
    return found


def search_via_amazon_bestsellers(domain, tag, num_links, already_processed):
    """Emergency fallback: Scrape Amazon Bestsellers page via proxy. Always has active products."""
    found = []
    # Bestseller categories to try
    BESTSELLER_PATHS = [
        "gp/bestsellers/apparel",
        "gp/bestsellers/fashion",
        "gp/bestsellers/shoes",
        "s?bbn=1571271031&rh=n%3A1571271031",
    ]
    try:
        for path in BESTSELLER_PATHS:
            if len(found) >= num_links:
                break
            target_url = f"https://www.{domain}/{path}"
            proxy_url = f"https://translate.google.com/translate?sl=auto&tl=en&u={urllib.parse.quote(target_url)}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            print(f"[Source 3] Bestsellers: {target_url}")
            try:
                res = requests.get(proxy_url, headers=headers, timeout=25)
                if res.status_code != 200:
                    continue
                soup = BeautifulSoup(res.text, "html.parser")
                iframe = soup.find("iframe", id="content-frame") or soup.find("iframe", class_="content-frame")
                if iframe and iframe.get("src"):
                    ir = requests.get(iframe["src"], headers=headers, timeout=20)
                    if ir.status_code == 200:
                        soup = BeautifulSoup(ir.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if "uddg=" in href:
                        qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                        href = qs.get("uddg", [href])[0]
                    asin = extract_asin(href)
                    if asin and asin not in already_processed and len(found) < num_links:
                        aff = f"https://www.{domain}/dp/{asin}/?tag={tag}"
                        found.append(aff)
                        already_processed.add(asin)
                        print(f"  [+] Bestseller ASIN {asin} -> {aff}")
            except Exception as ex:
                print(f"  Bestsellers path {path} failed: {ex}")
        print(f"  Source 3 found {len(found)} products.")
    except Exception as e:
        print(f"  Source 3 failed: {e}")
    return found


def find_trending_products(tag, num_links=15):
    print("=" * 52)
    print("   AMAZON TREND FINDER — v2.0 (Self-Healing)  ")
    print("=" * 52)
    print(f"Tag: {tag} | Seeking {num_links} new products")

    already_processed = get_already_processed()
    print(f"Already tracked ASINs: {len(already_processed)}")

    keyword = get_next_keyword()
    domain = "amazon.in" if tag.endswith("-21") else "amazon.com"
    print(f"Domain: {domain}")

    all_found = []

    # Source 1: Google Translate proxy (primary)
    results = search_via_google_translate_proxy(keyword, domain, tag, num_links, already_processed)
    all_found.extend(results)
    if len(all_found) >= num_links:
        return all_found[:num_links]

    # Source 2: DuckDuckGo (secondary — needs remaining count)
    still_needed = num_links - len(all_found)
    results2 = search_via_duckduckgo(keyword, domain, tag, still_needed, already_processed)
    all_found.extend(results2)
    if len(all_found) >= num_links:
        return all_found[:num_links]

    # Source 3: Amazon Bestsellers (emergency fallback — always works)
    still_needed = num_links - len(all_found)
    results3 = search_via_amazon_bestsellers(domain, tag, still_needed, already_processed)
    all_found.extend(results3)

    return all_found[:num_links]


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Amazon Trend Finder v2.0")
    parser.add_argument("--count", type=int, default=15, help="Number of products to find")
    args = parser.parse_args()

    config = load_config()
    tag = config.get("amazon_associates_tag")
    if not tag or "YOUR_" in tag:
        print("ERROR: amazon_associates_tag not configured in config.json")
        sys.exit(1)

    try:
        new_links = find_trending_products(tag, num_links=args.count)
        if not new_links:
            print("No new unique products found in this run.")
            return
        print(f"\nAdding {len(new_links)} links to queue...")
        with open(QUEUE_PATH, "a", encoding="utf-8") as f:
            f.write("\n# Auto-added by Trend Finder\n")
            for link in new_links:
                f.write(f"{link}\n")
        print("Queue updated.")
    except Exception as e:
        print(f"ERROR during Trend Finder: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

import os
import sys
import json
import time
import random
import urllib.parse
from playwright.sync_api import sync_playwright

# Configure stdout and stderr for UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
QUEUE_PATH = os.path.join(BASE_DIR, "amazon_links.txt")
HISTORY_PATH = os.path.join(BASE_DIR, "amazon_links_history.txt")

# Standard fashion keywords to rotate and search
TREND_KEYWORDS = [
    "women summer linen dress",
    "women bohemian maxi dress",
    "women floral print wrap dress",
    "women casual sundress with pockets",
    "women chic vacation dress",
    "women puff sleeve midi dress",
    "women classic linen blend shirt dress",
    "women tiered ruffle beach dress"
]

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def get_already_processed():
    """Gets list of all links already in queue or history to prevent duplicates."""
    processed = set()
    
    # Read queue
    if os.path.exists(QUEUE_PATH):
        with open(QUEUE_PATH, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    # Extract clean ASIN if possible to match
                    asin = extract_asin(stripped)
                    if asin:
                        processed.add(asin)
                        
    # Read history
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            for line in f:
                # History format: [date] URL: url | ...
                if "URL: " in line:
                    parts = line.split("URL: ")
                    if len(parts) > 1:
                        url = parts[1].split(" | ")[0].strip()
                        asin = extract_asin(url)
                        if asin:
                            processed.add(asin)
                            
    return processed

def extract_asin(url):
    """Extracts the 10-char ASIN from an Amazon link, resolving short links first."""
    import re
    import requests
    
    # Resolve short amzn.to link
    resolved_url = url
    if "amzn.to" in url:
        try:
            res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True, timeout=10)
            resolved_url = res.url
        except Exception:
            pass
            
    # Matches B0xxxxxxxx or 10-digit ISBNs
    match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', resolved_url)
    if match:
        return match.group(1)
    return None

def find_trending_products(tag, num_links=5):
    print("==================================================")
    print("      AMAZON AUTOMATED FASHION TREND FINDER       ")
    print("==================================================")
    print(f"Targeting Amazon Tag: {tag}")
    
    already_processed = get_already_processed()
    print(f"Already processed ASINs: {len(already_processed)}")
    
    new_affiliate_links = []
    
    # Pick a random keyword to find fresh content
    keyword = random.choice(TREND_KEYWORDS)
    print(f"Selected search trend keyword: '{keyword}'")
    
    # Determine the correct base domain based on the affiliate tag
    domain = "amazon.in" if tag.endswith("-21") else "amazon.com"
    location_code = "110001" if domain == "amazon.in" else "10001"
    print(f"Using marketplace domain: {domain} with delivery code: {location_code}")
    
    # 1. Try Gemini with Google Search Grounding first (Highly reliable on cloud, bypasses CAPTCHA)
    print("Attempting to find trending products using Gemini with Google Search Grounding...")
    config = load_config()
    gemini_key = os.environ.get("GEMINI_API_KEY") or config.get("gemini_api_key", "")
    
    if gemini_key and not gemini_key.startswith("YOUR_"):
        try:
            from google import genai
            from google.genai import types
            
            client = genai.Client(api_key=gemini_key)
            prompt = f"""
            Find {num_links + 5} real, active product URLs for trending women's fashion items (related to '{keyword}') on Amazon {domain} (www.{domain}).
            Format the output as a valid JSON list of objects, where each object has "title" and "url".
            Return ONLY the raw JSON list, no markdown code block or extra explanation text.
            """
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                )
            )
            
            # Clean and parse the response text to find the JSON array
            text_response = response.text.strip()
            if "```json" in text_response:
                text_response = text_response.split("```json")[1].split("```")[0].strip()
            elif "```" in text_response:
                text_response = text_response.split("```")[1].split("```")[0].strip()
                
            try:
                products = json.loads(text_response)
                if isinstance(products, list):
                    count = 0
                    for p in products:
                        if count >= num_links:
                            break
                        url_val = p.get("url", "")
                        asin = extract_asin(url_val)
                        if asin and asin not in already_processed:
                            # Construct correct affiliate link
                            aff_url = f"https://www.{domain}/dp/{asin}/?tag={tag}"
                            new_affiliate_links.append(aff_url)
                            already_processed.add(asin)
                            print(f"Found new fashion item via Gemini Grounding: {asin} -> {aff_url}")
                            count += 1
                            
                    if new_affiliate_links:
                        print(f"Successfully retrieved {len(new_affiliate_links)} products using Gemini Grounding.")
                        return new_affiliate_links
            except Exception as parse_err:
                print(f"Failed to parse Gemini response as JSON: {parse_err}")
                print(f"Raw response: {text_response}")
        except Exception as api_err:
            print(f"Gemini Search Grounding method failed: {api_err}")
            
    # 2. Fallback to Playwright browser scraper if Gemini Grounding failed
    print("Falling back to Playwright browser scraper...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        context = browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1280, "height": 1000}
        )
        page = context.new_page()
        page.add_init_script("delete navigator.webdriver")
        
        try:
            # 1. Establish session and set delivery location
            print(f"Navigating to Amazon ({domain}) to set location...")
            page.goto(f"https://www.{domain}", wait_until="load")
            time.sleep(2)
            
            loc_btn = page.query_selector("#nav-global-location-popover-link")
            if loc_btn:
                loc_btn.click()
                time.sleep(2)
                zip_input = page.query_selector("#GLUXZipUpdateInput")
                if zip_input:
                    zip_input.fill(location_code)
                    time.sleep(1)
                    apply_btn = page.query_selector("#GLUXZipUpdate")
                    if apply_btn:
                        apply_btn.click()
                        time.sleep(2)
                        try:
                            page.click("text=Continue", timeout=2000)
                        except Exception:
                            try:
                                page.click(".a-popover-footer input", timeout=2000)
                            except Exception:
                                pass
                        time.sleep(2)
                        page.reload()
                        time.sleep(2)
                        
            # 2. Search for the keyword
            search_url = f"https://www.{domain}/s?k={urllib.parse.quote(keyword)}"
            print(f"Loading search page: {search_url}")
            page.goto(search_url, wait_until="load")
            time.sleep(3)
            
            # 3. Parse organic results
            results = page.query_selector_all("div[data-component-type='s-search-result']")
            print(f"Discovered {len(results)} search result cards.")
            
            count = 0
            for res in results:
                if count >= num_links:
                    break
                    
                # Skip sponsored
                sponsored = res.query_selector(".puis-sponsored-label-text")
                if sponsored:
                    continue
                    
                # Get ASIN directly from the element attribute
                asin = res.get_attribute("data-asin")
                if not asin or len(asin) != 10:
                    continue
                    
                # Check for duplicates
                if asin in already_processed:
                    continue
                    
                # Construct affiliate link
                aff_url = f"https://www.{domain}/dp/{asin}/?tag={tag}"
                new_affiliate_links.append(aff_url)
                already_processed.add(asin)
                print(f"Found new fashion item ASIN: {asin} -> {aff_url}")
                count += 1
        except Exception as playwright_err:
            print(f"Playwright scraping error: {playwright_err}")
        finally:
            browser.close()
        
    return new_affiliate_links

def main():
    config = load_config()
    tag = config.get("amazon_associates_tag")
    
    if not tag or "YOUR_" in tag:
        print("❌ Error: amazon_associates_tag is not configured in config.json.")
        print("Please edit config.json and add: 'amazon_associates_tag': 'designforyo0e-21'")
        sys.exit(1)
        
    try:
        new_links = find_trending_products(tag, num_links=5)
        
        if not new_links:
            print("\n⚠️ No new unique fashion items found in this run.")
            return
            
        # Append to queue
        print(f"\nAdding {len(new_links)} new affiliate links to {os.path.basename(QUEUE_PATH)}...")
        with open(QUEUE_PATH, "a", encoding="utf-8") as f:
            f.write("\n# Automatically added by Trend Finder\n")
            for link in new_links:
                f.write(f"{link}\n")
                
        print("✅ Queue updated successfully!")
        
    except Exception as e:
        print(f"❌ Error during Trend Finder run: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

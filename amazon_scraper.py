import os
import sys
import time
import urllib.parse
import requests
from bs4 import BeautifulSoup

# Configure stdout and stderr for UTF-8 to prevent encoding issues on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

class AmazonScraper:
    def __init__(self, temp_dir=TEMP_DIR):
        self.temp_dir = temp_dir
        
    def scrape_product(self, url):
        """
        Scrapes Amazon product page using Playwright to handle dynamic JS loading,
        downloads the main product image, takes a screenshot, and extracts details.
        """
        from playwright.sync_api import sync_playwright
        
        user_agent = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
        
        # Resolve short amzn.to links to their full form
        resolved_url = url
        if "amzn.to" in url:
            print(f"Resolving shortened link {url}...")
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                }
                res = requests.get(url, headers=headers, allow_redirects=True, timeout=15)
                resolved_url = res.url
                print(f"Resolved to: {resolved_url}")
            except Exception as e:
                print(f"Failed to resolve shortened link: {e}")
                
        print(f"Opening browser to scrape Amazon link: {resolved_url}")
        
        result = {
            "url": resolved_url,
            "title": "Premium Fashion Garment",
            "price": "",
            "image_path": None,
            "screenshot_path": None,
            "details": ""
        }
        
        parsed_url = urllib.parse.urlparse(resolved_url)
        clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        domain = parsed_url.netloc.lower()
        
        # We navigate directly to the resolved URL because natural query parameters help bypass robot checks.
        target_nav_url = resolved_url
        
        with sync_playwright() as p:
            # Launch chromium with realistic user-agent
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-web-security"
                ]
            )
            
            # Create a mobile device context to bypass robot check CAPTCHAs and load faster
            iphone = p.devices['iPhone 14 Pro']
            device_config = {**iphone, 'user_agent': user_agent}
            context = browser.new_context(**device_config)
            
            page = context.new_page()
            
            # Anti-detection scripts
            page.add_init_script("delete navigator.webdriver")
            
            try:
                # Navigate directly to the product page. Visiting the homepage first triggers aggressive bot checks.
                print(f"Navigating directly to product page: {target_nav_url}")
                page.goto(target_nav_url, timeout=45000, wait_until="load")
                time.sleep(4)
                
                # Check for "Continue shopping" form and click it to bypass bot wall
                page_title = page.title().strip()
                is_captcha = "captcha" in page_title.lower() or "robot" in page_title.lower() or page_title.lower() == "amazon.in" or page_title.lower() == "amazon.com"
                
                if is_captcha:
                    print("⚠️ Amazon CAPTCHA/Bot wall detected via page title. Attempting to bypass...")
                    for _ in range(2):
                        continue_btn = page.query_selector("text=Continue shopping") or page.query_selector("input[value='Continue shopping']") or page.query_selector("input[type='submit']")
                        if continue_btn:
                            print("🤖 Bot verification screen detected. Clicking 'Continue shopping' button...")
                            continue_btn.click()
                            time.sleep(4)
                            page_title = page.title().strip()
                            if not ("captcha" in page_title.lower() or "robot" in page_title.lower() or page_title.lower() == "amazon.in" or page_title.lower() == "amazon.com"):
                                is_captcha = False
                                break
                        else:
                            break
                
                if is_captcha:
                    print("❌ Playwright was blocked by CAPTCHA. Skipping screenshot and title parsing so it falls back or fails.")
                    raise RuntimeError("Playwright was blocked by Amazon CAPTCHA.")
                else:
                    # Take page screenshot
                    screenshot_path = os.path.join(self.temp_dir, "amazon_product_screenshot.png")
                    page.screenshot(path=screenshot_path, full_page=False)
                    result["screenshot_path"] = screenshot_path
                    print(f"Saved product screenshot to {screenshot_path}")
                    
                    # Extract Title (support both mobile and desktop title elements)
                    title_elem = page.query_selector("#title") or page.query_selector("#productTitle") or page.query_selector(".product-title")
                    if title_elem:
                        result["title"] = title_elem.inner_text().strip()
                    else:
                        # Fallback to page.title() but strip Amazon branding
                        if ":" in page_title:
                            parts = page_title.split(":", 1)
                            result["title"] = parts[1].strip()
                        else:
                            result["title"] = page_title
                    print(f"Product Title: {result['title']}")
                    
                    # Extract Price
                    price_elem = page.query_selector(".a-price .a-offscreen") or page.query_selector("#corePriceDisplay_desktop_feature_div .a-price-whole") or page.query_selector("#corePrice_desktop .a-price-whole") or page.query_selector(".priceToPay")
                    price = None
                    if price_elem:
                        price = price_elem.inner_text().strip()
                    result["price"] = price if price else ""
                    print(f"Product Price: {result['price']}")
                
                # Extract main image URL (support mobile #main-image and metadata og:image)
                img_url = None
                
                # Check meta tag first
                meta_img = page.query_selector('meta[property="og:image"]')
                if meta_img:
                    img_url = meta_img.get_attribute("content")
                    if img_url and "m.media-amazon.com" in img_url:
                        print(f"Discovered product main image URL via metadata: {img_url}")
                
                # Check mobile view main image element (#main-image)
                if not img_url:
                    mobile_img = page.query_selector("#main-image")
                    if mobile_img:
                        img_url = mobile_img.get_attribute("src")
                        print(f"Discovered product main image URL via mobile selector: {img_url}")
                
                # Desktop fallbacks
                if not img_url:
                    img_elem = page.query_selector("#landingImage")
                    if img_elem:
                        img_url = img_elem.get_attribute("src")
                        # Try to get high resolution version from data-old-hires or data-a-dynamic-image
                        hires = img_elem.get_attribute("data-old-hires")
                        if hires:
                            img_url = hires
                        else:
                            dynamic_img = img_elem.get_attribute("data-a-dynamic-image")
                            if dynamic_img:
                                try:
                                    import json
                                    img_dict = json.loads(dynamic_img)
                                    # The keys are image URLs and values are resolutions. Get the highest resolution.
                                    img_url = max(img_dict.keys(), key=lambda k: img_dict[k][0] * img_dict[k][1])
                                    print(f"Discovered product main image URL via dynamic-image: {img_url}")
                                except Exception:
                                    pass
                    
                    if not img_url:
                        # Fallback to book cover
                        book_img = page.query_selector("#imgBlkFront")
                        if book_img:
                            img_url = book_img.get_attribute("src")
                            print(f"Discovered product main image URL via book cover: {img_url}")
                
                # Download main image
                if img_url:
                    print(f"Discovered product main image URL: {img_url}")
                    img_data = requests.get(img_url, headers={"User-Agent": user_agent}, timeout=15).content
                    image_path = os.path.join(self.temp_dir, "amazon_product_image.jpg")
                    with open(image_path, "wb") as f:
                        f.write(img_data)
                    result["image_path"] = image_path
                    print(f"Downloaded main product image to {image_path}")
                else:
                    # If we couldn't get the image URL, crop the screenshot around the product image if possible
                    # Or use the screenshot itself as the image
                    result["image_path"] = screenshot_path
                    print("⚠️ Could not find main product image element. Using page screenshot as product image.")
                
                # Extract Features / Details
                details = []
                feature_bullets = page.query_selector("#feature-bullets")
                if feature_bullets:
                    bullet_list = feature_bullets.query_selector_all("li")
                    for bullet in bullet_list:
                        text = bullet.inner_text().strip()
                        if text:
                            details.append(text)
                            
                # If no features, try product description
                if not details:
                    desc_elem = page.query_selector("#productDescription")
                    if desc_elem:
                        details.append(desc_elem.inner_text().strip())
                        
                result["details"] = "\n".join(details)
                print(f"Extracted {len(details)} product details.")
                
            except Exception as e:
                print(f"Error scraping product with Playwright: {e}")
                # Save screenshot anyway if page was opened
                try:
                    screenshot_path = os.path.join(self.temp_dir, "amazon_product_screenshot_error.png")
                    page.screenshot(path=screenshot_path)
                    result["screenshot_path"] = screenshot_path
                except Exception:
                    pass
            finally:
                browser.close()
                
        # Final fallback if playwright failed and didn't download image
        if not result["image_path"]:
            print("⚠️ Playwright scraping failed to get product image. Trying standard request fallback...")
            self._scrape_fallback(clean_url, result)
            
        return result
        
    def _scrape_fallback(self, url, result):
        """Fallback scraper using requests and BeautifulSoup (non-JS)"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        # Try Google Translate proxy first (Highly effective at bypassing cloud IP CAPTCHAs)
        try:
            print("Attempting to crawl via Google Translate Web Proxy...")
            encoded_url = urllib.parse.quote(url)
            proxy_url = f"https://translate.google.com/translate?sl=auto&tl=en&u={encoded_url}"
            
            res = requests.get(proxy_url, headers=headers, timeout=20)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                
                # Check for content-frame iframe
                iframe = soup.find("iframe", id="content-frame") or soup.find("iframe", class_="content-frame")
                if iframe and iframe.get("src"):
                    print("Fetching iframe content from proxy...")
                    iframe_res = requests.get(iframe.get("src"), headers=headers, timeout=20)
                    if iframe_res.status_code == 200:
                        soup = BeautifulSoup(iframe_res.text, "html.parser")
                
                # Title
                title_elem = soup.find(id="productTitle") or soup.find(id="title")
                if title_elem:
                    result["title"] = title_elem.get_text().strip()
                    print(f"Proxy scraped Title: {result['title']}")
                
                # Price
                price_elem = soup.find(class_="a-price-whole") or soup.find(class_="a-offscreen") or soup.find(id="priceToPay")
                if price_elem:
                    result["price"] = price_elem.get_text().strip()
                    print(f"Proxy scraped Price: {result['price']}")
                
                # Image URL
                img_url = None
                img_elem = soup.find(id="landingImage") or soup.find(id="main-image")
                if img_elem:
                    img_url = img_elem.get("data-old-hires") or img_elem.get("src")
                if img_url:
                    print(f"Proxy scraped Image URL: {img_url}")
                    img_data = requests.get(img_url, headers=headers, timeout=15).content
                    image_path = os.path.join(self.temp_dir, "amazon_product_image_proxy.jpg")
                    with open(image_path, "wb") as f:
                        f.write(img_data)
                    result["image_path"] = image_path
                    result["screenshot_path"] = image_path
                    print("Proxy download successful!")
                    return  # Success! Exit fallback function early
        except Exception as proxy_err:
            print(f"Google Translate proxy crawler failed: {proxy_err}")
            
        # Last resort: Direct requests to Amazon (Usually blocked on cloud IPs)
        print("Proxy failed or blocked. Trying direct requests as last resort...")
        try:
            res = requests.get(url, headers=headers, timeout=15)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                
                # Title check for CAPTCHA
                title = soup.title.string.strip() if soup.title else ""
                if "captcha" in title.lower() or "robot" in title.lower() or title.lower() == "amazon.in" or title.lower() == "amazon.com":
                    print("❌ Fallback requests scraper blocked by CAPTCHA.")
                    return
                    
                title_elem = soup.find(id="productTitle")
                if title_elem:
                    result["title"] = title_elem.get_text().strip()
                
                # Price fallback
                price_elem = soup.find(class_="a-price-whole") or soup.find(class_="a-offscreen")
                result["price"] = price_elem.get_text().strip() if price_elem else ""
                
                # Main Image
                img_url = None
                img_elem = soup.find(id="landingImage")
                if img_elem:
                    img_url = img_elem.get("data-old-hires") or img_elem.get("src")
                        
                if img_url:
                    img_data = requests.get(img_url, headers=headers, timeout=15).content
                    image_path = os.path.join(self.temp_dir, "amazon_product_image_fallback.jpg")
                    with open(image_path, "wb") as f:
                        f.write(img_data)
                    result["image_path"] = image_path
                    result["screenshot_path"] = image_path
                    print("Fallback direct download successful!")
            else:
                print(f"Fallback requests returned status code: {res.status_code}")
        except Exception as ex:
            print(f"Fallback direct scraping error: {ex}")

if __name__ == "__main__":
    # Test script run
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
        scraper = AmazonScraper()
        res = scraper.scrape_product(test_url)
        print("\nScrape Result Summary:")
        print(f"Title: {res['title']}")
        print(f"Image Path: {res['image_path']}")
        print(f"Screenshot Path: {res['screenshot_path']}")
        print(f"Details length: {len(res['details'])}")

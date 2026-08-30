import os
import sys
import json
import urllib.request
import requests
import math
import time
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.genai import types

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(BASE_DIR, "assets", "fonts")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
os.makedirs(FONTS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# Helper to load config
def load_config():
    config_path = os.path.join(BASE_DIR, "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def download_font_if_missing(name, url):
    path = os.path.join(FONTS_DIR, name)
    if not os.path.exists(path):
        print(f"Downloading premium font '{name}' from Google Fonts...")
        try:
            urllib.request.urlretrieve(url, path)
            print(f"Font saved to {path}")
        except Exception as e:
            print(f"Failed to download font '{name}': {e}. Will fall back to system default.")
    return path

# Download premium fonts dynamically (Static fonts from verified URLs)
HEADER_BOLD_FONT_URL = "https://cdn.jsdelivr.net/npm/@expo-google-fonts/playfair-display@0.2.3/PlayfairDisplay_700Bold.ttf"
HEADER_REGULAR_FONT_URL = "https://cdn.jsdelivr.net/npm/@expo-google-fonts/playfair-display@0.2.3/PlayfairDisplay_400Regular.ttf"
HEADER_ITALIC_FONT_URL = "https://cdn.jsdelivr.net/npm/@expo-google-fonts/playfair-display@0.2.3/PlayfairDisplay_400Regular_Italic.ttf"
TEXT_BOLD_FONT_URL = "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf"
TEXT_REGULAR_FONT_URL = "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Regular.ttf"

def draw_vector_icon(draw, icon_name, cx, cy, color, bg_color=None):
    """Draws a custom fashion outline vector icon at the specified coordinates."""
    if bg_color:
        # Draw background circle
        r = 22
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=bg_color)
        
    icon_name = icon_name.lower()
    
    if "fabric" in icon_name or "leaf" in icon_name:
        # Leaf icon
        draw.line([(cx - 10, cy + 10), (cx + 10, cy - 10)], fill=color, width=2)
        draw.arc([cx - 8, cy - 12, cx + 12, cy + 8], 135, 315, fill=color, width=2)
        draw.arc([cx - 12, cy - 8, cx + 8, cy + 12], 315, 135, fill=color, width=2)
        
    elif "fit" in icon_name or "shirt" in icon_name or "hanger" in icon_name:
        # Hanger/Shirt icon
        draw.arc([cx - 3, cy - 12, cx + 3, cy - 6], 180, 360, fill=color, width=2)
        draw.line([(cx, cy - 6), (cx, cy - 2)], fill=color, width=2)
        draw.line([(cx, cy - 2), (cx - 12, cy + 6)], fill=color, width=2)
        draw.line([(cx, cy - 2), (cx + 12, cy + 6)], fill=color, width=2)
        draw.line([(cx - 12, cy + 6), (cx + 12, cy + 6)], fill=color, width=2)
        
    elif "stripe" in icon_name or "pattern" in icon_name or "wave" in icon_name:
        # Waves icon
        for dy in [-6, 0, 6]:
            points = []
            for dx in range(-12, 13, 2):
                y_val = cy + dy + int(3 * math.sin(dx * 0.35))
                points.append((cx + dx, y_val))
            draw.line(points, fill=color, width=2)
            
    elif "collar" in icon_name or "neck" in icon_name:
        # Collar icon
        draw.line([(cx - 12, cy - 8), (cx, cy + 4)], fill=color, width=2)
        draw.line([(cx + 12, cy - 8), (cx, cy + 4)], fill=color, width=2)
        draw.line([(cx - 12, cy - 8), (cx - 4, cy - 8)], fill=color, width=2)
        draw.line([(cx + 12, cy - 8), (cx + 4, cy - 8)], fill=color, width=2)
        draw.line([(cx - 4, cy - 8), (cx - 10, cy - 2)], fill=color, width=2)
        draw.line([(cx + 4, cy - 8), (cx + 10, cy - 2)], fill=color, width=2)
        draw.line([(cx - 10, cy - 2), (cx, cy + 4)], fill=color, width=2)
        draw.line([(cx + 10, cy - 2), (cx, cy + 4)], fill=color, width=2)
        
    elif "style" in icon_name or "versatile" in icon_name or "button" in icon_name:
        # Button/dots icon
        draw.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], outline=color, width=2)
        draw.ellipse([cx - 4, cy - 4, cx - 2, cy - 2], fill=color)
        draw.ellipse([cx + 2, cy - 4, cx + 4, cy - 2], fill=color)
        draw.ellipse([cx - 4, cy + 2, cx - 2, cy + 4], fill=color)
        draw.ellipse([cx + 2, cy + 2, cx + 4, cy + 4], fill=color)
        
    elif "briefcase" in icon_name or "office" in icon_name:
        # Briefcase
        draw.rectangle([cx - 10, cy - 6, cx + 10, cy + 8], outline=color, width=2)
        draw.arc([cx - 4, cy - 10, cx + 4, cy - 6], 180, 360, fill=color, width=2)
        
    elif "shopping" in icon_name or "casual" in icon_name:
        # Shopping Bag
        draw.polygon([(cx - 8, cy - 6), (cx + 8, cy - 6), (cx + 10, cy + 8), (cx - 10, cy + 8)], outline=color, width=2)
        draw.arc([cx - 4, cy - 10, cx + 4, cy - 4], 180, 360, fill=color, width=2)
        
    elif "coffee" in icon_name or "brunch" in icon_name or "cup" in icon_name:
        # Coffee Cup
        draw.arc([cx - 8, cy - 6, cx + 4, cy + 6], 0, 180, fill=color, width=2)
        draw.line([(cx - 8, cy - 6), (cx + 4, cy - 6)], fill=color, width=2)
        draw.arc([cx + 2, cy - 3, cx + 8, cy + 3], 270, 90, fill=color, width=2)
        
    elif "airplane" in icon_name or "travel" in icon_name or "vacation" in icon_name:
        # Airplane
        draw.line([(cx - 10, cy), (cx + 10, cy)], fill=color, width=2)
        draw.line([(cx - 2, cy - 8), (cx + 4, cy + 8)], fill=color, width=2)
        draw.line([(cx - 6, cy - 4), (cx - 6, cy + 4)], fill=color, width=2)
        
    else:
        draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=color)

class PosterGenerator:
    def __init__(self):
        self.config = load_config()
        self.gemini_key = os.environ.get("GEMINI_API_KEY") or self.config.get("gemini_api_key", "")
        self.openai_key = os.environ.get("OPENAI_API_KEY") or self.config.get("openai_api_key", "")
        
        # Initialize Gemini client
        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY is not configured in config.json or environment variables.")
        self.genai_client = genai.Client(api_key=self.gemini_key)
        
        # Download fonts
        self.header_bold_font_path = download_font_if_missing("PlayfairDisplay-Bold.ttf", HEADER_BOLD_FONT_URL)
        self.header_regular_font_path = download_font_if_missing("PlayfairDisplay-Regular.ttf", HEADER_REGULAR_FONT_URL)
        self.header_italic_font_path = download_font_if_missing("PlayfairDisplay-Italic.ttf", HEADER_ITALIC_FONT_URL)
        self.text_bold_font_path = download_font_if_missing("Montserrat-Bold.ttf", TEXT_BOLD_FONT_URL)
        self.text_regular_font_path = download_font_if_missing("Montserrat-Regular.ttf", TEXT_REGULAR_FONT_URL)

    def get_font(self, font_path, size, fallback_system_names):
        """Loads a font from the specified path, or falls back to system fonts, or default."""
        if font_path and os.path.exists(font_path):
            try:
                # Make sure the file is not empty or corrupted (e.g. 404 HTML download)
                if os.path.getsize(font_path) > 1000:
                    return ImageFont.truetype(font_path, size)
                else:
                    print(f"Font file {font_path} is too small, likely corrupted. Removing.")
                    os.remove(font_path)
            except Exception as e:
                print(f"Error loading font from {font_path}: {e}")
                
        # Try Windows system fonts
        windows_font_dir = "C:\\Windows\\Fonts"
        for name in fallback_system_names:
            path = os.path.join(windows_font_dir, name)
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    def generate_ad_copy(self, product_image_path, title, details, price=""):
        """Sends the Amazon product image, price and details to Gemini to extract features and write copy."""
        print("Sending product image and info to Gemini for copywriting and prompt extraction...")
        
        # Load the product image bytes
        with open(product_image_path, "rb") as f:
            image_data = f.read()
            
        image_part = types.Part.from_bytes(
            data=image_data,
            mime_type="image/jpeg"
        )
        
        prompt = f"""
        Analyze this fashion product image and these details:
        Product Title: {title}
        Product Details: {details}
        Product Price: {price}
        
        You are a luxury fashion copywriter and art director. Generate high-conversion Pinterest marketing ad copy and a text-to-image prompt for this product.
        Also determine an elegant matching color palette based on the clothing color in the image.
        
        Output MUST be in raw JSON format matching this schema:
        {{
            "headline": "A short, elegant, premium headline for the poster (2-4 words, capitalized, e.g. 'STRIPED STYLE' or 'FLORAL KURTI')",
            "subheading": "A stylish subheading to complement the headline (e.g. 'GREEN & CHETAN SHIRT for Every Occasion')",
            "features": [
                "Feature 1 title (e.g. 'PREMIUM FABRIC') | Short feature description (e.g. 'Soft, breathable & lightweight')",
                "Feature 2 title | Short feature description",
                "Feature 3 title | Short feature description",
                "Feature 4 title | Short feature description",
                "Feature 5 title | Short feature description"
            ],
            "occasions": ["Occasion 1", "Occasion 2", "Occasion 3"],
            "styling_tip": "A short styling tip (max 150 chars)",
            "pin_title": "SEO-friendly Pinterest Pin Title (max 100 chars)",
            "pin_description": "Engaging Pinterest Pin Description including 4-5 relevant hashtags (max 500 chars)",
            "board_name": "Recommended Pinterest Board name",
            "image_generation_prompt": "A highly detailed prompt for FLUX to generate a lifestyle model photo wearing this EXACT garment. You must automatically identify the product type, colors, patterns, fabric, fit, sleeves, neckline, and design details from the uploaded image and describe them in vivid detail: 'A realistic professional photo of a chic, elegant female model wearing this [describe the identified product type, colors, patterns, fabric, fit, sleeves, neckline, and design details exactly to keep it identical to the reference image]'. Describe the setting: 'standing in a minimal luxury interior with soft beige and cream tones, natural warm sunlight, ultra-realistic 4K editorial photography, looking like a premium fashion brand campaign, vertical composition.' Do not mention any text or graphic design in the prompt.",
            "background_color": "Hex code for a soft, light pastel background matching the garment's color palette (e.g. '#FAF8F5' or '#F3ECE3' or light green '#F0F5F1')",
            "primary_color": "Hex code for main headers, deep contrasting color (e.g. '#3D3025' or deep green '#2E5B3C')",
            "accent_color": "Hex code for minor details/lines (e.g. '#D2C4B4')",
            "cursive_label": "Delicate script label prefix (e.g. 'Effortless Elegance' or 'Timeless Elegance')",
            "badge_pills": ["CHIC", "COMFY", "CONFIDENT"],
            "style_looks": ["Office Wear", "Casual Look", "Brunch Date", "Weekend Vibes"],
            "short_fabric_desc": "Short 3-4 word fabric label (e.g. 'Soft Fabric. Trendy Look.')",
            "price_banner_text": "Text for the price/deal badge (e.g. 'ONLY \\u20b9499' or 'SPECIAL PRICE' or 'BESTSELLER 2026')"
        }}
        """
        
        # Retry with fallback model in case of rate limits or 503 UNAVAILABLE
        models_to_try = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-2.5-flash-lite']
        response = None
        last_error = None
        
        for model_name in models_to_try:
            print(f"Trying copywriting with model '{model_name}'...")
            for attempt in range(3):
                try:
                    response = self.genai_client.models.generate_content(
                        model=model_name,
                        contents=[image_part, prompt],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json"
                        )
                    )
                    break
                except Exception as e:
                    last_error = e
                    print(f"Attempt {attempt + 1} failed with model '{model_name}': {e}")
                    time.sleep(2)
            if response:
                break
                
        if not response:
            raise last_error
        
        try:
            ad_copy = json.loads(response.text.strip())
            print("Successfully received structured ad copy from Gemini.")
            return ad_copy
        except Exception as e:
            print(f"Error parsing Gemini JSON response: {e}")
            print(response.text)
            # Return basic fallback dict
            return {
                "headline": "ELEGANT FASHION",
                "subheading": "Premium quality style.",
                "features": [
                    "PREMIUM FABRIC | 100% Premium Material",
                    "ELEGANT FIT | Elegant & Stylish Fit",
                    "MAXIMUM COMFORT | Comfortable feel for all-day wear",
                    "VERSATILE | Style it your way",
                    "CLASSIC DETAILS | Timeless elements"
                ],
                "occasions": ["Casual", "Day Out", "Dinner"],
                "styling_tip": "Style it: Pair with neutral accessories for a classic look.",
                "pin_title": f"Elegant {title[:50]}",
                "pin_description": f"Shop this stunning {title}. Perfect addition to your wardrobe. #fashion #style #wardrobeessentials",
                "board_name": "Fashion Inspiration",
                "image_generation_prompt": f"A realistic professional photo of a chic female model wearing a premium outfit inspired by {title}, minimal luxury neutral background.",
                "background_color": "#FAF8F5",
                "primary_color": "#3D3025",
                "accent_color": "#D2C4B4",
                "cursive_label": "Timeless Elegance",
                "badge_pills": ["CHIC", "COMFY", "CLASSIC"],
                "style_looks": ["Office Wear", "Casual Look", "Brunch Date", "Weekend Vibes"],
                "short_fabric_desc": "Premium Quality. Timeless Style.",
                "price_banner_text": f"ONLY {price}" if price else "SPECIAL OFFER"
            }

    def generate_model_image(self, prompt):
        """Generates the model image trying Ideogram 4 first, falling back to other methods."""
        # 0. Try Ideogram 4 (Gradio Client)
        hf_token = os.environ.get("HF_TOKEN") or self.config.get("hf_token", "")
        if hf_token:
            print("Trying Ideogram 4 generation via Gradio Space...")
            try:
                import shutil
                from gradio_client import Client
                client = Client("ideogram-ai/ideogram4", token=hf_token)
                
                # Get the mode choice
                mode_val = "Default • 20 steps"
                try:
                    for comp in client.config.get("components", []):
                        choices = comp.get("props", {}).get("choices", [])
                        if choices and len(choices) >= 2:
                            resolved_choice = choices[1]
                            if isinstance(resolved_choice, (list, tuple)):
                                mode_val = resolved_choice[0]
                            else:
                                mode_val = resolved_choice
                            break
                except Exception:
                    pass
                    
                result = client.predict(
                    prompt=prompt,
                    mode=mode_val,
                    upsampler='Ideogram (remote)',
                    width=1024,
                    height=1536,
                    seed=0,
                    randomize_seed=True,
                    api_name="/generate"
                )
                output_image_path = result[0] if isinstance(result, (list, tuple)) else result
                if output_image_path and os.path.exists(output_image_path):
                    path = os.path.join(TEMP_DIR, "generated_model_image.png")
                    shutil.copy(output_image_path, path)
                    print(f"Success: Image generated via Ideogram 4 and saved to {path}")
                    return path
            except Exception as e:
                print(f"Ideogram 4 generation failed: {e}")

        # 1. Try Gemini Imagen 3 (Primary request choice)
        if self.gemini_key and not self.gemini_key.startswith("YOUR_"):
            print("Trying Gemini Imagen 3 generation...")
            models_to_try = ['imagen-3.0-generate-002', 'imagen-3.0-fast-generate-001', 'imagen-4.0-generate-001']
            for model_name in models_to_try:
                try:
                    response = self.genai_client.models.generate_images(
                        model=model_name,
                        prompt=prompt,
                        config=types.GenerateImagesConfig(
                            number_of_images=1,
                            aspect_ratio="3:4"
                        )
                    )
                    if response.generated_images:
                        img_bytes = response.generated_images[0].image.image_bytes
                        path = os.path.join(TEMP_DIR, "generated_model_image.png")
                        with open(path, "wb") as f:
                            f.write(img_bytes)
                        print(f"Success: Image generated via Gemini ({model_name})")
                        return path
                except Exception as e:
                    print(f"Gemini Imagen model '{model_name}' failed: {e}")

        # 2. Try Gradio Client with Hugging Face Space (Free, keyless FLUX.1-schnell)
        print("Attempting free image generation via Gradio (FLUX.1-schnell)...")
        try:
            try:
                import gradio_client
            except ImportError:
                print("gradio_client not found. Dynamic installation starting...")
                import subprocess
                subprocess.check_call([sys.executable, "-m", "pip", "install", "gradio_client"])
                import gradio_client

            from gradio_client import Client
            client = Client("black-forest-labs/FLUX.1-schnell")
            
            result = client.predict(
                prompt=prompt,
                seed=0,
                randomize_seed=True,
                width=768,
                height=1024,
                num_inference_steps=4,
                api_name="/infer"
            )
            image_path = result[0] if isinstance(result, (list, tuple)) else result
            
            if image_path and os.path.exists(image_path):
                path = os.path.join(TEMP_DIR, "generated_model_image.png")
                img = Image.open(image_path)
                img.save(path)
                print(f"Success: Image generated via Gradio and saved to {path}")
                return path
        except Exception as e:
            print(f"Gradio FLUX.1-schnell generation failed: {e}")

        # 3. Try Pollinations AI (Free, keyless Flux)
        print("Attempting free image generation via Pollinations AI...")
        try:
            import urllib.parse
            encoded_prompt = urllib.parse.quote(prompt)
            url = f"https://image.pollinations.ai/p/{encoded_prompt}?width=768&height=1024&model=flux&nologo=true"
            response = requests.get(url, timeout=35)
            if response.status_code == 200:
                path = os.path.join(TEMP_DIR, "generated_model_image.png")
                with open(path, "wb") as f:
                    f.write(response.content)
                # Verify image integrity
                img = Image.open(path)
                img.verify()
                print(f"Success: Image generated via Pollinations AI and saved to {path}")
                return path
            else:
                print(f"Pollinations AI returned status code {response.status_code}")
        except Exception as e:
            print(f"Pollinations AI generation failed: {e}")

        # 4. Try OpenAI DALL-E 3 (if paid key is configured)
        if self.openai_key and not self.openai_key.startswith("YOUR_"):
            print("Generating model image using OpenAI DALL-E 3...")
            url = "https://api.openai.com/v1/images/generations"
            headers = {
                "Authorization": f"Bearer {self.openai_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": "1024x1792",
                "quality": "standard"
            }
            try:
                res = requests.post(url, json=data, headers=headers, timeout=60)
                if res.status_code == 200:
                    img_url = res.json()["data"][0]["url"]
                    img_data = requests.get(img_url, timeout=15).content
                    path = os.path.join(TEMP_DIR, "generated_model_image.png")
                    with open(path, "wb") as f:
                        f.write(img_data)
                    return path
                else:
                    print(f"OpenAI DALL-E 3 Error: {res.text}")
            except Exception as e:
                print(f"Error generating image with DALL-E 3: {e}")

            # 5. Try OpenAI DALL-E 2 (Fallback)
            print("Trying OpenAI DALL-E 2 fallback...")
            data_dalle2 = {
                "model": "dall-e-2",
                "prompt": prompt,
                "n": 1,
                "size": "1024x1024"
            }
            try:
                res = requests.post(url, json=data_dalle2, headers=headers, timeout=60)
                if res.status_code == 200:
                    img_url = res.json()["data"][0]["url"]
                    img_data = requests.get(img_url, timeout=15).content
                    path = os.path.join(TEMP_DIR, "generated_model_image.png")
                    with open(path, "wb") as f:
                        f.write(img_data)
                    return path
                else:
                    print(f"OpenAI DALL-E 2 Error: {res.text}")
            except Exception as e:
                print(f"Error generating image with DALL-E 2: {e}")

        return None

    def compose_poster(self, ad_copy, product_image_path):
        """Assembles the final poster image with the product image kept full on the right side."""
        print("Composing ad poster with full product photo on the right...")
        
        # Dimensions: 1000 x 1500 (Vertical)
        W, H = 1000, 1500
        
        # Helper to validate hex colors returned by Gemini
        def validate_hex_color(hex_str, default):
            if not hex_str or not isinstance(hex_str, str):
                return default
            hex_str = hex_str.strip()
            if not hex_str.startswith("#"):
                hex_str = "#" + hex_str
            import re
            if re.match(r'^#[0-9a-fA-F]{3}$', hex_str) or re.match(r'^#[0-9a-fA-F]{6}$', hex_str):
                return hex_str
            return default
            
        def hex_to_rgba(hex_str, alpha=255):
            hex_str = hex_str.lstrip('#')
            if len(hex_str) == 3:
                hex_str = ''.join([c*2 for c in hex_str])
            r = int(hex_str[0:2], 16)
            g = int(hex_str[2:4], 16)
            b = int(hex_str[4:6], 16)
            return (r, g, b, alpha)
            
        bg_color = validate_hex_color(ad_copy.get("background_color"), "#FAF8F5")
        primary_color = validate_hex_color(ad_copy.get("primary_color"), "#3D3025")
        accent_color = validate_hex_color(ad_copy.get("accent_color"), "#D2C4B4")
        
        cursive_label = ad_copy.get("cursive_label", "Effortless Elegance")
        headline_text = ad_copy.get("headline", "PREMIUM LOOK").upper()
        badge_pills = ad_copy.get("badge_pills", ["CHIC", "COMFY", "CONFIDENT"])
        style_looks = ad_copy.get("style_looks", ["Office Wear", "Casual Look", "Brunch Date", "Weekend Vibes"])
        price_banner_text = ad_copy.get("price_banner_text", "SPECIAL OFFER")
        
        # Base poster with solid color background
        poster = Image.new("RGB", (W, H), bg_color)
        draw = ImageDraw.Draw(poster)
        
        # Load fonts
        font_cursive = self.get_font(self.header_italic_font_path, 32, ["georgiai.ttf", "timesi.ttf"])
        font_cursive_banner = self.get_font(self.header_italic_font_path, 28, ["georgiai.ttf", "timesi.ttf"])
        font_sub_part1 = self.get_font(self.header_bold_font_path, 22, ["georgiab.ttf", "timesbd.ttf"])
        font_sub_part2 = self.get_font(self.text_regular_font_path, 16, ["segoeui.ttf", "arial.ttf"])
        font_feat_title = self.get_font(self.text_bold_font_path, 15, ["segoeuib.ttf", "arialbd.ttf"])
        font_feat_desc = self.get_font(self.text_regular_font_path, 13, ["segoeui.ttf", "arial.ttf"])
        font_look_label = self.get_font(self.header_italic_font_path, 16, ["georgiai.ttf", "timesi.ttf"])
        
        # 1. Paste original product photo on the right (x=440 to 950, y=50 to 1100) - KEEP FULL
        right_x1, right_y1 = 440, 50
        right_x2, right_y2 = 950, 1100
        box_w = right_x2 - right_x1
        box_h = right_y2 - right_y1
        
        orig_product = None
        if product_image_path and os.path.exists(product_image_path):
            try:
                orig_product = Image.open(product_image_path)
                p_w, p_h = orig_product.size
                
                # Proportional resize to fill the box completely (crop-to-fill)
                ratio = max(box_w / p_w, box_h / p_h)
                new_w = int(p_w * ratio)
                new_h = int(p_h * ratio)
                
                resized_product = orig_product.resize((new_w, new_h), Image.Resampling.LANCZOS)
                
                # Crop center to match box dimensions
                crop_x1 = (new_w - box_w) // 2
                crop_y1 = (new_h - box_h) // 2
                crop_x2 = crop_x1 + box_w
                crop_y2 = crop_y1 + box_h
                
                cropped_product = resized_product.crop((crop_x1, crop_y1, crop_x2, crop_y2))
                
                poster.paste(cropped_product, (right_x1, right_y1))
                print(f"Pasted cropped product photo at ({right_x1}, {right_y1}) with size {cropped_product.size}")
            except Exception as e:
                print(f"Error drawing product photo: {e}")
                draw.rectangle([right_x1, right_y1, right_x2, right_y2], fill="#EAE5DC")
        else:
            draw.rectangle([right_x1, right_y1, right_x2, right_y2], fill="#EAE5DC")

        # 2. Draw Left Column Card & Bottom Card (opaque background matching bg_color)
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        
        # Card color: slightly lighter or darker than bg_color for clean separation
        rgba_card = hex_to_rgba(bg_color, 255) # Opaque
        rgba_accent = hex_to_rgba(accent_color, 255)
        rgba_primary = hex_to_rgba(primary_color, 255)
        
        # Left Side Card: houses title & features
        card_x1, card_y1 = 50, 50
        card_x2, card_y2 = 440, 1100
        overlay_draw.rectangle([card_x1, card_y1, card_x2, card_y2], fill=rgba_card)
        overlay_draw.rectangle([card_x1, card_y1, card_x2, card_y2], outline=rgba_accent, width=1)
        
        # Bottom Card: houses looks & occasions
        overlay_draw.rectangle([50, 1110, 950, 1435], fill=rgba_card)
        overlay_draw.rectangle([50, 1110, 950, 1435], outline=rgba_accent, width=1)
        
        # Bottom solid banner (y = 1445 to 1500)
        overlay_draw.rectangle([0, 1445, W, 1500], fill=rgba_primary)
        
        # Composite overlay
        poster = Image.alpha_composite(poster.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(poster)
        
        # 3. Draw Left Column Text & Features
        left_margin = 80
        
        # Cursive label
        draw.text((left_margin, 65), cursive_label, fill=primary_color, font=font_cursive)
        
        # Headline title wrapping
        title_font_size = 75
        font_title = self.get_font(self.header_bold_font_path, title_font_size, ["georgiab.ttf", "timesbd.ttf"])
        title_words = headline_text.split()
        title_lines = []
        current_line = []
        for w in title_words:
            current_line.append(w)
            test_line = " ".join(current_line)
            bbox = draw.textbbox((0, 0), test_line, font=font_title)
            if bbox[2] - bbox[0] > 330:
                current_line.pop()
                if current_line:
                    title_lines.append(" ".join(current_line))
                current_line = [w]
        if current_line:
            title_lines.append(" ".join(current_line))
            
        ty = 110
        for line in title_lines[:2]:
            line_font = font_title
            bbox = draw.textbbox((0, 0), line, font=line_font)
            if bbox[2] - bbox[0] > 330:
                temp_font_size = int(title_font_size * 330 / (bbox[2] - bbox[0]))
                line_font = self.get_font(self.header_bold_font_path, temp_font_size, ["georgiab.ttf", "timesbd.ttf"])
            
            draw.text((left_margin, ty), line, fill=primary_color, font=line_font)
            ty += 78
            
        badge_y = ty + 10
        
        # Tagline Pills
        pill_text = "  •  ".join(badge_pills).upper()
        font_pill = self.get_font(self.text_bold_font_path, 13, ["segoeuib.ttf", "arialbd.ttf"])
        pill_bbox = draw.textbbox((0, 0), pill_text, font=font_pill)
        pill_w = pill_bbox[2] - pill_bbox[0]
        pill_h = pill_bbox[3] - pill_bbox[1]
        
        rect_w = pill_w + 30
        rect_h = 32
        
        cap_x1 = left_margin
        cap_y1 = badge_y
        cap_x2 = left_margin + rect_w
        cap_y2 = badge_y + rect_h
        
        draw.ellipse([cap_x1, cap_y1, cap_x1 + rect_h, cap_y2], fill=primary_color)
        draw.ellipse([cap_x2 - rect_h, cap_y1, cap_x2, cap_y2], fill=primary_color)
        draw.rectangle([cap_x1 + rect_h // 2, cap_y1, cap_x2 - rect_h // 2, cap_y2], fill=primary_color)
        draw.text((cap_x1 + 15, cap_y1 + (rect_h - pill_h) // 2 - 2), pill_text, fill="#FFFFFF", font=font_pill)
        
        # Occasion Subheading
        sub_y = badge_y + 55
        raw_sub = ad_copy.get("subheading", "Premium clothing for Every Occasion")
        if "for Every Occasion" in raw_sub:
            part1 = raw_sub.split("for Every Occasion")[0].strip().upper()
            part2 = "for Every Occasion"
        else:
            part1 = raw_sub.upper()
            part2 = "for Every Occasion"
            
        sub_font_size = 20
        font_sub = self.get_font(self.header_bold_font_path, sub_font_size, ["georgiab.ttf", "timesbd.ttf"])
        bbox_sub = draw.textbbox((0, 0), part1, font=font_sub)
        sub_w = bbox_sub[2] - bbox_sub[0]
        if sub_w > 330:
            sub_font_size = int(sub_font_size * 330 / sub_w)
            font_sub = self.get_font(self.header_bold_font_path, sub_font_size, ["georgiab.ttf", "timesbd.ttf"])
            
        draw.text((left_margin, sub_y), part1, fill=primary_color, font=font_sub)
        draw.text((left_margin, sub_y + 28), part2, fill=primary_color, font=font_sub_part2)
        
        # Dot Separator line
        sep_y = sub_y + 60
        draw.line([(left_margin, sep_y), (left_margin + 100, sep_y)], fill=accent_color, width=1)
        cx_sep = left_margin + 117
        draw.ellipse([cx_sep - 4, sep_y - 4, cx_sep + 4, sep_y + 4], fill=primary_color)
        draw.line([(left_margin + 135, sep_y), (left_margin + 235, sep_y)], fill=accent_color, width=1)
        
        # Features List
        feat_start_y = sep_y + 25
        features = ad_copy.get("features", ["PREMIUM FABRIC | Soft & breathable", "COMFORT FIT | Styled for daily wear"])
        
        feat_y = feat_start_y
        icon_names = ["leaf", "collar", "waves", "fit", "style"]
        
        for idx, feat in enumerate(features[:5]):
            if "|" in feat:
                f_title, f_desc = feat.split("|", 1)
                f_title = f_title.strip().upper()
                f_desc = f_desc.strip()
            else:
                f_title = feat.strip().upper()
                f_desc = ""
                
            circle_x = left_margin + 20
            circle_y = feat_y + 20
            
            icon_name = icon_names[idx % len(icon_names)]
            for key in ["fabric", "leaf", "material"]:
                if key in f_title.lower(): icon_name = "leaf"
            for key in ["fit", "loose", "oversized"]:
                if key in f_title.lower(): icon_name = "fit"
            for key in ["stripe", "pattern", "wave", "bold"]:
                if key in f_title.lower(): icon_name = "waves"
            for key in ["collar", "neck"]:
                if key in f_title.lower(): icon_name = "collar"
                
            draw_vector_icon(draw, icon_name, circle_x, circle_y, "#FFFFFF", bg_color=primary_color)
            draw.text((left_margin + 55, feat_y), f_title, fill=primary_color, font=font_feat_title)
            
            desc_end_x = left_margin + 55
            if f_desc:
                desc_words = f_desc.split()
                desc_lines = []
                curr_line = []
                for w in desc_words:
                    curr_line.append(w)
                    test_l = " ".join(curr_line)
                    bbox = draw.textbbox((0, 0), test_l, font=font_feat_desc)
                    if bbox[2] - bbox[0] > 260:
                        curr_line.pop()
                        desc_lines.append(" ".join(curr_line))
                        curr_line = [w]
                if curr_line:
                    desc_lines.append(" ".join(curr_line))
                    
                desc_draw_y = feat_y + 18
                for line_idx, line in enumerate(desc_lines[:2]):
                    draw.text((left_margin + 55, desc_draw_y), line, fill="#2C3E2D", font=font_feat_desc)
                    bbox = draw.textbbox((0, 0), line, font=font_feat_desc)
                    line_w = bbox[2] - bbox[0]
                    if left_margin + 55 + line_w > desc_end_x:
                        desc_end_x = left_margin + 55 + line_w
                    desc_draw_y += 16
            else:
                t_bbox = draw.textbbox((0, 0), f_title, font=font_feat_title)
                desc_end_x = left_margin + 55 + (t_bbox[2] - t_bbox[0])
                
            # Dotted connector line
            dot_start_x = desc_end_x + 10
            dot_end_x = 410
            if dot_start_x < dot_end_x:
                for dx in range(int(dot_start_x), int(dot_end_x), 6):
                    draw.ellipse([dx - 1, feat_y + 20 - 1, dx + 1, feat_y + 20 + 1], fill=accent_color)
                    
            feat_y += 90

        # 4. Circular Sticker Badge (Moved to bottom of left card below features text)
        cx_stamp = 245
        cy_stamp = 980
        r_stamp = 85
        
        draw.ellipse([cx_stamp - r_stamp, cy_stamp - r_stamp, cx_stamp + r_stamp, cy_stamp + r_stamp], fill=primary_color)
        draw.ellipse([cx_stamp - r_stamp + 4, cy_stamp - r_stamp + 4, cx_stamp + r_stamp - 4, cy_stamp + r_stamp - 4], outline="#FFFFFF", width=1)
        
        font_stamp = self.get_font(self.text_bold_font_path, 12, ["segoeuib.ttf", "arialbd.ttf"])
        stamp_lines = [
            ("Soft Fabric.", font_stamp),
            ("Trendy Look.", font_stamp),
            ("Perfect You.", font_stamp)
        ]
        
        sy = cy_stamp - 27
        for line_txt, line_font in stamp_lines:
            lbl_bbox = draw.textbbox((0, 0), line_txt, font=line_font)
            lbl_w = lbl_bbox[2] - lbl_bbox[0]
            draw.text((cx_stamp - lbl_w // 2, sy), line_txt, fill="#FFFFFF", font=line_font)
            sy += 18

        # 5. Style It Your Way Section (inside the bottom card)
        style_y = 1120
        style_text = "STYLE IT YOUR WAY"
        style_bbox = draw.textbbox((0, 0), style_text, font=font_cursive_banner)
        style_w = style_bbox[2] - style_bbox[0]
        style_cx = W // 2
        
        draw.text((style_cx - style_w // 2, style_y), style_text, fill=primary_color, font=font_cursive_banner)
        draw.line([(60, style_y + 16), (style_cx - style_w // 2 - 20, style_y + 16)], fill=accent_color, width=1)
        draw.line([(style_cx + style_w // 2 + 20, style_y + 16), (940, style_y + 16)], fill=accent_color, width=1)
        
        # Grid of 4 Look Cards (cropped from original product image)
        card_w, card_h = 135, 185
        gap = 15
        card_start_y = style_y + 40
        
        # Ensure we have at least 4 looks to prevent empty cards
        looks_list = list(style_looks)
        default_looks = ["Office Wear", "Casual Look", "Brunch Date", "Weekend Vibes"]
        while len(looks_list) < 4:
            looks_list.append(default_looks[len(looks_list) % len(default_looks)])
            
        for i, look_name in enumerate(looks_list[:4]):
            cx = 50 + i * (card_w + gap)
            cy = card_start_y
            
            draw.rectangle([cx - 4, cy - 4, cx + card_w + 4, cy + card_h + 4], outline=accent_color, width=1)
            draw.rectangle([cx - 1, cy - 1, cx + card_w + 1, cy + card_h + 1], outline=accent_color, width=1)
            
            if orig_product:
                ow, oh = orig_product.size
                if i == 0:
                    crop_box = (0, 0, ow, int(oh * 0.65))
                elif i == 1:
                    crop_box = (int(ow * 0.1), int(oh * 0.15), int(ow * 0.9), int(oh * 0.8))
                elif i == 2:
                    crop_box = (int(ow * 0.2), int(oh * 0.2), int(ow * 0.8), int(oh * 0.55))
                else:
                    crop_box = (int(ow * 0.05), int(oh * 0.05), int(ow * 0.95), int(oh * 0.95))
                    
                crop_img = orig_product.crop(crop_box)
                crop_img = crop_img.resize((card_w, card_h), Image.Resampling.LANCZOS)
                poster.paste(crop_img, (cx, cy))
            else:
                draw.rectangle([cx, cy, cx + card_w, cy + card_h], fill="#EAE5DC")
                
            lbl_y = cy + card_h + 10
            lbl_bbox = draw.textbbox((0, 0), look_name, font=font_look_label)
            lbl_w = lbl_bbox[2] - lbl_bbox[0]
            draw.text((cx + (card_w - lbl_w) // 2, lbl_y), look_name, fill=primary_color, font=font_look_label)
            
        # Fabric Showcase Card
        fabric_card_x = 680
        fabric_card_y = card_start_y
        fabric_card_w = 270
        fabric_card_h = 220
        
        draw.rectangle([fabric_card_x - 4, fabric_card_y - 4, fabric_card_x + fabric_card_w + 4, fabric_card_y + fabric_card_h + 4], outline=accent_color, width=1)
        draw.rectangle([fabric_card_x - 1, fabric_card_y - 1, fabric_card_x + fabric_card_w + 1, fabric_card_y + fabric_card_h + 1], outline=accent_color, width=1)
        
        if orig_product:
            ow, oh = orig_product.size
            crop_box = (int(ow * 0.35), int(oh * 0.4), int(ow * 0.65), int(oh * 0.7))
            crop_img = orig_product.crop(crop_box)
            crop_img = crop_img.resize((fabric_card_w, fabric_card_h), Image.Resampling.LANCZOS)
            poster.paste(crop_img, (fabric_card_x, fabric_card_y))
        else:
            draw.rectangle([fabric_card_x, fabric_card_y, fabric_card_x + fabric_card_w, fabric_card_y + fabric_card_h], fill="#EAE5DC")
            
        lbl_box_h = 55
        lbl_box_y = fabric_card_y + fabric_card_h - lbl_box_h
        draw.rectangle([fabric_card_x, lbl_box_y, fabric_card_x + fabric_card_w, fabric_card_y + fabric_card_h], fill=bg_color)
        
        font_fabric_title = self.get_font(self.text_bold_font_path, 12, ["segoeuib.ttf", "arialbd.ttf"])
        font_fabric_desc = self.get_font(self.text_regular_font_path, 11, ["segoeui.ttf", "arial.ttf"])
        
        f_title_text = "PREMIUM FABRIC"
        f_desc_text = "Soft • Breathable • Lightweight"
        
        t_bbox = draw.textbbox((0, 0), f_title_text, font=font_fabric_title)
        t_w = t_bbox[2] - t_bbox[0]
        draw.text((fabric_card_x + (fabric_card_w - t_w) // 2, lbl_box_y + 8), f_title_text, fill=primary_color, font=font_fabric_title)
        
        d_bbox = draw.textbbox((0, 0), f_desc_text, font=font_fabric_desc)
        d_w = d_bbox[2] - d_bbox[0]
        draw.text((fabric_card_x + (fabric_card_w - d_w) // 2, lbl_box_y + 28), f_desc_text, fill=primary_color, font=font_fabric_desc)

        # 6. Occasions Section
        occ_y = 1380
        occ_title = "PERFECT FOR EVERY OCCASION"
        occ_font_title = self.get_font(self.text_bold_font_path, 12, ["segoeuib.ttf", "arialbd.ttf"])
        
        occ_bbox = draw.textbbox((0, 0), occ_title, font=occ_font_title)
        occ_w = occ_bbox[2] - occ_bbox[0]
        draw.text((W // 2 - occ_w // 2, occ_y), occ_title, fill=primary_color, font=occ_font_title)
        
        occ_items = [
            ("Office Wear", "briefcase"),
            ("Casual Outings", "shopping"),
            ("Brunch Dates", "coffee"),
            ("Travel & Vacations", "airplane"),
            ("Everyday Wear", "hanger")
        ]
        
        item_w = 140
        num_items = len(occ_items)
        spacing = (900 - num_items * item_w) // (num_items - 1)
        font_occ_lbl = self.get_font(self.text_regular_font_path, 10, ["segoeui.ttf", "arial.ttf"])
        
        for idx, (lbl, icon_type) in enumerate(occ_items):
            item_cx = 50 + idx * (item_w + spacing) + item_w // 2
            item_cy = occ_y + 30
            draw_vector_icon(draw, icon_type, item_cx - 45, item_cy, primary_color)
            draw.text((item_cx - 30, item_cy - 6), lbl, fill=primary_color, font=font_occ_lbl)

        # 7. Bottom solid footer banner
        footer_y = 1445
        footer_h = 55
        draw.rectangle([0, footer_y, W, footer_y + footer_h], fill=primary_color)
        
        footer_text = "TIMELESS STYLE  •  MADE FOR YOU"
        font_footer = self.get_font(self.text_bold_font_path, 14, ["segoeuib.ttf", "arialbd.ttf"])
        f_bbox = draw.textbbox((0, 0), footer_text, font=font_footer)
        f_w = f_bbox[2] - f_bbox[0]
        f_h = f_bbox[3] - f_bbox[1]
        
        draw.text((W // 2 - f_w // 2, footer_y + (footer_h - f_h) // 2 - 2), footer_text, fill="#FFFFFF", font=font_footer)
        
        # Save poster
        output_path = os.path.join(TEMP_DIR, "final_pinterest_ad.png")
        poster.save(output_path, "PNG")
        print(f"Successfully generated Mode B poster image at: {output_path}")
        return output_path

    def process_url(self, image_path, title, details, price=""):
        """E2E workflow for generating copy and poster using the product image directly or via AI centerpiece."""
        copy = self.generate_ad_copy(image_path, title, details, price)
        
        use_ai = self.config.get("use_ai_centerpiece", False)
        if use_ai:
            print("use_ai_centerpiece is enabled. Generating model centerpiece...")
            prompt = copy.get("image_generation_prompt")
            # Generate clean model photo
            generated_img = self.generate_model_image(prompt)
            if generated_img and os.path.exists(generated_img):
                print(f"Using generated model image: {generated_img}")
                poster_path = self.compose_poster(copy, generated_img)
                return copy, poster_path
            else:
                print("Failed to generate model image. Falling back to original product photo.")
                
        # Bypasses AI image generation to keep the actual product image 100% identical
        poster_path = self.compose_poster(copy, image_path)
        return copy, poster_path

if __name__ == "__main__":
    if len(sys.argv) > 2:
        img_path = sys.argv[1]
        p_title = sys.argv[2]
        p_details = sys.argv[3] if len(sys.argv) > 3 else "Details not provided"
        
        gen = PosterGenerator()
        ad, post_path = gen.process_url(img_path, p_title, p_details)
        print("\nPoster generation test run completed.")
        print(f"Board name suggestion: {ad.get('board_name')}")
        print(f"Pin Title: {ad.get('pin_title')}")
        print(f"Pin Description: {ad.get('pin_description')}")

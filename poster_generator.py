import os
import sys
import json
import re
import urllib.request
import requests
import time
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.genai import types

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(BASE_DIR, "assets", "fonts")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
os.makedirs(FONTS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# User's actual Pinterest boards for smart niche indexing
AVAILABLE_BOARDS = [
    "Contemporary Indian Fashion | Desi Outfit Inspo",
    "Traditional Indian Fashion | Outfit Inspiration",
    "Soft Desi Aesthetic",
    "Minimal Style Outfit Ideas",
    "Neutral Outfit Ideas",
    "Capsule Wardrobe Essentials",
    "Chic style",
    "Summer Date Night Outfits",
    "Summer Vacay Packing",
    "Korean Summer dress 2026",
    "Korean fashion outfit ideas",
    "Korean outfit ideas",
    "Korean summer outfit",
    "Korean Summer Outfits 2026",
    "K-Style Office",
    "Korean Beach Outfits Made Simple",
    "Pastel Style | Spring/Summer Fashion",
    "Monochromic Chic",
    "Denim Daily Style Inspo",
    "Elegant Women's Dress",
    "Fashion Aesthetic",
    "Cafe Outfit Ideas 2026",
    "Rainy Day outfits"
]

def load_config():
    config_path = os.path.join(BASE_DIR, "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def clean_ascii(text):
    """Strips non-ascii chars to avoid missing glyphs on PIL text rendering."""
    return re.sub(r'[^\x20-\x7E]', '', text).strip()

def download_font_if_missing(name, url):
    path = os.path.join(FONTS_DIR, name)
    if not os.path.exists(path):
        try:
            urllib.request.urlretrieve(url, path)
        except Exception as e:
            print(f"Failed to download font '{name}': {e}. Will fall back to system default.")
    return path

HEADER_BOLD_FONT_URL = "https://cdn.jsdelivr.net/npm/@expo-google-fonts/playfair-display@0.2.3/PlayfairDisplay_700Bold.ttf"
HEADER_REGULAR_FONT_URL = "https://cdn.jsdelivr.net/npm/@expo-google-fonts/playfair-display@0.2.3/PlayfairDisplay_400Regular.ttf"
HEADER_ITALIC_FONT_URL = "https://cdn.jsdelivr.net/npm/@expo-google-fonts/playfair-display@0.2.3/PlayfairDisplay_400Regular_Italic.ttf"
TEXT_BOLD_FONT_URL = "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf"
TEXT_REGULAR_FONT_URL = "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Regular.ttf"

class PosterGenerator:
    def __init__(self):
        self.config = load_config()
        self.gemini_key = os.environ.get("GEMINI_API_KEY") or self.config.get("gemini_api_key", "")
        self.openai_key = os.environ.get("OPENAI_API_KEY") or self.config.get("openai_api_key", "")
        
        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY is not configured in config.json or environment variables.")
        self.genai_client = genai.Client(api_key=self.gemini_key)
        
        # Download fonts
        self.header_bold_font_path = download_font_if_missing("PlayfairDisplay-Bold.ttf", HEADER_BOLD_FONT_URL)
        self.header_regular_font_path = download_font_if_missing("PlayfairDisplay-Regular.ttf", HEADER_REGULAR_FONT_URL)
        self.header_italic_font_path = download_font_if_missing("PlayfairDisplay-Italic.ttf", HEADER_ITALIC_FONT_URL)
        self.text_bold_font_path = download_font_if_missing("Montserrat-Bold.ttf", TEXT_BOLD_FONT_URL)
        self.text_regular_font_path = download_font_if_missing("Montserrat-Regular.ttf", TEXT_REGULAR_FONT_URL)

    def get_font(self, font_path, size, fallback_system_names=None):
        if fallback_system_names is None:
            fallback_system_names = ["georgia.ttf", "arial.ttf"]
            
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                pass
                
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
        """Sends product image and info to Gemini to generate high-CTR organic Pinterest copy."""
        print("Analyzing garment with Gemini for high-CTR organic Pinterest copywriting...")
        
        with open(product_image_path, "rb") as f:
            image_data = f.read()
            
        image_part = types.Part.from_bytes(
            data=image_data,
            mime_type="image/jpeg"
        )
        
        boards_list = "\n".join(f"- {b}" for b in AVAILABLE_BOARDS)
        
        prompt = f"""
Analyze this fashion product image and details:
Product Title: {title}
Product Details: {details}
Product Price: {price}

You are a top viral Pinterest fashion lookbook creator.
Generate organic, high-engagement Pinterest content that feels like an authentic aesthetic fashion post, NOT an advertisement.

Available Pinterest Boards:
{boards_list}

Select the SINGLE best matching board from the list above based on the garment style (ethnic/kurti -> Indian/Desi boards; casual/minimal dresses -> Minimal/Korean/Vacation boards).

Output strictly in raw JSON format:
{{
    "aesthetic_hook": "Short aesthetic title in title case or lowercase (2-4 words, e.g. 'Effortless Earthy Chic', 'The Viral Linen Dress', 'Minimalist Summer Styling')",
    "subheading": "Concise 3-5 word garment descriptor (e.g. 'Sleeveless Kurta & Palazzo Set', 'Tiered Floral Midi Dress', 'Cotton Blend Co-Ord Set')",
    "curator_tag": "Aesthetic capsule tag for the top corner (e.g. 'OUTFIT INSPO 2026', 'SUMMER LOOKBOOK', 'CASUAL CHIC', 'DESI STYLE INSPO')",
    "pin_title": "High-CTR, human Pinterest search title (max 75 chars). Format: [Aesthetic Hook / Outfit Inspo] | [Garment Name]. Do NOT include long Amazon keyword lists, brand names, or multiple pipes.",
    "pin_description": "Engaging micro-blog description written in an inspiring fashion curator voice (150-250 chars). Describe the silhouette, fabric feel, occasions to wear, and quick styling advice (shoes/bag). End with a clear call to action: 'Tap link to view details & shop this look on Amazon ✨ Save to your board for inspo 📌'. Include 6-8 targeted hashtags like #outfitinspo #chiclook #summerfashion #kurtaset #stylingideas #amazonfinds.",
    "board_name": "Must be the exact board name chosen from the Available Pinterest Boards list above"
}}
"""
        models_to_try = ['gemini-2.5-flash', 'gemini-1.5-flash']
        response = None
        last_error = None
        
        for model_name in models_to_try:
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
                    time.sleep(2)
            if response:
                break
                
        if not response:
            raise last_error or RuntimeError("Gemini failed to generate copy")
            
        try:
            ad_copy = json.loads(response.text.strip())
            print(f"Generated Organic Hook: '{ad_copy.get('aesthetic_hook')}'")
            print(f"Mapped to Board: '{ad_copy.get('board_name')}'")
            return ad_copy
        except Exception as e:
            print(f"Error parsing Gemini response: {e}")
            return {
                "aesthetic_hook": "Effortless Chic Look",
                "subheading": "Casual Summer Outfit",
                "curator_tag": "OUTFIT INSPO 2026",
                "pin_title": "Effortless Summer Outfit Inspo | Casual Chic Style",
                "pin_description": "Effortless daily style for work, weekend brunches, or coffee dates ✨ Tap link to shop this exact look on Amazon! 🤍 #outfitinspo #summerfashion #chicstyle",
                "board_name": "Capsule Wardrobe Essentials"
            }

    def compose_poster(self, ad_copy, product_image_path):
        """
        Assembles an organic, aesthetic Pinterest pin (1000x1500 px, 2:3 ratio).
        High-impact full-bleed hero visual with floating frosted glass typography card.
        """
        print("Composing high-converting organic Pinterest pin...")
        W, H = 1000, 1500
        
        orig = Image.open(product_image_path).convert("RGB")
        pw, ph = orig.size

        # Cover scaling: crop-to-fill 1000x1500
        ratio = max(W / pw, H / ph)
        nw, nh = int(pw * ratio), int(ph * ratio)
        resized = orig.resize((nw, nh), Image.Resampling.LANCZOS)
        cx = (nw - W) // 2
        cy = (nh - H) // 2
        poster = resized.crop((cx, cy, cx + W, cy + H))

        # Soft dark ambient gradient at bottom so the badge stands out gracefully
        gradient = Image.new("RGBA", (W, 380), (0, 0, 0, 0))
        g_draw = ImageDraw.Draw(gradient)
        for y in range(380):
            alpha = int(135 * (y / 380.0) ** 1.6)
            g_draw.line([(0, y), (W, y)], fill=(18, 14, 12, alpha))
        poster.paste(gradient, (0, H - 380), gradient)

        # Sanitize text for crisp rendering on PIL
        hook_raw = ad_copy.get("aesthetic_hook") or "Effortless Chic"
        sub_raw = ad_copy.get("subheading") or "Casual Daily Outfit"
        tag_raw = ad_copy.get("curator_tag") or "OUTFIT INSPO 2026"

        hook_clean = clean_ascii(hook_raw)
        sub_clean = clean_ascii(sub_raw).upper()
        tag_clean = clean_ascii(tag_raw).upper()

        font_hook = self.get_font(self.header_italic_font_path, 42, ["georgiai.ttf", "timesi.ttf"])
        font_sub = self.get_font(self.text_bold_font_path, 15, ["segoeuib.ttf", "arialbd.ttf"])
        font_tag = self.get_font(self.text_bold_font_path, 12, ["segoeuib.ttf", "arialbd.ttf"])

        draw = ImageDraw.Draw(poster)

        # Measure text for the floating badge
        hook_bbox = draw.textbbox((0, 0), hook_clean, font=font_hook)
        hw, hh = hook_bbox[2] - hook_bbox[0], hook_bbox[3] - hook_bbox[1]

        sub_full = f"{sub_clean}  •  TAP TO SHOP"
        sub_bbox = draw.textbbox((0, 0), sub_full, font=font_sub)
        sw, sh = sub_bbox[2] - sub_bbox[0], sub_bbox[3] - sub_bbox[1]

        badge_w = min(max(hw, sw) + 80, W - 80)
        badge_h = hh + sh + 46
        badge_x = (W - badge_w) // 2
        badge_y = H - badge_h - 60

        # Floating frosted glassmorphic card
        glass = Image.new("RGBA", (badge_w, badge_h), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glass)
        gdraw.rounded_rectangle(
            [0, 0, badge_w, badge_h],
            radius=22,
            fill=(255, 253, 250, 235),
            outline=(215, 205, 195, 210),
            width=2
        )
        poster.paste(glass, (badge_x, badge_y), glass)

        # Draw typography inside glass badge
        draw = ImageDraw.Draw(poster)
        draw.text((badge_x + (badge_w - hw) // 2, badge_y + 14), hook_clean, fill="#2A201C", font=font_hook)
        draw.text((badge_x + (badge_w - sw) // 2, badge_y + 14 + hh + 10), sub_full, fill="#7A685D", font=font_sub)

        # Minimal curator watermark in top-left
        tag_bbox = draw.textbbox((0, 0), tag_clean, font=font_tag)
        tw, th = tag_bbox[2] - tag_bbox[0], tag_bbox[3] - tag_bbox[1]
        tag_glass = Image.new("RGBA", (tw + 26, th + 14), (0, 0, 0, 0))
        tdraw = ImageDraw.Draw(tag_glass)
        tdraw.rounded_rectangle([0, 0, tw + 26, th + 14], radius=10, fill=(255, 255, 255, 215))
        poster.paste(tag_glass, (40, 40), tag_glass)

        draw = ImageDraw.Draw(poster)
        draw.text((53, 47), tag_clean, fill="#3D3028", font=font_tag)

        # Save poster
        output_path = os.path.join(TEMP_DIR, "final_pinterest_ad.png")
        poster.save(output_path, "PNG", quality=95)
        print(f"Successfully generated Organic Pinterest Pin at: {output_path}")
        return output_path

    def process_url(self, image_path, title, details, price=""):
        """E2E workflow for generating organic copy and aesthetic pin."""
        copy = self.generate_ad_copy(image_path, title, details, price)
        poster_path = self.compose_poster(copy, image_path)
        return copy, poster_path

if __name__ == "__main__":
    if len(sys.argv) > 2:
        img_path = sys.argv[1]
        p_title = sys.argv[2]
        p_details = sys.argv[3] if len(sys.argv) > 3 else ""
        gen = PosterGenerator()
        ad, post_path = gen.process_url(img_path, p_title, p_details)
        print(f"\nTitle: {ad.get('pin_title')}")
        print(f"Board: {ad.get('board_name')}")
        print(f"Pin saved to: {post_path}")

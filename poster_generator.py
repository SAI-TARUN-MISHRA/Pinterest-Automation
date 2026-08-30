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
    if not text:
        return ""
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
        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY is not configured in config.json or environment variables.")
        self.genai_client = genai.Client(api_key=self.gemini_key)
        
        # Download required fonts
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
        """Sends product image and info to Gemini to generate high-performing viral lookbook copy."""
        print("Analyzing garment with Gemini for high-conversion viral lookbook editorial copy...")
        
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

You are an art director and copywriter for a luxury fashion editorial lookbook (like Zara, Massimo Dutti, or Vogue).
Generate editorial content matching the exact aesthetic of our top viral pins (e.g. 'Effortless Sophistication: Chic Houndstooth Cowl Neck Top for Everyday Elegance').

Available Pinterest Boards:
{boards_list}

Select the SINGLE best matching board from the list above based on the garment style (ethnic/kurti -> Indian/Desi boards; dresses -> Korean/Dress/Vacation boards; neutral essentials -> Minimal/Neutral boards).

Output strictly in raw JSON format:
{{
    "headline_word1": "First luxury headline word in Title Case (e.g. 'Effortless', 'Timeless', 'Understated', 'Modern')",
    "headline_word2": "Second luxury headline word to be rendered in elegant cursive script (e.g. 'Sophistication', 'Elegance', 'Simplicity', 'Grace', 'Chic')",
    "tagline": "3-word punchy aesthetic descriptor separated by dots (e.g. 'Soft. Stylish. Timeless.', 'Breezy. Chic. Versatile.', 'Refined. Minimal. Effortless.')",
    "sub_desc": "Short, evocative 1-sentence description (max 50 chars, e.g. 'Designed to elevate your every day.')",
    "feature_title": "Key garment/fabric feature (2-4 words, e.g. 'Breathable Rayon Viscose', 'Soft Spun Knit Fabric', 'Relaxed Straight Silhouette')",
    "feature_sub": "Benefit callout for the feature (e.g. 'for All-Day Comfort', 'with Flattering Fluid Drape', 'for Easy Day-to-Night Wear')",
    "accent_color": "Hex color that matches the garment's palette (e.g. warm caramel '#8A6447', forest '#2E5B3C', navy '#2A3F54', berry '#6B2D42')",
    "pin_title": "High-CTR, viral Pinterest title (max 75 chars). Format: [Headline Word 1] [Headline Word 2]: [Chic Garment Name] for [Occasion/Style Inspo]. Do NOT include long Amazon keyword lists, brand names, or multiple pipes.",
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
            print(f"Generated Headline: '{ad_copy.get('headline_word1')} {ad_copy.get('headline_word2')}'")
            print(f"Mapped to Board: '{ad_copy.get('board_name')}'")
            return ad_copy
        except Exception as e:
            print(f"Error parsing Gemini response: {e}")
            return {
                "headline_word1": "Effortless",
                "headline_word2": "Sophistication",
                "tagline": "Soft. Stylish. Timeless.",
                "sub_desc": "Designed to elevate your every day.",
                "feature_title": "Soft Breathable Fabric",
                "feature_sub": "for All-Day Comfort",
                "accent_color": "#8A6447",
                "pin_title": "Effortless Sophistication: Everyday Chic Outfit Ideas",
                "pin_description": "Effortless daily style for work, weekend brunches, or coffee dates ✨ Tap link to shop this exact look on Amazon! 🤍 #outfitinspo #summerfashion #chicstyle",
                "board_name": "Capsule Wardrobe Essentials"
            }

    def compose_poster(self, ad_copy, product_image_path):
        """
        Assembles a viral lookbook pin matching the exact aesthetic of viral_top.jpg:
        - Full-height model presentation on the right
        - Seamless editorial atmosphere on the left with clean negative space
        - Luxury typography (Playfair Regular + Cursive Italic)
        - Thin divider with decorative dot
        - Tagline & lifestyle description
        - Bottom-left curved arch with delicate circular emblem & fabric/comfort callout
        - High-intent Amazon shopping CTA
        """
        print("Composing viral lookbook pin (Effortless Sophistication aesthetic)...")
        W, H = 1000, 1500
        
        orig = Image.open(product_image_path).convert("RGB")
        pw, ph = orig.size

        # Resize product photo to fill canvas height
        ratio = H / ph
        nw, nh = int(pw * ratio), int(ph * ratio)
        resized_photo = orig.resize((nw, nh), Image.Resampling.LANCZOS)

        # Sample edge color for seamless background
        corner_pixel = resized_photo.getpixel((15, 15))
        bg_color = (
            min(250, max(232, corner_pixel[0])),
            min(247, max(228, corner_pixel[1])),
            min(242, max(222, corner_pixel[2]))
        )
        poster = Image.new("RGB", (W, H), bg_color)

        # Center the subject gracefully around x=720
        if nw >= W:
            photo_x = max(W - nw, min(0, 720 - (nw // 2)))
        else:
            photo_x = max(0, W - nw - 20)
        poster.paste(resized_photo, (photo_x, 0))

        # Feather the left edge so typography has 100% clean background
        feather_w = 460
        feather_mask = Image.new("L", (feather_w, H), 0)
        f_draw = ImageDraw.Draw(feather_mask)
        for x in range(feather_w):
            alpha = int(255 * (1.0 - (x / float(feather_w))) ** 1.7)
            f_draw.line([(x, 0), (x, H)], fill=alpha)

        solid_left = Image.new("RGB", (feather_w, H), bg_color)
        poster.paste(solid_left, (0, 0), feather_mask)

        draw = ImageDraw.Draw(poster)

        # Typography & Copy
        w1 = clean_ascii(ad_copy.get("headline_word1", "Effortless"))
        w2 = clean_ascii(ad_copy.get("headline_word2", "Sophistication"))
        tagline = clean_ascii(ad_copy.get("tagline", "Soft. Stylish. Timeless."))
        sub_desc = clean_ascii(ad_copy.get("sub_desc", "Designed to elevate your every day."))
        feat_title = clean_ascii(ad_copy.get("feature_title", "Soft Spun Fabric"))
        feat_sub = clean_ascii(ad_copy.get("feature_sub", "for All-Day Comfort"))

        # Colors
        primary_color = "#362920"
        accent_color = ad_copy.get("accent_color", "#8A6447")
        if not (isinstance(accent_color, str) and accent_color.startswith("#") and len(accent_color) in (4, 7)):
            accent_color = "#8A6447"
        muted_color = "#6E5B4F"

        font_w1 = self.get_font(self.header_regular_font_path, 72, ["georgia.ttf", "times.ttf"])
        font_w2 = self.get_font(self.header_italic_font_path, 84, ["georgiai.ttf", "timesi.ttf"])
        font_tagline = self.get_font(self.header_regular_font_path, 22, ["georgia.ttf", "times.ttf"])
        font_sub_desc = self.get_font(self.text_regular_font_path, 15, ["segoeui.ttf", "arial.ttf"])
        font_badge_title = self.get_font(self.text_bold_font_path, 14, ["segoeuib.ttf", "arialbd.ttf"])
        font_badge_sub = self.get_font(self.text_regular_font_path, 13, ["segoeui.ttf", "arial.ttf"])

        left_x = 75
        cur_y = 130

        # Word 1: "Effortless"
        draw.text((left_x, cur_y), w1, fill=primary_color, font=font_w1)
        w1_bbox = draw.textbbox((0, 0), w1, font=font_w1)
        cur_y += (w1_bbox[3] - w1_bbox[1]) + 6

        # Word 2: "Sophistication" (cursive script)
        draw.text((left_x, cur_y), w2, fill=accent_color, font=font_w2)
        w2_bbox = draw.textbbox((0, 0), w2, font=font_w2)
        cur_y += (w2_bbox[3] - w2_bbox[1]) + 22

        # Divider line with small dot
        line_w = 210
        draw.line([(left_x, cur_y), (left_x + line_w, cur_y)], fill="#C5B5A5", width=1)
        draw.ellipse([left_x + line_w - 6, cur_y - 3, left_x + line_w, cur_y + 3], fill=accent_color)
        cur_y += 30

        # Tagline
        draw.text((left_x, cur_y), tagline, fill=accent_color, font=font_tagline)
        cur_y += 38

        # Sub-description
        sub_words = sub_desc.split()
        sub_line = []
        for word in sub_words:
            sub_line.append(word)
            if draw.textbbox((0, 0), " ".join(sub_line), font=font_sub_desc)[2] > 260:
                sub_line.pop()
                draw.text((left_x, cur_y), " ".join(sub_line), fill=muted_color, font=font_sub_desc)
                cur_y += 22
                sub_line = [word]
        if sub_line:
            draw.text((left_x, cur_y), " ".join(sub_line), fill=muted_color, font=font_sub_desc)

        # Bottom-left curved arch badge
        arch_w = 340
        arch_h = 320
        arch_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        a_draw = ImageDraw.Draw(arch_overlay)

        arch_bg_color = (
            min(255, bg_color[0] + 12),
            min(255, bg_color[1] + 10),
            min(255, bg_color[2] + 8),
            230
        )
        a_draw.pieslice([-100, H - arch_h * 2 + 100, arch_w * 2 - 100, H + 100], 180, 270, fill=arch_bg_color)
        a_draw.arc([-100, H - arch_h * 2 + 100, arch_w * 2 - 100, H + 100], 180, 270, fill=(215, 202, 190, 200), width=1)
        poster.paste(arch_overlay, (0, 0), arch_overlay)

        draw = ImageDraw.Draw(poster)

        # Delicate circular emblem
        icon_cx = left_x + 20
        icon_cy = H - 195
        ir = 26
        draw.ellipse([icon_cx - ir, icon_cy - ir, icon_cx + ir, icon_cy + ir], outline=accent_color, width=1)
        draw.line([(icon_cx - 10, icon_cy + 10), (icon_cx + 10, icon_cy - 10)], fill=accent_color, width=1)
        draw.arc([icon_cx - 8, icon_cy - 12, icon_cx + 12, icon_cy + 8], 135, 315, fill=accent_color, width=1)
        draw.arc([icon_cx - 12, icon_cy - 8, icon_cx + 8, icon_cy + 12], 315, 135, fill=accent_color, width=1)

        # Feature title & sub
        feat_y = icon_cy + 40
        draw.text((left_x, feat_y), feat_title, fill=primary_color, font=font_badge_title)
        draw.text((left_x, feat_y + 22), feat_sub, fill=muted_color, font=font_badge_sub)

        # Minimal CTA line
        draw.line([(left_x, feat_y + 52), (left_x + 150, feat_y + 52)], fill="#C5B5A5", width=1)
        cta_font = self.get_font(self.text_bold_font_path, 10, ["segoeuib.ttf", "arialbd.ttf"])
        draw.text((left_x, feat_y + 60), "TAP TO SHOP LOOK • AMAZON", fill=accent_color, font=cta_font)

        output_path = os.path.join(TEMP_DIR, "final_pinterest_ad.png")
        poster.save(output_path, "PNG", quality=95)
        print(f"Successfully generated Viral Lookbook Pin at: {output_path}")
        return output_path

    def process_url(self, image_path, title, details, price=""):
        """E2E workflow for generating viral lookbook copy and pin."""
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

import os
import json
import sys
from google import genai
from google.genai import types
import dotenv
dotenv.load_dotenv()

# Configure stdout and stderr for Unicode
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def load_config():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def get_gemini_api_key():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        config = load_config()
        key = config.get("gemini_api_key", "")
    return key

def test_text_model(client):
    print("Testing text generation (gemini-2.5-flash)...")
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents='Say Hello!'
        )
        return True, response.text.strip()
    except Exception as e:
        return False, str(e)

def test_image_model(client):
    print("Testing image generation (imagen-4.0-generate-001)...")
    try:
        response = client.models.generate_images(
            model='imagen-4.0-generate-001',
            prompt='a simple yellow circle on a white background',
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="1:1"
            )
        )
        if response.generated_images:
            return True, "Success (Generated image bytes)"
        return False, "Empty response"
    except Exception as e:
        return False, str(e)

def test_video_model(client):
    print("Testing video generation (veo-3.0-fast-generate-001)...")
    try:
        # Request a short 4-second video segment (minimum limit)
        operation = client.models.generate_videos(
            model='veo-3.0-fast-generate-001',
            prompt='a floating leaf falling in water, slow motion',
            config=types.GenerateVideosConfig(
                aspect_ratio="9:16",
                duration_seconds=4,
                number_of_videos=1
            )
        )
        # Just check if submission succeeded
        if operation:
            return True, f"Success (Submitted operation: {operation.name})"
        return False, "Empty operation response"
    except Exception as e:
        return False, str(e)

def main():
    api_key = get_gemini_api_key()
    if not api_key:
        print("\n❌ Error: GEMINI_API_KEY is not configured in config.json or environment variables!")
        sys.exit(1)
        
    print("==================================================")
    print("      GEMINI API DIAGNOSTIC CHECKS                ")
    print("==================================================")
    print(f"API Key source loaded: {api_key[:10]}...{api_key[-10:] if len(api_key) > 20 else ''}")
    
    client = genai.Client(api_key=api_key)
    
    # Run tests
    text_ok, text_msg = test_text_model(client)
    image_ok, image_msg = test_image_model(client)
    video_ok, video_msg = test_video_model(client)
    
    print("\n==================================================")
    print("              DIAGNOSTIC REPORT                   ")
    print("==================================================")
    
    print(f"1. Text Model (gemini-2.5-flash):")
    print(f"   Status: {'✅ SUCCESS' if text_ok else '❌ FAILED'}")
    print(f"   Detail: {text_msg}\n")
    
    print(f"2. Image Model (imagen-4.0-generate-001):")
    print(f"   Status: {'✅ SUCCESS' if image_ok else '❌ FAILED'}")
    print(f"   Detail: {image_msg}\n")
    
    print(f"3. Video Model (veo-3.0-fast-generate-001):")
    print(f"   Status: {'✅ SUCCESS' if video_ok else '❌ FAILED'}")
    print(f"   Detail: {video_msg}\n")
    
    print("==================================================")
    if not image_ok or not video_ok:
        print("💡 NOTE: If Image or Video model failed with quota/billing errors,")
        print("   your API key is on the free tier. Set up billing on your")
        print("   Google AI Studio project to enable media generation.")
    else:
        print("🚀 All Gemini models are working perfectly on your key!")
    print("==================================================")

if __name__ == "__main__":
    main()

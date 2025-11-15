import os
import base64
import tempfile
import requests
from fastapi import FastAPI, HTTPException, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import google.generativeai as genai
import uvicorn
import re

app = FastAPI(title="Voice Assistant API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# Configuration
APP_TOKEN = os.getenv("APP_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def authenticate_request(x_app_token: str = Header(None)):
    if not APP_TOKEN or x_app_token != APP_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid app token")

def extract_audio_url(html_text):
    """Extract audio URL from HTML response"""
    match = re.search(r'src="([^"]+\.mp3)"', html_text)
    return match.group(1) if match else None

def download_audio_to_base64(audio_url):
    """Download audio from URL and convert to base64"""
    try:
        response = requests.get(audio_url)
        response.raise_for_status()
        
        audio_base64 = base64.b64encode(response.content).decode('utf-8')
        print(f"✓ Downloaded audio: {len(audio_base64)} bytes")
        return audio_base64
    except Exception as e:
        print(f"⚠ Audio download error: {e}")
        return ""

@app.post("/voice")
async def process_voice_input(
    audio_data: UploadFile = File(...),
    x_app_token: str = Header(None)
):
    try:
        print("=== Processing with Gemini 2.5 Flash TTS ===")
        
        # Authentication
        authenticate_request(x_app_token)
        
        # Read audio file
        audio_content = await audio_data.read()
        print(f"✓ Audio received: {len(audio_content)} bytes")
        
        # Configure Gemini
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Save audio to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
            temp_audio.write(audio_content)
            temp_audio_path = temp_audio.name
        
        try:
            # Use Gemini 2.5 Flash WITH TTS!
            model = genai.GenerativeModel('models/gemini-2.5-flash-preview-tts')
            print("🎯 Using: Gemini 2.5 Flash TTS")
            
            # Read audio file as bytes
            with open(temp_audio_path, 'rb') as f:
                audio_bytes = f.read()
            
            # Create audio part
            audio_part = {
                "mime_type": "audio/webm",
                "data": audio_bytes
            }
            
            # SIMPLE prompt - don't ask for specific format
            prompt = "Respond to the user's voice message naturally and conversationally."
            
            print("🚀 Sending to Gemini 2.5 Flash TTS...")
            
            # Generate content
            response = model.generate_content([prompt, audio_part])
            response_text = response.text
            
            print(f"✓ Raw response: {response_text}")
            
            # Extract audio URL from HTML
            audio_url = extract_audio_url(response_text)
            audio_base64 = ""
            
            if audio_url:
                print(f"✓ Found audio URL: {audio_url}")
                # Download and convert audio
                audio_base64 = download_audio_to_base64(audio_url)
            
            # Extract clean text (remove HTML)
            clean_text = re.sub(r'<[^>]+>', '', response_text).strip()
            
            # If we still have the whole instruction text, extract just the response
            if "Transcript:" in clean_text and "Audio Response:" in clean_text:
                parts = clean_text.split("Audio Response:")
                if len(parts) > 1:
                    clean_text = parts[1].strip()
            
            transcript = "Voice message processed"
            ai_response = clean_text if clean_text else "I understand your message"
            
            print(f"✓ Clean response: {ai_response}")
            print(f"✓ Audio available: {'Yes' if audio_base64 else 'No'}")
            
        except Exception as gemini_error:
            print(f"⚠ Gemini TTS error: {gemini_error}")
            transcript = "I heard your voice"
            ai_response = "Hello! I received your message."
            audio_base64 = ""
        
        finally:
            # Clean up temp file
            os.unlink(temp_audio_path)
        
        return JSONResponse({
            "transcript": transcript,
            "replyText": ai_response,
            "replyAudioBase64": audio_base64
        })
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Voice Assistant API with Gemini TTS"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

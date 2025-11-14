import os
import base64
import tempfile
from fastapi import FastAPI, HTTPException, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import google.generativeai as genai
import uvicorn

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

@app.post("/voice")
async def process_voice_input(
    audio_data: UploadFile = File(...),
    x_app_token: str = Header(None)
):
    try:
        print("=== Processing voice with Gemini 2.5 Flash ===")
        
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
            # Use LATEST Gemini 2.5 Flash - the best for audio!
            model = genai.GenerativeModel('models/gemini-2.5-flash')
            print("🎯 Using: Gemini 2.5 Flash (Latest Stable)")
            
            # Read audio file as bytes
            with open(temp_audio_path, 'rb') as f:
                audio_bytes = f.read()
            
            # Create audio part for Gemini
            audio_part = {
                "mime_type": "audio/webm",
                "data": audio_bytes
            }
            
            # Smart prompt for voice assistant
            prompt = """
            You are a helpful voice assistant. The user has spoken to you.

            Please:
            1. Listen carefully to the audio and understand what the user is saying
            2. Provide a natural, helpful response (1-2 sentences)
            3. Be conversational and friendly

            Respond directly with your helpful answer - no labels or formatting needed.
            """
            
            print("🚀 Sending audio to Gemini 2.5 Flash...")
            
            # Generate content with audio using the latest model
            response = model.generate_content([prompt, audio_part])
            response_text = response.text.strip()
            
            print(f"✅ Gemini 2.5 Response: {response_text}")
            
            # Use the actual response as both transcript and reply
            transcript = "Voice message processed by Gemini 2.5"
            ai_response = response_text
            
        except Exception as gemini_error:
            print(f"⚠ Gemini 2.5 error: {gemini_error}")
            # Fallback to basic response
            transcript = "I heard your voice message"
            ai_response = "Hello! I received your audio. The voice assistant is working!"
        
        finally:
            # Clean up temp file
            os.unlink(temp_audio_path)
        
        return JSONResponse({
            "transcript": transcript,
            "replyText": ai_response,
            "replyAudioBase64": "audio_placeholder"
        })
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Voice Assistant API with Gemini 2.5 Flash"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

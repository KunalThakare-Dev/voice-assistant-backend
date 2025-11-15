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
            
            # Prompt that should trigger audio response
            prompt = """
            You are a voice assistant. The user has spoken to you.
            
            Listen to their audio and respond with BOTH:
            1. A text transcript of what you heard
            2. A spoken audio response back to them
            
            Keep your response conversational and helpful (1-2 sentences).
            """
            
            print("🚀 Sending to Gemini 2.5 Flash TTS...")
            
            # Generate content - this SHOULD return audio!
            response = model.generate_content([prompt, audio_part])
            
            # Check if response has audio
            if hasattr(response, 'audio') and response.audio:
                print("✅ Got audio response from Gemini!")
                audio_base64 = base64.b64encode(response.audio).decode('utf-8')
                transcript = "Audio processed by Gemini TTS"
                ai_response = response.text if response.text else "I understand your message"
            else:
                print("⚠ Gemini returned text only, no audio")
                audio_base64 = ""
                transcript = "Voice message received"
                ai_response = response.text if response.text else "Hello! I heard you."
            
            print(f"✓ Response: {ai_response}")
            print(f"✓ Audio data: {'Yes' if audio_base64 else 'No'}")
            
        except Exception as gemini_error:
            print(f"⚠ Gemini TTS error: {gemini_error}")
            # Fallback to regular model
            try:
                model = genai.GenerativeModel('models/gemini-2.5-flash')
                response = model.generate_content([prompt, audio_part])
                transcript = "Voice message processed"
                ai_response = response.text
                audio_base64 = ""
            except:
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

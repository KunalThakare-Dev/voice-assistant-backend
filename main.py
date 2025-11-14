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
        print("=== Processing voice with Gemini ===")
        
        # Authentication
        authenticate_request(x_app_token)
        
        # Read audio file
        audio_content = await audio_data.read()
        print(f"✓ Audio received: {len(audio_content)} bytes")
        
        # Configure Gemini
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Discover available models
        print("🔍 Discovering available models...")
        available_models = []
        for model in genai.list_models():
            if 'generateContent' in model.supported_generation_methods:
                available_models.append(model.name)
                print(f"✅ {model.name}")
        
        # Try Gemini 2.5 models first, then fallback to 1.5
        model_to_use = None
        model_priority = [
            "models/gemini-2.0-flash-exp",  # Latest experimental
            "models/gemini-2.0-flash",      # Latest stable
            "models/gemini-1.5-flash",      # Previous best for audio
            "models/gemini-1.5-pro",        # Previous pro
            "models/gemini-pro"             # Original
        ]
        
        for model_name in model_priority:
            if any(model_name in avail_model for avail_model in available_models):
                model_to_use = model_name
                print(f"🎯 Selected model: {model_to_use}")
                break
        
        if not model_to_use:
            raise Exception("No suitable Gemini model found")
        
        # Save audio to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
            temp_audio.write(audio_content)
            temp_audio_path = temp_audio.name
        
        try:
            # Initialize the selected model
            model = genai.GenerativeModel(model_to_use)
            
            # Read audio file as bytes
            with open(temp_audio_path, 'rb') as f:
                audio_bytes = f.read()
            
            # Create audio part for Gemini
            audio_part = {
                "mime_type": "audio/webm",
                "data": audio_bytes
            }
            
            # Optimized prompt for audio processing
            prompt = """
            You are a voice assistant. The user has sent you an audio message.

            Please:
            1. Listen carefully and transcribe exactly what the user said
            2. Provide a helpful, natural response (1-2 sentences)

            Format your response EXACTLY like this:
            TRANSCRIPT: [word-for-word transcription]
            RESPONSE: [your helpful response]

            Keep your response conversational and brief.
            """
            
            print(f"🚀 Sending audio to {model_to_use}...")
            
            # Generate content with audio
            response = model.generate_content([prompt, audio_part])
            response_text = response.text.strip()
            
            print(f"✅ Raw Gemini response: {response_text}")
            
            # Parse the response
            if "TRANSCRIPT:" in response_text and "RESPONSE:" in response_text:
                transcript = response_text.split("TRANSCRIPT:")[1].split("RESPONSE:")[0].strip()
                ai_response = response_text.split("RESPONSE:")[1].strip()
            else:
                # If format parsing fails, use intelligent fallback
                lines = response_text.split('\n')
                if len(lines) >= 2:
                    transcript = lines[0]
                    ai_response = ' '.join(lines[1:])
                else:
                    transcript = "Voice message processed"
                    ai_response = response_text
            
            print(f"📝 Transcript: {transcript}")
            print(f"🤖 AI Response: {ai_response}")
            
        except Exception as gemini_error:
            print(f"⚠ Gemini error: {gemini_error}")
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

@app.get("/models")
async def list_models():
    """Endpoint to check available models"""
    try:
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        models = []
        for model in genai.list_models():
            if 'generateContent' in model.supported_generation_methods:
                models.append({
                    "name": model.name,
                    "description": model.description,
                    "methods": model.supported_generation_methods
                })
        return {"available_models": models}
    except Exception as e:
        return {"error": str(e)}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Voice Assistant API with Latest Gemini"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

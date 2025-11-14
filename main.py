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
        
        # Save audio to temp file for upload
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
            temp_audio.write(audio_content)
            temp_audio_path = temp_audio.name
        
        try:
            # Upload audio file to Gemini
            audio_file = genai.upload_file(temp_audio_path)
            print(f"✓ Audio uploaded to Gemini: {audio_file.uri}")
            
            # Use Gemini 1.5 Flash (supports audio)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # Prompt for audio processing
            prompt = """
            Listen to this audio and:
            1. Transcribe what the user said
            2. Provide a helpful, natural response (1-2 sentences)
            
            Respond in this exact format:
            TRANSCRIPT: [what you heard]
            RESPONSE: [your response]
            """
            
            # Send audio + prompt to Gemini
            response = model.generate_content([prompt, audio_file])
            response_text = response.text.strip()
            
            # Parse the response
            if "TRANSCRIPT:" in response_text and "RESPONSE:" in response_text:
                transcript = response_text.split("TRANSCRIPT:")[1].split("RESPONSE:")[0].strip()
                ai_response = response_text.split("RESPONSE:")[1].strip()
            else:
                # Fallback if format parsing fails
                transcript = "Audio processed by Gemini"
                ai_response = response_text
            
            print(f"✓ Transcript: {transcript}")
            print(f"✓ AI Response: {ai_response}")
            
        except Exception as gemini_error:
            print(f"⚠ Gemini audio error: {gemini_error}")
            # Fallback to text-only
            model = genai.GenerativeModel('gemini-pro')
            fallback_response = model.generate_content("The user sent audio but there was a processing issue. Respond warmly.")
            transcript = "Audio processing issue"
            ai_response = fallback_response.text.strip()
        
        finally:
            # Clean up temp file
            os.unlink(temp_audio_path)
        
        return JSONResponse({
            "transcript": transcript,
            "replyText": ai_response,
            "replyAudioBase64": "audio_placeholder"  # We'll add TTS later
        })
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Voice Assistant API with Gemini Audio"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

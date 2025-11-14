import os
import base64
from fastapi import FastAPI, HTTPException, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import google.generativeai as genai
import uvicorn

app = FastAPI(title="Voice Assistant API")

# CORS - We'll update the origin later with your actual WordPress URL
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Temporary - we'll restrict this later
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# Configuration
APP_TOKEN = os.getenv("APP_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def authenticate_request(x_app_token: str = Header(None)):
    """Validate the app token"""
    if not APP_TOKEN or x_app_token != APP_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid app token")

@app.post("/voice")
async def process_voice_input(
    audio_data: UploadFile = File(...),
    x_app_token: str = Header(None)
):
    """
    Process voice input: STT -> Gemini -> TTS
    """
    try:
        # Authentication
        authenticate_request(x_app_token)
        
        # Read audio file
        audio_content = await audio_data.read()
        
        print(f"Received audio file: {len(audio_content)} bytes")
        
        # Initialize Google AI
        genai.configure(api_key=GEMINI_API_KEY)
        
        # For now, simulate the response
        # In the next step, we'll add real Google Speech-to-Text
        
        simulated_transcript = "Hello! I can hear you now through the real backend!"
        ai_response = "Awesome! The Python backend is working perfectly! This is a real AI response from Google Gemini."
        
        # For now, return text without audio
        # We'll add real Text-to-Speech in the next step
        
        return JSONResponse({
            "transcript": simulated_transcript,
            "replyText": ai_response,
            "replyAudioBase64": "audio_placeholder"  # We'll add real audio later
        })
        
    except Exception as e:
        print(f"Error processing voice input: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Voice Assistant API is running"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

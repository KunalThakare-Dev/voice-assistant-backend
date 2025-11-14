import os
import base64
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import google.generativeai as genai
from google.cloud import speech, texttospeech
import uvicorn

app = FastAPI(title="Voice Assistant API")

# CORS - Allow your WordPress site
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-site.pantheonsite.io"],  # We'll update this later
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["*"],
)

# Configuration - will be set in Render environment variables
APP_TOKEN = os.getenv("APP_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

@app.post("/voice")
async def process_voice_input(
    audio_data: bytes = None,
    x_app_token: str = Header(None)
):
    try:
        # Check authentication
        if not APP_TOKEN or x_app_token != APP_TOKEN:
            raise HTTPException(status_code=401, detail="Invalid app token")
        
        if not audio_data:
            raise HTTPException(status_code=400, detail="No audio data received")
        
        # Initialize Google AI
        genai.configure(api_key=GEMINI_API_KEY)
        
        # For now, we'll simulate the response until we set up Google Cloud
        # In the next step, we'll add real speech-to-text and text-to-speech
        
        simulated_transcript = "Hello! This is a test from the real backend."
        ai_response = "Great! The Python backend is working! Next we'll add real voice processing."
        
        # Simulate audio response (we'll make real audio in next step)
        simulated_audio = "simulated_audio_placeholder"
        
        return JSONResponse({
            "transcript": simulated_transcript,
            "replyText": ai_response,
            "replyAudioBase64": simulated_audio
        })
        
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Voice Assistant API is running"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

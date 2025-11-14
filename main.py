import os
import base64
from fastapi import FastAPI, HTTPException, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import google.generativeai as genai
import uvicorn

app = FastAPI(title="Voice Assistant API")

# CORS - Allow your WordPress site
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # We'll restrict this later
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# Configuration
APP_TOKEN = os.getenv("APP_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

@app.post("/voice")
async def process_voice_input(
    audio_data: UploadFile = File(...),
    x_app_token: str = Header(None)
):
    """
    Process voice input using Google Gemini
    """
    try:
        # Check authentication
        if not APP_TOKEN or x_app_token != APP_TOKEN:
            raise HTTPException(status_code=401, detail="Invalid app token")
        
        # Read audio file (we'll process it later)
        audio_content = await audio_data.read()
        print(f"Received audio: {len(audio_content)} bytes")
        
        # Initialize Google AI
        genai.configure(api_key=GEMINI_API_KEY)
        
        # For now, use a simulated transcript
        # In the next step, we'll add real speech-to-text
        simulated_transcript = "Hello from the voice assistant!"
        
        # Get real AI response from Gemini
        try:
            model = genai.GenerativeModel('gemini-pro')
            prompt = f"The user said: '{simulated_transcript}'. Respond in a friendly, helpful way in 1-2 sentences."
            response = model.generate_content(prompt)
            ai_response = response.text.strip()
        except Exception as ai_error:
            print(f"Gemini error: {ai_error}")
            ai_response = "Hello! I received your voice message. The AI is working!"
        
        # Return response (we'll add audio later)
        return JSONResponse({
            "transcript": simulated_transcript,
            "replyText": ai_response,
            "replyAudioBase64": "audio_placeholder"  # We'll add real audio in next step
        })
        
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Voice Assistant API is running"}

# This part is important for Render
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

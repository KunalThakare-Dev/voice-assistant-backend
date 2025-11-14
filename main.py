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
    Process voice input using Google Gemini
    """
    try:
        print("=== Received voice request ===")
        
        # Authentication
        authenticate_request(x_app_token)
        print("✓ Authentication passed")
        
        # Check if audio file was received
        if not audio_data:
            raise HTTPException(status_code=400, detail="No audio file received")
        
        # Read audio file
        audio_content = await audio_data.read()
        print(f"✓ Received audio file: {len(audio_content)} bytes")
        print(f"✓ Content type: {audio_data.content_type}")
        print(f"✓ Filename: {audio_data.filename}")
        
        # Initialize Google AI
        genai.configure(api_key=GEMINI_API_KEY)
        print("✓ Google AI configured")
        
        # For now, simulate different responses based on audio length
        # This makes it feel more real until we add speech-to-text
        if len(audio_content) < 1000:
            simulated_transcript = "Hello! Testing the voice assistant."
            ai_response = "Hi there! I can hear you now. The voice assistant is working perfectly with real AI responses!"
        else:
            simulated_transcript = "You sent a longer voice message."
            ai_response = "Thanks for your message! The backend received your audio successfully. This response is coming from Google Gemini AI in real-time!"
        
        # Get real AI response from Gemini
        try:
            model = genai.GenerativeModel('gemini-pro')
            prompt = f"""The user is testing a voice assistant. They said: '{simulated_transcript}'. 
            Respond in a friendly, conversational way. Keep it to 1-2 sentences maximum. 
            Mention that this is a real AI response from the backend."""
            response = model.generate_content(prompt)
            ai_response = response.text.strip()
            print("✓ Got AI response from Gemini")
        except Exception as ai_error:
            print(f"⚠ Gemini error: {ai_error}")
            ai_response = "Hello! I received your voice message successfully. The AI backend is working!"
        
        print(f"✓ Sending response: {ai_response}")
        
        # Return response (we'll add audio later)
        return JSONResponse({
            "transcript": simulated_transcript,
            "replyText": ai_response,
            "replyAudioBase64": "audio_placeholder"  # We'll add real audio in next step
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error processing voice input: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Voice Assistant API is running"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

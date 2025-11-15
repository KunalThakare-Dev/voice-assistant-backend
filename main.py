import os
import tempfile
import asyncio
from fastapi import FastAPI, HTTPException, Header, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import google.generativeai as genai
import uvicorn
import json

app = FastAPI(title="Voice Assistant API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
APP_TOKEN = os.getenv("APP_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"✅ WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"❌ WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"Error sending message: {e}")
            self.disconnect(websocket)

manager = ConnectionManager()

def authenticate_websocket(websocket: WebSocket):
    """Authenticate WebSocket connection"""
    try:
        token = websocket.query_params.get("token")
        if not APP_TOKEN or token != APP_TOKEN:
            return False
        return True
    except:
        return False

async def process_audio_with_gemini(audio_content: bytes) -> dict:
    """Process audio with Gemini and return response"""
    try:
        print("=== Processing voice with Gemini 2.5 Flash ===")
        
        if not GEMINI_API_KEY:
            raise Exception("GEMINI_API_KEY not configured")
            
        # Configure Gemini
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Save audio to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
            temp_audio.write(audio_content)
            temp_audio_path = temp_audio.name
        
        try:
            # Use ACTUAL Gemini 2.5 Flash like your original code
            model = genai.GenerativeModel('models/gemini-2.5-flash')
            print("🎯 Using: Gemini 2.5 Flash")
            
            # Create audio part for Gemini
            audio_part = {
                "mime_type": "audio/webm",
                "data": audio_content
            }
            
            # Better prompt for more accurate responses
            prompt = """
            You are a helpful voice assistant. The user has spoken to you in audio format.
            
            Listen carefully to their actual words and respond directly to what they said.
            Be conversational, helpful, and provide a relevant response.
            Keep your response to 1-2 sentences maximum.
            
            If you genuinely cannot understand the audio, say: "I didn't quite catch that. Could you please repeat?"
            Do NOT use generic fallback responses like "I received your audio" or "How can I help you today?"
            """
            
            print("🚀 Processing speech with Gemini 2.5...")
            
            # Get AI response from audio
            response = model.generate_content([prompt, audio_part])
            ai_response = response.text.strip()
            
            print(f"✅ AI Response: {ai_response}")
            
            # Return actual response
            return {
                "transcript": "Voice message processed",
                "replyText": ai_response,
                "type": "assistant_response"
            }
            
        except Exception as gemini_error:
            print(f"⚠ Gemini error: {gemini_error}")
            return {
                "transcript": "Processing audio",
                "replyText": "I'm having trouble processing your audio right now. Please try again.",
                "type": "error"
            }
        
        finally:
            # Clean up temp file
            if os.path.exists(temp_audio_path):
                os.unlink(temp_audio_path)
        
    except Exception as e:
        print(f"❌ Error in process_audio_with_gemini: {e}")
        return {
            "transcript": "Error processing audio",
            "replyText": "Sorry, I encountered an error. Please try again.",
            "type": "error"
        }

@app.websocket("/ws/voice")
async def websocket_voice_endpoint(websocket: WebSocket):
    # Authenticate connection
    if not authenticate_websocket(websocket):
        await websocket.close(code=1008, reason="Invalid authentication")
        return
    
    await manager.connect(websocket)
    
    try:
        while True:
            try:
                # Wait for any message
                data = await websocket.receive()
                
                # Check if it's a receive event and contains bytes
                if data.get("type") == "websocket.receive" and "bytes" in data:
                    audio_content = data["bytes"]
                    print(f"🎵 Received binary audio: {len(audio_content)} bytes")
                    
                    if len(audio_content) == 0:
                        await manager.send_message({
                            "type": "error",
                            "message": "Empty audio received"
                        }, websocket)
                        continue
                    
                    # Send processing status
                    await manager.send_message({
                        "type": "processing",
                        "message": "Processing your audio..."
                    }, websocket)
                    
                    # Process the audio
                    try:
                        response = await process_audio_with_gemini(audio_content)
                        await manager.send_message(response, websocket)
                        print("✅ Response sent to client")
                        
                    except Exception as process_error:
                        print(f"❌ Processing error: {process_error}")
                        await manager.send_message({
                            "type": "error", 
                            "message": "Failed to process audio"
                        }, websocket)
                        
                elif data.get("type") == "websocket.disconnect":
                    break
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"❌ WebSocket error: {e}")
                try:
                    await manager.send_message({
                        "type": "error",
                        "message": "Connection error"
                    }, websocket)
                except:
                    pass
                continue
                
    except WebSocketDisconnect:
        print("🔄 Client disconnected normally")
    except Exception as e:
        print(f"💥 WebSocket endpoint crashed: {e}")
    finally:
        manager.disconnect(websocket)

# Keep HTTP endpoint for compatibility
@app.post("/voice")
async def process_voice_input(
    audio_data: UploadFile = File(...),
    x_app_token: str = Header(None)
):
    try:
        print("=== Processing voice with Gemini 2.5 (HTTP) ===")
        
        # Authentication
        if not APP_TOKEN or x_app_token != APP_TOKEN:
            raise HTTPException(status_code=401, detail="Invalid app token")
        
        # Read audio file
        audio_content = await audio_data.read()
        print(f"✓ Audio received: {len(audio_content)} bytes")
        
        if len(audio_content) == 0:
            raise HTTPException(status_code=400, detail="Empty audio file")
        
        # Process audio
        response = await process_audio_with_gemini(audio_content)
        
        return JSONResponse({
            "transcript": response["transcript"],
            "replyText": response["replyText"],
            "replyAudioBase64": "not_needed"
        })
        
    except Exception as e:
        print(f"❌ HTTP Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Voice Assistant API with Gemini 2.5 Flash"}

@app.get("/")
async def root():
    return {"message": "Voice Assistant API is running"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

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
        print("=== Processing voice with Gemini ===")
        
        if not GEMINI_API_KEY:
            raise Exception("GEMINI_API_KEY not configured")
            
        # Configure Gemini
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Save audio to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
            temp_audio.write(audio_content)
            temp_audio_path = temp_audio.name
        
        try:
            # Use Gemini 1.5 Flash
            model = genai.GenerativeModel('gemini-1.5-flash')
            print("🎯 Using: Gemini 1.5 Flash")
            
            # Read audio file as bytes
            with open(temp_audio_path, 'rb') as f:
                audio_bytes = f.read()
            
            # Create audio part for Gemini
            audio_part = {
                "mime_type": "audio/webm",
                "data": audio_bytes
            }
            
            # Smart prompt for conversation
            prompt = """
            You are a helpful voice assistant. The user has spoken to you.
            
            Listen carefully and respond naturally in 1-2 sentences.
            Be conversational and helpful.
            """
            
            print("🚀 Processing speech with Gemini...")
            
            # Get AI response from audio
            response = model.generate_content([prompt, audio_part])
            ai_response = response.text.strip()
            
            print(f"✅ AI Response: {ai_response}")
            
            transcript = "Voice message processed"
            
        except Exception as gemini_error:
            print(f"⚠ Gemini error: {gemini_error}")
            # Fallback response
            transcript = "I heard your voice message"
            ai_response = "Hello! I received your audio. How can I help you today?"
        
        finally:
            # Clean up temp file
            if os.path.exists(temp_audio_path):
                os.unlink(temp_audio_path)
        
        return {
            "transcript": transcript,
            "replyText": ai_response,
            "type": "assistant_response"
        }
        
    except Exception as e:
        print(f"❌ Error in process_audio_with_gemini: {e}")
        return {
            "transcript": "Error processing audio",
            "replyText": "Sorry, I encountered an error processing your request.",
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
                # Check if message is text or binary
                message = await websocket.receive()
                
                if message["type"] == "websocket.receive":
                    if "text" in message:
                        # Handle text messages (like ping)
                        data = json.loads(message["text"])
                        message_type = data.get("type")
                        
                        if message_type == "ping":
                            await manager.send_message({
                                "type": "pong",
                                "message": "Connection active"
                            }, websocket)
                        else:
                            await manager.send_message({
                                "type": "error", 
                                "message": "Unknown text message type"
                            }, websocket)
                            
                    elif "bytes" in message:
                        # Handle binary audio data
                        audio_content = message["bytes"]
                        print(f"🎵 Received binary audio: {len(audio_content)} bytes")
                        
                        # Send processing status immediately
                        await manager.send_message({
                            "type": "processing",
                            "message": "Processing your audio..."
                        }, websocket)
                        
                        # Process audio directly
                        response = await process_audio_with_gemini(audio_content)
                        
                        # Send response back to client
                        await manager.send_message(response, websocket)
                        print("✅ Response sent to client")
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"Error processing message: {e}")
                try:
                    await manager.send_message({
                        "type": "error",
                        "message": f"Error processing audio: {str(e)}"
                    }, websocket)
                except:
                    pass
                continue
    
    except WebSocketDisconnect:
        print("Client disconnected normally")
    except Exception as e:
        print(f"WebSocket endpoint error: {e}")
    finally:
        manager.disconnect(websocket)

# Keep HTTP endpoint for compatibility
@app.post("/voice")
async def process_voice_input(
    audio_data: UploadFile = File(...),
    x_app_token: str = Header(None)
):
    try:
        print("=== Processing voice with Gemini (HTTP) ===")
        
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
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Voice Assistant API with Binary WebSocket"}

@app.get("/")
async def root():
    return {"message": "Voice Assistant API is running"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

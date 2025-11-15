import os
import base64
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
    allow_methods=["POST", "GET"],
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
        
        # Configure Gemini
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Save audio to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
            temp_audio.write(audio_content)
            temp_audio_path = temp_audio.name
        
        try:
            # Use Gemini 2.5 Flash
            model = genai.GenerativeModel('models/gemini-2.5-flash')
            print("🎯 Using: Gemini 2.5 Flash")
            
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
            
            print("🚀 Processing speech with Gemini 2.5...")
            
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
            # Use receive_text() for better error handling
            try:
                data = await websocket.receive_text()
                message_data = json.loads(data)
                message_type = message_data.get("type")
                
                if message_type == "audio_data":
                    # Send processing status
                    await manager.send_message({
                        "type": "processing",
                        "message": "Processing your audio..."
                    }, websocket)
                    
                    # Process audio data
                    audio_base64 = message_data.get("audio_data")
                    audio_content = base64.b64decode(audio_base64)
                    
                    # Get AI response
                    response = await process_audio_with_gemini(audio_content)
                    
                    # Send response back to client
                    await manager.send_message(response, websocket)
                    
                elif message_type == "ping":
                    # Keep connection alive
                    await manager.send_message({
                        "type": "pong",
                        "message": "Connection active"
                    }, websocket)
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"Error processing message: {e}")
                # Send error back to client but keep connection alive
                await manager.send_message({
                    "type": "error",
                    "message": "Error processing request"
                }, websocket)
                continue  # Continue listening for next message
    
    except WebSocketDisconnect:
        print("Client disconnected normally")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)

# Keep existing HTTP endpoints for compatibility
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
        
        # Process audio
        response = await process_audio_with_gemini(audio_content)
        
        return JSONResponse({
            "transcript": response["transcript"],
            "replyText": response["replyText"],
            "replyAudioBase64": "not_needed"
        })
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Voice Assistant API with WebSocket support"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

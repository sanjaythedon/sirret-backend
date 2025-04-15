from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import openai
import os
from typing import List, Optional
from dotenv import load_dotenv
import json
import asyncio
import tempfile

# Load environment variables from .env file if it exists
load_dotenv()
app = FastAPI(root_path="/prod")  # This is important for API Gateway stage name

# Configure CORS more comprehensively for direct API Gateway integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"],  # Expose all headers
)

# Set your OpenAI API key
# In production, use environment variables for secrets
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key-here")
openai.api_key = OPENAI_API_KEY

class GroceryItem(BaseModel):
    tamil_name: str
    english_name: str
    weight: str  # For weights like "500 grams", "1 kg", "1 litre", etc.
    quantity: Optional[int] = None  # Numerical quantity if specified

@app.get("/")
def read_root():
    return {"message": "Grocery List Speech-to-Text API"}

# Add OPTIONS endpoint to handle preflight requests
@app.options("/{full_path:path}")
async def options_route(full_path: str):
    return JSONResponse(
        content={"message": "OK"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
        },
    )

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_json(self, websocket: WebSocket, data: dict):
        await websocket.send_json(data)

manager = ConnectionManager()

# System prompt for processing grocery items
SYSTEM_PROMPT = """
Extract grocery items from the provided text. The text may contain items in Tamil and English.
For each item, provide:
1. The Tamil name in Tamil script (தமிழ் எழுத்து) - NOT transliterated
2. The English name (translate if only Tamil name is given)
3. The weight in English (e.g., "500 grams", "1 kg", "1 litre", "1 ml", etc.)
4. The quantity as a number (if specifically mentioned)

IMPORTANT NOTES ON TAMIL QUANTITIES:
- "கால் கிலோ" (kaal kilo) means "250 grams", NOT 0.25 kilograms
- "அரை கிலோ" (arai kilo) means "500 grams", NOT half kilogram
- "முக்கால் கிலோ" (mukkaal kilo) means "750 grams", NOT 0.75 kilograms
- If someone says "அரை கிலோ ரெண்டு" (arai kilo rendu), it means quantity = 2, weight = "500 grams"
- Always express weights in English (grams, kg, litre, ml, etc.)
- If only a quantity is mentioned (like "2 apples"), set weight to an empty string and quantity to the number

CRITICAL INSTRUCTIONS FOR TAMIL SPELLING:
- Maintain Tamil words in proper Tamil script (UTF-8) characters
- Do NOT transliterate Tamil words to English/Roman script
- Ensure correct Tamil spelling with proper vowel and consonant marks
- Common Tamil grocery items should appear in Tamil script, for example:
  * "அரிசி" (rice)
  * "வெங்காயம்" (onion)
  * "தக்காளி" (tomato)
  * "மிளகாய்" (chili)
  * "பட்டாணி" (peas)
  * "கீரை" (greens)
- If the audio contains Tamil words in Tamil script, preserve them as-is
- If the audio contains transliterated Tamil words, convert them to proper Tamil script

Return a JSON array with objects having the keys 'tamil_name', 'english_name', 'weight', and 'quantity'.
The response should be in this format: {"items": [{"tamil_name": "", "english_name": "", "weight": "", "quantity": null}]}
If no quantity is specified, set it to null.
"""

# Add a non-async version of process_audio for Lambda usage
def process_audio(audio_data, websocket=None):
    """
    Non-async version of process_audio that can be called directly from Lambda
    If websocket is None, we're in Lambda mode and need to return the results instead of sending them
    """
    # Create a temporary file to store the audio chunk
    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(audio_data)
        
        print(f"Processing audio chunk of size {len(audio_data)} bytes")
        results = []
        
        # Use OpenAI Whisper to transcribe the audio
        with open(temp_file_path, "rb") as audio_file:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            
            # Use a faster whisper model for real-time processing
            try:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
                print(f"Transcribed: {transcript}")
            except Exception as e:
                error_message = str(e)
                print(f"Transcription error: {error_message}")
                error_data = {"error": f"Error from server: {error_message}"}
                if websocket:
                    # In FastAPI mode, send error to websocket
                    asyncio.run(manager.send_json(websocket, error_data))
                return error_data
        
        if not transcript.strip():
            print("Empty transcript, skipping")
            return {"message": "Empty transcript"}
        
        # For real-time processing, use a more focused prompt for faster inference
        user_prompt = f"Here's the transcript: {transcript}\n\nExtract grocery items with quantities in Tamil or English."
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3  # Lower temperature for more consistent, faster responses
            )
            
            # Parse the JSON response
            result = response.choices[0].message.content
            grocery_items = json.loads(result).get("items", [])
            
            if not grocery_items:
                print("No grocery items found in transcript")
                return {"message": "No grocery items found"}
                
            print(f"Found {len(grocery_items)} grocery items")
            
            if websocket:
                # In FastAPI mode, send items to websocket
                for item in grocery_items:
                    asyncio.run(manager.send_json(websocket, item))
            else:
                # In Lambda mode, return all items
                return grocery_items
                
        except Exception as e:
            error_message = str(e)
            print(f"GPT processing error: {error_message}")
            error_data = {"error": f"Error processing text: {error_message}"}
            if websocket:
                # In FastAPI mode, send error to websocket
                asyncio.run(manager.send_json(websocket, error_data))
            return error_data
            
    except Exception as e:
        error_message = str(e)
        print(f"Error processing audio: {error_message}")
        error_data = {"error": f"Error from server: {error_message}"}
        if websocket:
            # In FastAPI mode, send error to websocket
            asyncio.run(manager.send_json(websocket, error_data))
        return error_data
    finally:
        # Clean up the temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

# Rename the async version to avoid confusion
async def process_audio_async(audio_data, websocket: WebSocket):
    # Create a temporary file to store the audio chunk
    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(audio_data)
        
        print(f"Processing audio chunk of size {len(audio_data)} bytes")
        
        # Use OpenAI Whisper to transcribe the audio
        with open(temp_file_path, "rb") as audio_file:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            
            # Use a faster whisper model for real-time processing
            try:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
                print(f"Transcribed: {transcript}")
            except Exception as e:
                error_message = str(e)
                print(f"Transcription error: {error_message}")
                await manager.send_json(websocket, {"error": f"Error from server: {error_message}"})
                return
        
        if not transcript.strip():
            print("Empty transcript, skipping")
            return
        
        # For real-time processing, use a more focused prompt for faster inference
        user_prompt = f"Here's the transcript: {transcript}\n\nExtract grocery items with quantities in Tamil or English."
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3  # Lower temperature for more consistent, faster responses
            )
            
            # Parse the JSON response
            result = response.choices[0].message.content
            grocery_items = json.loads(result).get("items", [])
            
            if not grocery_items:
                print("No grocery items found in transcript")
                return
                
            print(f"Found {len(grocery_items)} grocery items")
            
            # Send each item individually to the frontend
            for item in grocery_items:
                await manager.send_json(websocket, item)
                
        except Exception as e:
            error_message = str(e)
            print(f"GPT processing error: {error_message}")
            await manager.send_json(websocket, {"error": f"Error processing text: {error_message}"})
            
    except Exception as e:
        error_message = str(e)
        print(f"Error processing audio: {error_message}")
        await manager.send_json(websocket, {"error": f"Error from server: {error_message}"})
    finally:
        # Clean up the temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@app.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    
    try:
        while True:
            # Receive binary data from the WebSocket
            data = await websocket.receive_bytes()
            
            # Check for end-of-stream marker
            if len(data) == 1 and data[0] == 255:
                # Send completion message
                await manager.send_json(websocket, {"status": "completed"})
                continue
            
            # Process the complete audio chunk
            # No need to accumulate, each chunk is a valid audio file now
            if len(data) > 0:
                await process_audio_async(data, websocket)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
        if websocket in manager.active_connections:
            manager.disconnect(websocket)

@app.post("/transcribe/", response_model=List[GroceryItem])
async def transcribe_audio(file: UploadFile = File(...)):
    # Save the uploaded file temporarily
    temp_file_path = f"/tmp/temp_{file.filename}"  # Use /tmp for Lambda
    with open(temp_file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    try:
        # Use OpenAI Whisper to transcribe the audio
        with open(temp_file_path, "rb") as audio_file:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )
        
        print(transcript)
        # Process the transcript to extract grocery items
        # This is a simplified version. In a real app, you'd use more sophisticated NLP
        
        user_prompt = f"Here's the transcript: {transcript}\n\nPlease extract the grocery items with their quantities following the guidelines for Tamil quantity terms."
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Parse the JSON response
        result = response.choices[0].message.content
        import json
        grocery_items = json.loads(result).get("items", [])
        
        return grocery_items
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio: {str(e)}")
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

# This section will be used when running locally, not in Lambda
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
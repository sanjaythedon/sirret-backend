from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai
import os
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

# Add CORS middleware to allow requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set your OpenAI API key
# In production, use environment variables for secrets
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key-here")
openai.api_key = OPENAI_API_KEY

class GroceryItem(BaseModel):
    tamil_name: str
    english_name: str
    quantity: str

@app.get("/")
def read_root():
    return {"message": "Grocery List Speech-to-Text API"}

@app.post("/transcribe/", response_model=List[GroceryItem])
async def transcribe_audio(file: UploadFile = File(...)):
    # Save the uploaded file temporarily
    temp_file_path = f"temp_{file.filename}"
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
        system_prompt = """
        Extract grocery items from the provided text. The text may contain items in Tamil and English.
        For each item, provide:
        1. The Tamil name in Tamil script (தமிழ் எழுத்து) - NOT transliterated
        2. The English name (translate if only Tamil name is given)
        3. The quantity mentioned

        IMPORTANT NOTES ON TAMIL QUANTITIES:
        - "கால் கிலோ" (kaal kilo) means 250 grams, NOT 0.25 kilograms
        - "அரை கிலோ" (arai kilo) means 500 grams, NOT half kilogram
        - "முக்கால் கிலோ" (mukkaal kilo) means 750 grams, NOT 0.75 kilograms
        - If someone says "அரை கிலோ ரெண்டு" (arai kilo rendu), it means "2 quantities of half kilo" (2 × 500g), NOT 2.5 kilograms
        - Always preserve the original quantity format mentioned in the audio
        
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
        
        Return a JSON array with objects having the keys 'tamil_name', 'english_name', and 'quantity'.
        The response should be in this format: {"items": [{"tamil_name": "", "english_name": "", "quantity": ""}]}
        """
        
        user_prompt = f"Here's the transcript: {transcript}\n\nPlease extract the grocery items with their quantities following the guidelines for Tamil quantity terms."
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Parse the JSON response
        result = response.choices[0].message.content
        import json
        grocery_items = json.loads(result).get("items", [])
        
        return grocery_items
        
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
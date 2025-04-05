# Grocery List Speech-to-Text API

This is the backend API for the Tamil/English Grocery List Speech-to-Text application. It provides a FastAPI-based service that transcribes audio recordings of grocery lists and returns structured data.

## Features

- Audio transcription using OpenAI's Whisper model
- Extraction of grocery items with Tamil and English names
- Quantity recognition for each grocery item
- CORS-enabled API for frontend integration

## Setup

1. Create a Python virtual environment:
   ```
   python3 -m venv venv
   ```

2. Activate the virtual environment:
   ```
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install fastapi uvicorn python-multipart openai pydantic
   ```

4. Set up your OpenAI API key as an environment variable:
   ```
   export OPENAI_API_KEY="your-api-key-here"
   ```

5. Run the server:
   ```
   uvicorn main:app --reload
   ```

The API will be available at http://localhost:8000

## API Endpoints

- `GET /`: Basic health check endpoint
- `POST /transcribe/`: Endpoint to transcribe audio files and extract grocery items

## API Response Format

The API returns a JSON array of grocery items with the following structure:

```json
[
  {
    "tamil_name": "அரிசி",
    "english_name": "Rice",
    "quantity": "2kg"
  },
  {
    "tamil_name": "பால்",
    "english_name": "Milk",
    "quantity": "1 liter"
  }
]
``` 
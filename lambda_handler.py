import json
import os
import base64
import boto3
from main import process_audio

def handler(event, context):
    # Log the event for debugging
    print(f"Received event: {json.dumps(event)}")
    
    # Get connection ID
    connection_id = event.get('requestContext', {}).get('connectionId')
    if not connection_id:
        return {'statusCode': 400, 'body': 'ConnectionId not found'}
    
    # Handle different route types
    route_key = event.get('requestContext', {}).get('routeKey')
    
    if route_key == '$connect':
        return handle_connect(event)
    elif route_key == '$disconnect':
        return handle_disconnect(event)
    else:  # $default or any other route
        return handle_default_message(event, connection_id)

def handle_connect(event):
    # Handle new connection
    print("New connection established")
    return {'statusCode': 200, 'body': 'Connected'}

def handle_disconnect(event):
    # Handle disconnection
    print("Connection closed")
    return {'statusCode': 200, 'body': 'Disconnected'}

def handle_default_message(event, connection_id):
    # For binary messages (audio data)
    print(f"handle_default_message {json.dumps(event)}")
    if event.get('isBase64Encoded', False):
        print(f"Processing base64 encoded message for connection {connection_id}")
        body = event.get('body', '')
        # Decode base64 data
        audio_data = base64.b64decode(body)
        print(f"Decoded audio data of size: {len(audio_data)} bytes")
        
        # Set up API Gateway Management API client to send messages back
        domain = event['requestContext']['domainName']
        stage = event['requestContext']['stage']
        endpoint_url = f"https://{domain}/{stage}"
        print(f"Using endpoint URL: {endpoint_url}")
        
        try:
            # Process the audio data
            # We need to adapt the process_audio function to work in this context
            print(f"Calling process_audio_lambda for connection {connection_id}")
            results = process_audio_lambda(audio_data, connection_id, domain, stage)
            print(f"Audio processing completed with results: {results}")
            return {'statusCode': 200, 'body': 'Processing audio'}
        except Exception as e:
            print(f"Error processing audio: {str(e)}")
            error_message = {'error': f"Error processing audio: {str(e)}"}
            send_message(connection_id, domain, stage, error_message)
            return {'statusCode': 500, 'body': str(e)}
    else:
        # For text messages
        print(f"Processing text message for connection {connection_id}")
        try:
            body = json.loads(event.get('body', '{}'))
            print(f"Received text message: {body}")
            return {'statusCode': 200, 'body': json.dumps({'message': 'Received text message'})}
        except Exception as e:
            print(f"Error parsing message: {str(e)}")
            return {'statusCode': 400, 'body': json.dumps({'message': 'Invalid message format'})}

def process_audio_lambda(audio_data, connection_id, domain, stage):
    """Adapted version of process_audio for Lambda environment"""
    print(f"process_audio_lambda started for connection {connection_id}")
    
    # Create a temporary file to store the audio chunk
    import tempfile
    import os
    
    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(audio_data)
        
        print(f"Created temporary file at {temp_file_path}")
        print(f"Processing audio chunk of size {len(audio_data)} bytes")
        
        # Use OpenAI Whisper to transcribe the audio
        with open(temp_file_path, "rb") as audio_file:
            import openai
            
            OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
            if not OPENAI_API_KEY:
                print("OPENAI_API_KEY environment variable not set")
                raise ValueError("OPENAI_API_KEY environment variable not set")
                
            print("Initializing OpenAI client")
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            
            # Use a faster whisper model for real-time processing
            try:
                print("Sending audio to OpenAI for transcription")
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
                print(f"Transcribed: {transcript}")
            except Exception as e:
                error_message = str(e)
                print(f"Transcription error: {error_message}")
                send_message(connection_id, domain, stage, {"error": f"Error from server: {error_message}"})
                return
        
        if not transcript.strip():
            print("Empty transcript, skipping")
            return
        
        # For real-time processing, use a more focused prompt for faster inference
        user_prompt = f"Here's the transcript: {transcript}\n\nExtract grocery items with quantities in Tamil or English."
        print(f"Created user prompt: {user_prompt}")
        
        # System prompt from main.py
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
        
        try:
            print("Sending transcript to GPT for processing")
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3  # Lower temperature for more consistent, faster responses
            )
            print("Received response from GPT")
            
            # Parse the JSON response
            result = response.choices[0].message.content
            print(f"GPT response content: {result}")
            grocery_items = json.loads(result).get("items", [])
            
            if not grocery_items:
                print("No grocery items found in transcript")
                return
                
            print(f"Found {len(grocery_items)} grocery items: {grocery_items}")
            
            # Send each item individually to the frontend
            for item in grocery_items:
                print(f"Sending item to client: {item}")
                send_message(connection_id, domain, stage, item)
                
        except Exception as e:
            error_message = str(e)
            print(f"GPT processing error: {error_message}")
            send_message(connection_id, domain, stage, {"error": f"Error processing text: {error_message}"})
            
    except Exception as e:
        error_message = str(e)
        print(f"Error processing audio: {error_message}")
        send_message(connection_id, domain, stage, {"error": f"Error from server: {error_message}"})
    finally:
        # Clean up the temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            print(f"Removing temporary file: {temp_file_path}")
            os.remove(temp_file_path)

def send_message(connection_id, domain_name, stage_name, message):
    """Send a message back to the client through the WebSocket connection"""
    gateway_api = boto3.client('apigatewaymanagementapi', 
                              endpoint_url=f'https://{domain_name}/{stage_name}')
    
    try:
        gateway_api.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(message).encode('utf-8')
        )
        return True
    except Exception as e:
        print(f"Error sending message: {str(e)}")
        return False 
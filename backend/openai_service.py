"""
OpenAI Service - Wrapper for OpenAI API calls

Provides:
- LLM chat completions (GPT)
- Audio transcription (Whisper)
- Text-to-speech (TTS)
"""

import openai
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize OpenAI client
openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def call_llm(user_message: str, conversation_history: list[dict] = None) -> str:
    """
    Call OpenAI GPT to generate a response.
    
    Args:
        user_message: User's message (usually empty string if conversation_history 
                     already contains the user message)
        conversation_history: List of message dicts with 'role' and 'content' keys.
                             Should include: system message, conversation history, 
                             and current user message.
    
    Returns:
        str: The assistant's response text
    
    Raises:
        Exception: If OpenAI API call fails
    
    Note:
        - Uses gpt-4o-mini by default (cheaper, great for character chatbots)
        - Max tokens: 300 (keeps responses concise)
        - Temperature: 0.7 (balanced creativity/consistency)
    """
    messages = []
    
    # Add conversation history if provided (should already include system + history + user message)
    if conversation_history:
        messages.extend(conversation_history)
    else:
        # Fallback: If no history, just add the user message
        # (This shouldn't happen in normal flow since app.py always provides history)
        if user_message:
            messages.append({
                "role": "user",
                "content": user_message
            })
    
    try:
        # Token limits:
        # - gpt-3.5-turbo: ~4,096 tokens total context
        # - gpt-4o-mini: ~128k tokens (much cheaper, great for character chatbots)
        # - gpt-4o: ~128k tokens (more expensive, better for complex reasoning)
        # max_tokens is for response length, not total context
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),  # Default to 4o-mini (cheaper, still great quality)
            messages=messages,
            max_tokens=300,  # Character responses should be concise (~225 words)
            temperature=0.7  # Balance between creativity and consistency
        )
        
        return response.choices[0].message.content
    except Exception as e:
        raise Exception(f"OpenAI API error: {str(e)}")


def transcribe_audio(audio_file_path: str) -> str:
    """
    Transcribe audio file to text using OpenAI Whisper API.
    
    Args:
        audio_file_path: Path to audio file (supports various formats including webm)
    
    Returns:
        str: Transcribed text
    
    Raises:
        Exception: If transcription fails
    
    Note:
        - Uses whisper-1 model
        - Returns plain text (not JSON)
    """
    try:
        with open(audio_file_path, 'rb') as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"  # Returns plain text, not JSON
            )
        return transcript
    except Exception as e:
        raise Exception(f"Whisper transcription error: {str(e)}")


def text_to_speech(text: str, voice: str = "onyx") -> bytes:
    """
    Convert text to speech using OpenAI TTS.
    
    Args:
        text: Text to convert to speech
        voice: Voice to use. Options:
            - "alloy": Neutral voice
            - "echo": Neutral voice
            - "fable": Neutral voice
            - "onyx": Deep, masculine voice (default - good for Batman)
            - "nova": Neutral voice
            - "shimmer": Neutral voice
    
    Returns:
        bytes: Audio file bytes (MP3 format)
    
    Raises:
        Exception: If TTS generation fails
    
    Note:
        - Uses tts-1 model
        - Returns MP3 audio bytes
    """
    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text
        )
        return response.content
    except Exception as e:
        raise Exception(f"TTS error: {str(e)}")

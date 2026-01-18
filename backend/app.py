"""
Hologram Backend - Character Chatbot with RAG

Main Flask application that provides:
- Voice-to-text transcription (Whisper)
- Character chatbot with RAG (GPT + Pinecone)
- Text-to-speech (TTS)
- Document upload and vector storage

Architecture:
- In-memory conversation history (per session)
- Pinecone vector DB for document knowledge (persistent)
- Strict RAG mode: answers only from retrieved knowledge
"""

from flask import Flask, request, jsonify, send_file, send_from_directory, session
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from functools import wraps
from openai_service import call_llm, transcribe_audio, text_to_speech
from document_processor import process_uploaded_file
from pinecone_service import get_or_create_index, get_embedding
import os
import tempfile
import io
import uuid

# ============================================================================
# FLASK APP INITIALIZATION
# ============================================================================

app = Flask(__name__, static_folder='../frontend/dist', static_url_path='')
CORS(app)  # Enable CORS for React frontend

# Session configuration for authentication
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(32))  # Use env var or generate random key
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'  # Secure cookies in production
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent XSS attacks
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection

# ============================================================================
# RATE LIMITING & COST PROTECTION
# ============================================================================

# Initialize rate limiter (uses IP address to identify users)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["500 per day", "100 per hour"],  # Global limits per IP - generous for normal use
    storage_uri="memory://"  # In-memory storage (resets on restart)
)

# Request size limits (prevent large payloads that could be expensive)
MAX_MESSAGE_LENGTH = 2000  # characters
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_AUDIO_DURATION = 60  # seconds (Whisper costs $0.006/minute)

# ============================================================================
# CONVERSATION STATE (In-Memory, Per Session)
# ============================================================================

# Store conversation history as list of message dicts
# Format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
# This is NOT persisted - each session starts fresh
conversation_history = []

# Current character being spoken to (set dynamically based on user request)
# Format: {"name": "Character Name", "set_by_user": True/False}
current_character = None

# Context configuration
# For character chatbots, 6-10 messages (3-5 exchanges) is usually enough
# System prompt maintains character consistency, recent context just helps conversation flow
MAX_CONTEXT_MESSAGES = 10  # Last 10 messages (5 exchanges) - optimal for character chatbots
# Too much context can actually dilute character consistency

# ============================================================================
# CHARACTER CONFIGURATION
# ============================================================================

def detect_character_request(message: str) -> str | None:
    """
    Detect if user wants to speak to a specific character.
    
    Looks for patterns like:
    - "I'd like to speak to [character]"
    - "I want to talk to [character]"
    - "Can I speak with [character]?"
    - "Let me talk to [character]"
    
    Returns:
        str: Character name if detected, None otherwise
    """
    import re
    
    message_lower = message.lower().strip()
    
    # Patterns to detect character requests
    patterns = [
        r"i'?d?\s+like\s+to\s+speak\s+to\s+(.+)",
        r"i'?d?\s+like\s+to\s+talk\s+to\s+(.+)",
        r"i\s+want\s+to\s+speak\s+to\s+(.+)",
        r"i\s+want\s+to\s+talk\s+to\s+(.+)",
        r"can\s+i\s+speak\s+with\s+(.+)",
        r"can\s+i\s+talk\s+to\s+(.+)",
        r"let\s+me\s+talk\s+to\s+(.+)",
        r"let\s+me\s+speak\s+to\s+(.+)",
        r"speak\s+to\s+(.+)",
        r"talk\s+to\s+(.+)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message_lower)
        if match:
            character = match.group(1).strip()
            # Remove trailing punctuation/question marks
            character = re.sub(r'[?.!]+$', '', character).strip()
            if character and len(character) > 0:
                return character
    
    return None


def build_character_system_prompt(character_name: str, knowledge: str = None) -> str:
    """
    Build a dynamic system prompt for a character based on RAG knowledge.
    
    Args:
        character_name: Name of the character
        knowledge: Optional knowledge retrieved from vector DB
    
    Returns:
        str: System prompt for the character
    """
    if knowledge:
        # If we have knowledge about the character, use it to build the prompt
        prompt = f"""You are {character_name}. You are speaking to someone who wants to talk with you.

Based on the knowledge provided about you, respond as {character_name} would:
- Stay true to your character as described in the knowledge
- Use the information provided to inform your responses
- Be consistent with your personality and background
- Keep responses concise and in character
- Don't break character or mention that you're an AI

IMPORTANT - STRICT KNOWLEDGE REQUIREMENTS:
You have been provided with the following knowledge about yourself:

{knowledge}

CRITICAL RULES:
1. You MUST ONLY use information from the knowledge provided above
2. If the knowledge doesn't contain information to answer the question, say "I can't seem to remember that right now"
3. DO NOT make up facts, details, or information not in the provided knowledge
4. DO NOT use general knowledge - only use what's explicitly in the knowledge above
5. Stay in character as {character_name}, but be strictly truthful to the provided knowledge
6. If asked about something not in the knowledge, acknowledge you don't have that information

Remember: You ARE {character_name}. Stay in character throughout the conversation, but only use information from your knowledge base."""
    else:
        # If no knowledge found, create a basic prompt that requires knowledge
        prompt = f"""You are {character_name}. You are speaking to someone who wants to talk with you.

However, you don't have any knowledge about yourself in your knowledge base yet. 
Please let the user know that information about you needs to be uploaded first.

Say something like: I'd be happy to speak with you, but I don't have any information about myself in my knowledge base yet. Please upload documents about me first so I can answer your questions accurately."""
    
    return prompt

# ============================================================================
# RAG CONFIGURATION
# ============================================================================

# Set to True to enable RAG (requires Pinecone with character knowledge base)
# When enabled, retrieves relevant knowledge from Pinecone and adds to system prompt
USE_RAG = True  # Enabled for testing with Batman knowledge

# ============================================================================
# AUTHENTICATION
# ============================================================================

def load_credentials():
    """
    Load credentials from AUTH_CREDENTIALS environment variable.
    
    Format: "username1:password1,username2:password2,..."
    
    Returns:
        dict: Dictionary mapping usernames to passwords
    """
    creds_str = os.environ.get('AUTH_CREDENTIALS', '')
    if not creds_str:
        return {}
    
    credentials = {}
    for pair in creds_str.split(','):
        pair = pair.strip()
        if ':' in pair:
            username, password = pair.split(':', 1)  # Split on first colon only
            credentials[username.strip()] = password.strip()
    
    return credentials


def require_auth(f):
    """
    Decorator to require authentication for protected endpoints.
    
    Checks if user is logged in via session. Returns 401 if not authenticated.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# API ENDPOINTS
# ============================================================================

# Authentication endpoints (unprotected)
@app.route('/api/login', methods=['POST'])
def login():
    """
    Login endpoint - authenticates user with username/password.
    
    Request body:
        {
            "username": "username",
            "password": "password"
        }
    
    Response:
        {
            "success": true,
            "message": "Logged in successfully"
        }
    """
    data = request.json
    username = data.get('username', '')
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    credentials = load_credentials()
    
    # Check if credentials are configured
    if not credentials:
        return jsonify({'error': 'Authentication not configured'}), 500
    
    # Verify credentials
    if username in credentials and credentials[username] == password:
        session['authenticated'] = True
        session['username'] = username
        return jsonify({
            'success': True,
            'message': 'Logged in successfully'
        })
    else:
        return jsonify({'error': 'Invalid username or password'}), 401


@app.route('/api/logout', methods=['POST'])
def logout():
    """
    Logout endpoint - clears user session.
    
    Response:
        {
            "success": true,
            "message": "Logged out successfully"
        }
    """
    session.clear()
    return jsonify({
        'success': True,
        'message': 'Logged out successfully'
    })


@app.route('/api/auth/check', methods=['GET'])
def auth_check():
    """
    Check if user is authenticated.
    
    Response:
        {
            "authenticated": true/false,
            "username": "username" (if authenticated)
        }
    """
    if session.get('authenticated'):
        return jsonify({
            'authenticated': True,
            'username': session.get('username')
        })
    else:
        return jsonify({
            'authenticated': False
        })

# Support both /api/chat and /chat for compatibility
@app.route('/api/chat', methods=['POST'])
@app.route('/chat', methods=['POST'])
@limiter.limit("15 per minute")  # 7 chat messages per minute per IP (stricter for cost protection)
@require_auth
def chat():
    """
    Main chat endpoint - handles user messages and returns character responses.
    
    Flow:
    1. Receives user message
    2. If RAG enabled: Retrieves relevant knowledge from Pinecone
    3. Builds message history (system prompt + conversation history + user message)
    4. Calls OpenAI GPT to generate character response
    5. Updates in-memory conversation history
    6. Returns response
    
    Request body:
        {
            "message": "user's message text"
        }
    
    Response:
        {
            "response": "character's response text"
        }
    """
    global conversation_history, current_character

    data = request.json
    user_message = data.get("message", "")
    if not user_message:
        return jsonify({'error': 'Message is required'}), 400
    
    # Input validation - prevent abuse and limit costs
    if len(user_message) > MAX_MESSAGE_LENGTH:
        return jsonify({
            'error': f'Message too long. Maximum {MAX_MESSAGE_LENGTH} characters allowed.'
        }), 400
    
    # Basic sanity check - reject empty or whitespace-only messages
    if not user_message.strip():
        return jsonify({'error': 'Message cannot be empty'}), 400
    
    try:
        # Check if user wants to speak to a specific character
        detected_character = detect_character_request(user_message)
        
        if detected_character:
            # User requested a character - set it as current character
            current_character = {"name": detected_character, "set_by_user": True}
            # Retrieve knowledge about this character from vector DB
            knowledge = ""
            if USE_RAG:
                try:
                    from rag_service import retrieve_character_knowledge
                    # Search for knowledge about this specific character
                    # Include character name in query to find character-specific knowledge
                    character_query = f"{detected_character} {user_message}"
                    knowledge = retrieve_character_knowledge(character_query, top_k=5)
                except ImportError:
                    pass
            
            # Build system prompt for this character
            system_content = build_character_system_prompt(detected_character, knowledge)
            
            # Confirm character selection to user
            if knowledge:
                reply = f"Hello! I'm {detected_character}. I'm ready to speak with you based on the information in my knowledge base. How can I help you?"
            else:
                reply = f"Hello! I'm {detected_character}. However, I don't have any information about myself in my knowledge base yet. Please upload documents about me first so I can answer your questions accurately."
            
            # Update conversation history
            conversation_history.append({"role": "user", "content": user_message})
            conversation_history.append({"role": "assistant", "content": reply})
            
            return jsonify({'response': reply})
        
        # If no character is set yet, prompt user to select one
        if current_character is None:
            return jsonify({
                'response': "Hello! To start chatting, please tell me which character you'd like to speak with. For example, say 'I'd like to speak to [character name]'. Make sure you've uploaded documents about that character first!"
            })
        
        # Character is set - continue conversation
        character_name = current_character["name"]
        
        # Build messages array for OpenAI API
        messages = []
        
        # Retrieve RAG knowledge about the current character
        knowledge = ""
        if USE_RAG:
            try:
                from rag_service import retrieve_character_knowledge
                # Include character name in query to find character-specific knowledge
                character_query = f"{character_name} {user_message}"
                knowledge = retrieve_character_knowledge(character_query, top_k=5)
            except ImportError:
                pass
        
        # Build system prompt with character and RAG knowledge
        system_content = build_character_system_prompt(character_name, knowledge)
        
        # ALWAYS add system message first (OpenAI needs it for every request to maintain character)
        messages.append({
            "role": "system",
            "content": system_content
        })
        
        # Add conversation history (last N messages)
        # This keeps context within the current conversation session
        for msg in conversation_history[-MAX_CONTEXT_MESSAGES:]:
            messages.append(msg)
        
        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        # Call OpenAI - pass the full messages list
        # Note: user_message param is empty because messages already contains everything
        reply = call_llm("", messages)
        
        # Update conversation history (in-memory only, not stored)
        conversation_history.append({"role": "user", "content": user_message})
        conversation_history.append({"role": "assistant", "content": reply})
        
        # Keep only last N messages for context (to manage memory and token usage)
        conversation_history = conversation_history[-MAX_CONTEXT_MESSAGES:]
        
        return jsonify({'response': reply})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/reset', methods=['POST'])
@app.route('/reset', methods=['POST'])
@require_auth
def reset():
    """
    Reset conversation history and current character, starting a new conversation session.
    
    This clears the in-memory conversation history and character selection. 
    Note: This does NOT affect the Pinecone knowledge base (uploaded documents remain available).
    
    Response:
        {
            "message": "Conversation reset"
        }
    """
    global conversation_history, current_character
    conversation_history = []
    current_character = None
    return jsonify({'message': 'Conversation reset'})


@app.route('/api/transcribe', methods=['POST'])
@app.route('/transcribe', methods=['POST'])
@limiter.limit("15 per minute")  # 5 transcriptions per minute per IP (stricter for cost protection)
@require_auth
def transcribe():
    """
    Transcribe audio file to text using OpenAI Whisper.
    
    Flow:
    1. Receives audio file (webm format from browser)
    2. Saves to temporary file
    3. Calls OpenAI Whisper API to transcribe
    4. Returns transcribed text
    
    Request:
        Form data with 'audio' file field
    
    Response:
        {
            "text": "transcribed text"
        }
    """
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400
    
    audio_file = request.files['audio']
    
    # Check file size (Whisper costs $0.006/minute, limit to prevent abuse)
    # Note: We can't easily check audio duration without processing, so limit file size
    audio_file.seek(0, os.SEEK_END)
    file_size = audio_file.tell()
    audio_file.seek(0)  # Reset to beginning
    
    if file_size > MAX_FILE_SIZE:
        return jsonify({
            'error': f'Audio file too large. Maximum {MAX_FILE_SIZE // (1024*1024)} MB allowed.'
        }), 400
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as tmp_file:
        audio_file.save(tmp_file.name)
        tmp_path = tmp_file.name
    
    try:
        # Use OpenAI Whisper for transcription
        transcript_text = transcribe_audio(tmp_path)
        
        # Clean up temp file
        os.unlink(tmp_path)
        
        return jsonify({'text': transcript_text})
        
    except Exception as e:
        # Clean up temp file on error
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return jsonify({'error': str(e)}), 500


@app.route('/api/upload', methods=['POST'])
@app.route('/upload', methods=['POST'])
@limiter.limit("10 per hour")  # 2 uploads per hour per IP (MOST EXPENSIVE - each upload generates many embeddings)
@require_auth
def upload_document():
    """
    Upload PDF or TXT file and add to Pinecone vector database.
    
    Flow:
    1. Receives file (PDF or TXT)
    2. Extracts text from file
    3. Chunks text into smaller pieces (1000 chars with 200 overlap)
    4. For each chunk:
       a. Generates embedding vector using OpenAI
       b. Stores in Pinecone with metadata containing full text
    5. Returns success message with chunk count
    
    Important:
    - Documents are stored persistently in Pinecone
    - Same Pinecone index is used every time (previous uploads remain accessible)
    - Full text is stored in metadata (no need to keep original files)
    
    Request:
        Form data with 'file' field (PDF or TXT)
    
    Response:
        {
            "message": "Successfully uploaded filename.pdf",
            "chunks_stored": 10,
            "total_chunks": 10
        }
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Check file size (prevent expensive processing of huge files)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # Reset to beginning
    
    if file_size > MAX_FILE_SIZE:
        return jsonify({
            'error': f'File too large. Maximum {MAX_FILE_SIZE // (1024*1024)} MB allowed.'
        }), 400
    
    # Check file type
    filename = file.filename
    file_ext = os.path.splitext(filename)[1].lower()
    if file_ext not in ['.pdf', '.txt', '.text']:
        return jsonify({'error': 'Unsupported file type. Please upload PDF or TXT files.'}), 400
    
    try:
        # Process file into chunks
        # Returns list of dicts: [{"content": "chunk text", "metadata": {...}}, ...]
        chunks = process_uploaded_file(file, filename)
        
        if not chunks:
            return jsonify({'error': 'Failed to extract text from file'}), 400
        
        # Get Pinecone index (creates if doesn't exist)
        index = get_or_create_index()
        if index is None:
            return jsonify({'error': 'Pinecone is not configured'}), 500
        
        # Store each chunk in Pinecone
        stored_count = 0
        errors = []
        for chunk_data in chunks:
            try:
                # Get embedding vector for this chunk
                # This converts text to a 1536-dimensional vector
                embedding = get_embedding(chunk_data["content"])
                
                # Prepare metadata (include full text for retrieval)
                # Pinecone returns metadata when querying, so we store full text here
                metadata = {
                    "content": chunk_data["content"],  # Full chunk text - this is what gets retrieved
                    "filename": chunk_data["metadata"]["filename"],
                    "chunk_index": chunk_data["metadata"]["chunk_index"],
                    "total_chunks": chunk_data["metadata"]["total_chunks"],
                    "type": "document_chunk",
                    "file_type": chunk_data["metadata"]["file_type"]
                }
                
                # Generate unique ID for this chunk
                chunk_id = f"doc_{uuid.uuid4()}_{chunk_data['metadata']['chunk_index']}"
                
                # Store in Pinecone (upsert = update or insert)
                # This is persistent - same index every time
                index.upsert(
                    vectors=[{
                        "id": chunk_id,
                        "values": embedding,  # The 1536-dim vector
                        "metadata": metadata  # The text + file info
                    }]
                )
                
                stored_count += 1
                
            except Exception as e:
                error_msg = f"Chunk {chunk_data['metadata']['chunk_index']}: {str(e)}"
                print(f"Error storing {error_msg}")
                errors.append(error_msg)
                continue
        
        if stored_count == 0:
            error_details = "; ".join(errors) if errors else "Unknown error"
            return jsonify({
                'error': f'Failed to store any chunks. Errors: {error_details}',
                'chunks_stored': 0,
                'total_chunks': len(chunks)
            }), 500
        
        response = {
            'message': f'Successfully uploaded {filename}',
            'chunks_stored': stored_count,
            'total_chunks': len(chunks)
        }
        
        if errors:
            response['warnings'] = f'Some chunks failed: {len(errors)}/{len(chunks)}'
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': f'Failed to process file: {str(e)}'}), 500


@app.route('/api/tts', methods=['POST'])
@app.route('/tts', methods=['POST'])
@limiter.limit("15 per minute")  # 7 TTS requests per minute per IP (stricter for cost protection)
@require_auth
def tts():
    """
    Convert text to speech using OpenAI TTS.
    
    Flow:
    1. Receives text to convert
    2. Calls OpenAI TTS API
    3. Returns audio file (MP3)
    
    Request body:
        {
            "text": "text to convert to speech",
            "voice": "onyx"  // optional, defaults to "onyx"
        }
    
    Response:
        Audio file (MP3) - can be played directly or saved
    """
    data = request.json
    text = data.get("text", "")
    voice = data.get("voice", "onyx")  # Options: alloy, echo, fable, onyx, nova, shimmer
    
    if not text:
        return jsonify({'error': 'Text is required'}), 400
    
    # Input validation - TTS costs $15 per 1M characters, limit text length
    if len(text) > MAX_MESSAGE_LENGTH:
        return jsonify({
            'error': f'Text too long for TTS. Maximum {MAX_MESSAGE_LENGTH} characters allowed.'
        }), 400
    
    try:
        # Generate speech audio bytes
        audio_bytes = text_to_speech(text, voice=voice)
        
        # Return as audio file
        return send_file(
            io.BytesIO(audio_bytes),
            mimetype='audio/mpeg',
            as_attachment=True,
            download_name='speech.mp3'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# FRONTEND SERVING (Must be last - catch-all for React Router)
# ============================================================================

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    """
    Serve React app for all non-API routes.
    This must be defined AFTER all API routes to avoid conflicts.
    
    Handles:
    - Static assets (JS, CSS, images) - serves files directly
    - React Router routes - serves index.html for all other paths
    - Page reloads - ensures index.html is served so React Router can handle routing
    """
    # Don't serve frontend for API routes (they're handled above)
    if path.startswith('api/'):
        return jsonify({'error': 'Not found'}), 404
    
    # Check if static folder exists (for production)
    # Try multiple path resolutions to handle different deployment scenarios
    static_path = None
    if app.static_folder:
        # Try 1: Relative to app.py location (most common)
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        candidate_path = os.path.abspath(os.path.join(backend_dir, app.static_folder))
        if os.path.exists(candidate_path):
            static_path = candidate_path
        else:
            # Try 2: Absolute path (if already absolute)
            if os.path.isabs(app.static_folder) and os.path.exists(app.static_folder):
                static_path = app.static_folder
            else:
                # Try 3: Relative to current working directory
                candidate_path = os.path.abspath(app.static_folder)
                if os.path.exists(candidate_path):
                    static_path = candidate_path
    
    if static_path and os.path.exists(static_path):
        
        # Normalize the path (remove leading/trailing slashes, handle ..)
        if path:
            # Remove leading slash if present
            path = path.lstrip('/')
            file_path = os.path.join(static_path, path)
            # Normalize the path to prevent directory traversal
            file_path = os.path.normpath(file_path)
            # Ensure it's still within static_path
            if not file_path.startswith(static_path):
                # Security: path outside static folder, serve index.html
                return send_from_directory(static_path, 'index.html')
            
            # Check if it's a file and exists
            if os.path.isfile(file_path):
                return send_from_directory(static_path, path)
        
        # For root path or any non-file path, serve index.html (React Router will handle routing)
        # This ensures page reloads work correctly - React Router handles client-side routing
        return send_from_directory(static_path, 'index.html')
    else:
        # In development, if frontend isn't built, return a helpful message
        return jsonify({
            'message': 'Frontend not built. Run: cd frontend && npm run build',
            'api_endpoints': ['/chat', '/transcribe', '/upload', '/tts', '/reset']
        }), 200


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug, host='0.0.0.0', port=port)

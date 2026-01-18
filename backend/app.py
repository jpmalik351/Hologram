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
from pinecone_service import get_or_create_index, get_embedding, delete_chunks
from database import db, init_db, UploadedFile
from file_utils import calculate_file_hash, get_next_version_filename, sanitize_filename
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

# Initialize database
init_db(app)

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
    Upload PDF or TXT file - Step 1: Check for duplicates
    
    Flow:
    1. Receives file (PDF or TXT)
    2. Calculates file hash
    3. Checks for duplicate in database
    4. If duplicate found, returns duplicate info (requires user confirmation)
    5. If no duplicate, processes and stores file
    
    Request:
        Form data with 'file' field (PDF or TXT)
    
    Response (no duplicate):
        {
            "message": "Successfully uploaded filename.pdf",
            "chunks_stored": 10,
            "file_id": 123
        }
    
    Response (duplicate found):
        {
            "duplicate": true,
            "existing_file": {...},
            "file_hash": "...",
            "file_size": 12345
        }
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Sanitize filename
    filename = sanitize_filename(file.filename)
    
    # Read file data (we need it for hash calculation)
    file_data = file.read()
    file_size = len(file_data)
    
    # Check file size
    if file_size > MAX_FILE_SIZE:
        return jsonify({
            'error': f'File too large. Maximum {MAX_FILE_SIZE // (1024*1024)} MB allowed.'
        }), 400
    
    # Check file type
    file_ext = os.path.splitext(filename)[1].lower()
    if file_ext not in ['.pdf', '.txt', '.text']:
        return jsonify({'error': 'Unsupported file type. Please upload PDF or TXT files.'}), 400
    
    try:
        # Calculate file hash for duplicate detection
        file_hash = calculate_file_hash(file_data)
        
        # Check for duplicate in database
        existing_file = UploadedFile.query.filter_by(file_hash=file_hash).first()
        
        if existing_file:
            # Duplicate found - return info and ask user what to do
            return jsonify({
                'duplicate': True,
                'existing_file': existing_file.to_dict(),
                'file_hash': file_hash,
                'file_size': file_size,
                'filename': filename
            })
        
        # No duplicate - process and store the file
        return _process_and_store_file(file_data, filename, file_hash, file_size, file_ext)
        
    except Exception as e:
        return jsonify({'error': f'Failed to process file: {str(e)}'}), 500


@app.route('/api/upload/confirm', methods=['POST'])
@app.route('/upload/confirm', methods=['POST'])
@limiter.limit("10 per hour")
@require_auth
def upload_document_confirm():
    """
    Upload PDF or TXT file - Step 2: Handle duplicate resolution
    
    Called when user chooses how to handle a duplicate file.
    
    Request body:
        {
            "file_hash": "sha256hash",
            "filename": "document.pdf",
            "file_size": 12345,
            "action": "overwrite" | "keep_both"
        }
    
    Note: File data must be re-uploaded in form data.
    
    Response:
        {
            "message": "Successfully uploaded filename.pdf",
            "chunks_stored": 10,
            "file_id": 123
        }
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    action = request.form.get('action')  # 'overwrite' or 'keep_both'
    
    if action not in ['overwrite', 'keep_both']:
        return jsonify({'error': 'Invalid action. Must be "overwrite" or "keep_both"'}), 400
    
    # Read file data
    filename = sanitize_filename(file.filename)
    file_data = file.read()
    file_size = len(file_data)
    file_ext = os.path.splitext(filename)[1].lower()
    
    try:
        # Calculate file hash
        file_hash = calculate_file_hash(file_data)
        
        # Find existing file
        existing_file = UploadedFile.query.filter_by(file_hash=file_hash).first()
        
        if action == 'overwrite':
            # Delete old chunks from Pinecone
            if existing_file and existing_file.chunk_ids:
                delete_chunks(existing_file.chunk_ids)
            
            # Delete old database record
            if existing_file:
                db.session.delete(existing_file)
                db.session.commit()
            
            # Process and store new file with same name
            return _process_and_store_file(file_data, filename, file_hash, file_size, file_ext)
        
        else:  # keep_both
            # Get all files to find next version number
            all_files = UploadedFile.query.all()
            all_filenames = [f.filename for f in all_files]
            
            # Generate versioned filename
            versioned_filename = get_next_version_filename(filename, all_filenames)
            
            # Process and store with versioned name
            return _process_and_store_file(file_data, versioned_filename, file_hash, file_size, file_ext, original_filename=filename)
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to process file: {str(e)}'}), 500


def _process_and_store_file(file_data: bytes, filename: str, file_hash: str, file_size: int, file_ext: str, original_filename: str = None):
    """
    Internal helper to process file and store in Pinecone + database.
    
    Args:
        file_data: File contents as bytes
        filename: Filename to use (may be versioned)
        file_hash: SHA256 hash of file
        file_size: Size in bytes
        file_ext: File extension
        original_filename: Original filename before versioning (optional)
    
    Returns:
        JSON response with upload success
    """
    # Save to temporary file for processing
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
        tmp_file.write(file_data)
        tmp_path = tmp_file.name
    
    try:
        # Create a file-like object for process_uploaded_file
        from io import BytesIO
        file_obj = BytesIO(file_data)
        
        # Process file into chunks
        chunks = process_uploaded_file(file_obj, filename)
        
        if not chunks:
            return jsonify({'error': 'Failed to extract text from file'}), 400
        
        # Get Pinecone index
        index = get_or_create_index()
        if index is None:
            return jsonify({'error': 'Pinecone is not configured'}), 500
        
        # Store each chunk in Pinecone and track chunk IDs
        chunk_ids = []
        stored_count = 0
        errors = []
        
        for chunk_data in chunks:
            try:
                # Get embedding vector
                embedding = get_embedding(chunk_data["content"])
                
                # Prepare metadata
                metadata = {
                    "content": chunk_data["content"],
                    "filename": filename,
                    "chunk_index": chunk_data["metadata"]["chunk_index"],
                    "total_chunks": chunk_data["metadata"]["total_chunks"],
                    "type": "document_chunk",
                    "file_type": file_ext
                }
                
                # Generate unique ID
                chunk_id = f"doc_{uuid.uuid4()}_{chunk_data['metadata']['chunk_index']}"
                chunk_ids.append(chunk_id)
                
                # Store in Pinecone
                index.upsert(
                    vectors=[{
                        "id": chunk_id,
                        "values": embedding,
                        "metadata": metadata
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
            }), 500
        
        # Save file record to database
        uploaded_file = UploadedFile(
            filename=filename,
            original_filename=original_filename or filename,
            file_hash=file_hash,
            file_size=file_size,
            file_type=file_ext,
            chunk_ids=chunk_ids,
            chunk_count=stored_count
        )
        db.session.add(uploaded_file)
        db.session.commit()
        
        response = {
            'message': f'Successfully uploaded {filename}',
            'chunks_stored': stored_count,
            'file_id': uploaded_file.id
        }
        
        if errors:
            response['warnings'] = f'Some chunks failed: {len(errors)}/{len(chunks)}'
        
        return jsonify(response)
        
    finally:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


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


@app.route('/api/files', methods=['GET'])
@app.route('/files', methods=['GET'])
@require_auth
def list_files():
    """
    List all uploaded files with optional search/filter.
    
    Query parameters:
        search: Optional search term to filter by filename
        sort_by: Field to sort by (upload_date, filename, file_size) - default: upload_date
        order: Sort order (asc, desc) - default: desc
    
    Response:
        {
            "files": [
                {
                    "id": 1,
                    "filename": "document.pdf",
                    "original_filename": "document.pdf",
                    "file_size": 12345,
                    "file_type": ".pdf",
                    "upload_date": "2024-01-01T12:00:00",
                    "chunk_count": 10
                },
                ...
            ],
            "total": 5
        }
    """
    try:
        # Get query parameters
        search_term = request.args.get('search', '').strip()
        sort_by = request.args.get('sort_by', 'upload_date')
        order = request.args.get('order', 'desc')
        
        # Build query
        query = UploadedFile.query
        
        # Apply search filter if provided
        if search_term:
            query = query.filter(
                UploadedFile.filename.ilike(f'%{search_term}%')
            )
        
        # Apply sorting
        sort_field = getattr(UploadedFile, sort_by, UploadedFile.upload_date)
        if order == 'desc':
            query = query.order_by(sort_field.desc())
        else:
            query = query.order_by(sort_field.asc())
        
        # Execute query
        files = query.all()
        
        # Convert to dict
        files_data = [f.to_dict() for f in files]
        
        return jsonify({
            'files': files_data,
            'total': len(files_data)
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve files: {str(e)}'}), 500


@app.route('/api/files/<int:file_id>', methods=['DELETE'])
@app.route('/files/<int:file_id>', methods=['DELETE'])
@require_auth
def delete_file(file_id):
    """
    Delete uploaded file and all its chunks from Pinecone.
    
    Flow:
    1. Find file in database
    2. Delete all chunks from Pinecone using stored chunk IDs
    3. Delete database record
    
    Path parameters:
        file_id: ID of file to delete
    
    Response:
        {
            "message": "File deleted successfully",
            "filename": "document.pdf",
            "chunks_deleted": 10
        }
    """
    try:
        # Find file in database
        uploaded_file = UploadedFile.query.get(file_id)
        
        if not uploaded_file:
            return jsonify({'error': 'File not found'}), 404
        
        # Delete chunks from Pinecone
        chunks_deleted = 0
        if uploaded_file.chunk_ids:
            try:
                delete_chunks(uploaded_file.chunk_ids)
                chunks_deleted = len(uploaded_file.chunk_ids)
            except Exception as e:
                print(f"Error deleting chunks from Pinecone: {str(e)}")
                # Continue with database deletion even if Pinecone deletion fails
        
        # Store filename for response
        filename = uploaded_file.filename
        
        # Delete from database
        db.session.delete(uploaded_file)
        db.session.commit()
        
        return jsonify({
            'message': 'File deleted successfully',
            'filename': filename,
            'chunks_deleted': chunks_deleted
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to delete file: {str(e)}'}), 500


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

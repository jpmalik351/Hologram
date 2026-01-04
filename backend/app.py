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

from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
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

# ============================================================================
# CONVERSATION STATE (In-Memory, Per Session)
# ============================================================================

# Store conversation history as list of message dicts
# Format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
# This is NOT persisted - each session starts fresh
conversation_history = []

# Context configuration
# For character chatbots, 6-10 messages (3-5 exchanges) is usually enough
# System prompt maintains character consistency, recent context just helps conversation flow
MAX_CONTEXT_MESSAGES = 10  # Last 10 messages (5 exchanges) - optimal for character chatbots
# Too much context can actually dilute character consistency

# ============================================================================
# CHARACTER CONFIGURATION
# ============================================================================

# Character system prompt - defines how the character responds
# This is sent with every request to maintain character consistency
CHARACTER_SYSTEM_PROMPT = """You are Batman, the Dark Knight of Gotham City. You are speaking to someone who needs your help or wants to talk.

Respond as Batman would:
- You are serious, focused, and mission-driven
- You speak with authority and determination
- You're protective and want to help people
- You might reference Gotham, justice, or your mission
- You're direct but not unkind
- Keep responses concise and in character
- Don't break character or mention that you're an AI

Remember: You ARE Batman. Stay in character throughout the conversation."""

# ============================================================================
# RAG CONFIGURATION
# ============================================================================

# Set to True to enable RAG (requires Pinecone with character knowledge base)
# When enabled, retrieves relevant knowledge from Pinecone and adds to system prompt
USE_RAG = True  # Enabled for testing with Batman knowledge

# ============================================================================
# API ENDPOINTS
# ============================================================================

# Support both /api/chat and /chat for compatibility
@app.route('/api/chat', methods=['POST'])
@app.route('/chat', methods=['POST'])
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
    global conversation_history

    data = request.json
    user_message = data.get("message", "")
    if not user_message:
        return jsonify({'error': 'Message is required'}), 400
    
    try:
        # Build messages array for OpenAI API
        messages = []
        
        # Build system prompt with optional RAG context
        system_content = CHARACTER_SYSTEM_PROMPT
        
        # Add RAG knowledge if enabled (STRICT MODE - only use provided context)
        if USE_RAG:
            try:
                from rag_service import retrieve_character_knowledge
                # Retrieve top 3 most relevant knowledge chunks from Pinecone
                knowledge = retrieve_character_knowledge(user_message, top_k=3)
                if knowledge:
                    # STRICT RAG: Only answer based on provided knowledge
                    # This ensures the character only uses information from uploaded documents
                    system_content += f"""

IMPORTANT - STRICT KNOWLEDGE REQUIREMENTS:
You have been provided with the following knowledge from historical sources:

{knowledge}

CRITICAL RULES:
1. You MUST ONLY use information from the knowledge provided above
2. If the knowledge doesn't contain information to answer the question, say "I don't have that information in my knowledge base"
3. DO NOT make up facts, details, or information not in the provided knowledge
4. DO NOT use general knowledge - only use what's explicitly in the knowledge above
5. Stay in character, but be truthful to the sources provided
6. If asked about something not in the knowledge, acknowledge you don't have that information

Stay in character, but be strictly truthful to the provided knowledge."""
            except ImportError:
                pass  # RAG not available, continue without it
        
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
def reset():
    """
    Reset conversation history and start a new conversation session.
    
    This clears the in-memory conversation history. Note: This does NOT affect
    the Pinecone knowledge base (uploaded documents remain available).
    
    Response:
        {
            "message": "Conversation reset"
        }
    """
    global conversation_history
    conversation_history = []
    return jsonify({'message': 'Conversation reset'})


@app.route('/api/transcribe', methods=['POST'])
@app.route('/transcribe', methods=['POST'])
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
    """
    # Don't serve frontend for API routes (they're handled above)
    if path.startswith('api/'):
        return jsonify({'error': 'Not found'}), 404
    
    # Check if static folder exists (for production)
    if app.static_folder and os.path.exists(app.static_folder):
        # If path exists as a file, serve it
        if path and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        # Otherwise serve index.html (for React Router)
        return send_from_directory(app.static_folder, 'index.html')
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

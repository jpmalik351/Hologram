# Handoff Guide

This document is for engineers taking ownership of the project.

## Architecture at a Glance

- Single Flask service serves:
  - API routes under `/api/*`
  - built React frontend (`frontend/dist`)
- Frontend provides two main tabs:
  - Chat (voice + text)
  - Files (upload/manage knowledge docs)
- Knowledge storage split:
  - Pinecone stores embeddings and text chunks (persistent)
  - SQL DB stores uploaded file metadata and chunk IDs
- Conversation state is in-memory per authenticated session.

## Code Map (Where To Look First)

- `backend/app.py`
  - Request orchestration, auth/session, route handlers
  - RAG toggle: `USE_RAG`
  - Context window: `MAX_CONTEXT_MESSAGES`
  - Character prompt construction: `build_character_system_prompt()`

- `backend/openai_service.py`
  - `call_llm()` chat completions
  - `transcribe_audio()` whisper transcription
  - `text_to_speech()` tts generation

- `backend/rag_service.py`
  - `retrieve_character_knowledge()` semantic retrieval from Pinecone

- `backend/pinecone_service.py`
  - `get_or_create_index()` Pinecone index lifecycle
  - `get_embedding()` embedding generation
  - `delete_chunks()` vector cleanup

- `backend/database.py`
  - `init_db()` DB connection configuration
  - `UploadedFile` model for upload metadata

- `backend/document_processor.py`
  - text extraction and chunking

- `frontend/src/App.jsx`
  - app shell, auth check, tab state, message send flow

- `frontend/src/components/FilesManager.jsx`
  - file list/filter/delete UX

- `frontend/src/components/FileUpload.jsx`
  - upload + duplicate resolution flow

## Request Flows

### Chat Flow

1. Frontend sends `/api/chat` with message.
2. Backend resolves session context and current character.
3. If RAG enabled, backend retrieves top chunks from Pinecone.
4. Backend builds strict character system prompt and sends to OpenAI chat model.
5. Response is returned; frontend auto-calls `/api/tts` to speak it.

### Upload Flow

1. Frontend sends file to `/api/upload`.
2. Backend computes SHA256 hash and checks duplicates in SQL DB.
3. If duplicate, frontend prompts for overwrite vs keep-both.
4. File text is extracted/chunked and chunk embeddings are upserted to Pinecone.
5. File metadata + chunk IDs are stored in SQL DB.

## Capabilities

- Authenticated chat UI with session cookies.
- Character selection from natural phrase matching (e.g. "talk to X").
- Strictly grounded RAG-style prompting.
- PDF/TXT ingestion with chunking and duplicate handling.
- Files management with search/sort/delete.
- Voice input (Whisper) and voice output (TTS).
- Basic rate limiting and request size limits for cost control.

## Limitations

- Conversation history is in-memory and expires with session timeout/app restarts.
- File history persistence depends on DB config; SQLite fallback is not durable across many deployment scenarios.
- RAG retrieval does not yet hard-filter by character metadata/namespace.
- Minimal automated test coverage in current repo.
- Logging is improved but still application-level (no centralized observability stack).

## Configuration Reference

- `.env.example` is the source-of-truth template for local/dev variable names.
- `render.yaml` is the source-of-truth deployment config.

### Database Swap Snippets

Use this section when moving from SQLite/Render Postgres to another persistent DB.

**Current pattern in `backend/database.py`:**

```python
database_url = os.environ.get('DATABASE_URL')

if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///hologram.db'
```

**Recommended production-safe variant (fail fast outside local):**

```python
database_url = os.environ.get("DATABASE_URL")
flask_env = os.environ.get("FLASK_ENV", "development")

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

if flask_env == "production" and not database_url:
    raise RuntimeError("DATABASE_URL is required in production")

app.config["SQLALCHEMY_DATABASE_URI"] = database_url or "sqlite:///hologram.db"
```

**Switching to Neon/Supabase/managed Postgres:**

- Set only `DATABASE_URL` to provider connection string in Render.
- No code change needed if provider is Postgres-compatible.
- Keep `psycopg2-binary` in `backend/requirements.txt`.

### Model and Retrieval Tuning

- **Chat model**
  - Env var: `OPENAI_MODEL`
  - Code path: `backend/openai_service.py` -> `call_llm()`

- **Embedding model**
  - Hardcoded in `backend/pinecone_service.py` -> `get_embedding()`
  - Current: `text-embedding-3-small` with `dimensions=1024`
  - If changed, keep Pinecone index dimension aligned.

- **RAG retrieval count**
  - `top_k` currently set in `backend/app.py` when calling `retrieve_character_knowledge(..., top_k=5)`.

- **Conversation context size**
  - `MAX_CONTEXT_MESSAGES` in `backend/app.py`.

- **RAG toggle**
  - `USE_RAG` in `backend/app.py`.

### Swapping Model Providers (Code Snippets)

Current chat call uses OpenAI in `backend/openai_service.py`:

```python
response = client.chat.completions.create(
    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    messages=messages,
    max_tokens=300,
    temperature=0.7
)
```

Note: embeddings are currently OpenAI-dependent in `backend/pinecone_service.py`. If chat provider changes but embeddings stay OpenAI, keep `OPENAI_API_KEY`. If embeddings also move, update `get_embedding()` and ensure vector dimensions match Pinecone index.

## Operational Debugging Notes

- Backend now emits structured route-level logs for:
  - login/logout
  - chat request/response
  - RAG retrieval presence
  - upload and duplicate actions
  - files list/delete operations
- Check Render logs first for env misconfigurations and external API failures.

## Suggested First Improvements for New Owner

1. Use a durable PostgreSQL deployment configuration so file upload history remains persistent across sessions and restarts.
2. Add metadata-based character filtering in Pinecone retrieval.
3. Add API tests for auth/chat/upload/files flows.
4. Add an endpoint such as `/api/chat/suggestions` to help users map natural language requests to likely character names.

## First 30 Minutes for a New Engineer

Use this quick checklist for first-day orientation.

1. Read `README.md` (5 min) to understand product and repo layout.
2. Read `docs/RENDER_SETUP.md` (10 min) to understand production wiring and env vars.
3. Run locally:
   - `cp .env.example .env`
   - `cd frontend && npm install && npm run build`
   - `cd ../backend && pip install -r requirements.txt && python app.py`
4. Verify core flow in browser (10 min):
   - login
   - upload one `.txt`
   - ask for character chat
   - verify file list and delete
5. Open these files in order for code orientation:
   - `backend/app.py`
   - `backend/openai_service.py`
   - `backend/rag_service.py`
   - `backend/database.py`
   - `frontend/src/App.jsx`
   - `frontend/src/components/FilesManager.jsx`

Backend logs are the first place to check for most setup/runtime failures, especially env/service misconfiguration.

## STT/TTS Model Swaps

STT/TTS can now be switched using env vars, similar to `OPENAI_MODEL`.

- `STT_MODEL` (default `whisper-1`)
- `TTS_MODEL` (default `tts-1`)
- `TTS_VOICE` (default `onyx`)

Current code path in `backend/openai_service.py`:

```python
stt_model = os.getenv("STT_MODEL", "whisper-1")
...
model=stt_model
```

```python
tts_model = os.getenv("TTS_MODEL", "tts-1")
resolved_voice = voice or os.getenv("TTS_VOICE", "onyx")
...
model=tts_model,
voice=resolved_voice
```

Provider-family swaps (for example OpenAI -> other STT/TTS vendors) still require code changes, but the same adapter pattern used for `call_llm()` can be applied to `transcribe_audio()` and `text_to_speech()`.

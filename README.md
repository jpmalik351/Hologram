# Hologram

Character-first voice chat app with retrieval-augmented responses from your uploaded documents.

## What It Does

- Chat with a selected character using text or voice input.
- Transcribe microphone audio with Whisper and auto-play responses with OpenAI TTS.
- Upload PDF/TXT documents to build a Pinecone-backed knowledge base.
- Use strict RAG prompting so responses are grounded in retrieved chunks.
- Manage uploaded files (list/search/sort/delete) from the UI.

## Tech Stack

- Backend: Flask + SQLAlchemy + Flask-Limiter
- Frontend: React (Vite)
- AI services: OpenAI (chat, embeddings, STT, TTS)
- Vector store: Pinecone
- File metadata DB: PostgreSQL in production (Render), SQLite fallback locally

## Quick Start (Local)

1. Copy env template and fill required keys:
   - `cp .env.example .env`
2. Build and run frontend:
   - `cd frontend && npm install && npm run build`
3. Install and run backend:
   - `cd ../backend && pip install -r requirements.txt && python app.py`
4. Open `http://localhost:5000`.

## Deployment

Render is the primary deployment target, wired via `render.yaml`.

- Full setup: `docs/RENDER_SETUP.md`
- Deep technical handoff: `docs/HANDOFF_GUIDE.md`
- Implementation roadmap: `docs/TODO.md`

## Repository Map

- `backend/app.py` Flask routes, auth, session conversation state, upload/file APIs
- `backend/openai_service.py` OpenAI wrappers (chat, whisper, TTS)
- `backend/rag_service.py` retrieval from Pinecone
- `backend/pinecone_service.py` index + embeddings + vector deletion
- `backend/database.py` DB initialization + `UploadedFile` model
- `backend/document_processor.py` PDF/TXT extraction + chunking
- `frontend/src/App.jsx` main authenticated app shell (chat/files tabs)

## Current Limitations

- Conversation history is session-scoped in memory and not persisted across restarts.
- `/api/files` depends on the configured database; running without persistent Postgres can make uploaded file history appear session/local-instance bound.
- RAG retrieval is semantic but not character-filtered by namespace/metadata yet.
- Render free tier has strict limits; depending on usage, optimization or a higher-tier/alternative hosting plan may be needed.
- LLM/STT/TTS model names are env-driven; switching provider families requires small adapter changes in backend service wrappers.

## License

Private/internal project unless otherwise specified by owner.

# Backend Reference

Flask backend that powers chat, voice, document upload, and file management APIs.

## Run Locally

1. Install dependencies:
   - `pip install -r requirements.txt`
2. Configure env vars using project root `.env.example`.
3. Start server:
   - `python app.py`

## Main Endpoints

- `POST /api/login` and `POST /api/logout`
- `GET /api/auth/check`
- `POST /api/chat`
- `POST /api/transcribe`
- `POST /api/tts`
- `POST /api/upload`
- `POST /api/upload/confirm`
- `GET /api/files`
- `DELETE /api/files/<file_id>`
- `POST /api/reset`

## Important Files

- `app.py` route handlers and orchestration
- `openai_service.py` OpenAI wrappers
- `pinecone_service.py` Pinecone operations and embeddings
- `rag_service.py` retrieval helpers
- `database.py` SQLAlchemy config and models
- `document_processor.py` extraction/chunking

## Notes

- Session conversations are in-memory and short-lived.
- Uploaded file metadata is persisted in configured DB.
- Vector chunks live in Pinecone and are referenced by DB chunk IDs.

For full system handoff details, use:

- `../docs/HANDOFF_GUIDE.md`
- `../docs/RENDER_SETUP.md`
- `../docs/TODO.md`


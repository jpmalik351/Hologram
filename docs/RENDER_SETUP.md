# Render Setup Guide

This guide is the canonical deployment reference for handing off this project.

## 1) Prerequisites

- GitHub repo with this project pushed.
- Render account connected to GitHub.
- OpenAI API key.
- Pinecone project + API key.
- Optional but recommended: external Postgres provider (Neon/Supabase) if you do not want Render free-tier DB constraints.

## 2) Deploy via `render.yaml` (Recommended)

At repo root, this file defines:

- a Postgres service: `hologram-db`
- a web service: `hologram-chatbot`
- build command: `chmod +x build.sh && ./build.sh`
- start command: gunicorn serving `backend/app.py`

In Render:

1. Click **New +** -> **Blueprint**.
2. Select this GitHub repo.
3. Confirm services from `render.yaml`.
4. Deploy.

## 2.1) Is Flask Needed on Render?

Yes. Render is the hosting platform; Flask is still the backend web framework.

- **Local:** you run Flask directly (`python backend/app.py`) and Flask serves API + built frontend.
- **Render:** Render runs your Flask app via gunicorn (`startCommand` in `render.yaml`).
- **What Render replaces:** VM/container setup, networking, TLS, process management, deployment automation.
- **What Render does NOT replace:** your app code/framework (Flask), route handlers, business logic.

## 3) Required Environment Variables

These are required for full functionality:

- `OPENAI_API_KEY` (secret)
- `PINECONE_API_KEY` (secret)
- `AUTH_CREDENTIALS` (secret; format `user1:pass1,user2:pass2`)
- `FLASK_SECRET_KEY` (secret; long random string)

Notes:

- Current application code expects `AUTH_CREDENTIALS` for login (`/api/login`).
- If you replace app-level auth with another provider, update backend auth logic and then remove `AUTH_CREDENTIALS` dependency.

Set defaults already defined in `render.yaml`:

- `OPENAI_MODEL=gpt-4o-mini`
- `STT_MODEL=whisper-1` (optional override)
- `TTS_MODEL=tts-1` (optional override)
- `TTS_VOICE=onyx` (optional override)
- `PINECONE_INDEX_NAME=hologram-conversations`
- `PINECONE_REGION=us-east-1`
- `FLASK_ENV=production`
- `PYTHON_VERSION=3.11.0`

Database wiring in `render.yaml`:

- `DATABASE_URL` comes from `hologram-db` connection string automatically.

## 4) External Services and Where They Are Used

- **OpenAI**
  - Chat model in `backend/openai_service.py` (`call_llm`)
  - Whisper STT in `backend/openai_service.py` (`transcribe_audio`)
  - TTS in `backend/openai_service.py` (`text_to_speech`)
  - Embeddings in `backend/pinecone_service.py` (`get_embedding`)

- **Pinecone**
  - Index creation/access in `backend/pinecone_service.py` (`get_or_create_index`)
  - Retrieval in `backend/rag_service.py` (`retrieve_character_knowledge`)
  - Deletion of chunk vectors in `backend/pinecone_service.py` (`delete_chunks`)

- **Database (Postgres/SQLite)**
  - Initialization and model definitions in `backend/database.py`
  - File metadata reads/writes in `backend/app.py` (`/api/upload`, `/api/files`, `/api/files/<id>`)

## 5) Smoke Test Checklist

After deploy, verify:

1. Login works with `AUTH_CREDENTIALS`.
2. Upload one small `.txt` file in Files tab.
3. Confirm file appears in files list.
4. Start chat: "I'd like to speak to Batman".
5. Ask a question from uploaded doc and verify grounded response.
6. Test voice record and TTS playback.

## 6) Common Failure Modes

- **Build fails for frontend**
  - Check `build.sh` output; ensure Node/npm steps run successfully.

- **500 on chat/upload**
  - Usually missing `OPENAI_API_KEY` or `PINECONE_API_KEY`.

- **No files shown**
  - Verify `DATABASE_URL` points to persistent Postgres in Render env.
  - Check app logs for `[FILES_API]` messages.

- **Authentication not configured**
  - `AUTH_CREDENTIALS` not set or malformed.

## 7) Swapping Models (Production)

Change `OPENAI_MODEL` in Render env variables.

- Default: `gpt-4o-mini`
- Higher quality / higher cost: e.g. `gpt-4o`

No code change needed for chat model swap because `call_llm()` reads from env.

### Provider Swap Example (OpenAI -> another provider)

If only changing OpenAI model, env-only update is enough.
If changing provider family (for example Anthropic or Bedrock), update `backend/openai_service.py` to branch by `LLM_PROVIDER`.

Minimal pattern:

```python
provider = os.getenv("LLM_PROVIDER", "openai")

if provider == "openai":
    # existing OpenAI call
    ...
elif provider == "anthropic":
    # anthropic API call
    ...
elif provider == "bedrock":
    # bedrock invoke call
    ...
```

Also set provider-specific keys in Render env vars.

### STT/TTS Model Swap Example

These can be changed by environment variables without code changes (within OpenAI-supported options):

- `STT_MODEL` (default `whisper-1`)
- `TTS_MODEL` (default `tts-1`)
- `TTS_VOICE` (default `onyx`)

Changing to a different provider family for STT/TTS requires updating `backend/openai_service.py` similar to LLM provider branching.

### Database Swap Example (Render DB -> external Postgres)

For Neon/Supabase/other Postgres, set `DATABASE_URL` directly in Render Web Service env vars to the external connection string.

No schema code change is required if URL is valid Postgres.

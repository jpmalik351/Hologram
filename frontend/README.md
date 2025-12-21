# Hologram Frontend

React frontend for the Hologram chat application with voice recording capabilities.

## Setup

1. Install dependencies:
```bash
npm install
```

2. Start the development server:
```bash
npm run dev
```

The app will be available at `http://localhost:3000`

## Features

- Chat window displaying conversation history
- Voice recording button (hold to talk)
- Automatic transcription of audio recordings
- Integration with backend chat API

## Backend Requirements

Make sure the Flask backend is running on `http://localhost:5000` with:
- `/chat` endpoint for sending messages
- `/transcribe` endpoint for audio transcription


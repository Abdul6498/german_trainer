# Roadmap

## Implemented

- FastAPI backend for trainer sessions
- Browser frontend with study, quiz, and result views
- AI-backed word profiles, study notes, and sentence feedback
- Daily new-word goal support
- Local progress/history/word metadata persistence

## Next

- Add user-editable settings inside the frontend
- Add audio playback from the browser with selectable voices
- Add richer detail view tabs for nouns, verbs, and grammar notes
- Add import/export for custom vocabulary packs

## Known gaps

- The checked-in frontend JS is browser-ready, but there is not yet a Node build pipeline in the repo
- Audio currently uses browser speech synthesis rather than a backend-generated stream in the web UI
- The session state is single-user and in-memory, which is fine locally but not designed for multi-user deployment


# Roadmap

## Implemented

- Timed popup scheduler with configurable interval
- Vocabulary translation quizzes (EN -> DE) using CEFR curriculum + `wonderwords`
- Article practice (`der/die/das`)
- Sentence creation validation
- Verb/adjective/adverb lookup with `verbformen-cli` API and noun metadata via `german-nouns`
- Spaced repetition with per-word `next_review`
- Pronunciation playback using `gTTS`
- Session statistics with `rich`
- Skip shortcut (`Esc`) and CEFR level controls (`A1`..`C2`)
- Immediate repeat for incorrect answers until correct
- "I have learned this word" checkbox to mark and skip words
- Study-first architecture: show German+details first, then quiz only after user confirms understanding
- Rich dictionary details in UI from `german-nouns` (flexion/compound) and `verbformen-cli`
- Session mode switch: `mixed`, `study-only`, `quiz-only`
- Table-based study view with `basic` and `detail` layouts
- AI level-aware word explanation in study view and AI sentence translation/structure feedback in result view

## Next features

- Add strictness levels for answer matching (normal/lenient/strict)
- Add full fill-in-the-blank UI variant with dedicated prompt field
- Add grammar drill modes (Akkusativ, Dativ, adjective endings)
- Add import/export for vocabulary packs

## Known gaps

- Some grammar lookups rely on fallback heuristics if external tools fail
- Translation and TTS may need internet connectivity depending package behavior
- Verb conjugation parsing is resilient but not tied to one guaranteed CLI output format
- WSL without WSLg will not display tkinter popups

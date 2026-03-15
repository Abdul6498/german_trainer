# Architecture

## Module map

- `main.py`: composition root, CLI config, scheduler loop, mode routing (`mixed/study-only/quiz-only`)
- `engine/quiz_engine.py`: quiz creation + answer evaluation
- `engine/spaced_repetition.py`: review interval decisions
- `engine/grammar_checker.py`: noun metadata + POS/conjugations via `german-nouns` + `verbformen-cli`
- `engine/sentence_generator.py`: sentence templates and validation
- `services/translator.py`: EN -> DE translation adapter
- `services/word_source.py`: CEFR curriculum + `wonderwords` generation + level-scoped cached files + weighted selection
- `services/pronunciation.py`: text-to-speech playback
- `services/progress_tracker.py`: JSON persistence for progress/stats
- `services/ai_sentence_service.py`: optional OpenAI sentence generation/correction + level-aware word explanation + sentence structure analysis
- `services/sentence_checker.py`: local LanguageTool grammar checks
- `ui/quiz_window.py`: user input popup
- `ui/result_window.py`: feedback popup
- `ui/study_window.py`: study-first popup using table-based rendering (`basic` or `detail` view)

## Data flow

1. Scheduler triggers a session.
2. `WordSource` builds a CEFR-focused pool (`A1`..`C2`) and stores it in `data/generated_words_<level>.txt`, then picks using weighted selection (mistakes + due words).
3. `TranslatorService` translates EN word to DE.
4. `GrammarChecker` derives noun metadata from `german-nouns` and verb/adjective/adverb details from `verbformen-cli`.
5. `ProgressTracker` checks learning stage (`study` or `quiz`) for the word.
6. Mode routing:
   - `study-only`: always `StudyWindow`
   - `quiz-only`: always `QuizWindow`
   - `mixed`: stage-based `study -> quiz`
7. `StudyWindow` shows full word details (including noun flexion/compound parsing and verbformen metadata) and can promote to `quiz`.
8. `QuizWindow` collects translation/article/type/sentence.
9. `QuizEngine.evaluate()` checks answer correctness, optionally requests AI sentence translation/structure notes, and updates spaced repetition/history.
10. `ResultWindow` displays expected answer and examples.
11. `rich` prints current stats in terminal.

## Extension points

- Add a new exercise mode by extending `focus_mode` behavior in `QuizEngine`.
- Add API providers by introducing new service adapters in `services/` and injecting into `QuizEngine`.
- Swap persistence by replacing `ProgressTracker` with a DB-backed implementation using the same public methods.

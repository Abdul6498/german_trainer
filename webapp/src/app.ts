type SessionStage = "idle" | "study" | "quiz" | "result";

interface SessionResponse {
  stage: SessionStage;
  interval_minutes: number;
  next_due_in_seconds: number;
  pace: "timed" | "continuous";
  focus_timeout_minutes: number;
  daily_goal_words: number;
  srs_intensity: string;
  level: string;
  new_words_today: number;
  mode: string;
  practice_mode: "learn-new" | "repeat-practice" | "story";
  view: string;
  idle_message: string;
  quiz: QuizPayload | null;
  result: Record<string, unknown> | null;
  stats: StatsPayload;
}

interface QuizPayload {
  english_word: string;
  german_word: string;
  word_type: string;
  cefr_level: string;
  is_new: boolean;
  noun_info: {
    article: string;
    plural: string;
    gender: string;
  };
  examples: string[];
  ai_word_notes: string[];
  conjugations: Record<string, string>;
  analysis_details: Record<string, unknown>;
  story: Record<string, unknown>;
  focus_mode: string;
}

interface StatsPayload {
  total_questions: number;
  correct_answers: number;
  wrong_answers: number;
  accuracy: number;
  last_updated: string;
}

const state = {
  session: null as SessionResponse | null,
  settingsOpen: false,
  activeStudyKey: null as string | null,
  activeQuizKey: null as string | null,
  activeCardStartedAt: 0,
  timeoutExceeded: false,
};

let countdownHandle: number | null = null;
let refreshInFlight = false;
let autoTriggerPending = false;

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  return (await response.json()) as T;
}

async function speakGerman(text: string): Promise<void> {
  if (!text.trim()) return;
  const audio = new Audio(`/api/pronunciation?text=${encodeURIComponent(text)}`);
  audio.preload = "auto";
  await audio.play();
}

function setVisible(id: string, visible: boolean): void {
  document.getElementById(id)?.classList.toggle("hidden", !visible);
}

function setText(id: string, value: string): void {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function fillPills(id: string, items: string[]): void {
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = "";
  items.forEach((item) => {
    const pill = document.createElement("span");
    pill.className = "pill";
    pill.textContent = item;
    el.appendChild(pill);
  });
}

function fillList(id: string, items: string[], speakable = false): void {
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = "";
  items.forEach((item) => {
    const li = document.createElement("li");
    if (speakable) {
      li.className = "speakable-item";
      const button = document.createElement("button");
      button.type = "button";
      button.className = "speak-inline-button list-speak-button";
      button.setAttribute("aria-label", `Pronounce sentence: ${item}`);
      button.textContent = "🔊";
      button.addEventListener("click", () => void speakGerman(item));
      const text = document.createElement("span");
      text.textContent = item;
      li.appendChild(button);
      li.appendChild(text);
    } else {
      li.textContent = item;
    }
    el.appendChild(li);
  });
}

function applyViewMode(view: string): void {
  document.body.classList.toggle("view-basic", view === "basic");
  document.body.classList.toggle("view-detail", view === "detail");
  setVisible("studyNotesCard", view === "detail");
  setVisible("resultExamplesCard", view === "detail");
}

function setSettingsOpen(open: boolean): void {
  state.settingsOpen = open;
  setVisible("settingsOverlay", open);
  setVisible("settingsDrawer", open);
  const drawer = document.getElementById("settingsDrawer");
  if (drawer) drawer.setAttribute("aria-hidden", open ? "false" : "true");
}

function setBadge(stage: SessionStage): void {
  const badge = document.getElementById("stageBadge");
  if (!badge) return;
  badge.textContent = stage;
  badge.className = `status-pill status-${stage}`;
}

function setTimeoutState(active: boolean): void {
  state.timeoutExceeded = active;
  setVisible("timeoutBadge", active);
  document.getElementById("studyCard")?.classList.toggle("card-timeout", active && state.session?.stage === "study");
  document.getElementById("quizCard")?.classList.toggle("card-timeout", active && state.session?.stage === "quiz");
}

function setResultChecks(items: Array<{ label: string; ok: boolean }>): void {
  const el = document.getElementById("resultChecks");
  if (!el) return;
  el.innerHTML = "";
  items.forEach((item) => {
    const li = document.createElement("li");
    li.className = item.ok ? "ok" : "bad";
    li.textContent = item.label;
    el.appendChild(li);
  });
}

function formatCountdown(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

function formatSettingLabel(value: string): string {
  const normalized = value.trim().toLowerCase();
  const labels: Record<string, string> = {
    "mixed": "Mixed",
    "study-only": "Study Only",
    "quiz-only": "Quiz Only",
    "learn-new": "New",
    "repeat-practice": "Review",
    "story": "Story",
  };
  return labels[normalized] ?? value.replace(/-/g, " ");
}

function currentSpokenWord(): string {
  const quiz = state.session?.quiz;
  if (!quiz) return "";
  if (quiz.word_type === "noun" && quiz.noun_info.article) {
    return `${quiz.noun_info.article} ${quiz.german_word}`;
  }
  return quiz.german_word;
}

function currentStoryText(): string {
  const story = (state.session?.quiz?.story || {}) as Record<string, unknown>;
  return String(story.text || "").trim();
}

function currentQuizSpeakText(): string {
  const quiz = state.session?.quiz;
  if (!quiz) return "";
  if (quiz.focus_mode === "story") {
    const story = (quiz.story || {}) as Record<string, unknown>;
    return (
      String(story.topic || "").trim() ||
      String(story.title || "").trim() ||
      String(story.question || "").trim() ||
      currentStoryText()
    );
  }
  return currentSpokenWord();
}

function render(): void {
  const session = state.session;
  if (!session) return;

  setText("modeValue", formatSettingLabel(session.mode));
  setText("practiceModeValue", formatSettingLabel(session.practice_mode));
  setText("levelValue", session.level || session.quiz?.cefr_level || "-");
  setText("countdownValue", session.pace === "continuous" ? "instant" : formatCountdown(session.next_due_in_seconds));
  setText("goalValue", `${session.new_words_today}/${session.daily_goal_words}`);
  setText("accuracyValue", `${session.stats.accuracy.toFixed(0)}%`);
  setText("questionsValue", String(session.stats.total_questions));
  setText("correctValue", String(session.stats.correct_answers));
  setText("wrongValue", String(session.stats.wrong_answers));
  setText("newTodayValue", String(session.new_words_today));
  setBadge(session.stage);
  applyViewMode(session.view);
  if (!state.settingsOpen) {
    (document.getElementById("settingsLevel") as HTMLSelectElement).value = session.level;
    (document.getElementById("settingsIntensity") as HTMLSelectElement).value = session.srs_intensity;
    (document.getElementById("settingsMode") as HTMLSelectElement).value = session.mode;
    (document.getElementById("settingsPracticeMode") as HTMLSelectElement).value = session.practice_mode;
    (document.getElementById("settingsView") as HTMLSelectElement).value = session.view;
    (document.getElementById("settingsPace") as HTMLSelectElement).value = session.pace;
    (document.getElementById("settingsFocusTimeout") as HTMLInputElement).value = String(session.focus_timeout_minutes);
    (document.getElementById("settingsGoal") as HTMLInputElement).value = String(session.daily_goal_words);
  }

  setVisible("studyCard", session.stage === "study");
  setVisible("quizCard", session.stage === "quiz");
  setVisible("resultCard", session.stage === "result");

  if (session.stage === "idle") {
    setTimeoutState(false);
    setText("heroTitle", session.pace === "continuous" ? "Ready for the next card" : "Waiting for the next card");
    setText(
      "heroCopy",
      session.idle_message ||
        (session.pace === "continuous"
          ? "Continuous mode is on. Finish a card and the next one appears immediately."
          : "Stay here and the next prompt will slide into place automatically."),
    );
  }

  if (session.stage === "study" && session.quiz) {
    const story = (session.quiz.story || {}) as Record<string, unknown>;
    const storyTopic = String(story.topic || "").trim();
    const storyText = String(story.text || "").trim();
    const storyTitle = String(story.title || "").trim();
    const storyVocabulary = ((story.vocabulary as string[] | undefined) || []).filter(Boolean);
    const storyMode = session.quiz.focus_mode === "story";
    const studyKey = `${session.quiz.english_word}::${session.quiz.german_word}::${session.quiz.word_type}`;
    if (state.activeStudyKey !== studyKey) {
      state.activeStudyKey = studyKey;
      (document.getElementById("understoodCheckbox") as HTMLInputElement).checked = false;
      state.activeCardStartedAt = Date.now();
      setTimeoutState(false);
    }
    setText("heroTitle", storyMode ? "Study the story" : `Study ${session.quiz.german_word}`);
    setText(
      "heroCopy",
      storyMode
        ? "Read the story, listen to it aloud, and continue when you understand it."
        : "Scan the word, hear it, then move it forward when you're ready.",
    );
    setText("studyEyebrow", storyMode ? "Story Study" : "Study");
    setText("studyGerman", session.quiz.german_word);
    setText("studyEnglish", `English: ${session.quiz.english_word}`);
    setVisible("studyNewBadge", Boolean(session.quiz.is_new));
    setVisible("studyWordBlock", !storyMode);
    setVisible("studyMeta", !storyMode);
    setVisible("studyStoryCard", Boolean(storyText));
    setVisible("studyStoryVocabWrap", storyVocabulary.length > 0);
    setVisible("studySupportGrid", !storyMode);
    setText("studyStoryTitle", storyTitle || storyTopic || "Story");
    setText("studyStoryText", storyText);
    setText("studyExamplesTitle", storyText ? "Quick Examples" : "Examples");
    fillPills("studyStoryVocab", storyVocabulary);
    const meta = [
      session.quiz.word_type,
      session.quiz.cefr_level || "-",
      session.quiz.noun_info.article ? `Article ${session.quiz.noun_info.article}` : "",
      session.quiz.noun_info.plural ? `Plural ${session.quiz.noun_info.plural}` : "",
    ].filter(Boolean);
    const metaHost = document.getElementById("studyMeta");
    if (metaHost) {
      metaHost.innerHTML = "";
      meta.forEach((item) => {
        const pill = document.createElement("span");
        pill.className = "pill";
        pill.textContent = item;
        metaHost.appendChild(pill);
      });
    }
    fillList("studyExamples", session.quiz.examples, true);
    fillList("studyNotes", session.quiz.ai_word_notes.length ? session.quiz.ai_word_notes : ["No extra notes for this card."]);
    setText(
      "understoodLabel",
      storyMode
        ? "I understand this story. Next time ask me to rewrite it."
        : "I understand this word. Next time quiz me in English.",
    );
  }

  if (session.stage !== "study") {
    state.activeStudyKey = null;
    setVisible("studyNewBadge", false);
    setVisible("studyStoryCard", false);
    setVisible("studyWordBlock", true);
    setVisible("studyMeta", true);
    setVisible("studySupportGrid", true);
    setText("studyEyebrow", "Study");
    setText("understoodLabel", "I understand this word. Next time quiz me in English.");
  }

  if (session.stage === "quiz" && session.quiz) {
    const story = (session.quiz.story || {}) as Record<string, unknown>;
    const storyMode = session.quiz.focus_mode === "story";
    const storyTopic = String(story.topic || "").trim();
    const storyTitle = String(story.title || "").trim();
    const storyQuestion = String(story.question || "").trim();
    const storyHints = ((story.hints as string[] | undefined) || []).filter(Boolean);
    const storyVocabulary = ((story.vocabulary as string[] | undefined) || []).filter(Boolean);
    const quizKey = `${session.quiz.english_word}::${session.quiz.german_word}::${session.quiz.word_type}`;
    if (state.activeQuizKey !== quizKey) {
      state.activeQuizKey = quizKey;
      (document.getElementById("translationInput") as HTMLInputElement).value = "";
      (document.getElementById("articleInput") as HTMLSelectElement).value = "";
      (document.getElementById("wordTypeInput") as HTMLSelectElement).value = "";
      (document.getElementById("sentenceInput") as HTMLTextAreaElement).value = "";
      (document.getElementById("learnedCheckbox") as HTMLInputElement).checked = false;
      state.activeCardStartedAt = Date.now();
      setTimeoutState(false);
    }
    setText("heroTitle", storyMode ? `Quiz: ${storyTopic || storyTitle || "Story"}` : `Quiz: ${session.quiz.english_word}`);
    setText(
      "heroCopy",
      storyMode
        ? "Use the hints and vocabulary, then rewrite the story in German."
        : "Translate, identify the word type, and add a sentence when you want feedback.",
    );
    setText("quizEnglish", storyMode ? (storyTopic || storyTitle || session.quiz.english_word) : session.quiz.english_word);
    setVisible("quizNewBadge", Boolean(session.quiz.is_new));
    setVisible("quizStoryCard", storyMode);
    setVisible("translationField", !storyMode);
    setVisible("articleField", !storyMode);
    setVisible("wordTypeField", !storyMode);
    setText("sentenceFieldLabel", storyMode ? "Write the story" : "Your sentence");
    setText("quizStoryQuestion", storyQuestion || "Schreibe die Geschichte in deinen eigenen Worten nach. | Rewrite the story in your own words.");
    setVisible("quizStoryHintsWrap", storyHints.length > 0);
    setVisible("quizStoryVocabWrap", storyVocabulary.length > 0);
    fillList("quizStoryHints", storyHints);
    fillPills("quizStoryVocab", storyVocabulary);
  }

  if (session.stage !== "quiz") {
    state.activeQuizKey = null;
    setVisible("quizNewBadge", false);
    setVisible("quizStoryCard", false);
    setVisible("translationField", true);
    setVisible("articleField", true);
    setVisible("wordTypeField", true);
    setText("sentenceFieldLabel", "Your sentence");
  }

  if (session.stage === "result" && session.result) {
    setTimeoutState(false);
    const result = session.result as Record<string, unknown>;
    const quiz = result.quiz as QuizPayload;
    const resultStory = (quiz?.story || {}) as Record<string, unknown>;
    const resultStoryTopic = String(resultStory.topic || "").trim();
    const resultStoryTitle = String(resultStory.title || "").trim();
    const isStoryResult = String(result.expected_type || "").trim() === "story";
    setText("heroTitle", String(result.result_label || "Result"));
    setText(
      "heroCopy",
      isStoryResult
        ? `Story: ${resultStoryTitle || resultStoryTopic || String(result.expected_translation || "")}`
        : `Word: ${quiz.german_word} • English: ${quiz.english_word}`,
    );
    setText("resultLabel", String(result.result_label || "Result"));
    const resultLabel = document.getElementById("resultLabel");
    if (resultLabel) {
      resultLabel.className = String(result.is_correct) === "true" ? "result-correct" : "result-wrong";
    }
    const scoreOutOf10 = String(result.score_out_of_10 || "").trim();
    const estimatedLevel = String(result.estimated_level || "").trim();
    const summaryParts = [`Expected: ${String(result.expected_translation || "")}`, `Type: ${String(result.expected_type || "")}`];
    if (estimatedLevel) summaryParts.push(`Level: ${estimatedLevel}`);
    if (scoreOutOf10) summaryParts.push(`Score: ${scoreOutOf10}`);
    setText("resultSummary", summaryParts.join(" • "));
    const customChecks = (result.evaluation_checks as Array<{ label: string; ok: boolean }> | undefined) || [];
    if (customChecks.length) {
      setResultChecks(customChecks);
    } else {
      setResultChecks([
        { label: `Translation correct: ${String(result.translation_correct)}`, ok: Boolean(result.translation_correct) },
        { label: `Article correct: ${String(result.article_correct)}`, ok: Boolean(result.article_correct) },
        { label: `Type correct: ${String(result.type_correct)}`, ok: Boolean(result.type_correct) },
      ]);
    }
    const sentenceItems: string[] = [];
    if (result.sentence_corrected) sentenceItems.push(`Correction: ${String(result.sentence_corrected)}`);
    if (result.sentence_translation_en) sentenceItems.push(`English: ${String(result.sentence_translation_en)}`);
    if (result.sentence_structure) sentenceItems.push(`Structure: ${String(result.sentence_structure)}`);
    const points = (result.sentence_structure_points as string[]) || [];
    sentenceItems.push(...points);
    if ((result.sentence_issues as string[] | undefined)?.length) {
      sentenceItems.push(...((result.sentence_issues as string[]) || []));
    }
    fillList("resultSentence", sentenceItems.length ? sentenceItems : ["No sentence feedback for this round."]);
    const resultExamples = (result.examples as string[]) || [];
    setVisible("resultExamplesCard", session.view === "detail" && resultExamples.length > 0);
    fillList("resultExamples", resultExamples, true);
  }
}

async function refresh(): Promise<void> {
  if (refreshInFlight) return;
  refreshInFlight = true;
  try {
    state.session = await request<SessionResponse>("/api/session");
    if (state.session.stage !== "idle") {
      autoTriggerPending = false;
    }
    render();
  } finally {
    refreshInFlight = false;
  }
}

async function triggerDueCard(): Promise<void> {
  if (refreshInFlight || autoTriggerPending || state.settingsOpen) return;
  autoTriggerPending = true;
  refreshInFlight = true;
  try {
    state.session = await request<SessionResponse>("/api/trigger", { method: "POST" });
    render();
  } catch (error) {
    console.error("Failed to trigger next card", error);
  } finally {
    refreshInFlight = false;
    autoTriggerPending = false;
  }
}

function stopPolling(): void {
  if (countdownHandle !== null) {
    window.clearInterval(countdownHandle);
    countdownHandle = null;
  }
}

function startPolling(): void {
  stopPolling();

  countdownHandle = window.setInterval(() => {
    if (!state.session) return;
    if (
      !state.timeoutExceeded &&
      state.activeCardStartedAt > 0 &&
      (state.session.stage === "study" || state.session.stage === "quiz") &&
      state.session.focus_timeout_minutes > 0
    ) {
      const limitMs = state.session.focus_timeout_minutes * 60 * 1000;
      if (Date.now() - state.activeCardStartedAt >= limitMs) {
        setTimeoutState(true);
      }
    }
    if (state.session.stage === "idle" && state.session.next_due_in_seconds > 0) {
      state.session = {
        ...state.session,
        next_due_in_seconds: Math.max(0, state.session.next_due_in_seconds - 1),
      };
      autoTriggerPending = false;
      render();
      return;
    }
    if (state.session.stage === "idle" && state.session.next_due_in_seconds <= 0) {
      void triggerDueCard();
    }
  }, 1000);
}

function bindEvents(): void {
  document.getElementById("triggerNowButton")?.addEventListener("click", async () => {
    state.session = await request<SessionResponse>("/api/trigger", { method: "POST" });
    autoTriggerPending = false;
    render();
  });

  document.getElementById("openSettingsButton")?.addEventListener("click", () => setSettingsOpen(true));
  document.getElementById("closeSettingsButton")?.addEventListener("click", () => setSettingsOpen(false));
  document.getElementById("settingsOverlay")?.addEventListener("click", () => setSettingsOpen(false));

  document.getElementById("settingsForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    state.session = await request<SessionResponse>("/api/settings", {
      method: "POST",
      body: JSON.stringify({
        level: (document.getElementById("settingsLevel") as HTMLSelectElement).value,
        srs_intensity: (document.getElementById("settingsIntensity") as HTMLSelectElement).value,
        mode: (document.getElementById("settingsMode") as HTMLSelectElement).value,
        practice_mode: (document.getElementById("settingsPracticeMode") as HTMLSelectElement).value,
        view: (document.getElementById("settingsView") as HTMLSelectElement).value,
        pace: (document.getElementById("settingsPace") as HTMLSelectElement).value,
        focus_timeout_minutes: Number((document.getElementById("settingsFocusTimeout") as HTMLInputElement).value || 0),
        daily_goal_words: Number((document.getElementById("settingsGoal") as HTMLInputElement).value || 0),
      }),
    });
    setSettingsOpen(false);
    autoTriggerPending = false;
    render();
  });

  document.getElementById("studyWordSpeakButton")?.addEventListener("click", () => void speakGerman(currentSpokenWord()));
  document.getElementById("studyStorySpeakButton")?.addEventListener("click", () => void speakGerman(currentStoryText()));
  document.getElementById("quizWordSpeakButton")?.addEventListener("click", () => void speakGerman(currentQuizSpeakText()));

  document.getElementById("studyContinueButton")?.addEventListener("click", async () => {
    const understood = (document.getElementById("understoodCheckbox") as HTMLInputElement).checked;
    state.session = await request<SessionResponse>("/api/study", {
      method: "POST",
      body: JSON.stringify({ understood }),
    });
    autoTriggerPending = false;
    render();
  });

  document.getElementById("quizForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      translation: (document.getElementById("translationInput") as HTMLInputElement).value,
      article: (document.getElementById("articleInput") as HTMLSelectElement).value,
      word_type: (document.getElementById("wordTypeInput") as HTMLSelectElement).value,
      sentence: (document.getElementById("sentenceInput") as HTMLTextAreaElement).value,
      learned: (document.getElementById("learnedCheckbox") as HTMLInputElement).checked,
      skipped: false,
    };
    state.session = await request<SessionResponse>("/api/quiz", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    autoTriggerPending = false;
    render();
  });

  document.getElementById("skipButton")?.addEventListener("click", async () => {
    state.session = await request<SessionResponse>("/api/quiz", {
      method: "POST",
      body: JSON.stringify({ skipped: true }),
    });
    autoTriggerPending = false;
    render();
  });

  document.getElementById("resultNextButton")?.addEventListener("click", async () => {
    state.session = await request<SessionResponse>("/api/next", { method: "POST" });
    autoTriggerPending = false;
    render();
  });
}

async function bootstrap(): Promise<void> {
  bindEvents();
  await refresh();
  startPolling();
}

void bootstrap();

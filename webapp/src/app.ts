type SessionStage = "idle" | "study" | "quiz" | "result";

interface SessionResponse {
  stage: SessionStage;
  interval_minutes: number;
  next_due_in_seconds: number;
  daily_goal_words: number;
  srs_intensity: string;
  level: string;
  new_words_today: number;
  mode: string;
  view: string;
  quiz: QuizPayload | null;
  result: Record<string, unknown> | null;
  stats: StatsPayload;
}

interface QuizPayload {
  english_word: string;
  german_word: string;
  word_type: string;
  cefr_level: string;
  noun_info: {
    article: string;
    plural: string;
    gender: string;
  };
  examples: string[];
  ai_word_notes: string[];
  conjugations: Record<string, string>;
  analysis_details: Record<string, unknown>;
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
  activeQuizKey: null as string | null,
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

function fillList(id: string, items: string[]): void {
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = "";
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
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

function render(): void {
  const session = state.session;
  if (!session) return;

  setText("modeValue", session.mode);
  setText("levelValue", session.level || session.quiz?.cefr_level || "-");
  setText("countdownValue", formatCountdown(session.next_due_in_seconds));
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
    (document.getElementById("settingsView") as HTMLSelectElement).value = session.view;
    (document.getElementById("settingsGoal") as HTMLInputElement).value = String(session.daily_goal_words);
  }

  setVisible("studyCard", session.stage === "study");
  setVisible("quizCard", session.stage === "quiz");
  setVisible("resultCard", session.stage === "result");

  if (session.stage === "idle") {
    setText("heroTitle", "Waiting for the next card");
    setText("heroCopy", "Stay here and the next prompt will slide into place automatically.");
  }

  if (session.stage === "study" && session.quiz) {
    setText("heroTitle", `Study ${session.quiz.german_word}`);
    setText("heroCopy", "Scan the word, hear it, then move it forward when you're ready.");
    setText("studyGerman", session.quiz.german_word);
    setText("studyEnglish", `English: ${session.quiz.english_word}`);
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
    fillList("studyExamples", session.quiz.examples);
    fillList("studyNotes", session.quiz.ai_word_notes.length ? session.quiz.ai_word_notes : ["No extra notes for this card."]);
  }

  if (session.stage === "quiz" && session.quiz) {
    const quizKey = `${session.quiz.english_word}::${session.quiz.german_word}::${session.quiz.word_type}`;
    if (state.activeQuizKey !== quizKey) {
      state.activeQuizKey = quizKey;
      (document.getElementById("translationInput") as HTMLInputElement).value = "";
      (document.getElementById("articleInput") as HTMLSelectElement).value = "";
      (document.getElementById("wordTypeInput") as HTMLSelectElement).value = "";
      (document.getElementById("sentenceInput") as HTMLTextAreaElement).value = "";
      (document.getElementById("learnedCheckbox") as HTMLInputElement).checked = false;
    }
    setText("heroTitle", `Quiz: ${session.quiz.english_word}`);
    setText("heroCopy", "Translate, identify the word type, and add a sentence when you want feedback.");
    setText("quizEnglish", session.quiz.english_word);
  }

  if (session.stage !== "quiz") {
    state.activeQuizKey = null;
  }

  if (session.stage === "result" && session.result) {
    const result = session.result as Record<string, unknown>;
    const quiz = result.quiz as QuizPayload;
    setText("heroTitle", String(result.result_label || "Result"));
    setText("heroCopy", `Word: ${quiz.german_word} • English: ${quiz.english_word}`);
    setText("resultLabel", String(result.result_label || "Result"));
    const resultLabel = document.getElementById("resultLabel");
    if (resultLabel) {
      resultLabel.className = String(result.is_correct) === "true" ? "result-correct" : "result-wrong";
    }
    setText("resultSummary", `Expected: ${String(result.expected_translation || "")} • Type: ${String(result.expected_type || "")}`);
    setResultChecks([
      { label: `Translation correct: ${String(result.translation_correct)}`, ok: Boolean(result.translation_correct) },
      { label: `Article correct: ${String(result.article_correct)}`, ok: Boolean(result.article_correct) },
      { label: `Type correct: ${String(result.type_correct)}`, ok: Boolean(result.type_correct) },
    ]);
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
    fillList("resultExamples", (result.examples as string[]) || []);
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
  } finally {
    refreshInFlight = false;
    if (state.session?.stage !== "idle") {
      autoTriggerPending = false;
    }
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

function currentSpokenWord(): string {
  const quiz = state.session?.quiz;
  if (!quiz) return "";
  if (quiz.word_type === "noun" && quiz.noun_info.article) {
    return `${quiz.noun_info.article} ${quiz.german_word}`;
  }
  return quiz.german_word;
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
        view: (document.getElementById("settingsView") as HTMLSelectElement).value,
        daily_goal_words: Number((document.getElementById("settingsGoal") as HTMLInputElement).value || 0),
      }),
    });
    setSettingsOpen(false);
    autoTriggerPending = false;
    render();
  });

  document.getElementById("studyPlayButton")?.addEventListener("click", () => void speakGerman(currentSpokenWord()));
  document.getElementById("quizPlayButton")?.addEventListener("click", () => void speakGerman(currentSpokenWord()));

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

const state = {
  session: null,
  settingsOpen: false,
  activeStudyKey: null,
  activeQuizKey: null,
  activeCardStartedAt: 0,
  timeoutExceeded: false,
};

let countdownHandle = null;
let refreshInFlight = false;
let autoTriggerPending = false;

async function request(url, options) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  return await response.json();
}

async function speakGerman(text) {
  if (!text || !text.trim()) return;
  const audio = new Audio(`/api/pronunciation?text=${encodeURIComponent(text)}`);
  audio.preload = "auto";
  await audio.play();
}

function setVisible(id, visible) {
  document.getElementById(id)?.classList.toggle("hidden", !visible);
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function fillPills(id, items) {
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

function fillList(id, items, speakable = false) {
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

function applyViewMode(view) {
  document.body.classList.toggle("view-basic", view === "basic");
  document.body.classList.toggle("view-detail", view === "detail");
  setVisible("studyNotesCard", view === "detail");
  setVisible("resultExamplesCard", view === "detail");
}

function setSettingsOpen(open) {
  state.settingsOpen = open;
  setVisible("settingsOverlay", open);
  setVisible("settingsDrawer", open);
  const drawer = document.getElementById("settingsDrawer");
  if (drawer) drawer.setAttribute("aria-hidden", open ? "false" : "true");
}

function setBadge(stage) {
  const badge = document.getElementById("stageBadge");
  if (!badge) return;
  badge.textContent = stage;
  badge.className = `status-pill status-${stage}`;
}

function setTimeoutState(active) {
  state.timeoutExceeded = active;
  setVisible("timeoutBadge", active);
  document.getElementById("studyCard")?.classList.toggle("card-timeout", active && state.session?.stage === "study");
  document.getElementById("quizCard")?.classList.toggle("card-timeout", active && state.session?.stage === "quiz");
}

function setResultChecks(items) {
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

function formatCountdown(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${String(secs).padStart(2, "0")}`;
}

function formatSettingLabel(value) {
  const normalized = String(value || "").trim().toLowerCase();
  const labels = {
    "mixed": "Mixed",
    "study-only": "Study Only",
    "quiz-only": "Quiz Only",
    "learn-new": "New",
    "repeat-practice": "Review",
    "story": "Story",
  };
  return labels[normalized] || String(value || "").replace(/-/g, " ");
}

function currentSpokenWord() {
  const quiz = state.session?.quiz;
  if (!quiz) return "";
  if (quiz.word_type === "noun" && quiz.noun_info.article) {
    return `${quiz.noun_info.article} ${quiz.german_word}`;
  }
  return quiz.german_word;
}

function currentStoryText() {
  const story = state.session?.quiz?.story || {};
  return String(story.text || "").trim();
}

function render() {
  const session = state.session;
  if (!session) return;

  setText("modeValue", formatSettingLabel(session.mode));
  setText("practiceModeValue", formatSettingLabel(session.practice_mode));
  setText("levelValue", session.level || (session.quiz && session.quiz.cefr_level) || "-");
  setText("countdownValue", session.pace === "continuous" ? "instant" : formatCountdown(session.next_due_in_seconds));
  setText("goalValue", `${session.new_words_today}/${session.daily_goal_words}`);
  setText("accuracyValue", `${Number(session.stats.accuracy || 0).toFixed(0)}%`);
  setText("questionsValue", String(session.stats.total_questions || 0));
  setText("correctValue", String(session.stats.correct_answers || 0));
  setText("wrongValue", String(session.stats.wrong_answers || 0));
  setText("newTodayValue", String(session.new_words_today || 0));
  setBadge(session.stage);
  applyViewMode(session.view);
  if (!state.settingsOpen) {
    document.getElementById("settingsLevel").value = session.level;
    document.getElementById("settingsIntensity").value = session.srs_intensity;
    document.getElementById("settingsMode").value = session.mode;
    document.getElementById("settingsPracticeMode").value = session.practice_mode;
    document.getElementById("settingsView").value = session.view;
    document.getElementById("settingsPace").value = session.pace;
    document.getElementById("settingsFocusTimeout").value = String(session.focus_timeout_minutes);
    document.getElementById("settingsGoal").value = String(session.daily_goal_words);
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
    const story = session.quiz.story || {};
    const storyText = String(story.text || "").trim();
    const storyTitle = String(story.title || "").trim();
    const storyVocabulary = (Array.isArray(story.vocabulary) ? story.vocabulary : []).filter(Boolean);
    const storyMode = session.quiz.focus_mode === "story";
    const studyKey = `${session.quiz.english_word}::${session.quiz.german_word}::${session.quiz.word_type}`;
    if (state.activeStudyKey !== studyKey) {
      state.activeStudyKey = studyKey;
      document.getElementById("understoodCheckbox").checked = false;
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
    setVisible("studyNewBadge", !!session.quiz.is_new);
    setVisible("studyWordBlock", !storyMode);
    setVisible("studyMeta", !storyMode);
    setVisible("studyStoryCard", !!storyText);
    setVisible("studyStoryVocabWrap", storyVocabulary.length > 0);
    setVisible("studySupportGrid", !storyMode);
    setText("studyStoryTitle", storyTitle || "Story");
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
    fillList("studyExamples", session.quiz.examples || [], true);
    fillList("studyNotes", session.quiz.ai_word_notes && session.quiz.ai_word_notes.length ? session.quiz.ai_word_notes : ["No extra notes for this card."]);
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
    const story = session.quiz.story || {};
    const storyMode = session.quiz.focus_mode === "story";
    const storyQuestion = String(story.question || "").trim();
    const storyHints = (Array.isArray(story.hints) ? story.hints : []).filter(Boolean);
    const storyVocabulary = (Array.isArray(story.vocabulary) ? story.vocabulary : []).filter(Boolean);
    const quizKey = `${session.quiz.english_word}::${session.quiz.german_word}::${session.quiz.word_type}`;
    if (state.activeQuizKey !== quizKey) {
      state.activeQuizKey = quizKey;
      document.getElementById("translationInput").value = "";
      document.getElementById("articleInput").value = "";
      document.getElementById("wordTypeInput").value = "";
      document.getElementById("sentenceInput").value = "";
      document.getElementById("learnedCheckbox").checked = false;
      state.activeCardStartedAt = Date.now();
      setTimeoutState(false);
    }
    setText("heroTitle", `Quiz: ${session.quiz.english_word}`);
    setText(
      "heroCopy",
      storyMode
        ? "Use the hints and vocabulary, then rewrite the story in German."
        : "Translate, identify the word type, and add a sentence when you want feedback.",
    );
    setText("quizEnglish", session.quiz.english_word);
    setVisible("quizNewBadge", !!session.quiz.is_new);
    setVisible("quizStoryCard", storyMode);
    setVisible("translationField", !storyMode);
    setVisible("articleField", !storyMode);
    setVisible("wordTypeField", !storyMode);
    setText("sentenceFieldLabel", storyMode ? "Write the story" : "Your sentence");
    setText("quizStoryQuestion", storyQuestion || "Rewrite the story in your own words.");
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
    const result = session.result;
    const quiz = result.quiz || {};
    setText("heroTitle", String(result.result_label || "Result"));
    setText("heroCopy", `Word: ${quiz.german_word || ""} • English: ${quiz.english_word || ""}`);
    setText("resultLabel", String(result.result_label || "Result"));
    const resultLabel = document.getElementById("resultLabel");
    if (resultLabel) {
      resultLabel.className = String(result.is_correct) === "true" ? "result-correct" : "result-wrong";
    }
    setText("resultSummary", `Expected: ${String(result.expected_translation || "")} • Type: ${String(result.expected_type || "")}`);
    const customChecks = Array.isArray(result.evaluation_checks) ? result.evaluation_checks : [];
    if (customChecks.length) {
      setResultChecks(customChecks);
    } else {
      setResultChecks([
        { label: `Translation correct: ${String(result.translation_correct)}`, ok: Boolean(result.translation_correct) },
        { label: `Article correct: ${String(result.article_correct)}`, ok: Boolean(result.article_correct) },
        { label: `Type correct: ${String(result.type_correct)}`, ok: Boolean(result.type_correct) },
      ]);
    }
    const sentenceItems = [];
    if (result.sentence_corrected) sentenceItems.push(`Correction: ${String(result.sentence_corrected)}`);
    if (result.sentence_translation_en) sentenceItems.push(`English: ${String(result.sentence_translation_en)}`);
    if (result.sentence_structure) sentenceItems.push(`Structure: ${String(result.sentence_structure)}`);
    (result.sentence_structure_points || []).forEach((point) => sentenceItems.push(point));
    (result.sentence_issues || []).forEach((issue) => sentenceItems.push(issue));
    fillList("resultSentence", sentenceItems.length ? sentenceItems : ["No sentence feedback for this round."]);
    fillList("resultExamples", result.examples || [], true);
  }
}

async function refresh() {
  if (refreshInFlight) return;
  refreshInFlight = true;
  try {
    state.session = await request("/api/session");
    if (state.session.stage !== "idle") {
      autoTriggerPending = false;
    }
    render();
  } finally {
    refreshInFlight = false;
  }
}

async function triggerDueCard() {
  if (refreshInFlight || autoTriggerPending || state.settingsOpen) return;
  autoTriggerPending = true;
  refreshInFlight = true;
  try {
    state.session = await request("/api/trigger", { method: "POST" });
    render();
  } catch (error) {
    console.error("Failed to trigger next card", error);
  } finally {
    refreshInFlight = false;
    autoTriggerPending = false;
  }
}

function stopPolling() {
  if (countdownHandle !== null) {
    window.clearInterval(countdownHandle);
    countdownHandle = null;
  }
}

function startPolling() {
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

function bindEvents() {
  document.getElementById("triggerNowButton")?.addEventListener("click", async () => {
    state.session = await request("/api/trigger", { method: "POST" });
    autoTriggerPending = false;
    render();
  });

  document.getElementById("openSettingsButton")?.addEventListener("click", () => setSettingsOpen(true));
  document.getElementById("closeSettingsButton")?.addEventListener("click", () => setSettingsOpen(false));
  document.getElementById("settingsOverlay")?.addEventListener("click", () => setSettingsOpen(false));

  document.getElementById("settingsForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    state.session = await request("/api/settings", {
      method: "POST",
      body: JSON.stringify({
        level: document.getElementById("settingsLevel").value,
        srs_intensity: document.getElementById("settingsIntensity").value,
        mode: document.getElementById("settingsMode").value,
        practice_mode: document.getElementById("settingsPracticeMode").value,
        view: document.getElementById("settingsView").value,
        pace: document.getElementById("settingsPace").value,
        focus_timeout_minutes: Number(document.getElementById("settingsFocusTimeout").value || 0),
        daily_goal_words: Number(document.getElementById("settingsGoal").value || 0),
      }),
    });
    setSettingsOpen(false);
    autoTriggerPending = false;
    render();
  });

  document.getElementById("studyWordSpeakButton")?.addEventListener("click", () => void speakGerman(currentSpokenWord()));
  document.getElementById("studyStorySpeakButton")?.addEventListener("click", () => void speakGerman(currentStoryText()));
  document.getElementById("quizWordSpeakButton")?.addEventListener("click", () => void speakGerman(currentSpokenWord()));

  document.getElementById("studyContinueButton")?.addEventListener("click", async () => {
    const understood = document.getElementById("understoodCheckbox").checked;
    state.session = await request("/api/study", {
      method: "POST",
      body: JSON.stringify({ understood }),
    });
    autoTriggerPending = false;
    render();
  });

  document.getElementById("quizForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      translation: document.getElementById("translationInput").value,
      article: document.getElementById("articleInput").value,
      word_type: document.getElementById("wordTypeInput").value,
      sentence: document.getElementById("sentenceInput").value,
      learned: document.getElementById("learnedCheckbox").checked,
      skipped: false,
    };
    state.session = await request("/api/quiz", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    autoTriggerPending = false;
    render();
  });

  document.getElementById("skipButton")?.addEventListener("click", async () => {
    state.session = await request("/api/quiz", {
      method: "POST",
      body: JSON.stringify({ skipped: true }),
    });
    autoTriggerPending = false;
    render();
  });

  document.getElementById("resultNextButton")?.addEventListener("click", async () => {
    state.session = await request("/api/next", { method: "POST" });
    autoTriggerPending = false;
    render();
  });
}

async function bootstrap() {
  bindEvents();
  await refresh();
  startPolling();
}

void bootstrap();

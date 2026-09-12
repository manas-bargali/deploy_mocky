"use strict";

// ── State ──────────────────────────────────────────────────────
let state = {
  questions:    [],    // [{id, q_num, question, options, marks, type, chapter}]
  answers:      {},    // {qid: "a" | "text"}
  currentIdx:   0,
  totalTime:    0,
  timeLeft:     0,
  timerHandle:  null,
  startEpoch:   0,
  submitted:    false,
  config:       null,
};

// ── DOM helpers ─────────────────────────────────────────────────
const $  = id => document.getElementById(id);
const screens = ["home","loading","exam","result"];

function show(name) {
  screens.forEach(s => {
    const el = $(`screen-${s}`);
    if (el) el.classList.toggle("active", s === name);
    if (el) el.style.display = (s === name) ? "block" : "none";
  });
  // For loading, override display
  if (name === "loading") {
    $("screen-loading").style.display = "flex";
  }
}

// ── Init ─────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  show("home");

  // Load config
  const cfg = await fetch("/config").then(r => r.json());
  state.config = cfg;

  // Render chapter checkboxes
  const container = $("chapter-checkboxes");
  cfg.chapters.forEach((ch, idx) => {
    const item = document.createElement("label");
    item.className = "chapter-item";
    item.innerHTML = `<input type="checkbox" value="${ch}" ${idx === 0 ? "checked" : ""}> ${ch}`;
    item.querySelector("input").addEventListener("change", e => {
      item.classList.toggle("checked", e.target.checked);
    });
    if (idx === 0) item.classList.add("checked");
    container.appendChild(item);
  });

  // Select all
  $("btn-select-all").addEventListener("click", () => {
    document.querySelectorAll("#chapter-checkboxes input").forEach(cb => {
      cb.checked = true;
      cb.closest("label").classList.add("checked");
    });
  });

  // Count pills
  document.querySelectorAll(".pill").forEach(pill => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".pill").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
    });
  });

  // Start practice
  $("btn-start-practice").addEventListener("click", startPractice);
  $("btn-start-full").addEventListener("click", startFullMock);

  // Exam buttons
  $("btn-prev").addEventListener("click", () => navigate(-1));
  $("btn-next").addEventListener("click", () => navigate(1));
  $("btn-clear").addEventListener("click", clearAnswer);
  $("btn-submit-early").addEventListener("click", confirmSubmit);

  // Result
  $("btn-new-test").addEventListener("click", () => { window.location.reload(); });
});

// ── Start Practice ──────────────────────────────────────────────
async function startPractice() {
  const chapters = Array.from(document.querySelectorAll("#chapter-checkboxes input:checked"))
                        .map(cb => cb.value);
  if (chapters.length === 0) {
    alert("Please select at least one chapter.");
    return;
  }

  const count = parseInt(document.querySelector(".pill.active").dataset.count, 10);

  const res = await fetch("/start", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({mode: "practice", chapters, count}),
  }).then(r => r.json());

  if (res.status !== "ok") { alert("Error starting session."); return; }

  $("exam-mode-label").textContent = "Chapter Practice";
  $("exam-chapter-label").textContent = chapters.join(", ");

  await runGeneration(count);
}

// ── Start Full Mock ─────────────────────────────────────────────
async function startFullMock() {
  const res = await fetch("/start", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({mode: "full"}),
  }).then(r => r.json());

  if (res.status !== "ok") { alert("Error starting session."); return; }

  $("exam-mode-label").textContent = "Full Mock";
  $("exam-chapter-label").textContent = "All Chapters — CBSE 417 Board Pattern";

  // full mock: 30 obj + 6 short + 5 long = 41
  await runGeneration(41);
}

// ── Generation loop ──────────────────────────────────────────────
async function runGeneration(total) {
  show("loading");
  $("loading-title").textContent = "Generating Your Paper";
  $("progress-fill").style.width = "0%";
  $("progress-label").textContent = `0 / ${total}`;

  const tips = [
    "💡 Each question is unique — generated fresh every session!",
    "📝 Questions are based on CBSE 417 syllabus + PYQ patterns.",
    "🎯 Mix of MCQ, assertion-reason, fill-blank, and case-study types.",
    "📊 Answers are hidden during the test — revealed after submission.",
  ];
  let tipIdx = 0;
  const tipEl = $("loading-tip");
  const tipTimer = setInterval(() => {
    tipIdx = (tipIdx + 1) % tips.length;
    tipEl.textContent = tips[tipIdx];
  }, 3000);

  let generated = 0;
  let retries   = 0;

  while (generated < total && retries < 8) {
    try {
      const result = await fetch("/generate-next", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: "{}",
      }).then(r => r.json());

      if (result.error) {
        retries++;
        $("loading-sub").textContent = `Retrying… (${result.error.slice(0,60)})`;
        await sleep(2000);
        continue;
      }

      retries   = 0;
      generated = result.generated;
      const pct = Math.round((generated / total) * 100);
      $("progress-fill").style.width = `${pct}%`;
      $("progress-label").textContent = `${generated} / ${total}`;
      $("loading-sub").textContent = `Generated ${generated} of ${total} questions…`;

      if (result.done) break;
    } catch(e) {
      retries++;
      await sleep(2000);
    }
  }

  clearInterval(tipTimer);

  if (generated === 0) {
    alert("Couldn't generate questions. Please check that the server has a valid GROQ_API_KEY configured, then try again.");
    show("home");
    return;
  }

  // Fetch all questions
  const data = await fetch("/questions").then(r => r.json());
  state.questions = data.questions;
  state.totalTime = data.time_sec;

  if (!state.questions || state.questions.length === 0) {
    alert("No questions were generated. Please try again.");
    show("home");
    return;
  }

  initExam();
}

// ── Init Exam ────────────────────────────────────────────────────
function initExam() {
  state.answers    = {};
  state.currentIdx = 0;
  state.submitted  = false;
  state.startEpoch = Date.now();
  state.timeLeft   = state.totalTime;

  buildNavBar();
  renderQuestion(0);
  startTimer();
  show("exam");
}

function buildNavBar() {
  const nav = $("q-nav");
  nav.innerHTML = "";
  state.questions.forEach((q, i) => {
    const btn = document.createElement("button");
    btn.className = "q-nav-btn" + (i === 0 ? " active" : "");
    btn.id        = `nav-btn-${i}`;
    btn.textContent = q.q_num;
    btn.title       = q.chapter;
    btn.addEventListener("click", () => navigate(i - state.currentIdx));
    nav.appendChild(btn);
  });
}

function updateNav() {
  state.questions.forEach((q, i) => {
    const btn = $(`nav-btn-${i}`);
    if (!btn) return;
    btn.classList.toggle("active", i === state.currentIdx);
    btn.classList.toggle("answered", !!state.answers[q.id]);
  });
}

// ── Render Question ──────────────────────────────────────────────
function renderQuestion(idx) {
  const q = state.questions[idx];
  if (!q) return;

  $("q-counter").textContent    = `Q ${q.q_num} of ${state.questions.length}`;
  $("q-chapter-tag").textContent = q.chapter;
  $("q-marks-tag").textContent  = `${q.marks} mark${q.marks > 1 ? "s" : ""}`;
  $("q-text").textContent       = q.question;

  const optsEl  = $("q-options");
  const subjEl  = $("subjective-area");
  const inputEl = $("subjective-input");

  if (q.type === "subjective") {
    optsEl.style.display  = "none";
    subjEl.style.display  = "block";
    $("subj-word-limit").textContent = q.marks === 2 ? "20–30 words" : "50–80 words";
    inputEl.value = state.answers[q.id] || "";
    inputEl.oninput = () => { state.answers[q.id] = inputEl.value.trim(); updateNav(); };
  } else {
    optsEl.style.display  = "flex";
    subjEl.style.display  = "none";
    optsEl.innerHTML = "";

    const opts = q.options || {};
    const keys = Object.keys(opts).sort();

    keys.forEach(key => {
      const btn = document.createElement("button");
      btn.className = "option-btn" + (state.answers[q.id] === key ? " selected" : "");
      btn.innerHTML = `
        <span class="opt-label">${key.toUpperCase()}</span>
        <span class="opt-text">${opts[key]}</span>`;
      btn.addEventListener("click", () => {
        state.answers[q.id] = key;
        renderQuestion(idx);
        updateNav();
      });
      optsEl.appendChild(btn);
    });
  }

  $("btn-prev").disabled = idx === 0;
  $("btn-next").textContent = idx === state.questions.length - 1 ? "Submit ✓" : "Next →";
  updateNav();
}

function navigate(delta) {
  const next = state.currentIdx + delta;
  if (next < 0) return;
  if (next >= state.questions.length) {
    confirmSubmit();
    return;
  }
  state.currentIdx = next;
  renderQuestion(next);
}

function clearAnswer() {
  const q = state.questions[state.currentIdx];
  if (!q) return;
  delete state.answers[q.id];
  renderQuestion(state.currentIdx);
  updateNav();
}

// ── Timer ────────────────────────────────────────────────────────
function startTimer() {
  updateTimerDisplay();
  state.timerHandle = setInterval(() => {
    state.timeLeft--;
    updateTimerDisplay();
    if (state.timeLeft <= 0) {
      clearInterval(state.timerHandle);
      autoSubmit();
    }
  }, 1000);
}

function updateTimerDisplay() {
  const m = Math.floor(Math.abs(state.timeLeft) / 60);
  const s = Math.abs(state.timeLeft) % 60;
  $("timer-display").textContent = `${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}`;
  const box = $("timer-box");
  box.className = "timer-box";
  if (state.timeLeft < 300 && state.timeLeft > 60) box.classList.add("timer-warn");
  if (state.timeLeft <= 60) box.classList.add("timer-danger");
}

function autoSubmit() {
  if (!state.submitted) submitExam();
}

function confirmSubmit() {
  const unanswered = state.questions.length - Object.keys(state.answers).length;
  const msg = unanswered > 0
    ? `You have ${unanswered} unanswered question(s). Submit anyway?`
    : "Submit your paper?";
  if (confirm(msg)) submitExam();
}

// ── Submit ───────────────────────────────────────────────────────
async function submitExam() {
  if (state.submitted) return;
  state.submitted = true;
  clearInterval(state.timerHandle);

  const timeTaken = Math.round((Date.now() - state.startEpoch) / 1000);

  show("loading");
  $("loading-title").textContent = "Evaluating Your Paper…";
  $("loading-sub").textContent   = "Grading answers and building analysis…";
  $("progress-fill").style.width = "80%";

  try {
    const result = await fetch("/submit", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({answers: state.answers, time_taken_sec: timeTaken}),
    }).then(r => r.json());

    if (result.error) {
      alert("Submission error: " + result.error);
      return;
    }

    renderResult(result);
    show("result");
  } catch(e) {
    alert("Network error. Please try again.");
  }
}

// ── Result ───────────────────────────────────────────────────────
function renderResult(r) {
  $("result-grade").textContent = r.grade;
  $("res-score").textContent    = `${r.obj_score}/${r.obj_total}`;
  $("res-pct").textContent      = `${r.percent}%`;
  $("res-attempted").textContent = r.attempted;

  const t = r.time_taken_sec;
  const tm = Math.floor(t/60), ts = t%60;
  $("res-time").textContent = `${tm}m ${ts}s`;

  // Chapter breakdown
  const cb = $("chapter-breakdown");
  cb.innerHTML = "";
  (r.chapter_summary || []).reverse().forEach(c => {
    const color = c.accuracy >= 75 ? "#16a34a" : c.accuracy >= 50 ? "#d97706" : "#dc2626";
    cb.innerHTML += `
      <div class="chapter-row">
        <span class="ch-name">${c.chapter}</span>
        <div class="ch-bar"><div class="ch-fill" style="width:${c.accuracy}%;background:${color}"></div></div>
        <span class="ch-acc" style="color:${color}">${c.accuracy}%</span>
      </div>`;
  });

  // Weak chapters
  const wb = $("weak-block");
  const wc = $("weak-chapters");
  if (r.weak_chapters && r.weak_chapters.length) {
    wb.style.display = "block";
    wc.innerHTML = r.weak_chapters.map(w => `<span class="weak-tag">📌 ${w}</span>`).join("");
  }

  // Subjective note
  if (r.subjective_note) {
    $("subj-note-block").style.display = "block";
  }

  // Review
  const rl = $("review-list");
  rl.innerHTML = "";
  (r.review || []).forEach((it, i) => {
    const isSubj = it.type === "subjective";
    const cls = isSubj ? "subjective-item"
              : it.is_correct === null ? "skipped"
              : it.is_correct ? "correct" : it.user_ans ? "wrong" : "skipped";

    const badge = isSubj ? `<span class="review-badge badge-subjective">Subjective</span>`
                : it.is_correct ? `<span class="review-badge badge-correct">✓ Correct</span>`
                : it.user_ans   ? `<span class="review-badge badge-wrong">✗ Wrong</span>`
                : `<span class="review-badge badge-skipped">— Skipped</span>`;

    let bodyHtml = `<div class="review-q"><strong>Q${it.q_num}.</strong> ${escHtml(it.question)}</div>`;

    if (isSubj) {
      bodyHtml += `
        <div class="review-subj-ans">
          <strong>Your answer:</strong><br>
          ${it.user_ans ? escHtml(it.user_ans) : "<em>Not attempted</em>"}
        </div>`;
    } else {
      const opts = it.options || {};
      const keys = Object.keys(opts).sort();
      bodyHtml += `<div class="review-opts">`;
      keys.forEach(k => {
        let cls2 = "";
        if (k === it.answer) cls2 = "correct-ans";
        else if (k === it.user_ans && !it.is_correct) cls2 = "user-wrong";
        bodyHtml += `<div class="review-opt ${cls2}">(${k}) ${escHtml(opts[k])}</div>`;
      });
      bodyHtml += `</div>`;
    }

    rl.innerHTML += `
      <div class="review-item ${cls}">
        <div class="review-header">
          ${badge}
          <span>${it.chapter}</span>
          <span style="margin-left:auto;color:#64748b;font-size:.8rem">${it.marks_avail} mark${it.marks_avail>1?"s":""}</span>
        </div>
        <div class="review-body">${bodyHtml}</div>
      </div>`;
  });
}

// ── Utils ────────────────────────────────────────────────────────
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function escHtml(s) {
  if (!s) return "";
  return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
           .replace(/"/g,"&quot;").replace(/\n/g,"<br>");
}

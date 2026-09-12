"""
mockyX — CBSE AI Subject Code 417 Class X Mock Test Platform
=============================================================
Modes
-----
1. Chapter Practice  – pick one or more chapters, choose question count (10/20/30/50).
                       Timer scaled from CBSE exam pace (120 min / 50 marks total theory).
2. Full Mock         – complete paper simulation following CBSE 417 board pattern:
                       Section A: Objective (24 marks) + Section B: Subjective (26 marks)
                       Total 50 marks, 120 minutes.

Questions are generated fresh every session via Groq API using context-engineered
prompts seeded with PYQ patterns and CBSE syllabus.  Answers are hidden during the
test and revealed only after submission.
"""

from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
from openai import OpenAI
import json, os, uuid, re

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "mockyX_cbse_ai_417")

_SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".flask_session")
os.makedirs(_SESSION_DIR, exist_ok=True)
app.config["SESSION_TYPE"]      = "filesystem"
app.config["SESSION_FILE_DIR"]  = _SESSION_DIR
app.config["SESSION_PERMANENT"] = False
Session(app)

# ── RAG data ─────────────────────────────────────────────────────────────────
with open("data/cbse_ai_patterns.json") as f:
    CBSE_PATTERNS = json.load(f)

CHAPTERS = list(CBSE_PATTERNS["chapters"].keys())

# ── Groq client (OpenAI-compatible) ──────────────────────────────────────────
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ.get("GROQ_API_KEY", ""),
)
# llama-3.3-70b-versatile was decommissioned by Groq on 08/16/2026.
# Using their recommended replacement; overridable via GROQ_MODEL env var
# so future Groq deprecations don't require another code change.
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

# ── Timing constants (CBSE 417 board pace) ───────────────────────────────────
# Board paper: 50 marks, 120 min → 2.4 min/mark
# Objective  (1-mark): 72 sec per question
# Short ans  (2-mark): 3 min per question
# Long ans   (4-mark): 6 min per question
# For practice mode we use 90 sec/question as a balanced pace
PRACTICE_SEC_PER_Q = 90      # seconds per question in practice/chapter mode
FULL_MOCK_TIME_SEC = 120 * 60  # 2 hours for full mock

QUESTION_COUNT_CHOICES = [10, 20, 30, 50]


def _practice_time(count: int) -> int:
    return PRACTICE_SEC_PER_Q * count


# ── System prompt builder ─────────────────────────────────────────────────────
def build_system_prompt(chapter: str) -> str:
    ch = CBSE_PATTERNS["chapters"].get(chapter, {})
    qtypes = ch.get("question_types", [])
    pyqs   = ch.get("pyq_examples", [])

    types_text = "\n".join(
        f"  - {qt['type']}: e.g. {qt['example']}\n    Options style: {qt['options_style']}"
        for qt in qtypes
    )

    pyq_text = "\n".join(f"  * {p}" for p in pyqs[:8])

    return f"""You are a CBSE AI Subject (Code 417) Class X exam question generator.
You have studied the CBSE AI 417 syllabus for session 2026-2027 and real PYQ papers.

CHAPTER: {chapter}
DESCRIPTION: {ch.get('description', '')}

ACTUAL QUESTION TYPES FROM THIS CHAPTER:
{types_text}

REAL PYQ EXAMPLES FROM BOARD / PRE-BOARD PAPERS:
{pyq_text}

STRICT RULES:
1. Generate EXACTLY ONE question at a time.
2. Provide EXACTLY 4 options labeled (a) through (d).
3. Mark correct answer as "ANSWER: (x)" on the LAST line — no explanation.
4. Match CBSE 417 difficulty — not too easy, not too hard.
5. Vary question types — do NOT repeat the same sub-type consecutively.
6. Question must be self-contained (no "refer to above table" unless table is included).
7. Use real-world AI scenarios relatable to Class 10 students.
8. For Assertion-Reason questions: use format "Assertion(A): ... Reason(R): ..."
9. For True/False or Fill-in-blank: still provide 4 MCQ options.
10. NO explanation, NO preamble. ONLY: Question + 4 options + ANSWER line.

FORMAT (follow EXACTLY):
Q. [Question text here]
(a) Option A
(b) Option B
(c) Option C
(d) Option D
ANSWER: (b)"""


def build_full_mock_prompt(q_num: int, section: str, q_type: str) -> str:
    """Prompt for full mock — mixes chapters, follows board pattern."""
    all_pyqs = []
    for ch_data in CBSE_PATTERNS["chapters"].values():
        all_pyqs.extend(ch_data.get("pyq_examples", [])[:3])

    sample_pyqs = "\n".join(f"  * {p}" for p in all_pyqs[:15])

    if section == "objective":
        return f"""You are a CBSE AI 417 Class X board exam question generator.
Generate question #{q_num} for SECTION A (Objective, 1 mark each).
Type hint: {q_type}

CBSE 417 syllabus covers: AI Project Cycle, Ethical Frameworks, AI vs ML vs DL,
Supervised/Unsupervised/Reinforcement Learning, Neural Networks, Perceptron/ANN/CNN,
Model Evaluation (Accuracy/Precision/Recall/F1/Confusion Matrix), Computer Vision
(Pixels/RGB/Grayscale/Resolution/Object Detection/CNN), NLP (Tokenization/BoW/
Stemming/Lemmatization/Chatbots/Sentiment Analysis), Employability Skills.

REAL PYQ EXAMPLES:
{sample_pyqs}

STRICT RULES:
1. EXACTLY ONE question, EXACTLY 4 options (a)-(d).
2. ANSWER: (x) on last line. No explanation.
3. Mix chapters across the paper — for question #{q_num} focus on {q_type}.
4. CBSE board style: scenario-based, assertion-reason, fill-blank, true/false as MCQ.
5. Self-contained. No external reference.

FORMAT:
Q. [question]
(a) Option A
(b) Option B
(c) Option C
(d) Option D
ANSWER: (b)"""

    else:  # subjective
        marks = 2 if "short" in q_type.lower() else 4
        word_count = "20-30" if marks == 2 else "50-80"
        return f"""You are a CBSE AI 417 Class X board exam subjective question generator.
Generate question #{q_num} for SECTION B (Subjective, {marks} marks).
Type: {q_type}

CBSE 417 syllabus: AI Project Cycle, Ethical Frameworks, ML Models, Neural Networks,
Model Evaluation, Computer Vision, NLP, Employability Skills.

STRICT RULES:
1. Generate ONE subjective question worth {marks} marks.
2. Expected answer: {word_count} words.
3. CBSE style: case-study, explain-the-concept, calculate, draw-and-label.
4. For {marks}-mark questions, ask {marks//2} sub-parts if needed.
5. End with: MARKS: {marks}
6. No answer — just the question.

FORMAT:
Q. [question text, possibly with sub-parts a) b)]
MARKS: {marks}"""


# ── Question parser ───────────────────────────────────────────────────────────
def parse_question(raw: str, q_type: str = "objective"):
    lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]

    if q_type == "subjective":
        marks = 2
        q_lines = []
        for line in lines:
            if line.startswith("MARKS:"):
                try:
                    marks = int(line.replace("MARKS:", "").strip())
                except:
                    pass
            else:
                q_lines.append(line)
        question_text = " ".join(q_lines).lstrip("Q. ").strip()
        return {"question": question_text, "options": {}, "answer": "", "marks": marks, "type": "subjective"}

    question_lines, options, answer = [], {}, ""
    for line in lines:
        if line.upper().startswith("ANSWER:"):
            answer = line.split(":", 1)[1].strip()
        elif re.match(r"^\(([abcdABCD])\)", line):
            key = line[1].lower()
            val = line[4:].strip()
            options[key] = val
        else:
            question_lines.append(line)

    question_text = " ".join(question_lines).lstrip("Q. ").strip()
    return {
        "question": question_text,
        "options":  options,
        "answer":   re.sub(r"[^abcd]", "", answer.lower())[:1],
        "marks":    1,
        "type":     "objective",
    }


def detect_chapter(text: str) -> str:
    """Best-guess chapter from question text for analytics."""
    t = text.lower()
    if any(w in t for w in ["confusion matrix", "precision", "recall", "f1", "accuracy", "train", "test split", "overfitting"]):
        return "Evaluating Models"
    if any(w in t for w in ["pixel", "rgb", "grayscale", "resolution", "object detection", "cnn", "convolution", "computer vision"]):
        return "Computer Vision"
    if any(w in t for w in ["tokeniz", "corpus", "stemm", "lemma", "bag of words", "nlp", "chatbot", "sentiment", "tfidf"]):
        return "Natural Language Processing"
    if any(w in t for w in ["neural network", "perceptron", "supervised", "unsupervised", "reinforcement", "deep learning", "ann", "layer"]):
        return "Modeling in AI"
    if any(w in t for w in ["project cycle", "ethical", "bias", "ai access", "4w", "problem scoping", "domain"]):
        return "AI Project Cycle & Ethics"
    if any(w in t for w in ["sdg", "entrepreneur", "communication", "self-manag", "motivation", "ict"]):
        return "Employability Skills"
    return "General"


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    session.clear()
    return render_template("index.html")


@app.route("/config")
def get_config():
    return jsonify({
        "chapters":        CHAPTERS,
        "question_counts": QUESTION_COUNT_CHOICES,
        "full_mock": {
            "total_marks": 50,
            "time_sec":    FULL_MOCK_TIME_SEC,
            "description": "Section A: 24 MCQ + Section B: 26 marks Subjective — CBSE 417 Board Pattern",
        }
    })


@app.route("/start", methods=["POST"])
def start_exam():
    data = request.json or {}
    mode = data.get("mode", "practice")

    session.clear()
    session["mode"]          = mode
    session["bank"]          = {}
    session["queue"]         = []
    session["history"]       = []
    session["results"]       = []
    session["submitted"]     = False

    if mode == "full":
        # Full mock plan: 30 objective + 6 short + 5 long (ask, student answers 4+3)
        plan = {
            "mode":       "full",
            "time_sec":   FULL_MOCK_TIME_SEC,
            "obj_target": 30,   # generate 30 MCQ (student answers 20 in real board — we let all be answered)
            "short_target": 6,  # 2-mark
            "long_target":  5,  # 4-mark
        }
    else:
        chapters = data.get("chapters", [CHAPTERS[0]])
        count    = int(data.get("count", 20))
        if count not in QUESTION_COUNT_CHOICES:
            count = 20
        plan = {
            "mode":     "practice",
            "chapters": chapters,
            "count":    count,
            "time_sec": _practice_time(count),
        }

    session["plan"] = plan
    return jsonify({"status": "ok", "plan": plan})


@app.route("/generate-next", methods=["POST"])
def generate_next():
    """Generate ONE more question. Called in a loop by frontend until done."""
    plan  = session.get("plan")
    queue = session.get("queue", [])
    bank  = session.get("bank", {})

    if not plan:
        return jsonify({"error": "No active session"}), 400

    mode = plan.get("mode", "practice")

    # ── Determine if we need more questions ──────────────────────────────────
    if mode == "full":
        obj_done   = sum(1 for qid in queue if bank.get(qid, {}).get("type") == "objective")
        short_done = sum(1 for qid in queue if bank.get(qid, {}).get("marks") == 2 and bank.get(qid, {}).get("type") == "subjective")
        long_done  = sum(1 for qid in queue if bank.get(qid, {}).get("marks") == 4 and bank.get(qid, {}).get("type") == "subjective")

        obj_need   = plan["obj_target"]   - obj_done
        short_need = plan["short_target"] - short_done
        long_need  = plan["long_target"]  - long_done

        total_done   = obj_done + short_done + long_done
        total_target = plan["obj_target"] + plan["short_target"] + plan["long_target"]

        if total_done >= total_target:
            return jsonify({"done": True, "generated": total_done, "total": total_target})

        # Decide what to generate next
        if obj_need > 0:
            q_type   = "objective"
            q_num    = obj_done + 1
            chapters = CHAPTERS
            chapter_for_prompt = chapters[(obj_done) % len(chapters)]
            type_hint = _get_obj_type_hint(obj_done)
        elif short_need > 0:
            q_type   = "subjective"
            q_num    = short_done + 1
            chapters = CHAPTERS
            chapter_for_prompt = chapters[(short_done) % (len(chapters) - 1)]
            type_hint = f"2-mark short answer on {chapter_for_prompt}"
        else:
            q_type   = "subjective"
            q_num    = long_done + 1
            chapters = CHAPTERS
            chapter_for_prompt = chapters[(long_done) % (len(chapters) - 1)]
            type_hint = f"4-mark long answer / case-study on {chapter_for_prompt}"

    else:
        target   = plan["count"]
        chapters = plan.get("chapters", [CHAPTERS[0]])
        if len(queue) >= target:
            return jsonify({"done": True, "generated": len(queue), "total": target})
        q_type   = "objective"
        q_num    = len(queue) + 1
        chapter_for_prompt = chapters[(len(queue)) % len(chapters)]
        type_hint = None

    # ── Build history note to force variety ──────────────────────────────────
    history     = session.get("history", [])
    hist_note   = ""
    if history:
        last_2 = ", ".join(history[-2:])
        hist_note = f"\n\nIMPORTANT: Last question types were [{last_2}]. Use a DIFFERENT type now."

    # ── Call Groq ─────────────────────────────────────────────────────────────
    try:
        if mode == "full":
            system = build_full_mock_prompt(q_num, q_type, type_hint) + hist_note
            user_msg = f"Generate {'an objective MCQ' if q_type == 'objective' else 'a subjective'} question #{q_num} for CBSE AI 417 Class X board exam."
        else:
            system   = build_system_prompt(chapter_for_prompt) + hist_note
            user_msg = f"Generate 1 question for chapter '{chapter_for_prompt}' of CBSE AI 417 Class X."

        response = client.chat.completions.create(
            model    = GROQ_MODEL,
            messages = [
                {"role": "system", "content": system},
                {"role": "user",   "content": user_msg},
            ],
            max_tokens   = 600,
            temperature  = 0.8,
        )
        raw = response.choices[0].message.content or ""

        if not raw.strip():
            raise ValueError("Empty response from model")

        q       = parse_question(raw, q_type)
        chapter = detect_chapter(q["question"]) if mode == "full" else chapter_for_prompt

        qid = uuid.uuid4().hex[:8]
        bank[qid] = {
            "question": q["question"],
            "options":  q["options"],
            "answer":   q["answer"],
            "marks":    q["marks"],
            "type":     q["type"],
            "chapter":  chapter,
        }
        session["bank"] = bank

        queue.append(qid)
        session["queue"] = queue

        # track type for variety
        history.append(chapter)
        session["history"] = history[-8:]

        total_target = plan.get("count", plan.get("obj_target", 0) + plan.get("short_target", 0) + plan.get("long_target", 0))
        done_now = len(queue) >= total_target

        return jsonify({"done": done_now, "generated": len(queue), "total": total_target})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _get_obj_type_hint(idx: int) -> str:
    """Rotate chapter hints for full mock objective questions."""
    rotation = [
        "Employability Skills — communication, self-management, ICT, entrepreneurship, SDG",
        "AI Project Cycle & Ethical Frameworks — stages, domains, bias, AI access",
        "Modeling in AI — AI vs ML vs DL, supervised, unsupervised, reinforcement, neural networks",
        "Evaluating Models — confusion matrix, accuracy, precision, recall, F1 score, train-test split",
        "Computer Vision — pixels, RGB, grayscale, resolution, object detection, CNN",
        "Natural Language Processing — tokenization, BoW, stemming, lemmatization, chatbots, sentiment",
        "Employability Skills — self-motivation, goal-setting, barriers to communication",
        "AI Project Cycle — 4W canvas, problem statement template, ethical frameworks",
        "Modeling in AI — perceptron calculation, neural network layers, CNN vs ANN",
        "Evaluating Models — case-study with numbers, error rate calculation",
        "Computer Vision — image classification vs object detection, convolution operator",
        "Natural Language Processing — NLP stages, TF-IDF, corpus, stop words",
    ]
    return rotation[idx % len(rotation)]


@app.route("/questions")
def get_questions():
    """Return all questions for the current session — options shown, answers hidden."""
    queue = session.get("queue", [])
    bank  = session.get("bank", {})
    plan  = session.get("plan", {})

    questions = []
    for i, qid in enumerate(queue):
        b = bank[qid]
        questions.append({
            "id":       qid,
            "q_num":    i + 1,
            "question": b["question"],
            "options":  b["options"],
            "marks":    b["marks"],
            "type":     b["type"],
            "chapter":  b["chapter"],
        })

    return jsonify({
        "mode":       plan.get("mode"),
        "total":      len(queue),
        "time_sec":   plan.get("time_sec", FULL_MOCK_TIME_SEC),
        "questions":  questions,
    })


@app.route("/submit", methods=["POST"])
def submit():
    """Grade the exam server-side. Answers revealed only here."""
    if session.get("submitted"):
        return jsonify({"error": "Already submitted"}), 400

    data       = request.json or {}
    answers    = data.get("answers", {})       # {qid: "a" | "b" | "c" | "d" | "text"}
    time_taken = data.get("time_taken_sec", 0)

    queue = session.get("queue", [])
    bank  = session.get("bank", {})
    plan  = session.get("plan", {})

    total_marks   = 0
    scored_marks  = 0
    attempted     = 0
    chapter_stats = {}
    items         = []

    for i, qid in enumerate(queue):
        b           = bank[qid]
        raw_user    = answers.get(qid, "")
        marks_avail = b["marks"]
        is_obj      = b["type"] == "objective"

        if is_obj:
            user_ans    = (raw_user or "").lower().strip("() ")[:1]
            correct_ans = (b["answer"] or "").lower().strip("() ")[:1]
            is_correct  = bool(user_ans) and user_ans == correct_ans
            marks_got   = marks_avail if is_correct else 0
        else:
            # Subjective — mark as attempted if answered; auto-scored as 0 (teacher grades)
            user_ans    = raw_user or ""
            correct_ans = ""
            is_correct  = None      # null = needs teacher grading
            marks_got   = 0         # placeholder

        if raw_user:
            attempted += 1

        total_marks  += marks_avail
        scored_marks += marks_got

        # chapter stats
        ch = b.get("chapter", "General")
        cs = chapter_stats.setdefault(ch, {"correct": 0, "attempted": 0, "total": 0, "marks": 0})
        cs["total"]  += 1
        cs["marks"]  += marks_avail
        if raw_user:
            cs["attempted"] += 1
        if is_obj and is_correct:
            cs["correct"]  += 1

        items.append({
            "qid":        qid,
            "q_num":      i + 1,
            "question":   b["question"],
            "options":    b["options"],
            "answer":     b["answer"],
            "user_ans":   user_ans,
            "is_correct": is_correct,
            "marks_avail":marks_avail,
            "marks_got":  marks_got,
            "type":       b["type"],
            "chapter":    b["chapter"],
        })

    obj_total   = sum(1 for it in items if it["type"] == "objective")
    obj_scored  = sum(it["marks_avail"] for it in items if it["type"] == "objective" and it["is_correct"])
    pct         = round((obj_scored / max(obj_total, 1)) * 100, 1)

    chapter_summary = []
    for ch, cs in chapter_stats.items():
        acc = round((cs["correct"] / cs["attempted"] * 100) if cs["attempted"] else 0, 1)
        chapter_summary.append({"chapter": ch, "accuracy": acc, **cs})
    chapter_summary.sort(key=lambda x: x["accuracy"])

    weak = [c["chapter"] for c in chapter_summary if c["attempted"] > 0 and c["accuracy"] < 60][:4]

    result = {
        "mode":            plan.get("mode"),
        "obj_score":       obj_scored,
        "obj_total":       obj_total,
        "total_marks":     total_marks,
        "attempted":       attempted,
        "percent":         pct,
        "grade":           _grade(pct),
        "time_taken_sec":  time_taken,
        "chapter_summary": chapter_summary,
        "weak_chapters":   weak,
        "review":          items,
        "subjective_note": "Subjective questions are shown for self-evaluation. Ask your teacher to grade them." if plan.get("mode") == "full" else "",
    }

    session["result"]    = result
    session["submitted"] = True
    return jsonify(result)


@app.route("/result")
def get_result():
    result = session.get("result")
    if not result:
        return jsonify({"error": "No result yet"}), 404
    return jsonify(result)


def _grade(pct):
    if pct >= 90: return "Outstanding — Board Exam Ready! 🏆"
    if pct >= 75: return "Very Good — Keep Practicing! 📚"
    if pct >= 60: return "Good — Revise Weak Chapters 💡"
    if pct >= 40: return "Average — Need More Practice ⚠️"
    return "Below Average — Revise Concepts First 📖"


if __name__ == "__main__":
    app.run(debug=True, port=5000, use_reloader=False)

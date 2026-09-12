# mockyX — CBSE AI 417 Class X Mock Test Platform

AI-generated mock tests for CBSE Artificial Intelligence (Subject Code 417), Class X.
Built on the same architecture as mocky (IBPS), adapted for the 2026-27 syllabus.

---

## Features
- **Chapter Practice** — select 1 or more chapters, choose 10/20/30/50 questions
- **Full Mock** — complete board-pattern paper (Section A + B, 50 marks, 2 hours)
- Questions generated fresh every session via **Groq API** (llama-3.3-70b-versatile)
- Context-engineered prompts seeded with real PYQ patterns from CBSE pre-board / SQP
- Answers hidden during test; revealed only after submission
- Chapter-wise accuracy breakdown + weak chapter identification
- Subjective questions shown for self-review (teacher grades)

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Get a free Groq API key
- Go to https://console.groq.com
- Create a free account → API Keys → Create key
- Free tier: 6000 tokens/min on llama-3.3-70b-versatile (more than enough)

### 3. Set environment variable
```bash
# Linux / Mac
export GROQ_API_KEY="gsk_your_key_here"

# Windows
set GROQ_API_KEY=gsk_your_key_here
```

### 4. Run
```bash
python app.py
```
Open http://localhost:5000 in your browser.

---

## CBSE 417 Chapters Covered
1. AI Project Cycle & Ethical Frameworks
2. Advanced Concepts of Modeling in AI (ML, DL, ANN, CNN)
3. Evaluating Models (Confusion Matrix, Precision, Recall, F1)
4. Computer Vision (Pixels, RGB, Object Detection, CNN)
5. Natural Language Processing (Tokenization, BoW, Chatbots, Sentiment)
6. Employability Skills (Communication, ICT, Entrepreneurship, Green Skills)

## Question Types
- MCQ (1 mark) — board style
- Assertion-Reason
- Statement 1 / Statement 2
- Case-study based calculations (confusion matrix, perceptron)
- Fill-in-the-blank (as MCQ)
- Short answer (2 marks) — subjective
- Long answer / case-study (4 marks) — subjective

## Token Usage (Groq Free Tier)
Each question generation call uses ~400-600 tokens.
A 20-question practice: ~10,000 tokens (well within 6000/min limit with pacing).
A full mock (41 questions): ~20,000 tokens total, batched over ~2 minutes.
The app generates 1 question per API call, so rate limits are handled naturally.

## Project Structure
```
mockyX/
├── app.py                  # Flask backend
├── requirements.txt
├── README.md
├── data/
│   └── cbse_ai_patterns.json   # RAG: syllabus + PYQ context
├── templates/
│   └── index.html
└── static/
    ├── css/style.css
    └── js/app.js
```

# ── PASTE THESE INTO server.py ────────────────────────────────────────────────
# Add these 3 routes before the  if __name__ == "__main__":  line
# Also add this route at the top with the other @app.get routes:
#   @app.get("/study")
#   def serve_study():
#       return FileResponse("study.html")
# ─────────────────────────────────────────────────────────────────────────────

STUDY_TUTOR_PROMPT = """You are Chotu in STUDY MODE — a sharp, no-nonsense tutor.

Your job is to help a CSE student understand concepts clearly and prepare for exams.

Rules:
- Give clear, direct explanations. Use simple language first, then technical terms.
- Always give a concrete example after explaining a concept.
- If the subject is set, stay focused on that subject's context.
- When comparing two things (X vs Y), use a clear structure.
- For exam preparation, think about what examiners actually ask.
- Keep answers focused — not too long, not too short. Exam-relevant depth.
- You can still be slightly Chotu-like (natural language, occasional "bhai") but stay academic.
- Never say "Great question". Just answer.

Subject context will be injected. Use it to anchor all explanations."""

STUDY_QUIZ_PROMPT = """You are generating quiz questions for a CSE student exam preparation.

Given the provided text/notes, generate exactly 5 questions.

Rules:
- Mix question types: definition, application, comparison, true/false, fill-in-blank
- Questions should test understanding, not just memorization
- Each question must have a clear, concise correct answer (1-2 sentences max)
- Make questions exam-relevant — the kind that actually appear in university exams

Respond ONLY with valid JSON in this exact format, nothing else:
{
  "questions": [
    {"question": "...", "answer": "..."},
    {"question": "...", "answer": "..."},
    {"question": "...", "answer": "..."},
    {"question": "...", "answer": "..."},
    {"question": "...", "answer": "..."}
  ]
}"""

STUDY_CHECK_PROMPT = """You are checking a student's quiz answer.

Given the question, correct answer, and student's answer:
1. Determine if the student's answer is correct (accept partial credit if the core concept is right)
2. Give brief feedback — 1-2 sentences max
3. If wrong, explain why briefly

Respond ONLY with valid JSON:
{"correct": true/false, "feedback": "..."}"""


class StudyChatRequest(BaseModel):
    message: str
    subject: str = ""
    history: list[dict] = []

class QuizRequest(BaseModel):
    notes: str
    subject: str = ""

class CheckRequest(BaseModel):
    question: str
    correct_answer: str
    user_answer: str
    subject: str = ""


@app.get("/study")
def serve_study():
    return FileResponse("study.html")


@app.post("/study/chat")
async def study_chat(req: StudyChatRequest):
    subject_ctx = f"Current subject: {req.subject}" if req.subject else "No subject set — answer generally for CSE."

    messages = [{"role": "system", "content": STUDY_TUTOR_PROMPT + f"\n\n{subject_ctx}"}]
    for h in req.history[-10:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": req.message})

    try:
        resp = CLIENT.chat.completions.create(
            model=MODEL, messages=messages, temperature=0.5, max_tokens=700
        )
        return {"reply": resp.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/study/quiz")
async def generate_quiz(req: QuizRequest):
    subject_hint = f"Subject: {req.subject}. " if req.subject else ""
    prompt = f"{subject_hint}Generate 5 quiz questions from this text:\n\n{req.notes[:3000]}"

    messages = [
        {"role": "system", "content": STUDY_QUIZ_PROMPT},
        {"role": "user",   "content": prompt}
    ]
    try:
        resp = CLIENT.chat.completions.create(
            model=MODEL, messages=messages, temperature=0.4, max_tokens=800
        )
        raw = resp.choices[0].message.content
        # strip markdown fences if present
        clean = raw.replace("```json","").replace("```","").strip()
        data  = json.loads(clean)
        return {"questions": data["questions"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quiz generation failed: {str(e)}")


@app.post("/study/check")
async def check_answer(req: CheckRequest):
    prompt = f"Question: {req.question}\nCorrect answer: {req.correct_answer}\nStudent's answer: {req.user_answer}"

    messages = [
        {"role": "system", "content": STUDY_CHECK_PROMPT},
        {"role": "user",   "content": prompt}
    ]
    try:
        resp = CLIENT.chat.completions.create(
            model=MODEL, messages=messages, temperature=0.3, max_tokens=200
        )
        raw   = resp.choices[0].message.content
        clean = raw.replace("```json","").replace("```","").strip()
        data  = json.loads(clean)
        return {"correct": data["correct"], "feedback": data["feedback"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

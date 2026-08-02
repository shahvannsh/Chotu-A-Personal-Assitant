from fastapi import APIRouter, HTTPException, Request, UploadFile, File
import os, json, re, secrets
import requests
import fitz

from core import (
    get_db, require_user, validate_string, rag, logger,
    UPLOADS_DIR, MAX_PDF_SIZE, GROQ_API_KEY, OLLAMA_BASE_URL, GEMINI_API_KEY,
)

router = APIRouter()

@router.post('/upload/pdf')
async def upload_pdf(file: UploadFile = File(...), request: Request = None):
    try:
        user = require_user(request)

        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail='Only PDFs allowed')

        content = await file.read()
        if len(content) > MAX_PDF_SIZE:
            raise HTTPException(status_code=413, detail='File too large')

        file_path = os.path.join(UPLOADS_DIR, f"{user['id']}_{secrets.token_hex(4)}_{file.filename[:30]}")
        with open(file_path, 'wb') as f:
            f.write(content)

        try:
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            text = text[:1000000]
        except Exception as e:
            logger.error(f"PDF extraction failed for {file.filename}: {e}")
            raise HTTPException(status_code=400, detail='Cannot extract PDF text')

        if not text:
            raise HTTPException(status_code=400, detail='No text in PDF')

        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""

        for sentence in sentences[:1000]:
            if len(current_chunk) + len(sentence) < 512:
                current_chunk += " " + sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip()[:512])
                current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk.strip()[:512])

        chunks = chunks[:100]

        db = get_db()
        try:
            cursor = db.execute('INSERT INTO pdf_documents (user_id, filename, file_path, file_size) VALUES(%s,%s,%s,%s) RETURNING id',
                      (user['id'], file.filename[:255], file_path, len(content)))
            doc_id = cursor.fetchone()['id']
            db.commit()

            for i, chunk in enumerate(chunks):
                embedding = rag.embed(chunk)
                db.execute('INSERT INTO document_chunks (document_id, chunk_text, chunk_index, embedding) VALUES(%s,%s,%s,%s)',
                          (doc_id, chunk, i, embedding.tobytes()))

            db.commit()
            return {'status': 'ok', 'chunks': len(chunks), 'document_id': doc_id}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF upload failed for {file.filename}: {e}")
        raise HTTPException(status_code=500, detail='PDF upload failed')

@router.get('/models')
def list_models(request: Request):
    """Real availability only — no entry unless it actually responds right now."""
    require_user(request)
    models = []
    if GROQ_API_KEY:
        models.append({'provider': 'groq', 'model': 'llama-3.3-70b-versatile', 'label': 'Groq · Llama 3.3 70B'})
    if GEMINI_API_KEY:
        models.append({'provider': 'gemini', 'model': 'gemini-2.0-flash', 'label': 'Gemini · 2.0 Flash'})
    try:
        resp = requests.get(f'{OLLAMA_BASE_URL}/api/tags', timeout=2)
        if resp.ok:
            for m in resp.json().get('models', []):
                models.append({'provider': 'ollama', 'model': m['name'], 'label': f"Ollama · {m['name']}"})
    except Exception:
        pass
    return {'models': models}

def _call_groq(prompt):
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(model="llama-3.3-70b-versatile",
                                             messages=[{"role": "user", "content": prompt}],
                                             max_tokens=500, temperature=0.7)
    return response.choices[0].message.content

def _call_ollama(prompt, model_name):
    resp = requests.post(f'{OLLAMA_BASE_URL}/api/chat', json={
        'model': model_name,
        'messages': [{'role': 'user', 'content': prompt}],
        'stream': False,
    }, timeout=60)
    resp.raise_for_status()
    return resp.json()['message']['content']

def _call_gemini(prompt):
    resp = requests.post(
        f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}',
        json={'contents': [{'parts': [{'text': prompt}]}]}, timeout=30)
    resp.raise_for_status()
    return resp.json()['candidates'][0]['content']['parts'][0]['text']

def _build_context(user_id, question, db):
    memory_rows = db.execute('SELECT fact FROM user_memory WHERE user_id=%s ORDER BY created_at DESC LIMIT 20', (user_id,)).fetchall()
    memory_facts = [r['fact'] for r in memory_rows] if memory_rows else []

    chunks_data = db.execute('''SELECT dc.chunk_text FROM document_chunks dc
                               JOIN pdf_documents pd ON dc.document_id = pd.id
                               WHERE pd.user_id = %s LIMIT 100''', (user_id,)).fetchall()
    chunks = [row['chunk_text'] for row in chunks_data] if chunks_data else []

    relevant_chunks = []
    confidence = 0
    if chunks:
        results = rag.hybrid_search(question, chunks, top_k=3)
        relevant_chunks = [r['text'] for r in results]
        confidence = int(sum(r['confidence'] for r in results) / len(results)) if results else 0

    context = "\n".join(relevant_chunks)
    if memory_facts:
        context = "Known facts about this user:\n" + "\n".join(f"- {f}" for f in memory_facts) + "\n\n" + context

    try:
        params = {'action': 'query', 'format': 'json', 'titles': question.split()[0][:50],
                 'prop': 'extracts', 'explaintext': True, 'exintro': True}
        resp = requests.get("https://en.wikipedia.org/w/api.php", params=params, timeout=5)
        if resp.ok:
            data = resp.json()
            for page_data in data['query']['pages'].values():
                if 'extract' in page_data:
                    context += "\n" + page_data['extract'][:500]
                    break
    except:
        pass

    return context, chunks, relevant_chunks, confidence

def _dispatch(provider, model_name, prompt):
    """Returns (answer_or_None, error_message_or_None). Never raises."""
    try:
        if provider == 'ollama' and model_name:
            return _call_ollama(prompt, model_name), None
        elif provider == 'gemini' and GEMINI_API_KEY:
            return _call_gemini(prompt), None
        elif provider == 'groq' and GROQ_API_KEY:
            return _call_groq(prompt), None
        else:
            return None, f"'{provider}' isn't configured on this server."
    except Exception as e:
        logger.error(f"{provider} call failed: {e}")
        return None, str(e)[:200]

@router.post('/chat/ask')
def chat_ask(req: dict, request: Request):
    try:
        user = require_user(request)
        question = validate_string(req.get('question', ''), 'question', 3, 500)
        provider = req.get('provider', 'groq')
        model_name = req.get('model', '')

        db = get_db()
        try:
            context, chunks, relevant_chunks, confidence = _build_context(user['id'], question, db)

            answer = None
            prompt = f"You are an AI tutor. Answer this based on context:\n\nContext:\n{context[:2000]}\n\nQuestion: {question}\n\nProvide concise educational answer."
            answer, _err = _dispatch(provider, model_name, prompt)

            if answer is None:
                if provider == 'ollama':
                    answer = f"Couldn't reach Ollama at {OLLAMA_BASE_URL} (or model '{model_name}' isn't pulled). Check it's running and the model name is right."
                elif provider == 'gemini':
                    answer = "Gemini call failed — check GEMINI_API_KEY is set and valid."
                elif not GROQ_API_KEY:
                    answer = "I can't reach the AI backend right now — GROQ_API_KEY isn't set on the server. Ask whoever runs this to add it."
                elif context:
                    answer = "I hit an error calling the AI model, but here's what I found in your materials:\n\n" + context[:500]
                else:
                    answer = "I hit an error calling the AI model and don't have any study materials uploaded for this yet. Try again in a moment, or upload a relevant PDF."

            db.execute('''INSERT INTO chat_history (user_id, question, answer, relevant_chunks, relevance_score, confidence)
                         VALUES(%s,%s,%s,%s,%s,%s)''',
                      (user['id'], question, answer[:2000], json.dumps(relevant_chunks[:3]),
                       sum(r['score'] for r in rag.hybrid_search(question, chunks, top_k=3)) / max(1, len(rag.hybrid_search(question, chunks, top_k=3))) if chunks else 0,
                       confidence))
            db.commit()

            return {'status': 'ok', 'answer': answer[:2000], 'relevant_chunks': relevant_chunks[:3], 'confidence': confidence}
        finally:
            db.close()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='Chat failed')

@router.post('/chat/compare')
def chat_compare(req: dict, request: Request):
    """
    Compare Mode: same question, sent to 2+ models, real latency measured
    per call. No ranking/consensus/merging — that's a separate, bigger
    feature. This just shows what each model actually said, side by side.
    """
    import time
    try:
        user = require_user(request)
        question = validate_string(req.get('question', ''), 'question', 3, 500)
        targets = req.get('models', [])

        if not isinstance(targets, list) or not (2 <= len(targets) <= 4):
            raise HTTPException(status_code=400, detail='Provide 2-4 models to compare')

        db = get_db()
        try:
            context, _chunks, _relevant, _confidence = _build_context(user['id'], question, db)
        finally:
            db.close()

        prompt = f"You are an AI tutor. Answer this based on context:\n\nContext:\n{context[:2000]}\n\nQuestion: {question}\n\nProvide concise educational answer."

        def run_one(t):
            provider = t.get('provider', '')
            model_name = t.get('model', '')
            label = t.get('label', f'{provider} {model_name}'.strip())
            t0 = time.monotonic()
            answer, error = _dispatch(provider, model_name, prompt)
            latency_ms = int((time.monotonic() - t0) * 1000)
            return {'provider': provider, 'model': model_name, 'label': label,
                    'answer': answer, 'error': error, 'latency_ms': latency_ms}

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(targets)) as pool:
            results = list(pool.map(run_one, targets))

        return {'question': question, 'results': results}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='Compare failed')

@router.get('/chat/history')
def chat_history(request: Request):
    try:
        user = require_user(request)
        db = get_db()
        try:
            history = db.execute('''SELECT * FROM chat_history WHERE user_id=%s
                                   ORDER BY created_at DESC LIMIT 50''', (user['id'],)).fetchall()
            return {'history': [dict(h) for h in history]}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='Failed to get history')

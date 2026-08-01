from fastapi import APIRouter, HTTPException, Request, UploadFile, File
import os, json, re, secrets
import requests
import fitz

from core import (
    get_db, require_user, validate_string, rag, logger,
    UPLOADS_DIR, MAX_PDF_SIZE, GROQ_API_KEY,
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

@router.post('/chat/ask')
def chat_ask(req: dict, request: Request):
    try:
        user = require_user(request)
        question = validate_string(req.get('question', ''), 'question', 3, 500)

        db = get_db()
        try:
            chunks_data = db.execute('''SELECT dc.chunk_text FROM document_chunks dc
                                       JOIN pdf_documents pd ON dc.document_id = pd.id
                                       WHERE pd.user_id = %s LIMIT 100''', (user['id'],)).fetchall()

            chunks = [row['chunk_text'] for row in chunks_data] if chunks_data else []

            relevant_chunks = []
            confidence = 0

            if chunks:
                results = rag.hybrid_search(question, chunks, top_k=3)
                relevant_chunks = [r['text'] for r in results]
                confidence = int(sum(r['confidence'] for r in results) / len(results)) if results else 0

            context = "\n".join(relevant_chunks)

            try:
                params = {'action': 'query', 'format': 'json', 'titles': question.split()[0][:50],
                         'prop': 'extracts', 'explaintext': True, 'exintro': True}
                resp = requests.get("https://en.wikipedia.org/w/api.php", params=params, timeout=5)
                wiki = ""
                if resp.ok:
                    data = resp.json()
                    for page_data in data['query']['pages'].values():
                        if 'extract' in page_data:
                            wiki = page_data['extract'][:500]
                            break
                context += "\n" + wiki
            except:
                pass

            answer = None

            if GROQ_API_KEY:
                try:
                    from groq import Groq
                    client = Groq(api_key=GROQ_API_KEY)
                    prompt = f"You are an AI tutor. Answer this based on context:\n\nContext:\n{context[:2000]}\n\nQuestion: {question}\n\nProvide concise educational answer."
                    response = client.chat.completions.create(model="llama-3.3-70b-versatile",
                                                             messages=[{"role": "user", "content": prompt}],
                                                             max_tokens=500, temperature=0.7)
                    answer = response.choices[0].message.content
                except Exception as e:
                    logger.error(f"Groq call failed: {e}")

            if answer is None:
                if not GROQ_API_KEY:
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

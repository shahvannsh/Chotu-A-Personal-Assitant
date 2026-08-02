from fastapi import APIRouter, HTTPException, Request

from core import get_db, require_user, validate_string

router = APIRouter()

@router.get('/leaderboard/global')
def leaderboard():
    try:
        db = get_db()
        try:
            users = db.execute('SELECT * FROM leaderboard ORDER BY total_points DESC LIMIT 100').fetchall()
            return {'leaderboard': [dict(u) for u in users]}
        finally:
            db.close()
    except Exception:
        raise HTTPException(status_code=500, detail='Failed to get leaderboard')

@router.get('/notifications')
def get_notifications(request: Request):
    try:
        user = require_user(request)
        db = get_db()
        try:
            n = db.execute('SELECT * FROM notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT 50',
                          (user['id'],)).fetchall()
            return {'notifications': [dict(x) for x in n]}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='Failed to get notifications')

@router.get('/search')
def search(q: str, request: Request):
    """
    Ctrl+K search-everywhere. Real data only — notes, exams, and past
    chat Q&A for the current user. No files/GitHub/agents/etc: those
    don't exist in this app, so they're not in the results.
    """
    try:
        user = require_user(request)
        q = validate_string(q, 'q', 1, 200)
        like = f'%{q}%'

        db = get_db()
        try:
            notes = db.execute(
                '''SELECT id, title, content FROM user_notes
                   WHERE user_id=%s AND (title ILIKE %s OR content ILIKE %s)
                   ORDER BY updated_at DESC LIMIT 8''',
                (user['id'], like, like)).fetchall()

            exams = db.execute(
                '''SELECT id, exam_name, subject, exam_date FROM exams
                   WHERE user_id=%s AND (exam_name ILIKE %s OR subject ILIKE %s)
                   ORDER BY exam_date LIMIT 8''',
                (user['id'], like, like)).fetchall()

            chats = db.execute(
                '''SELECT id, question, answer FROM chat_history
                   WHERE user_id=%s AND (question ILIKE %s OR answer ILIKE %s)
                   ORDER BY created_at DESC LIMIT 8''',
                (user['id'], like, like)).fetchall()

            memories = db.execute(
                '''SELECT id, fact FROM user_memory
                   WHERE user_id=%s AND fact ILIKE %s
                   ORDER BY created_at DESC LIMIT 8''',
                (user['id'], like)).fetchall()

            def snippet(text, length=140):
                text = (text or '').strip()
                return text[:length] + ('…' if len(text) > length else '')

            results = []
            for n in notes:
                results.append({'type': 'note', 'id': n['id'], 'title': n['title'],
                                'snippet': snippet(n['content']), 'url': '/notes.html'})
            for e in exams:
                results.append({'type': 'exam', 'id': e['id'], 'title': e['exam_name'],
                                'snippet': f"{e['subject']} · {e['exam_date']}", 'url': '/dashboard.html'})
            for c in chats:
                results.append({'type': 'chat', 'id': c['id'], 'title': snippet(c['question'], 80),
                                'snippet': snippet(c['answer']), 'url': '/history.html'})
            for m in memories:
                results.append({'type': 'memory', 'id': m['id'], 'title': snippet(m['fact'], 60),
                                'snippet': 'Saved fact', 'url': '/dashboard.html'})

            return {'results': results, 'count': len(results)}
        finally:
            db.close()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='Search failed')


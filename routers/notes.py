from fastapi import APIRouter, HTTPException, Request

from core import get_db, require_user, validate_string

router = APIRouter()

@router.post('/notes/create')
def note_create(req: dict, request: Request):
    try:
        user = require_user(request)

        title = validate_string(req.get('title', ''), 'title')
        content = req.get('content', '').strip()

        if len(content) > 50000:
            raise ValueError("Content too long")

        db = get_db()
        try:
            cursor = db.execute('INSERT INTO user_notes (user_id, title, content) VALUES(%s,%s,%s) RETURNING id',
                      (user['id'], title, content))
            note_id = cursor.fetchone()['id']
            db.commit()
            return {'status': 'ok', 'note_id': note_id}
        finally:
            db.close()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='Failed to create note')

@router.get('/notes')
def notes_get(request: Request):
    try:
        user = require_user(request)
        db = get_db()
        try:
            notes = db.execute('SELECT * FROM user_notes WHERE user_id=%s ORDER BY updated_at DESC LIMIT 100',
                              (user['id'],)).fetchall()
            return {'notes': [dict(n) for n in notes]}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='Failed to get notes')

@router.delete('/notes/{note_id}')
def delete_note(note_id: int, request: Request):
    try:
        user = require_user(request)
        db = get_db()
        try:
            db.execute('DELETE FROM user_notes WHERE id=%s AND user_id=%s', (note_id, user['id']))
            db.commit()
            return {'status': 'ok'}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='Failed to delete note')

from fastapi import APIRouter, HTTPException, Request

from core import get_db, require_user, validate_string

router = APIRouter()

MAX_FACTS_PER_USER = 200  # keeps context injection bounded, not a hard product limit

@router.post('/memory')
def create_memory(req: dict, request: Request):
    try:
        user = require_user(request)
        fact = validate_string(req.get('fact', ''), 'fact', 1, 300)

        db = get_db()
        try:
            count = db.execute('SELECT COUNT(*) as c FROM user_memory WHERE user_id=%s', (user['id'],)).fetchone()['c']
            if count >= MAX_FACTS_PER_USER:
                raise HTTPException(status_code=400, detail=f'Limit of {MAX_FACTS_PER_USER} saved facts reached — delete some first.')

            cursor = db.execute('INSERT INTO user_memory (user_id, fact) VALUES(%s,%s) RETURNING id', (user['id'], fact))
            fact_id = cursor.fetchone()['id']
            db.commit()
            return {'status': 'ok', 'id': fact_id, 'fact': fact}
        finally:
            db.close()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='Failed to save')

@router.get('/memory')
def list_memory(request: Request):
    try:
        user = require_user(request)
        db = get_db()
        try:
            rows = db.execute('SELECT id, fact, created_at FROM user_memory WHERE user_id=%s ORDER BY created_at DESC',
                              (user['id'],)).fetchall()
            return {'facts': [dict(r) for r in rows]}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='Failed to load')

@router.delete('/memory/{fact_id}')
def delete_memory(fact_id: int, request: Request):
    try:
        user = require_user(request)
        db = get_db()
        try:
            db.execute('DELETE FROM user_memory WHERE id=%s AND user_id=%s', (fact_id, user['id']))
            db.commit()
            return {'status': 'ok'}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='Failed to delete')

from fastapi import APIRouter, HTTPException, Request
from datetime import datetime, timedelta

from core import get_db, require_user, validate_string, logger

router = APIRouter()

@router.post('/focus-session/start')
def focus_start(req: dict, request: Request):
    try:
        user = require_user(request)
        subject = validate_string(req.get('subject', 'General'), 'subject', 1)
        duration = max(1, min(120, int(req.get('duration', 25))))

        db = get_db()
        try:
            cursor = db.execute('INSERT INTO focus_sessions (user_id, subject, duration_minutes) VALUES(%s,%s,%s) RETURNING id',
                      (user['id'], subject, duration))
            sid = cursor.fetchone()['id']
            db.commit()
            return {'session_id': sid, 'duration': duration}
        finally:
            db.close()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='Failed to start focus')

@router.post('/focus-session/{session_id}/end')
def focus_end(session_id: int, req: dict, request: Request):
    try:
        user = require_user(request)
        duration = max(1, min(120, int(req.get('duration', 25))))

        db = get_db()
        try:
            session = db.execute('SELECT * FROM focus_sessions WHERE id=%s AND user_id=%s',
                               (session_id, user['id'])).fetchone()

            if not session:
                raise HTTPException(status_code=404, detail='Session not found')

            db.execute('''UPDATE focus_sessions SET completed=TRUE, ended_at=to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD"T"HH24:MI:SS.US') WHERE id=%s AND user_id=%s''',
                      (session_id, user['id']))

            db.execute('INSERT INTO study_history (user_id, subject, session_type, duration_minutes) VALUES(%s,%s,%s,%s)',
                      (user['id'], session['subject'], 'focus', duration))

            today = datetime.now().date().isoformat()
            db.execute('''INSERT INTO daily_goals (user_id, goal_date, completed_minutes) VALUES(%s,%s,%s)
                          ON CONFLICT(user_id, goal_date) DO UPDATE SET completed_minutes=completed_minutes+%s''',
                      (user['id'], today, duration, duration))

            db.commit()
            return {'status': 'ok'}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='Failed to end focus')

@router.get('/focus-sessions')
def focus_sessions_list(request: Request):
    """
    Real read endpoint for data /focus-session/start and /end already write.
    Returns completed sessions plus simple aggregates computed from real rows
    (today/week totals, 14-day daily breakdown) — no fabricated numbers.
    """
    try:
        user = require_user(request)
        db = get_db()
        try:
            rows = db.execute('''SELECT id, subject, duration_minutes, started_at, ended_at
                                  FROM focus_sessions
                                  WHERE user_id=%s AND completed=TRUE
                                  ORDER BY started_at DESC LIMIT 200''', (user['id'],)).fetchall()

            sessions = []
            daily_seconds = {}
            today_str = datetime.now().date().isoformat()
            today_secs = 0
            week_secs = 0
            cutoff = datetime.now() - timedelta(days=14)

            for r in rows:
                dur_secs = (r['duration_minutes'] or 0) * 60
                started_raw = r['started_at']
                try:
                    started_dt = datetime.fromisoformat(started_raw.replace(' ', 'T')) if started_raw else None
                except Exception:
                    started_dt = None
                date_str = started_dt.date().isoformat() if started_dt else None

                sessions.append({
                    'task': r['subject'],
                    'duration': dur_secs,
                    'start': started_raw,
                    'date': date_str,
                })

                if date_str == today_str:
                    today_secs += dur_secs
                if started_dt and started_dt >= (datetime.now() - timedelta(days=7)):
                    week_secs += dur_secs
                if started_dt and started_dt >= cutoff and date_str:
                    daily_seconds[date_str] = daily_seconds.get(date_str, 0) + dur_secs

            streak_row = db.execute('SELECT current_streak FROM streaks WHERE user_id=%s', (user['id'],)).fetchone()
            streak = streak_row['current_streak'] if streak_row else 0

            def fmt(secs):
                h, m = divmod(int(secs) // 60, 60)
                return f'{h}h {m}m' if h else f'{m}m'

            return {
                'sessions': sessions,
                'stats': {'streak': streak, 'daily': daily_seconds},
                'fmt': {'today': fmt(today_secs), 'week': fmt(week_secs)}
            }
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"focus_sessions_list failed: {e}")
        raise HTTPException(status_code=500, detail='Failed to load sessions')

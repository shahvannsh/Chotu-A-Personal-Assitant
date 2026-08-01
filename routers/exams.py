from fastapi import APIRouter, HTTPException, Request
from datetime import datetime, timedelta

from core import get_db, require_user, validate_string

router = APIRouter()

@router.post('/exams/create')
def create_exam(req: dict, request: Request):
    try:
        user = require_user(request)
        exam_name = validate_string(req.get('exam_name', ''), 'exam_name')
        subject = validate_string(req.get('subject', ''), 'subject')
        exam_date = req.get('exam_date', '')
        estimated_hours = max(0, min(1000, int(req.get('estimated_hours', 0))))

        try:
            exam_dt = datetime.fromisoformat(exam_date)
        except:
            raise HTTPException(status_code=400, detail='Invalid date')

        db = get_db()
        try:
            db.execute('INSERT INTO exams (user_id, exam_name, subject, exam_date, estimated_hours) VALUES(%s,%s,%s,%s,%s)',
                      (user['id'], exam_name, subject, exam_date, estimated_hours))
            db.commit()

            exam = db.execute('SELECT id FROM exams WHERE user_id=%s AND exam_name=%s ORDER BY created_at DESC LIMIT 1',
                             (user['id'], exam_name)).fetchone()
            exam_id = exam['id']

            today = datetime.now().date()
            days_left = max(1, (exam_dt.date() - today).days)

            for day in range(min(days_left, 365)):
                schedule_date = (today + timedelta(days=day)).isoformat()
                db.execute('INSERT INTO exam_schedule (exam_id, day_number, date, hours_planned) VALUES(%s,%s,%s,%s)',
                          (exam_id, day + 1, schedule_date, 1))

            db.commit()
            return {'status': 'ok', 'exam_id': exam_id}
        finally:
            db.close()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='Exam creation failed')

@router.get('/exams')
def get_exams(request: Request):
    try:
        user = require_user(request)
        db = get_db()
        try:
            exams = db.execute('SELECT * FROM exams WHERE user_id=%s ORDER BY exam_date LIMIT 100',
                              (user['id'],)).fetchall()
            return {'exams': [dict(e) for e in exams]}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='Failed to get exams')

@router.get('/streaks')
def get_streaks(request: Request):
    try:
        user = require_user(request)
        db = get_db()
        try:
            streak = db.execute('SELECT * FROM streaks WHERE user_id=%s', (user['id'],)).fetchone()
            return dict(streak) if streak else {'current_streak': 0, 'longest_streak': 0}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='Failed to get streaks')

@router.post('/streaks/log')
def log_streak(request: Request):
    try:
        user = require_user(request)
        today = datetime.now().date().isoformat()

        db = get_db()
        try:
            streak = db.execute('SELECT * FROM streaks WHERE user_id=%s', (user['id'],)).fetchone()

            if not streak:
                db.execute('INSERT INTO streaks (user_id, current_streak, longest_streak, last_study_date) VALUES(%s,%s,%s,%s) ON CONFLICT (user_id) DO NOTHING',
                          (user['id'], 1, 1, today))
            else:
                if streak['last_study_date'] != today:
                    new_current = streak['current_streak'] + 1 if streak['last_study_date'] and \
                                  (datetime.now().date() - datetime.fromisoformat(streak['last_study_date']).date()).days == 1 else 1
                    new_longest = max(new_current, streak['longest_streak'])
                    db.execute('UPDATE streaks SET current_streak=%s, longest_streak=%s, last_study_date=%s WHERE user_id=%s',
                              (new_current, new_longest, today, user['id']))

            db.commit()
            return {'status': 'ok'}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='Failed to log streak')

@router.get('/daily-report')
def get_daily_report(request: Request):
    try:
        user = require_user(request)
        today = datetime.now().date().isoformat()

        db = get_db()
        try:
            log = db.execute('SELECT * FROM daily_study_log WHERE user_id=%s AND study_date=%s',
                            (user['id'], today)).fetchone()

            if not log:
                return {'minutes': 0, 'points': 0}

            minutes = log['minutes_studied'] or 0
            points = (minutes // 15) * 5
            return {'minutes': minutes, 'points': points}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='Failed to get report')

@router.get('/daily-goal')
def get_goal(request: Request):
    try:
        user = require_user(request)
        today = datetime.now().date().isoformat()

        db = get_db()
        try:
            goal = db.execute('SELECT * FROM daily_goals WHERE user_id=%s AND goal_date=%s',
                             (user['id'], today)).fetchone()

            if not goal:
                db.execute('INSERT INTO daily_goals (user_id, goal_date, goal_minutes, completed_minutes) VALUES(%s,%s,%s,%s)',
                          (user['id'], today, 60, 0))
                db.commit()
                goal = db.execute('SELECT * FROM daily_goals WHERE user_id=%s AND goal_date=%s',
                                 (user['id'], today)).fetchone()

            d = dict(goal)
            progress = int((d['completed_minutes'] / d['goal_minutes']) * 100) if d['goal_minutes'] > 0 else 0
            return {'goal_minutes': d['goal_minutes'], 'completed_minutes': d['completed_minutes'], 'progress': progress}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='Failed to get goal')

@router.post('/daily-goal/update')
def update_goal(req: dict, request: Request):
    try:
        user = require_user(request)
        today = datetime.now().date().isoformat()
        minutes = max(0, min(1440, int(req.get('minutes', 0))))

        db = get_db()
        try:
            goal = db.execute('SELECT * FROM daily_goals WHERE user_id=%s AND goal_date=%s',
                             (user['id'], today)).fetchone()

            if goal:
                db.execute('UPDATE daily_goals SET completed_minutes=completed_minutes+%s WHERE user_id=%s AND goal_date=%s',
                          (minutes, user['id'], today))
            else:
                db.execute('INSERT INTO daily_goals (user_id, goal_date, goal_minutes, completed_minutes) VALUES(%s,%s,%s,%s)',
                          (user['id'], today, 60, minutes))

            db.commit()
            return {'status': 'ok'}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='Failed to update goal')

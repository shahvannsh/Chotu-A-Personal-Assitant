from fastapi import APIRouter, HTTPException, Request
import secrets
from datetime import datetime, timedelta

from core import (
    get_db, rate_limit, require_user,
    validate_email, validate_string,
    hash_password, verify_password,
)

router = APIRouter()


def _validate_password(password: str) -> str:
    if not isinstance(password, str):
        raise ValueError("password must be string")
    if len(password) < 8 or len(password) > 128:
        raise ValueError("password must be 8-128 chars")
    return password


@router.post('/auth/login')
@rate_limit(max_requests=50, seconds=60)
def login(req: dict, request: Request):
    """
    Doubles as signup + login on one endpoint (matches the existing
    frontend contract). Fix: previously this took ONLY email+name and
    logged the caller in as whatever user owned that email — anyone who
    knew (or guessed) another user's email could take over their account
    with zero verification. Now a password is required and checked.

    Known limitation: since there's no email verification (no SMTP
    configured), the FIRST login for a given email still just claims
    that email — this only stops someone from taking over an email
    that has *already* signed up. Real ownership verification needs a
    magic-link/OTP email flow, which needs mail sending infra this repo
    doesn't have yet.
    """
    try:
        email = validate_email(req.get('email', ''))
        name = validate_string(req.get('name', 'User'), 'name', 1, 100)
        password = _validate_password(req.get('password', ''))

        db = get_db()
        try:
            user = db.execute('SELECT * FROM users WHERE email=%s', (email,)).fetchone()

            if not user:
                # First time this email has been seen: create the account
                # with this password.
                db.execute('INSERT INTO users (email, name, password_hash) VALUES(%s,%s,%s)',
                          (email, name, hash_password(password)))
                db.commit()
                user = db.execute('SELECT * FROM users WHERE email=%s', (email,)).fetchone()
            elif not user['password_hash']:
                # Legacy account from before passwords existed. Claim it
                # with the password given now rather than locking the
                # owner out.
                db.execute('UPDATE users SET password_hash=%s WHERE id=%s',
                          (hash_password(password), user['id']))
                db.commit()
            else:
                if not verify_password(password, user['password_hash']):
                    raise HTTPException(status_code=401, detail='Incorrect password')

            token = secrets.token_urlsafe(32)
            expires_at = (datetime.now() + timedelta(days=30)).isoformat()
            ip = request.client.host if request.client else "unknown"

            db.execute('DELETE FROM sessions WHERE expires_at < %s', (datetime.now().isoformat(),))
            db.execute('INSERT INTO sessions (token, user_id, expires_at, ip_address) VALUES(%s,%s,%s,%s)',
                      (token, user['id'], expires_at, ip))
            db.commit()

            user_out = dict(user)
            user_out.pop('password_hash', None)
            return {'token': token, 'user': user_out, 'expires_at': expires_at}
        finally:
            db.close()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='Login failed')


@router.post('/auth/logout')
def logout(request: Request):
    try:
        user = require_user(request)
        auth_header = request.headers.get('Authorization', '').strip()
        if auth_header.startswith('Bearer '):
            token = auth_header[7:].strip()
            db = get_db()
            try:
                db.execute('DELETE FROM sessions WHERE token=%s', (token,))
                db.commit()
            finally:
                db.close()
        return {'status': 'ok'}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='Logout failed')


@router.get('/auth/me')
def get_me(request: Request):
    user = require_user(request)
    user.pop('password_hash', None)
    return user

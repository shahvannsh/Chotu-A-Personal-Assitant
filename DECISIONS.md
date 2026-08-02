# Architecture decisions & bugs found

Notes from the session that took this from a single 1200-line `app.py`
to what's in this repo now. Written for whoever (including future me)
wants to know *why* something is the way it is, not just what it does.

## Router split

`app.py` was one file: config, DB schema, auth, RAG, and every route,
all together. Split into:

- `core.py` — config, DB connection wrapper, `init_db()`, validators,
  `require_user`, password hashing, the `AdvancedRAG` class
- `routers/*.py` — one file per domain, each a plain `APIRouter`
- `app.py` — just creates the `FastAPI` app, wires CORS, includes the
  routers, runs `init_db()` on startup

The route set is identical before and after — this was proven by
diffing every `@app.get/post/delete(...)` decorator against every
`@router...` decorator post-split, not just assumed. No route logic
changed in the split itself.

## Auth: the account-takeover bug

Original `/auth/login` took `{email, name}` and logged the caller in
as whichever user owned that email — no password, no verification of
any kind. Anyone who knew (or guessed) another user's email could take
over their session instantly.

Fixed with PBKDF2-SHA256 password hashing (stdlib `hashlib`, no new
dependency — `passlib`/`bcrypt` weren't already in `requirements.txt`
and didn't need to be). First login for a new email creates the
account; every login after that requires the matching password.

**Known remaining gap, on purpose, not an oversight**: there's still
no email verification, because there's no SMTP configured. First
signup for a given email still just claims it. This closes
*account takeover*, not *identity verification* — those are different
problems, and a magic-link flow is a separate feature, not a bug fix.

## Postgres `ON CONFLICT` ambiguous column bug

`routers/focus.py`'s session-end handler had:

```sql
INSERT INTO daily_goals (user_id, goal_date, completed_minutes) VALUES(%s,%s,%s)
ON CONFLICT(user_id, goal_date) DO UPDATE SET completed_minutes=completed_minutes+%s
```

This silently 500'd on *every single call*, from the moment the table
was created. `completed_minutes` in the `SET` clause is ambiguous —
Postgres can't tell if you mean the existing row's value or the
about-to-be-rejected inserted row's value — and needs the table name
to disambiguate: `daily_goals.completed_minutes`. This wasn't caught
until building the Focus Timer UI actually exercised the endpoint for
the first time; the route existed and "worked" (returned 200 on the
happy path with no existing row) but broke the instant two sessions
happened on the same day, which is the normal case.

Lesson: an endpoint returning 200 once proves nothing about the
`ON CONFLICT` path unless you actually trigger the conflict.

## Multi-provider LLM routing

`routers/study.py` has `_dispatch(provider, model, prompt)` — a single
function every chat path goes through, returning
`(answer_or_None, error_or_None)` and never raising. `chat/ask` and
`chat/compare` both call it instead of duplicating provider
branching. Providers: Groq (`groq` SDK), Ollama (raw HTTP to
`OLLAMA_BASE_URL/api/chat`), Gemini (raw HTTP to the
`generateContent` endpoint — no SDK dependency added for one call).

`GET /models` only lists a provider if it's actually usable *right
now* — Groq/Gemini need a real key present, Ollama gets a live
`/api/tags` ping with a 2s timeout. Nothing appears in the dropdown
that doesn't actually work at that moment.

### The Docker networking gotcha

Ollama runs on the host machine (Windows, in this case); the app runs
inside a Linux container. `localhost` inside the container refers to
the container itself, not the host — a very common trap. Fixed by
defaulting `OLLAMA_BASE_URL` to `http://host.docker.internal:11434`,
which is Docker Desktop's special DNS name for "the host machine."
This needed a real running container to catch — nothing about it
would show up in a unit test or from reading the code casually.

## Compare Mode: parallel, not sequential

`chat/compare` uses a `ThreadPoolExecutor` to fire all model calls at
once rather than looping and awaiting each one. Verified with real
timing: two real network calls to two different providers, 140ms
total wall-clock time — proving genuine concurrency, not just
"the code looks like it should be parallel."

Each model's result carries its own `error` field. One model failing
(bad key, unreachable host, whatever) doesn't take down the others —
confirmed by deliberately breaking one provider and leaving the other
working, and checking both results came back independently correct.

## What "verified" means in this repo's history

Every feature above was checked against a **live Postgres database
and a live running server**, hitting real HTTP endpoints with `curl`
or `TestClient`, not just read for correctness or unit-tested in
isolation. Several real bugs (the `ON CONFLICT` ambiguity, two
extension-less nav links returning 404, a PowerShell env-var parsing
trap) were only caught this way — they would have shipped clean past
a code review that didn't actually run the thing.

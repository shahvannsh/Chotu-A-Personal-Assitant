# CHOTU - AI Study Operating System

Production-ready Phase 1-5 implementation with all features.

## Features

### Phase 1: Core
- Spaced Repetition with SM-2 algorithm
- Daily Streaks (current & longest)
- Exam Scheduling & Countdown
- Daily Study Reports

### Phase 2: Intelligence
- Mock Exams with scoring
- Knowledge Graph
- Weak Topic Coaching
- Quiz Attempts Tracking

### Phase 3: Habits
- Daily Goal Tracking (60 min default)
- Global + Weekly Leaderboard
- AI-powered Recommendations
- Badges & Achievements

### Phase 4: Distribution
- Notifications System
- Share Score/Rank
- Challenges (compete with friends)
- Referral System
- Friend Connections & Activity

### Phase 5: Premium
- Notes with persistent storage
- Bookmarks for resources
- Complete Study History
- Personal Goals Management
- AI Mentor (Groq integration)
- Interview Prep (mock interviews)
- Peer Tutoring Marketplace
- User Preferences & Customization

## Installation

### Local Development
```bash
pip install -r requirements.txt
python server.py
```

Visit `http://localhost:8000`

### Render Deployment
1. Push to GitHub
2. Connect to Render
3. Set environment variables:
   - `GROQ_API_KEY` - Groq API key for AI features
   - `GOOGLE_CLIENT_ID` - Google OAuth client ID
   - `GOOGLE_CLIENT_SECRET` - Google OAuth secret
   - `REDIRECT_URI` - OAuth redirect URL
4. Add Disk at `/data` for persistent storage
5. Deploy!

## Environment Variables

```
GROQ_API_KEY=your_groq_key
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_secret
REDIRECT_URI=https://your-domain.com/auth/callback
PORT=8000
```

## Database

SQLite database at `/data/chotu.db` (or `chotu.db` locally).

All tables auto-created on first run.

## API Documentation

### Auth
- `POST /auth/login` - Register/login with email
- `GET /auth/me` - Get current user

### Phase 1
- `POST /exams/create` - Create exam
- `GET /exams` - List exams
- `GET /streaks` - Get streak count
- `POST /streaks/log` - Log study day
- `GET /daily-report` - Get daily stats

### Phase 2
- `POST /mock-exam/generate` - Generate mock exam
- `POST /mock-exam/{id}/submit` - Submit answers

### Phase 3
- `GET /daily-goal` - Get today's goal
- `POST /daily-goal/update` - Update progress
- `GET /leaderboard/global` - Global rankings
- `GET /leaderboard/weekly` - Weekly rankings

### Phase 4
- `GET /notifications` - List notifications
- `POST /challenges/create` - Create challenge
- `POST /friends/connect` - Connect friend

### Phase 5
- `POST /notes/create` - Create note
- `GET /notes` - List notes
- `POST /bookmarks/add` - Add bookmark
- `GET /bookmarks` - List bookmarks
- `POST /study/log` - Log session
- `GET /study/history` - Study history
- `POST /goals/create` - Create goal
- `GET /goals` - List goals
- `POST /ai-mentor/ask` - Ask AI Mentor
- `POST /interview-prep/start` - Start interview prep
- `GET /subscription/status` - Check plan
- `POST /subscription/upgrade` - Upgrade plan

## Architecture

```
CHOTU/
├── server.py           # FastAPI backend (990 lines)
├── index.html          # Frontend UI
├── requirements.txt    # Python dependencies
├── runtime.txt         # Python version
├── Procfile            # Render configuration
└── README.md           # This file
```

## Technologies

- **Backend**: FastAPI, SQLite
- **AI**: Groq (Mixtral 8x7b)
- **Auth**: Google OAuth 2.0
- **Deployment**: Render.com
- **Storage**: SQLite + Render Disk

## License

MIT

## Support

For issues, open a GitHub issue or contact support.

---

**CHOTU v1.0.0** - Built for serious students.

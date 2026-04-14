# SAAITA — Ethereal Authentication Portal

A full-stack authentication system with a glassmorphism UI, React frontend, and Flask backend.

---

## Tech Stack

- **Frontend:** Vite + React 19, TailwindCSS v3, react-router-dom
- **Backend:** Python Flask, SQLite, Werkzeug (password hashing), Flask-CORS

---

## Project Structure

```
SAAITA/
├── frontend/        # Vite + React app
│   └── src/
│       ├── components/Auth.jsx     # Login / Signup form
│       ├── pages/Dashboard.jsx     # Protected dashboard
│       └── services/api.js         # All API calls
└── backend/         # Flask API server
    ├── app.py       # Routes & auth logic
    ├── database.py  # SQLite schema
    └── requirements.txt
```

---

## Setup & Running

### Backend

```bash
cd SAAITA/backend
pip install -r requirements.txt
python app.py
```

Runs at `http://localhost:5000`

### Frontend

```bash
cd SAAITA/frontend
npm install
npm run dev
```

Runs at `http://localhost:5173`

---

## API Endpoints

| Method | Endpoint            | Description              |
|--------|---------------------|--------------------------|
| POST   | /api/auth/signup    | Register a new user      |
| POST   | /api/auth/login     | Login and get session ID |
| GET    | /api/auth/me        | Verify session, get user |
| POST   | /api/auth/logout    | Destroy session          |

### Authentication

Send the session ID in the `X-Session-Id` header for protected endpoints.

---

## Password Requirements

- Minimum 8 characters
- At least one letter
- At least one number

---

## Security Notes

- Passwords are hashed with `werkzeug.security.generate_password_hash`
- Sessions are stored in SQLite (not in-memory) and expire after 7 days
- CORS is restricted to `localhost:5173` only
- The `saaita.db` file is git-ignored

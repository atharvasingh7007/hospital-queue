# Hospital Queue AI

Multi-agent AI system for hospital queue management. Built for real-world hospital workflows — walk-in patients, emergency detection, appointment scheduling, triage routing, and real-time queue tracking.

## What It Does

- **Patient Check-in**: Walk-in patients join a queue via chat interface
- **AI Triage**: Symptom analysis with urgency classification and department routing
- **Emergency Detection**: Autonomous detection of critical symptoms (chest pain, breathing difficulty) with auto-escalation
- **Live Queue Tracking**: Real-time position updates and estimated wait times
- **Doctor Dashboard**: Queue management with patient details, symptoms, and priority badges
- **Agent Transparency**: Full reasoning visualization — see which agents are thinking and why
- **Predictive Analytics**: Queue congestion forecasting and doctor delay predictions

## Agent Architecture

```
Patient Message
    │
    ▼
┌─────────┐     ┌──────────────────────────────┐
│  Nova    │────▶│  Intent Classification       │
│  (Hub)   │     │  emergency / triage / queue   │
└────┬─────┘     │  appointment / analytics      │
     │           └──────────────────────────────┘
     │
     ├──▶ Triage Agent ──── Symptom assessment, urgency scoring
     ├──▶ Queue Manager ─── Position tracking, wait estimates
     ├──▶ Scheduler ─────── Appointment coordination
     ├──▶ Notifier ──────── Patient alerts and reminders
     ├──▶ Analytics ─────── Congestion predictions
     └──▶ Emergency ─────── Autonomous critical detection
              │
     ┌────────▼────────┐
     │    Event Bus     │  Agents communicate directly
     │  (Pub/Sub)       │  without central routing
     └─────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Backend | FastAPI, Python 3.11+, SQLAlchemy (async) |
| AI | Google Gemini via Vertex AI |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Auth | JWT with role-based access |
| Streaming | Server-Sent Events (SSE) |

## Getting Started

### Backend

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # Edit with your GCP credentials
python seed.py          # Populate demo data
python main.py          # Starts on port 8080
```

### Frontend

```bash
cd frontend
npm install
npm run dev             # Starts on port 3002
```

Open [http://localhost:3002](http://localhost:3002) in your browser.

### Demo Accounts

| Role | Email | Password |
|------|-------|----------|
| Patient | patient@demo.com | demo123 |
| Doctor | doctor@demo.com | demo123 |
| Admin | admin@demo.com | demo123 |

## Project Structure

```
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── models.py            # SQLAlchemy models
│   ├── routes.py            # API endpoints
│   ├── database.py          # Database session
│   ├── seed.py              # Demo data seeder
│   ├── core/
│   │   └── config.py        # App configuration
│   └── services/
│       ├── gemini_service.py     # Gemini AI integration
│       ├── agent_orchestrator.py # Multi-agent coordinator
│       ├── event_bus.py          # Agent-to-agent pub/sub
│       ├── hospital_state.py     # Shared hospital snapshot
│       ├── emergency_detector.py # Autonomous emergency detection
│       └── queue_optimizer.py    # Predictive queue balancing
├── frontend/
│   └── src/app/
│       ├── page.tsx         # Main application
│       ├── layout.tsx       # Root layout
│       └── globals.css      # Global styles
├── .env.example
├── .gitignore
└── README.md
```

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Create new account |
| POST | `/api/v1/auth/login` | Sign in, get JWT token |
| GET | `/api/v1/auth/me` | Current user info |

### Hospital Operations
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/hospital/state` | Real-time hospital snapshot |
| POST | `/api/v1/queue/checkin` | Check in to queue |
| GET | `/api/v1/doctor/{id}/dashboard` | Doctor queue view |
| POST | `/api/v1/chat/stream` | AI chat (SSE streaming) |

### Agent System
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/agents/status` | All agent statuses |
| GET | `/api/v1/agents/activity` | Recent agent actions |
| POST | `/api/v1/emergency/assess` | Emergency severity check |
| GET | `/api/v1/analytics/predictions` | Queue forecasts |

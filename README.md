# 🏥 Hospital Queue AI — Multi-Agent Intelligence System

> **AI-powered hospital queue management using Google ADK, Vertex AI (Gemini 2.5), AlloyDB, BigQuery, and Cloud Run.**

**🔗 Live Demo:** https://hospital-queue-ai-343602196288.us-central1.run.app
**📦 GitHub:** https://github.com/atharvasingh7007/hospital-queue

---

## 🎯 What Is This?

A smart hospital queue system powered by **6 specialized AI agents** built with **Google Agent Development Kit (ADK)**. Patients chat naturally with Nova (the orchestrator) who intelligently routes requests to specialist agents for triage, appointments, queue management, notifications, and analytics.

### Key Capabilities
- **Natural Language Triage** — Describe symptoms, get severity scoring (0-100) and department routing
- **Emergency Detection** — Auto-escalation for critical cases (severity > 80)
- **Smart Queue Management** — Priority-based queuing with real-time position tracking
- **Appointment Booking** — Find available doctors and book with one conversation
- **Doctor Notifications** — Emergency alerts broadcast to all available physicians
- **Hospital Analytics** — Real-time congestion monitoring, wait time predictions, BigQuery insights

---

## 🏗️ Architecture

```
Patient / Doctor / Admin
         │
         │ HTTPS
         ▼
┌─────────────────────────────────────────────────┐
│              Google Cloud Run                    │
│  ┌───────────────────────────────────────────┐  │
│  │         ADK Web Server                     │  │
│  │                                            │  │
│  │  ┌──────────────────────────────────────┐  │  │
│  │  │  Nova (Root Orchestrator Agent)      │  │  │
│  │  │  ┌──────┐ ┌──────┐ ┌──────────────┐ │  │  │
│  │  │  │Triage│ │Sched-│ │   Queue      │ │  │  │
│  │  │  │Agent │ │uler  │ │   Manager    │ │  │  │
│  │  │  └──────┘ └──────┘ └──────────────┘ │  │  │
│  │  │  ┌──────┐ ┌──────────────────────┐  │  │  │
│  │  │  │Notify│ │  Analytics Agent     │  │  │  │
│  │  │  │Agent │ │  (BigQuery MCP)      │  │  │  │
│  │  │  └──────┘ └──────────────────────┘  │  │  │
│  │  └──────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────┘  │
│                    │                │             │
│          Vertex AI │       BigQuery │             │
│        (Gemini 2.5)│    (Analytics) │             │
│                    │                │             │
│            AlloyDB (PostgreSQL 17)               │
│            (IAM Authentication)                  │
└─────────────────────────────────────────────────┘
```

---

## 🤖 Multi-Agent System (Google ADK)

Six specialized `LlmAgent` instances orchestrated by Nova:

| Agent | Role | Tools | Trigger |
|---|---|---|---|
| **Nova** 🤖 | Root orchestrator — routes to specialist agents | `sub_agents` delegation | Always active first |
| **Triage** 🏥 | Symptom assessment, severity scoring (0-100), emergency detection | `assess_symptoms`, `get_emergency_protocol` | Patient describes symptoms |
| **Scheduler** 📅 | Doctor availability, appointment booking | `get_available_doctors`, `book_appointment`, `get_appointment_details` | "Book an appointment" |
| **Queue Manager** 📋 | Check-in, positions, wait times, department status | `check_in_patient`, `get_queue_position`, `get_department_queue_status` | "What's my queue number?" |
| **Notifier** 🔔 | Doctor alerts, patient notifications, emergency broadcasts | `send_notification`, `send_emergency_alert`, `get_notifications` | Auto-triggered on emergencies |
| **Analytics** 📊 | Hospital stats, congestion, wait predictions, BigQuery logging | `get_hospital_overview`, `get_department_congestion`, `predict_wait_times`, `log_to_bigquery` | "Show hospital stats" |

### Agent Delegation Flow

```
Patient Message → Nova (Orchestrator)
                    │
                    ├── Symptoms? → Triage Agent → assess_symptoms → severity score
                    │                               └── severity > 80 → Emergency Protocol
                    │
                    ├── Appointment? → Scheduler Agent → get_available_doctors → book_appointment
                    │
                    ├── Queue? → Queue Agent → check_in_patient → get_queue_position
                    │
                    ├── Notifications? → Notifier Agent → send_notification / emergency_alert
                    │
                    └── Analytics? → Analytics Agent → hospital_overview / congestion / predictions
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Agent Framework** | Google ADK (`google-adk`) — Multi-agent orchestration |
| **AI Model** | Gemini 2.5 Flash via Vertex AI |
| **Frontend** | ADK Web (built-in development UI) |
| **Database** | AlloyDB (PostgreSQL 17) with IAM authentication |
| **Analytics** | BigQuery (`hospital_analytics` dataset) |
| **Deployment** | Google Cloud Run (single container) |
| **Infrastructure** | GCP Artifact Registry + Cloud Build |

---

## 📁 Project Structure

```
hospital-queue/
├── hospital_queue/              # ADK agent package
│   ├── __init__.py
│   ├── agent.py                 # Root agent (Nova) + 5 sub-agents
│   ├── tools/
│   │   ├── shared_state.py      # In-memory hospital state (departments, doctors, queue)
│   │   ├── triage_tools.py      # Symptom assessment & emergency detection
│   │   ├── scheduler_tools.py   # Doctor availability & appointment booking
│   │   ├── queue_tools.py       # Queue check-in, positions, wait times
│   │   ├── notifier_tools.py    # Notifications & emergency alerts
│   │   └── analytics_tools.py   # Hospital stats, congestion, BigQuery logging
│   ├── db/
│   │   ├── connection.py        # AlloyDB connector (IAM auth) / SQLite fallback
│   │   └── models.py            # SQLAlchemy ORM models
│   └── services/
│       └── bigquery_service.py  # BigQuery analytics pipeline
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── .gitignore
└── README.md
```

---

## 🎬 Use Flows

### Patient Visit
```
1. Open → ADK Web chat UI
2. "Hi, I have a headache and fever since 2 days. I'm Rahul, 28."
3. Nova → delegates to Triage Agent
4. Triage → assesses severity (e.g., 45/100 MODERATE)
5. Triage → recommends General Medicine department
6. Nova → delegates to Queue Agent → checks in with NORMAL priority
7. Patient gets queue number #101, estimated wait ~15 min
```

### Emergency
```
1. "I'm having severe chest pain and difficulty breathing"
2. Nova → Triage Agent → severity 90/100 CRITICAL
3. Triage → get_emergency_protocol → CODE RED
4. Nova → Notifier Agent → send_emergency_alert
5. All emergency doctors notified with RED alert
6. Patient bypasses queue → front of line
```

### Analytics
```
1. "Show me hospital statistics"
2. Nova → Analytics Agent → get_hospital_overview
3. Shows: patients waiting, in consultation, completed
4. Department congestion levels (LOW/MODERATE/HIGH/CRITICAL)
5. Wait time predictions per department
```

---

## 🚀 Deployment

### One-Command Deploy (Cloud Run)

```bash
gcloud run deploy hospital-queue-ai \
  --source . \
  --platform managed \
  --region us-central1 \
  --project <YOUR_GCP_PROJECT_ID> \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --max-instances 10 \
  --port 8080 \
  --set-env-vars "GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=<YOUR_GCP_PROJECT_ID>,GOOGLE_CLOUD_LOCATION=us-central1,BIGQUERY_DATASET=hospital_analytics"
```

### Environment Variables

| Variable | Description | Required |
|---|---|---|
| `GOOGLE_GENAI_USE_VERTEXAI` | Enable Vertex AI backend | ✅ Set to TRUE |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID | ✅ Your project ID |
| `GOOGLE_CLOUD_LOCATION` | GCP region | ✅ us-central1 |
| `BIGQUERY_DATASET` | BigQuery dataset name | hospital_analytics |
| `ALLOYDB_INSTANCE` | AlloyDB instance URI | For DB persistence |
| `ALLOYDB_IAM_USER` | IAM user for AlloyDB | For DB persistence |

### Local Development

```bash
pip install -r requirements.txt

# Set Vertex AI environment
export GOOGLE_GENAI_USE_VERTEXAI=TRUE
export GOOGLE_CLOUD_PROJECT=<YOUR_GCP_PROJECT_ID>
export GOOGLE_CLOUD_LOCATION=us-central1

# Run ADK Web
adk web --port 8080 .
# Open http://localhost:8080
```

---

## 🔮 GCP Services Used

| Service | Purpose |
|---|---|
| **Google ADK** | Multi-agent orchestration framework |
| **Vertex AI** | Gemini 2.5 Flash model hosting |
| **AlloyDB** | PostgreSQL-compatible database (IAM auth) |
| **BigQuery** | Analytics data warehouse |
| **Cloud Run** | Serverless container deployment |
| **Cloud Build** | CI/CD container builds |
| **Artifact Registry** | Container image storage |

---

## 👨‍💻 Developed By

**Atharva Singh** — B.Tech CSE, LPU | Co-founder Bhooyam | AI/IoT Developer

*Built for Google GenAI Academy APAC Hackathon — demonstrating multi-agent AI systems with real hospital queue management capabilities.*

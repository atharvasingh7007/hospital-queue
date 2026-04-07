"""
Hospital Queue AI — API Routes
FastAPI endpoints for auth, patients, doctors, queue management, agent activity, and AI chat.
"""
from datetime import datetime, timezone
import asyncio
import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database import get_db
from models import (
    Patient, Doctor, QueueEntry, ChatMessage,
    Appointment, NotificationLog, Department,
    User, AgentActivity,
)
from auth import (
    hash_password, verify_password, create_token,
    RegisterRequest, LoginRequest, AuthResponse,
    get_current_user, require_auth, require_doctor, require_admin,
)

logger = logging.getLogger("hospital_queue.routes")

router = APIRouter(prefix="/api/v1", tags=["Hospital Queue AI"])


# ── Request / Response Schemas ─────────────────────────

class PatientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=10, max_length=15)
    age: Optional[int] = Field(None, ge=0, le=150)
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    allergies: Optional[str] = None


class PatientResponse(BaseModel):
    id: int
    name: str
    phone: str
    age: Optional[int]
    gender: Optional[str]
    blood_group: Optional[str]
    allergies: Optional[str]


class DoctorResponse(BaseModel):
    id: int
    name: str
    specialty: str
    phone: str
    department_id: int
    consultation_duration_minutes: int
    is_active: bool


class DepartmentResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]


class QueueCheckinRequest(BaseModel):
    patient_id: int
    doctor_id: int
    symptoms: Optional[str] = None


class QueueEntryResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    queue_number: int
    position: int
    status: str
    priority_score: int
    estimated_wait_minutes: Optional[int]
    symptoms: Optional[str]
    urgency_level: Optional[str]
    checked_in_at: datetime


class ChatRequest(BaseModel):
    patient_id: int
    agent_name: str = Field(default="nova")
    message: str = Field(..., min_length=1, max_length=5000)


class ChatMessageResponse(BaseModel):
    id: int
    patient_id: int
    agent_name: str
    role: str
    content: str
    created_at: datetime


# ── Health ─────────────────────────────────────────────

@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/health/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(select(func.count()).select_from(Patient))
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ready" if db_ok else "not_ready",
        "database": "ok" if db_ok else "error",
    }


# ── Authentication ─────────────────────────────────────

@router.post("/auth/register", response_model=AuthResponse)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user (patient, doctor, or admin)."""

    # Check for existing email
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    linked_patient_id = None
    linked_doctor_id = None

    # Create linked patient record if role is patient
    if data.role == "patient":
        existing_patient = await db.execute(
            select(Patient).where(Patient.phone == data.phone)
        )
        patient = existing_patient.scalar_one_or_none()
        if patient:
            linked_patient_id = patient.id
        else:
            patient = Patient(
                name=data.name, phone=data.phone,
                age=data.age, gender=data.gender,
            )
            db.add(patient)
            await db.flush()
            linked_patient_id = patient.id

    # Create linked doctor record if role is doctor
    elif data.role == "doctor":
        existing_doctor = await db.execute(
            select(Doctor).where(Doctor.phone == data.phone)
        )
        doctor = existing_doctor.scalar_one_or_none()
        if doctor:
            linked_doctor_id = doctor.id
        else:
            doctor = Doctor(
                name=data.name, phone=data.phone,
                specialty=data.specialty or "General Medicine",
                department_id=data.department_id or 1,
            )
            db.add(doctor)
            await db.flush()
            linked_doctor_id = doctor.id

    user = User(
        name=data.name,
        email=data.email,
        hashed_password=hash_password(data.password),
        phone=data.phone,
        role=data.role,
        patient_id=linked_patient_id,
        doctor_id=linked_doctor_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_token(user.id, user.role, user.name)

    return AuthResponse(
        token=token,
        user={
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "patient_id": user.patient_id,
            "doctor_id": user.doctor_id,
        },
        message="Registration successful",
    )


@router.post("/auth/login", response_model=AuthResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login and get a JWT token."""
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    token = create_token(user.id, user.role, user.name)

    return AuthResponse(
        token=token,
        user={
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "patient_id": user.patient_id,
            "doctor_id": user.doctor_id,
        },
        message="Login successful",
    )


@router.get("/auth/me")
async def get_me(user: dict = Depends(require_auth)):
    return user


# ── Departments ────────────────────────────────────────

@router.get("/departments", response_model=list[DepartmentResponse])
async def list_departments(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Department).order_by(Department.name))
    return result.scalars().all()


# ── Patients ───────────────────────────────────────────

@router.post("/patients", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(data: PatientCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Patient).where(Patient.phone == data.phone))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Patient with this phone already exists")

    patient = Patient(
        name=data.name, phone=data.phone,
        age=data.age, gender=data.gender,
        blood_group=data.blood_group, allergies=data.allergies,
    )
    db.add(patient)
    await db.commit()
    await db.refresh(patient)
    return patient


@router.get("/patients", response_model=list[PatientResponse])
async def list_patients(search: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    query = select(Patient).where(Patient.is_active == True)
    if search:
        query = query.where(
            (Patient.name.ilike(f"%{search}%")) |
            (Patient.phone.ilike(f"%{search}%"))
        )
    result = await db.execute(query.order_by(desc(Patient.created_at)).limit(50))
    return result.scalars().all()


@router.get("/patients/{patient_id}", response_model=PatientResponse)
async def get_patient(patient_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


# ── Doctors ────────────────────────────────────────────

@router.get("/doctors", response_model=list[DoctorResponse])
async def list_doctors(
    specialty: Optional[str] = None,
    department_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Doctor).where(Doctor.is_active == True)
    if specialty:
        query = query.where(Doctor.specialty == specialty)
    if department_id:
        query = query.where(Doctor.department_id == department_id)
    result = await db.execute(query.order_by(Doctor.name))
    return result.scalars().all()


@router.get("/doctors/{doctor_id}", response_model=DoctorResponse)
async def get_doctor(doctor_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Doctor).where(Doctor.id == doctor_id))
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor


@router.get("/doctors/{doctor_id}/queue", response_model=list[QueueEntryResponse])
async def get_doctor_queue(doctor_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(QueueEntry)
        .where(
            QueueEntry.doctor_id == doctor_id,
            QueueEntry.status.in_(["waiting", "called", "consultation"]),
        )
        .order_by(QueueEntry.position)
    )
    return result.scalars().all()


# ── Queue Management ──────────────────────────────────

@router.post("/queue/checkin", response_model=QueueEntryResponse, status_code=status.HTTP_201_CREATED)
async def check_in_patient(data: QueueCheckinRequest, db: AsyncSession = Depends(get_db)):
    patient_result = await db.execute(select(Patient).where(Patient.id == data.patient_id))
    patient = patient_result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    doctor_result = await db.execute(select(Doctor).where(Doctor.id == data.doctor_id))
    doctor = doctor_result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    if not doctor.is_active:
        raise HTTPException(status_code=400, detail="Doctor is not currently available")

    existing = await db.execute(
        select(QueueEntry).where(
            QueueEntry.patient_id == data.patient_id,
            QueueEntry.doctor_id == data.doctor_id,
            QueueEntry.status.in_(["waiting", "called"]),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Patient already in queue for this doctor")

    max_q = await db.execute(
        select(func.max(QueueEntry.queue_number)).where(
            QueueEntry.doctor_id == data.doctor_id
        )
    )
    queue_number = (max_q.scalar_one() or 0) + 1

    waiting_count = await db.execute(
        select(func.count(QueueEntry.id)).where(
            QueueEntry.doctor_id == data.doctor_id,
            QueueEntry.status == "waiting",
        )
    )
    position = waiting_count.scalar_one() + 1
    estimated_wait = position * doctor.consultation_duration_minutes

    entry = QueueEntry(
        patient_id=data.patient_id,
        doctor_id=data.doctor_id,
        queue_number=queue_number,
        position=position,
        status="waiting",
        priority_score=0,
        checked_in_at=datetime.now(timezone.utc),
        estimated_wait_minutes=estimated_wait,
        symptoms=data.symptoms,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


@router.get("/queue/{queue_id}", response_model=QueueEntryResponse)
async def get_queue_entry(queue_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(QueueEntry).where(QueueEntry.id == queue_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Queue entry not found")
    return entry


@router.patch("/queue/{queue_id}/status")
async def update_queue_status(queue_id: int, new_status: str, db: AsyncSession = Depends(get_db)):
    allowed = {"waiting", "called", "consultation", "completed", "no_show", "cancelled"}
    if new_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {sorted(allowed)}",
        )

    result = await db.execute(select(QueueEntry).where(QueueEntry.id == queue_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Queue entry not found")

    now = datetime.now(timezone.utc)
    entry.status = new_status

    if new_status == "called":
        entry.called_at = now
    elif new_status == "consultation":
        entry.consultation_started_at = now
    elif new_status in ("completed", "no_show", "cancelled"):
        entry.completed_at = now
        if entry.checked_in_at and entry.consultation_started_at:
            wait_seconds = (entry.consultation_started_at - entry.checked_in_at).total_seconds()
            entry.actual_wait_minutes = int(wait_seconds / 60)

        remaining = await db.execute(
            select(QueueEntry)
            .where(
                QueueEntry.doctor_id == entry.doctor_id,
                QueueEntry.status == "waiting",
            )
            .order_by(QueueEntry.position)
        )
        for idx, waiting_entry in enumerate(remaining.scalars().all(), start=1):
            waiting_entry.position = idx
            doctor_result = await db.execute(
                select(Doctor).where(Doctor.id == entry.doctor_id)
            )
            doctor = doctor_result.scalar_one_or_none()
            if doctor:
                waiting_entry.estimated_wait_minutes = idx * doctor.consultation_duration_minutes

    await db.commit()
    return {"status": "updated", "queue_id": queue_id, "new_status": new_status}


@router.post("/queue/call-next")
async def call_next_patient(doctor_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(QueueEntry)
        .where(
            QueueEntry.doctor_id == doctor_id,
            QueueEntry.status == "waiting",
        )
        .order_by(QueueEntry.position)
        .limit(1)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="No patients waiting in queue")

    entry.status = "called"
    entry.called_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "called": True,
        "queue_entry_id": entry.id,
        "patient_id": entry.patient_id,
        "queue_number": entry.queue_number,
    }


# ── Doctor Dashboard ───────────────────────────────────

@router.get("/doctor/{doctor_id}/dashboard")
async def doctor_dashboard(doctor_id: int, db: AsyncSession = Depends(get_db)):
    doctor_result = await db.execute(select(Doctor).where(Doctor.id == doctor_id))
    doctor = doctor_result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    queue_result = await db.execute(
        select(QueueEntry, Patient)
        .join(Patient, QueueEntry.patient_id == Patient.id)
        .where(
            QueueEntry.doctor_id == doctor_id,
            QueueEntry.status.in_(["waiting", "called", "consultation"]),
        )
        .order_by(QueueEntry.position)
    )

    queue_items = []
    for entry, patient in queue_result:
        queue_items.append({
            "queue_entry_id": entry.id,
            "queue_number": entry.queue_number,
            "position": entry.position,
            "status": entry.status,
            "priority_score": entry.priority_score,
            "symptoms": entry.symptoms,
            "urgency_level": entry.urgency_level,
            "estimated_wait_minutes": entry.estimated_wait_minutes,
            "checked_in_at": entry.checked_in_at.isoformat() if entry.checked_in_at else None,
            "patient": {
                "id": patient.id,
                "name": patient.name,
                "phone": patient.phone,
                "age": patient.age,
                "gender": patient.gender,
            },
        })

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    completed_result = await db.execute(
        select(func.count(QueueEntry.id)).where(
            QueueEntry.doctor_id == doctor_id,
            QueueEntry.status == "completed",
            QueueEntry.completed_at >= today_start,
        )
    )
    completed_today = completed_result.scalar_one()

    return {
        "doctor": {
            "id": doctor.id,
            "name": doctor.name,
            "specialty": doctor.specialty,
            "department_id": doctor.department_id,
            "consultation_duration_minutes": doctor.consultation_duration_minutes,
        },
        "queue": queue_items,
        "stats": {
            "total_waiting": len([q for q in queue_items if q["status"] == "waiting"]),
            "currently_consulting": len([q for q in queue_items if q["status"] == "consultation"]),
            "completed_today": completed_today,
            "avg_consultation_minutes": doctor.consultation_duration_minutes,
        },
    }


# ── Agent Activity & Status ────────────────────────────

@router.get("/agents/status")
async def get_agent_status():
    """Get current status of all agents in the system."""
    from services.agent_orchestrator import AGENT_REGISTRY
    agents = []
    for key, info in AGENT_REGISTRY.items():
        agents.append({
            "id": key,
            "name": info["display_name"],
            "emoji": info["emoji"],
            "color": info["color"],
            "role": info["role"],
            "description": info["description"],
            "status": "active",
        })
    return {"agents": agents, "total": len(agents)}


@router.get("/agents/activity")
async def get_agent_activity(
    limit: int = Query(default=20, ge=1, le=100),
    patient_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get recent agent activity log."""
    query = select(AgentActivity).order_by(desc(AgentActivity.created_at))
    if patient_id:
        query = query.where(AgentActivity.patient_id == patient_id)
    query = query.limit(limit)

    result = await db.execute(query)
    activities = result.scalars().all()

    return {
        "activities": [
            {
                "id": a.id,
                "session_id": a.session_id,
                "agent_name": a.agent_name,
                "action_type": a.action_type,
                "thinking_text": a.thinking_text,
                "result_text": a.result_text,
                "handed_off_from": a.handed_off_from,
                "handed_off_to": a.handed_off_to,
                "detected_intent": a.detected_intent,
                "confidence_score": a.confidence_score,
                "duration_ms": a.duration_ms,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in activities
        ]
    }


# ── AI Chat ────────────────────────────────────────────

@router.get("/patients/{patient_id}/chat", response_model=list[ChatMessageResponse])
async def get_patient_chat(patient_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.patient_id == patient_id)
        .order_by(ChatMessage.created_at)
        .limit(100)
    )
    return result.scalars().all()


@router.post("/chat/stream")
async def chat_stream(data: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Multi-agent streaming chat with thinking visualization."""

    from services.gemini_service import get_hospital_agent
    from services.agent_orchestrator import (
        classify_intent, stream_agent_pipeline, log_agent_activity,
        AGENT_REGISTRY,
    )

    # Validate patient
    patient_result = await db.execute(select(Patient).where(Patient.id == data.patient_id))
    patient = patient_result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Save the patient's message
    patient_msg = ChatMessage(
        patient_id=data.patient_id,
        agent_name="patient",
        role="patient",
        content=data.message,
    )
    db.add(patient_msg)
    await db.commit()

    # Get patient's queue context
    queue_result = await db.execute(
        select(QueueEntry)
        .where(
            QueueEntry.patient_id == data.patient_id,
            QueueEntry.status.in_(["waiting", "called", "consultation"]),
        )
        .order_by(desc(QueueEntry.checked_in_at))
        .limit(1)
    )
    active_queue = queue_result.scalar_one_or_none()

    queue_context = ""
    if active_queue:
        queue_context = f"""
Current Queue Status:
- Queue Number: #{active_queue.queue_number}
- Position: #{active_queue.position}
- Status: {active_queue.status}
- Estimated Wait: {active_queue.estimated_wait_minutes or 'unknown'} minutes
- Symptoms: {active_queue.symptoms or 'not provided'}
"""

    context = f"""Patient: {patient.name} (ID: {patient.id})
Phone: {patient.phone}
Age: {patient.age or 'Not provided'}
Gender: {patient.gender or 'Not provided'}
{queue_context}
Patient Message: {data.message}"""

    # Classify intent and determine agent pipeline
    intent = classify_intent(data.message)
    primary_agent_name = intent["agents"][0]
    session_id = str(uuid.uuid4())[:12]

    # Log the intent classification
    await log_agent_activity(
        db, session_id=session_id, agent_name="nova",
        action_type="classification", patient_id=data.patient_id,
        thinking_text=f"Classified intent: {intent['intent']}",
        detected_intent=intent["intent"],
        confidence_score=intent["confidence"],
    )
    await db.commit()

    # ── Emergency Detection (Autonomous) ──────────────
    emergency_result = None
    if intent["intent"] in ("emergency", "symptom_report"):
        from services.emergency_detector import assess_emergency, handle_emergency
        assessment = assess_emergency(data.message)
        if assessment["level"] != "normal":
            emergency_result = await handle_emergency(
                db, data.patient_id,
                1,  # default doctor — triage will route later
                assessment,
            )
            await log_agent_activity(
                db, session_id=session_id, agent_name="emergency_detector",
                action_type="emergency_detected", patient_id=data.patient_id,
                thinking_text=f"EMERGENCY: {assessment['level'].upper()} — severity {assessment['severity_score']}/100",
                detected_intent="emergency",
                confidence_score=assessment["severity_score"] / 100,
            )
            await db.commit()

    agent = get_hospital_agent(primary_agent_name)

    async def stream_response():
        full_response = ""
        try:
            # Stream emergency events first if detected
            if emergency_result and emergency_result.get("auto_escalated"):
                yield f"data: {json.dumps({'type': 'emergency', 'level': emergency_result['level'], 'severity': emergency_result['severity_score'], 'actions': emergency_result['actions_taken']})}\\n\\n"

            for event in stream_agent_pipeline(data.message, context, agent):

                yield f"data: {json.dumps(event)}\n\n"

                if event["type"] == "content":
                    full_response += event["text"]
        except Exception as exc:
            logger.error("AI streaming error: %s", exc)
            full_response = "I apologize, I'm having trouble connecting right now. Please try again or visit the reception desk for immediate help."
            yield f"data: {json.dumps({'type': 'content', 'text': full_response})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'agents_involved': [], 'intent': 'error', 'confidence': 0})}\n\n"

        # Save the agent's response
        if full_response:
            agent_msg = ChatMessage(
                patient_id=data.patient_id,
                agent_name=primary_agent_name,
                role="agent",
                content=full_response,
            )
            db.add(agent_msg)

            # Log the response
            await log_agent_activity(
                db, session_id=session_id, agent_name=primary_agent_name,
                action_type="response", patient_id=data.patient_id,
                result_text=full_response[:500],
            )
            await db.commit()

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/chat", response_model=ChatMessageResponse)
async def chat_simple(data: ChatRequest, db: AsyncSession = Depends(get_db)):
    from services.gemini_service import get_hospital_agent

    patient_result = await db.execute(select(Patient).where(Patient.id == data.patient_id))
    patient = patient_result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    patient_msg = ChatMessage(
        patient_id=data.patient_id,
        agent_name="patient",
        role="patient",
        content=data.message,
    )
    db.add(patient_msg)

    agent = get_hospital_agent(data.agent_name)
    context = f"""Patient: {patient.name} (ID: {patient.id})
Phone: {patient.phone}
Patient Message: {data.message}"""

    response_text = await asyncio.to_thread(agent.generate, context)

    agent_msg = ChatMessage(
        patient_id=data.patient_id,
        agent_name=data.agent_name,
        role="agent",
        content=response_text,
    )
    db.add(agent_msg)
    await db.commit()
    await db.refresh(agent_msg)
    return agent_msg


# ── Emergency Detection (Autonomous) ──────────────────

class EmergencyAssessRequest(BaseModel):
    patient_id: int
    doctor_id: int
    message: str


@router.post("/emergency/assess")
async def assess_emergency_endpoint(data: EmergencyAssessRequest, db: AsyncSession = Depends(get_db)):
    """Emergency Detection Agent — assesses message severity and auto-escalates."""
    from services.emergency_detector import assess_emergency, handle_emergency

    assessment = assess_emergency(data.message)

    if assessment["level"] != "normal":
        result = await handle_emergency(db, data.patient_id, data.doctor_id, assessment)
        return {
            "emergency_detected": True,
            "assessment": assessment,
            "actions": result,
        }

    return {
        "emergency_detected": False,
        "assessment": assessment,
        "actions": {"level": "normal", "actions_taken": []},
    }


# ── Hospital State (Shared) ──────────────────────────

@router.get("/hospital/state")
async def get_hospital_state(db: AsyncSession = Depends(get_db)):
    """Get the shared hospital state all agents read from."""
    from services.hospital_state import build_hospital_state

    state = await build_hospital_state(db)
    return {
        "timestamp": state.timestamp.isoformat(),
        "total_waiting": state.total_waiting,
        "total_in_consultation": state.total_in_consultation,
        "total_completed_today": state.total_completed_today,
        "avg_wait_minutes": state.avg_wait_minutes,
        "busiest_department": state.busiest_department,
        "least_busy_department": state.least_busy_department,
        "emergency_count": state.emergency_count,
        "doctors": [
            {
                "doctor_id": d.doctor_id,
                "doctor_name": d.doctor_name,
                "specialty": d.specialty,
                "waiting_patients": d.waiting_patients,
                "active_patients": d.active_patients,
                "estimated_clear_minutes": d.estimated_clear_time_minutes,
                "is_running_late": d.is_running_late,
                "delay_minutes": d.delay_minutes,
            }
            for d in state.doctors
        ],
        "departments": [
            {
                "department_id": d.department_id,
                "department_name": d.department_name,
                "total_waiting": d.total_waiting,
                "total_doctors": d.total_doctors,
                "avg_wait_minutes": d.avg_wait_minutes,
                "congestion_level": d.congestion_level,
            }
            for d in state.departments
        ],
    }


# ── Queue Predictions & Optimization ──────────────────

@router.get("/analytics/predictions")
async def get_queue_predictions(db: AsyncSession = Depends(get_db)):
    """Get AI-powered queue predictions from Analytics agent."""
    from services.queue_optimizer import predict_queue_state
    predictions = await predict_queue_state(db)
    return {
        "predictions": [
            {
                "doctor_id": p.doctor_id,
                "doctor_name": p.doctor_name,
                "current_waiting": p.current_waiting,
                "current_avg_wait": p.current_avg_wait,
                "predicted_30min_wait": p.predicted_wait_30min,
                "trend": p.congestion_trend,
                "recommendation": p.recommendation,
            }
            for p in predictions
        ]
    }


@router.get("/analytics/optimization")
async def get_optimization_report(db: AsyncSession = Depends(get_db)):
    """Full optimization report — agents collaborating to produce insights."""
    from services.queue_optimizer import get_optimization_report as build_report
    return await build_report(db)


@router.get("/predictions/delays")
async def get_delay_predictions(db: AsyncSession = Depends(get_db)):
    """Delay predictions from Analytics agent."""
    from services.queue_optimizer import predict_delays
    delays = await predict_delays(db)
    return {
        "forecasts": [
            {
                "doctor_id": d.doctor_id,
                "doctor_name": d.doctor_name,
                "delay_minutes": d.predicted_delay_minutes,
                "confidence": d.confidence,
                "reason": d.reason,
                "affected_patients": d.affected_patients,
                "recommendation": d.recommendation,
            }
            for d in delays
        ]
    }


# ── Event Bus ─────────────────────────────────────────

@router.get("/events/recent")
async def get_recent_events(limit: int = Query(default=20, ge=1, le=100)):
    """Get recent events from the agent event bus."""
    from services.event_bus import event_bus
    events = event_bus.get_recent_events(limit=limit)
    return {"events": events, "stats": event_bus.get_stats()}

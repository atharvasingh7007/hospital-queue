"""
Hospital Queue AI — Emergency Detection Agent
Monitors incoming messages for emergency keywords, auto-escalates patients,
skips queue, and alerts doctors — all autonomously without human routing.
"""
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import QueueEntry, Doctor, Patient, NotificationLog
from services.event_bus import event_bus, Events

logger = logging.getLogger("hospital_queue.emergency")


# Severity scoring for symptoms
EMERGENCY_PATTERNS = {
    # Critical (score 90-100) — life-threatening
    r"chest\s*pain": 95,
    r"heart\s*attack": 100,
    r"can'?t\s*breathe": 95,
    r"breathing\s*(difficulty|problem)": 90,
    r"unconscious": 100,
    r"not\s*breathing": 100,
    r"severe\s*bleeding": 95,
    r"stroke": 100,
    r"seizure": 90,
    r"anaphyla": 95,
    r"allergic\s*reaction": 85,

    # Urgent (score 70-89) — needs immediate attention
    r"high\s*fever": 75,
    r"fever.*\d{3}": 80,  # fever with 3-digit temp (e.g., 103)
    r"severe\s*pain": 75,
    r"accident": 80,
    r"fall\s*(down|injury)": 70,
    r"burn": 70,
    r"fracture": 75,
    r"broken\s*bone": 75,
    r"head\s*injury": 85,
    r"poisoning": 90,
    r"overdose": 90,
    r"suicid": 95,

    # Elevated (score 50-69) — should be seen soon
    r"vomiting\s*blood": 80,
    r"blood\s*in\s*(stool|urine)": 65,
    r"severe\s*headache": 60,
    r"dizziness.*faint": 55,
    r"confusion": 60,
    r"numbness": 50,
}


def assess_emergency(message: str) -> dict:
    """Assess a patient message for emergency severity.

    Returns:
        dict with severity_score, level, matched_symptoms, auto_actions
    """
    msg = message.lower().strip()
    matched = []
    max_score = 0

    for pattern, score in EMERGENCY_PATTERNS.items():
        if re.search(pattern, msg):
            matched.append({"pattern": pattern, "score": score})
            max_score = max(max_score, score)

    if max_score >= 90:
        level = "critical"
        auto_actions = ["skip_queue", "alert_doctor", "alert_reception", "prepare_emergency_bay"]
    elif max_score >= 70:
        level = "urgent"
        auto_actions = ["skip_queue", "alert_doctor"]
    elif max_score >= 50:
        level = "elevated"
        auto_actions = ["priority_boost", "alert_doctor"]
    else:
        level = "normal"
        auto_actions = []

    return {
        "severity_score": max_score,
        "level": level,
        "matched_symptoms": matched,
        "auto_actions": auto_actions,
        "assessed_at": datetime.now(timezone.utc).isoformat(),
    }


async def handle_emergency(
    db: AsyncSession,
    patient_id: int,
    doctor_id: int,
    assessment: dict,
) -> dict:
    """Execute emergency protocol autonomously.

    This is a true autonomous agent behavior — no human routing needed.
    The Emergency agent detects the situation and triggers a chain of
    agent-to-agent events.
    """
    actions_taken = []
    level = assessment["level"]

    if level in ("critical", "urgent"):
        # Auto-skip queue: move patient to position 1
        queue_result = await db.execute(
            select(QueueEntry).where(
                QueueEntry.patient_id == patient_id,
                QueueEntry.doctor_id == doctor_id,
                QueueEntry.status.in_(["waiting", "called"]),
            )
        )
        entry = queue_result.scalar_one_or_none()

        if entry:
            old_position = entry.position
            entry.position = 0  # Above everyone
            entry.priority_score = assessment["severity_score"]
            entry.urgency_level = level
            entry.status = "called"
            entry.called_at = datetime.now(timezone.utc)

            # Recalculate positions for other patients
            others = await db.execute(
                select(QueueEntry).where(
                    QueueEntry.doctor_id == doctor_id,
                    QueueEntry.status == "waiting",
                    QueueEntry.id != entry.id,
                ).order_by(QueueEntry.position)
            )
            for idx, other_entry in enumerate(others.scalars().all(), start=1):
                other_entry.position = idx

            actions_taken.append({
                "action": "skip_queue",
                "detail": f"Moved from position #{old_position} to #1 (emergency priority)",
                "agent": "queue_manager",
            })

        # Alert the doctor
        doctor_result = await db.execute(select(Doctor).where(Doctor.id == doctor_id))
        doctor = doctor_result.scalar_one_or_none()

        patient_result = await db.execute(select(Patient).where(Patient.id == patient_id))
        patient = patient_result.scalar_one_or_none()

        if doctor and patient:
            notification = NotificationLog(
                patient_id=patient_id,
                notification_type="emergency_alert",
                channel="in_app",
                message=f"🚨 EMERGENCY: {patient.name} — {level.upper()} — Severity: {assessment['severity_score']}/100. Immediate attention required.",
                status="sent",
                sent_at=datetime.now(timezone.utc),
            )
            db.add(notification)
            actions_taken.append({
                "action": "alert_doctor",
                "detail": f"Alert sent to {doctor.name}: emergency patient {patient.name}",
                "agent": "notifier",
            })

        await db.commit()

        # Publish event for other agents to react
        await event_bus.publish(
            Events.EMERGENCY_DETECTED,
            {
                "patient_id": patient_id,
                "doctor_id": doctor_id,
                "severity_score": assessment["severity_score"],
                "level": level,
                "summary": f"Emergency detected: {level} (score {assessment['severity_score']})",
                "actions_taken": actions_taken,
            },
            source_agent="emergency_detector",
        )

    elif level == "elevated":
        # Boost priority but don't skip queue entirely
        queue_result = await db.execute(
            select(QueueEntry).where(
                QueueEntry.patient_id == patient_id,
                QueueEntry.doctor_id == doctor_id,
                QueueEntry.status == "waiting",
            )
        )
        entry = queue_result.scalar_one_or_none()
        if entry:
            entry.priority_score = max(entry.priority_score, assessment["severity_score"])
            entry.urgency_level = level
            actions_taken.append({
                "action": "priority_boost",
                "detail": f"Priority boosted to {assessment['severity_score']}/100",
                "agent": "queue_manager",
            })
        await db.commit()

    return {
        "level": level,
        "severity_score": assessment["severity_score"],
        "actions_taken": actions_taken,
        "auto_escalated": level in ("critical", "urgent"),
    }

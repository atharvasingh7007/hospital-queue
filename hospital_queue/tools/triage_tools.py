"""
Triage tools for the Hospital Queue AI system.
Handles symptom assessment, severity scoring, and emergency detection.
"""

from datetime import datetime
from .shared_state import get_state, get_next_patient_id, log_event


def assess_symptoms(
    patient_name: str,
    age: int,
    symptoms: str,
    severity_score: int,
    urgency_level: str,
    recommended_department: str,
) -> dict:
    """Record a triage assessment for a patient after you have evaluated their symptoms.

    Call this tool after you have assessed the patient's symptoms and determined
    the severity score, urgency level, and recommended department.

    Args:
        patient_name: Full name of the patient.
        age: Patient's age in years.
        symptoms: Detailed description of symptoms reported by the patient.
        severity_score: Your assessed severity score from 0-100.
            0-30 = LOW, 31-60 = MODERATE, 61-80 = HIGH/URGENT, 81-100 = CRITICAL/EMERGENCY.
        urgency_level: One of LOW, MODERATE, HIGH, CRITICAL.
        recommended_department: The department key to route the patient to.
            Options: general_medicine, cardiology, orthopedics, pediatrics,
            neurology, emergency, dermatology, ent.

    Returns:
        Dictionary with assessment results including patient ID and triage record.
    """
    state = get_state()

    # Create or find patient
    patient_id = None
    for pid, p in state["patients"].items():
        if p["name"].lower() == patient_name.lower():
            patient_id = pid
            break

    if patient_id is None:
        patient_id = str(get_next_patient_id())
        state["patients"][patient_id] = {
            "id": patient_id,
            "name": patient_name,
            "age": age,
            "registered_at": datetime.now().isoformat(),
        }

    # Record triage
    triage_record = {
        "patient_id": patient_id,
        "patient_name": patient_name,
        "age": age,
        "symptoms": symptoms,
        "severity_score": severity_score,
        "urgency_level": urgency_level,
        "recommended_department": recommended_department,
        "assessed_at": datetime.now().isoformat(),
    }
    state["triage_records"].append(triage_record)

    # Update department load
    dept = recommended_department
    if dept in state["departments"]:
        state["departments"][dept]["current_load"] += 1

    # Log analytics event
    log_event("triage_assessment", {
        "patient_id": patient_id,
        "severity_score": severity_score,
        "urgency_level": urgency_level,
        "department": recommended_department,
    })

    dept_name = state["departments"].get(dept, {}).get("name", dept)

    return {
        "status": "success",
        "patient_id": patient_id,
        "patient_name": patient_name,
        "severity_score": severity_score,
        "urgency_level": urgency_level,
        "recommended_department": dept_name,
        "message": f"Triage assessment recorded. Patient {patient_name} (ID: {patient_id}) "
                   f"assessed with severity {severity_score}/100 ({urgency_level}). "
                   f"Recommended department: {dept_name}.",
    }


def get_emergency_protocol(severity_score: int) -> dict:
    """Get the emergency protocol based on severity score.

    Call this when a patient's severity score is above 70 to get
    the appropriate emergency response protocol.

    Args:
        severity_score: The triage severity score (0-100).

    Returns:
        Dictionary with emergency protocol details and required actions.
    """
    if severity_score >= 85:
        return {
            "protocol": "CODE RED — IMMEDIATE EMERGENCY",
            "priority": "P1 — CRITICAL",
            "actions": [
                "IMMEDIATELY route patient to Emergency department",
                "Alert nearest available emergency physician",
                "Bypass all queue — patient goes FIRST",
                "Prepare emergency bay and crash cart",
                "Notify on-call specialist if needed",
            ],
            "estimated_response_time": "Under 2 minutes",
            "message": "⚠️ CRITICAL EMERGENCY: Patient requires immediate medical attention. "
                       "All queue positions are bypassed. Emergency team alerted.",
        }
    elif severity_score >= 70:
        return {
            "protocol": "CODE ORANGE — URGENT",
            "priority": "P2 — URGENT",
            "actions": [
                "Fast-track patient in department queue",
                "Alert assigned doctor immediately",
                "Place patient in priority queue position",
                "Monitor vitals while waiting",
            ],
            "estimated_response_time": "Under 10 minutes",
            "message": "🔶 URGENT: Patient has been fast-tracked. Doctor will see them shortly.",
        }
    elif severity_score >= 50:
        return {
            "protocol": "STANDARD PRIORITY",
            "priority": "P3 — MODERATE",
            "actions": [
                "Add to department queue with moderate priority",
                "Standard check-in process",
            ],
            "estimated_response_time": "15-30 minutes",
            "message": "Patient added to queue with moderate priority.",
        }
    else:
        return {
            "protocol": "ROUTINE",
            "priority": "P4 — LOW",
            "actions": [
                "Standard queue placement",
                "Routine consultation",
            ],
            "estimated_response_time": "30-60 minutes",
            "message": "Patient added to standard queue for routine consultation.",
        }

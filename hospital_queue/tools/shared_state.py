"""
Shared in-memory hospital state.
Acts as the primary data store for the agent tools.
When AlloyDB is available (Cloud Run), data is also persisted to the database.
"""

import os
import threading
from datetime import datetime, timedelta
from typing import Any

_lock = threading.Lock()

# ─── Hospital State ───────────────────────────────────────────────────────────

HOSPITAL_STATE: dict[str, Any] = {
    "departments": {
        "general_medicine": {
            "name": "General Medicine",
            "capacity": 20,
            "current_load": 3,
            "avg_consultation_mins": 15,
        },
        "cardiology": {
            "name": "Cardiology",
            "capacity": 10,
            "current_load": 2,
            "avg_consultation_mins": 25,
        },
        "orthopedics": {
            "name": "Orthopedics",
            "capacity": 10,
            "current_load": 1,
            "avg_consultation_mins": 20,
        },
        "pediatrics": {
            "name": "Pediatrics",
            "capacity": 15,
            "current_load": 2,
            "avg_consultation_mins": 15,
        },
        "neurology": {
            "name": "Neurology",
            "capacity": 8,
            "current_load": 1,
            "avg_consultation_mins": 30,
        },
        "emergency": {
            "name": "Emergency",
            "capacity": 15,
            "current_load": 4,
            "avg_consultation_mins": 10,
        },
        "dermatology": {
            "name": "Dermatology",
            "capacity": 8,
            "current_load": 1,
            "avg_consultation_mins": 15,
        },
        "ent": {
            "name": "ENT (Ear, Nose, Throat)",
            "capacity": 8,
            "current_load": 0,
            "avg_consultation_mins": 15,
        },
    },
    "doctors": [
        {"id": 1, "name": "Dr. Anika Sharma", "department": "general_medicine", "specialization": "General Physician", "available": True, "patients_seen_today": 5},
        {"id": 2, "name": "Dr. Rajesh Patel", "department": "cardiology", "specialization": "Cardiologist", "available": True, "patients_seen_today": 3},
        {"id": 3, "name": "Dr. Priya Gupta", "department": "orthopedics", "specialization": "Orthopedic Surgeon", "available": True, "patients_seen_today": 2},
        {"id": 4, "name": "Dr. Vikram Singh", "department": "pediatrics", "specialization": "Pediatrician", "available": True, "patients_seen_today": 4},
        {"id": 5, "name": "Dr. Meera Nair", "department": "neurology", "specialization": "Neurologist", "available": True, "patients_seen_today": 1},
        {"id": 6, "name": "Dr. Arjun Reddy", "department": "emergency", "specialization": "Emergency Medicine", "available": True, "patients_seen_today": 6},
        {"id": 7, "name": "Dr. Sunita Joshi", "department": "general_medicine", "specialization": "Internal Medicine", "available": True, "patients_seen_today": 3},
        {"id": 8, "name": "Dr. Karthik Menon", "department": "dermatology", "specialization": "Dermatologist", "available": True, "patients_seen_today": 2},
        {"id": 9, "name": "Dr. Fatima Khan", "department": "ent", "specialization": "ENT Specialist", "available": True, "patients_seen_today": 1},
        {"id": 10, "name": "Dr. Amit Desai", "department": "cardiology", "specialization": "Interventional Cardiologist", "available": False, "patients_seen_today": 4},
    ],
    "patients": {},
    "queue": [],
    "appointments": [],
    "notifications": [],
    "triage_records": [],
    "analytics_events": [],
    "next_queue_number": 101,
    "next_patient_id": 1001,
}


def get_state() -> dict[str, Any]:
    """Get the current hospital state."""
    return HOSPITAL_STATE


def get_next_queue_number() -> int:
    """Get and increment the next queue number."""
    with _lock:
        num = HOSPITAL_STATE["next_queue_number"]
        HOSPITAL_STATE["next_queue_number"] += 1
        return num


def get_next_patient_id() -> int:
    """Get and increment the next patient ID."""
    with _lock:
        pid = HOSPITAL_STATE["next_patient_id"]
        HOSPITAL_STATE["next_patient_id"] += 1
        return pid


def log_event(event_type: str, data: dict) -> None:
    """Log an analytics event."""
    HOSPITAL_STATE["analytics_events"].append({
        "event_type": event_type,
        "data": data,
        "timestamp": datetime.now().isoformat(),
    })

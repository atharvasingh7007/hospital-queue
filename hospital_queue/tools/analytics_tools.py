"""
Analytics tools for the Hospital Queue AI system.
Handles hospital-wide statistics, congestion analysis, wait time predictions,
and BigQuery data operations.
"""

import os
from datetime import datetime
from .shared_state import get_state, log_event


def get_hospital_overview() -> dict:
    """Get a comprehensive overview of the hospital's current status.

    Returns all key metrics including total patients, queue status,
    department loads, and doctor availability.

    Returns:
        Dictionary with hospital-wide statistics and metrics.
    """
    state = get_state()

    total_waiting = sum(
        1 for e in state["queue"] if e["status"] == "WAITING"
    )
    total_in_consultation = sum(
        1 for e in state["queue"] if e["status"] == "IN_CONSULTATION"
    )
    total_completed = sum(
        1 for e in state["queue"] if e["status"] == "COMPLETED"
    )
    total_patients = len(state["patients"])
    total_doctors_available = sum(1 for d in state["doctors"] if d["available"])
    total_doctors = len(state["doctors"])
    total_appointments = len(state["appointments"])

    dept_summary = {}
    for key, dept in state["departments"].items():
        load_pct = (dept["current_load"] / dept["capacity"]) * 100
        dept_summary[key] = {
            "name": dept["name"],
            "load": f"{dept['current_load']}/{dept['capacity']}",
            "load_percentage": round(load_pct, 1),
            "congestion": _get_congestion_level(load_pct),
        }

    return {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "total_registered_patients": total_patients,
        "patients_waiting": total_waiting,
        "patients_in_consultation": total_in_consultation,
        "patients_completed_today": total_completed,
        "total_doctors": total_doctors,
        "doctors_available": total_doctors_available,
        "total_appointments_today": total_appointments,
        "department_summary": dept_summary,
        "message": f"🏥 Hospital Overview: {total_waiting} waiting, "
                   f"{total_in_consultation} in consultation, "
                   f"{total_completed} completed today. "
                   f"{total_doctors_available}/{total_doctors} doctors available.",
    }


def get_department_congestion() -> dict:
    """Analyze congestion levels across all departments.

    Returns detailed congestion data including load percentages,
    risk levels, and recommendations for load balancing.

    Returns:
        Dictionary with per-department congestion analysis.
    """
    state = get_state()

    congestion_data = []
    for key, dept in state["departments"].items():
        load_pct = (dept["current_load"] / dept["capacity"]) * 100
        waiting_count = sum(
            1 for e in state["queue"]
            if e["department"] == key and e["status"] == "WAITING"
        )
        available_docs = sum(
            1 for d in state["doctors"]
            if d["department"] == key and d["available"]
        )

        congestion_data.append({
            "department": dept["name"],
            "department_key": key,
            "current_load": dept["current_load"],
            "capacity": dept["capacity"],
            "load_percentage": round(load_pct, 1),
            "congestion_level": _get_congestion_level(load_pct),
            "patients_waiting": waiting_count,
            "doctors_available": available_docs,
            "estimated_clear_time_mins": waiting_count * dept["avg_consultation_mins"],
        })

    # Sort by load percentage descending
    congestion_data.sort(key=lambda x: x["load_percentage"], reverse=True)

    critical_depts = [d for d in congestion_data if d["congestion_level"] == "CRITICAL"]
    high_depts = [d for d in congestion_data if d["congestion_level"] == "HIGH"]

    recommendations = []
    if critical_depts:
        recommendations.append(
            f"⚠️ CRITICAL congestion in: {', '.join(d['department'] for d in critical_depts)}. "
            f"Consider redirecting patients to less busy departments."
        )
    if high_depts:
        recommendations.append(
            f"🔶 HIGH load in: {', '.join(d['department'] for d in high_depts)}. "
            f"Monitor closely and prepare for overflow."
        )

    low_depts = [d for d in congestion_data if d["congestion_level"] == "LOW"]
    if low_depts and (critical_depts or high_depts):
        recommendations.append(
            f"✅ Consider routing overflow to: {', '.join(d['department'] for d in low_depts[:3])}."
        )

    return {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "departments": congestion_data,
        "critical_count": len(critical_depts),
        "high_count": len(high_depts),
        "recommendations": recommendations,
        "message": f"📊 Congestion Analysis: {len(critical_depts)} critical, "
                   f"{len(high_depts)} high, across {len(congestion_data)} departments.",
    }


def predict_wait_times(department: str) -> dict:
    """Predict wait times for a specific department based on current load.

    Args:
        department: Department key to predict wait times for.
            Options: general_medicine, cardiology, orthopedics, pediatrics,
            neurology, emergency, dermatology, ent.

    Returns:
        Dictionary with predicted wait times and confidence levels.
    """
    state = get_state()

    dept_info = state["departments"].get(department)
    if not dept_info:
        for key, info in state["departments"].items():
            if department.lower() in key.lower() or department.lower() in info["name"].lower():
                department = key
                dept_info = info
                break

    if not dept_info:
        return {
            "status": "error",
            "message": f"Department '{department}' not found.",
        }

    waiting = sum(
        1 for e in state["queue"]
        if e["department"] == department and e["status"] == "WAITING"
    )
    available_docs = sum(
        1 for d in state["doctors"]
        if d["department"] == department and d["available"]
    )

    avg_mins = dept_info["avg_consultation_mins"]

    if available_docs > 0:
        parallel_factor = max(1, available_docs)
        base_wait = (waiting * avg_mins) / parallel_factor
    else:
        base_wait = waiting * avg_mins * 1.5  # Longer if no docs available

    # Add variability
    min_wait = max(0, base_wait * 0.8)
    max_wait = base_wait * 1.3

    load_pct = (dept_info["current_load"] / dept_info["capacity"]) * 100

    return {
        "status": "success",
        "department": dept_info["name"],
        "patients_waiting": waiting,
        "doctors_available": available_docs,
        "prediction": {
            "estimated_wait_minutes": round(base_wait),
            "min_wait_minutes": round(min_wait),
            "max_wait_minutes": round(max_wait),
            "confidence": "HIGH" if waiting < 5 else ("MEDIUM" if waiting < 10 else "LOW"),
        },
        "current_load_percentage": round(load_pct, 1),
        "message": f"⏱️ Predicted wait for {dept_info['name']}: "
                   f"~{round(base_wait)} minutes (range: {round(min_wait)}-{round(max_wait)} min). "
                   f"{waiting} patients waiting, {available_docs} doctor(s) available.",
    }


def log_to_bigquery(event_type: str, event_data: str) -> dict:
    """Log an analytics event for BigQuery ingestion.

    Records hospital events for later analysis in BigQuery.

    Args:
        event_type: Type of event (e.g., patient_visit, queue_update, triage, appointment).
        event_data: JSON string or description of the event data.

    Returns:
        Dictionary confirming the event was logged.
    """
    log_event(event_type, {"data": event_data})

    # If BigQuery is configured, also write there
    bq_project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if bq_project:
        try:
            from ..services.bigquery_service import insert_event
            insert_event(event_type, event_data)
        except Exception as e:
            pass  # Non-critical, don't fail the tool

    return {
        "status": "success",
        "event_type": event_type,
        "message": f"📊 Analytics event '{event_type}' logged successfully.",
    }


def _get_congestion_level(load_pct: float) -> str:
    """Get congestion level string from load percentage."""
    if load_pct >= 90:
        return "CRITICAL"
    elif load_pct >= 70:
        return "HIGH"
    elif load_pct >= 40:
        return "MODERATE"
    else:
        return "LOW"

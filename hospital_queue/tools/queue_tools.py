"""
Queue management tools for the Hospital Queue AI system.
Handles patient check-in, queue position tracking, and department queue status.
"""

from datetime import datetime
from .shared_state import get_state, get_next_queue_number, log_event


def check_in_patient(
    patient_name: str,
    department: str,
    priority: str = "NORMAL",
) -> dict:
    """Check in a patient to the hospital queue for a specific department.

    Args:
        patient_name: Full name of the patient.
        department: Department key to queue for.
            Options: general_medicine, cardiology, orthopedics, pediatrics,
            neurology, emergency, dermatology, ent.
        priority: Queue priority level. One of: NORMAL, HIGH, URGENT, EMERGENCY.
            EMERGENCY patients go to front of queue.

    Returns:
        Dictionary with queue number, position, and estimated wait time.
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
            "message": f"Department '{department}' not found. Available: {', '.join(state['departments'].keys())}",
        }

    # Check if patient already in queue
    for entry in state["queue"]:
        if entry["patient_name"].lower() == patient_name.lower() and entry["status"] == "WAITING":
            return {
                "status": "already_queued",
                "queue_number": entry["queue_number"],
                "position": _get_position(entry["queue_number"], state),
                "message": f"{patient_name} is already in the queue (#{entry['queue_number']}).",
            }

    # Find patient ID
    patient_id = None
    for pid, p in state["patients"].items():
        if p["name"].lower() == patient_name.lower():
            patient_id = pid
            break

    if patient_id is None:
        from .shared_state import get_next_patient_id
        patient_id = str(get_next_patient_id())
        state["patients"][patient_id] = {
            "id": patient_id,
            "name": patient_name,
            "registered_at": datetime.now().isoformat(),
        }

    queue_number = get_next_queue_number()

    queue_entry = {
        "queue_number": queue_number,
        "patient_id": patient_id,
        "patient_name": patient_name,
        "department": department,
        "department_name": dept_info["name"],
        "priority": priority,
        "status": "WAITING",
        "checked_in_at": datetime.now().isoformat(),
    }

    # Insert based on priority
    if priority == "EMERGENCY":
        # Find first non-emergency entry and insert before it
        insert_idx = 0
        for i, entry in enumerate(state["queue"]):
            if entry["status"] == "WAITING" and entry["priority"] != "EMERGENCY":
                insert_idx = i
                break
            insert_idx = i + 1
        state["queue"].insert(insert_idx, queue_entry)
    elif priority in ("URGENT", "HIGH"):
        # Insert after emergencies but before normal
        insert_idx = len(state["queue"])
        for i, entry in enumerate(state["queue"]):
            if entry["status"] == "WAITING" and entry["priority"] == "NORMAL":
                insert_idx = i
                break
        state["queue"].insert(insert_idx, queue_entry)
    else:
        state["queue"].append(queue_entry)

    position = _get_position(queue_number, state)
    avg_mins = dept_info.get("avg_consultation_mins", 15)
    estimated_wait = position * avg_mins

    log_event("patient_checked_in", {
        "patient_id": patient_id,
        "queue_number": queue_number,
        "department": department,
        "priority": priority,
    })

    return {
        "status": "success",
        "queue_number": queue_number,
        "patient_name": patient_name,
        "department": dept_info["name"],
        "priority": priority,
        "position": position,
        "estimated_wait_minutes": estimated_wait,
        "message": f"✅ {patient_name} checked in! Queue number: #{queue_number}. "
                   f"Department: {dept_info['name']}. Position: {position}. "
                   f"Estimated wait: ~{estimated_wait} minutes. Priority: {priority}.",
    }


def get_queue_position(patient_name: str) -> dict:
    """Get a patient's current position in the queue and estimated wait time.

    Args:
        patient_name: Full name of the patient to look up.

    Returns:
        Dictionary with queue position, number, and estimated wait time.
    """
    state = get_state()

    for entry in state["queue"]:
        if entry["patient_name"].lower() == patient_name.lower() and entry["status"] == "WAITING":
            position = _get_position(entry["queue_number"], state)
            dept = state["departments"].get(entry["department"], {})
            avg_mins = dept.get("avg_consultation_mins", 15)
            estimated_wait = position * avg_mins

            return {
                "status": "success",
                "queue_number": entry["queue_number"],
                "patient_name": patient_name,
                "department": entry["department_name"],
                "position": position,
                "priority": entry["priority"],
                "estimated_wait_minutes": estimated_wait,
                "checked_in_at": entry["checked_in_at"],
                "message": f"📋 {patient_name} — Queue #{entry['queue_number']}. "
                           f"Position: {position} in {entry['department_name']}. "
                           f"Estimated wait: ~{estimated_wait} minutes.",
            }

    # Check completed
    for entry in state["queue"]:
        if entry["patient_name"].lower() == patient_name.lower():
            return {
                "status": "completed",
                "queue_number": entry["queue_number"],
                "message": f"{patient_name}'s queue entry (#{entry['queue_number']}) "
                           f"has status: {entry['status']}.",
            }

    return {
        "status": "not_found",
        "message": f"No active queue entry found for '{patient_name}'. "
                   f"They may need to check in first.",
    }


def get_department_queue_status(department: str) -> dict:
    """Get the current queue status for a specific department.

    Args:
        department: Department key to check queue status for.
            Options: general_medicine, cardiology, orthopedics, pediatrics,
            neurology, emergency, dermatology, ent.

    Returns:
        Dictionary with department queue details including waiting count and load.
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

    waiting = [
        e for e in state["queue"]
        if e["department"] == department and e["status"] == "WAITING"
    ]

    load_pct = (dept_info["current_load"] / dept_info["capacity"]) * 100
    if load_pct >= 90:
        congestion = "CRITICAL"
    elif load_pct >= 70:
        congestion = "HIGH"
    elif load_pct >= 40:
        congestion = "MODERATE"
    else:
        congestion = "LOW"

    available_docs = [
        d["name"] for d in state["doctors"]
        if d["department"] == department and d["available"]
    ]

    return {
        "status": "success",
        "department": dept_info["name"],
        "patients_waiting": len(waiting),
        "current_load": dept_info["current_load"],
        "capacity": dept_info["capacity"],
        "load_percentage": round(load_pct, 1),
        "congestion_level": congestion,
        "available_doctors": available_docs,
        "avg_consultation_mins": dept_info["avg_consultation_mins"],
        "estimated_wait_new_patient": len(waiting) * dept_info["avg_consultation_mins"],
        "message": f"📊 {dept_info['name']}: {len(waiting)} patients waiting. "
                   f"Load: {dept_info['current_load']}/{dept_info['capacity']} ({congestion}). "
                   f"Available doctors: {', '.join(available_docs) if available_docs else 'None'}.",
    }


def _get_position(queue_number: int, state: dict) -> int:
    """Calculate queue position for a given queue number."""
    waiting = [e for e in state["queue"] if e["status"] == "WAITING"]
    for i, entry in enumerate(waiting):
        if entry["queue_number"] == queue_number:
            return i + 1
    return 0

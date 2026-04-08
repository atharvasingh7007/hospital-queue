"""
Scheduler tools for the Hospital Queue AI system.
Handles doctor availability checking and appointment booking.
"""

from datetime import datetime, timedelta
from .shared_state import get_state, log_event


def get_available_doctors(department: str) -> dict:
    """Get list of currently available doctors in a specific department.

    Args:
        department: Department key to search for available doctors.
            Options: general_medicine, cardiology, orthopedics, pediatrics,
            neurology, emergency, dermatology, ent.

    Returns:
        Dictionary with list of available doctors and department info.
    """
    state = get_state()

    dept_info = state["departments"].get(department)
    if not dept_info:
        # Try fuzzy match
        for key, info in state["departments"].items():
            if department.lower() in key.lower() or department.lower() in info["name"].lower():
                department = key
                dept_info = info
                break

    if not dept_info:
        return {
            "status": "error",
            "message": f"Department '{department}' not found. Available departments: "
                       f"{', '.join(state['departments'].keys())}",
            "available_departments": list(state["departments"].keys()),
        }

    available_docs = [
        {
            "id": d["id"],
            "name": d["name"],
            "specialization": d["specialization"],
            "patients_seen_today": d["patients_seen_today"],
        }
        for d in state["doctors"]
        if d["department"] == department and d["available"]
    ]

    return {
        "status": "success",
        "department": dept_info["name"],
        "department_key": department,
        "available_doctors": available_docs,
        "total_available": len(available_docs),
        "department_load": f"{dept_info['current_load']}/{dept_info['capacity']}",
        "message": f"Found {len(available_docs)} available doctor(s) in {dept_info['name']}."
                   if available_docs else
                   f"No doctors currently available in {dept_info['name']}. Please try again later.",
    }


def book_appointment(
    patient_name: str,
    doctor_name: str,
    department: str,
    reason: str,
) -> dict:
    """Book an appointment for a patient with a specific doctor.

    Args:
        patient_name: Full name of the patient.
        doctor_name: Name of the doctor to book with.
        department: Department key where the doctor practices.
        reason: Reason for the appointment / chief complaint.

    Returns:
        Dictionary with appointment confirmation details.
    """
    state = get_state()

    # Find doctor
    doctor = None
    for d in state["doctors"]:
        if doctor_name.lower() in d["name"].lower():
            doctor = d
            break

    if not doctor:
        return {
            "status": "error",
            "message": f"Doctor '{doctor_name}' not found. Please check the available doctors list.",
        }

    if not doctor["available"]:
        return {
            "status": "error",
            "message": f"{doctor['name']} is currently unavailable. Please choose another doctor.",
        }

    # Find or create patient
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

    # Create appointment
    appointment_id = f"APT-{len(state['appointments']) + 1:04d}"
    now = datetime.now()
    dept_info = state["departments"].get(department, {})
    avg_wait = dept_info.get("avg_consultation_mins", 15) * dept_info.get("current_load", 0)
    estimated_time = now + timedelta(minutes=max(avg_wait, 10))

    appointment = {
        "appointment_id": appointment_id,
        "patient_id": patient_id,
        "patient_name": patient_name,
        "doctor_id": doctor["id"],
        "doctor_name": doctor["name"],
        "department": dept_info.get("name", department),
        "reason": reason,
        "status": "SCHEDULED",
        "booked_at": now.isoformat(),
        "estimated_time": estimated_time.strftime("%I:%M %p"),
    }
    state["appointments"].append(appointment)

    # Update doctor stats
    doctor["patients_seen_today"] += 1

    log_event("appointment_booked", {
        "appointment_id": appointment_id,
        "patient_id": patient_id,
        "doctor_id": doctor["id"],
        "department": department,
    })

    return {
        "status": "success",
        "appointment_id": appointment_id,
        "patient_name": patient_name,
        "doctor_name": doctor["name"],
        "department": dept_info.get("name", department),
        "estimated_time": estimated_time.strftime("%I:%M %p"),
        "message": f"✅ Appointment booked! {patient_name} with {doctor['name']} "
                   f"({dept_info.get('name', department)}). "
                   f"Appointment ID: {appointment_id}. "
                   f"Estimated time: {estimated_time.strftime('%I:%M %p')}.",
    }


def get_appointment_details(patient_name: str) -> dict:
    """Get appointment details for a patient.

    Args:
        patient_name: Full name of the patient to look up.

    Returns:
        Dictionary with appointment details or not-found message.
    """
    state = get_state()

    patient_appointments = [
        apt for apt in state["appointments"]
        if apt["patient_name"].lower() == patient_name.lower()
    ]

    if not patient_appointments:
        return {
            "status": "not_found",
            "message": f"No appointments found for patient '{patient_name}'.",
        }

    latest = patient_appointments[-1]
    return {
        "status": "success",
        "appointments": patient_appointments,
        "latest_appointment": latest,
        "total_appointments": len(patient_appointments),
        "message": f"Found {len(patient_appointments)} appointment(s) for {patient_name}. "
                   f"Latest: {latest['appointment_id']} with {latest['doctor_name']} "
                   f"({latest['status']}).",
    }

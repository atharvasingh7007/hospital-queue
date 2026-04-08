"""
Notifier tools for the Hospital Queue AI system.
Handles sending notifications to doctors and patients.
"""

from datetime import datetime
from .shared_state import get_state, log_event


def send_notification(
    recipient_name: str,
    message: str,
    notification_type: str = "INFO",
    urgency: str = "NORMAL",
) -> dict:
    """Send a notification to a doctor or patient.

    Args:
        recipient_name: Name of the person to notify (doctor or patient).
        message: The notification message content.
        notification_type: Type of notification. One of:
            INFO, ALERT, EMERGENCY, REMINDER, QUEUE_UPDATE.
        urgency: Urgency level. One of: LOW, NORMAL, HIGH, CRITICAL.

    Returns:
        Dictionary confirming notification was sent.
    """
    state = get_state()

    notification = {
        "id": f"NOTIF-{len(state['notifications']) + 1:04d}",
        "recipient": recipient_name,
        "message": message,
        "type": notification_type,
        "urgency": urgency,
        "status": "SENT",
        "sent_at": datetime.now().isoformat(),
        "read": False,
    }
    state["notifications"].append(notification)

    log_event("notification_sent", {
        "notification_id": notification["id"],
        "recipient": recipient_name,
        "type": notification_type,
        "urgency": urgency,
    })

    emoji = {"INFO": "ℹ️", "ALERT": "🔔", "EMERGENCY": "🚨", "REMINDER": "⏰", "QUEUE_UPDATE": "📋"}.get(notification_type, "📩")

    return {
        "status": "success",
        "notification_id": notification["id"],
        "message": f"{emoji} Notification sent to {recipient_name}: {message}",
    }


def send_emergency_alert(
    patient_name: str,
    severity_score: int,
    symptoms: str,
    department: str = "emergency",
) -> dict:
    """Send an emergency alert to ALL available doctors in a department.

    This should be called when a patient has a critical severity score (>80).

    Args:
        patient_name: Name of the patient in emergency.
        severity_score: The triage severity score (should be > 80).
        symptoms: Brief description of critical symptoms.
        department: Department to alert. Defaults to emergency.

    Returns:
        Dictionary with alert details and list of notified doctors.
    """
    state = get_state()

    # Find available doctors in department (and emergency)
    target_depts = {department, "emergency"}
    doctors_to_alert = [
        d for d in state["doctors"]
        if d["department"] in target_depts and d["available"]
    ]

    alert_message = (
        f"🚨 EMERGENCY ALERT — Patient: {patient_name} | "
        f"Severity: {severity_score}/100 | Symptoms: {symptoms} | "
        f"IMMEDIATE ATTENTION REQUIRED"
    )

    notified = []
    for doc in doctors_to_alert:
        notification = {
            "id": f"EMRG-{len(state['notifications']) + 1:04d}",
            "recipient": doc["name"],
            "message": alert_message,
            "type": "EMERGENCY",
            "urgency": "CRITICAL",
            "status": "SENT",
            "sent_at": datetime.now().isoformat(),
            "read": False,
        }
        state["notifications"].append(notification)
        notified.append(doc["name"])

    log_event("emergency_alert", {
        "patient_name": patient_name,
        "severity_score": severity_score,
        "doctors_alerted": notified,
        "department": department,
    })

    return {
        "status": "success",
        "alert_level": "CRITICAL" if severity_score >= 85 else "URGENT",
        "patient_name": patient_name,
        "severity_score": severity_score,
        "doctors_notified": notified,
        "total_notified": len(notified),
        "message": f"🚨 EMERGENCY ALERT sent to {len(notified)} doctor(s): "
                   f"{', '.join(notified)}. Patient {patient_name} requires "
                   f"immediate attention (severity: {severity_score}/100).",
    }


def get_notifications(recipient_name: str) -> dict:
    """Get all notifications for a specific person.

    Args:
        recipient_name: Name of the person to get notifications for.

    Returns:
        Dictionary with list of notifications for the recipient.
    """
    state = get_state()

    notifications = [
        n for n in state["notifications"]
        if recipient_name.lower() in n["recipient"].lower()
    ]

    unread = [n for n in notifications if not n["read"]]

    return {
        "status": "success",
        "recipient": recipient_name,
        "total_notifications": len(notifications),
        "unread_count": len(unread),
        "notifications": notifications[-10:],  # Last 10
        "message": f"📬 {recipient_name} has {len(unread)} unread notification(s) "
                   f"out of {len(notifications)} total.",
    }

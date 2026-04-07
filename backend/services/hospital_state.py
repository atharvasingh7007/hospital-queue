"""
Hospital Queue AI — Shared Hospital State
Single source of truth for all agents. Computed from database in real-time.
Every agent reads from the same state to make coordinated decisions.
"""
import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models import Doctor, QueueEntry, Department, Patient

logger = logging.getLogger("hospital_queue.hospital_state")


@dataclass
class DoctorLoad:
    doctor_id: int
    doctor_name: str
    specialty: str
    department_id: int
    active_patients: int
    waiting_patients: int
    avg_consultation_minutes: int
    estimated_clear_time_minutes: int
    is_running_late: bool = False
    delay_minutes: int = 0


@dataclass
class DepartmentLoad:
    department_id: int
    department_name: str
    total_waiting: int
    total_doctors: int
    avg_wait_minutes: float
    congestion_level: str  # low, moderate, high, critical


@dataclass
class HospitalSnapshot:
    """Complete picture of the hospital at this moment."""
    timestamp: datetime
    total_waiting: int
    total_in_consultation: int
    total_completed_today: int
    doctors: list[DoctorLoad]
    departments: list[DepartmentLoad]
    avg_wait_minutes: float
    busiest_department: Optional[str]
    least_busy_department: Optional[str]
    emergency_count: int


async def build_hospital_state(db: AsyncSession) -> HospitalSnapshot:
    """Build a complete snapshot of the hospital's current state.
    Every agent can call this to make decisions based on the same data."""

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Fetch all active queue entries
    queue_result = await db.execute(
        select(QueueEntry, Doctor)
        .join(Doctor, QueueEntry.doctor_id == Doctor.id)
        .where(QueueEntry.status.in_(["waiting", "called", "consultation"]))
        .order_by(QueueEntry.position)
    )
    queue_entries = queue_result.all()

    # Fetch completed today
    completed_result = await db.execute(
        select(func.count(QueueEntry.id)).where(
            QueueEntry.status == "completed",
            QueueEntry.completed_at >= today_start,
        )
    )
    completed_today = completed_result.scalar_one()

    # Fetch all departments
    dept_result = await db.execute(select(Department))
    departments = {d.id: d for d in dept_result.scalars().all()}

    # Fetch all active doctors
    doctor_result = await db.execute(select(Doctor).where(Doctor.is_active == True))
    all_doctors = doctor_result.scalars().all()

    # Build doctor loads
    doctor_loads: dict[int, DoctorLoad] = {}
    for doc in all_doctors:
        doctor_loads[doc.id] = DoctorLoad(
            doctor_id=doc.id,
            doctor_name=doc.name,
            specialty=doc.specialty,
            department_id=doc.department_id,
            active_patients=0,
            waiting_patients=0,
            avg_consultation_minutes=doc.consultation_duration_minutes,
            estimated_clear_time_minutes=0,
        )

    # Count patients per doctor
    for entry, doctor in queue_entries:
        if doctor.id in doctor_loads:
            load = doctor_loads[doctor.id]
            if entry.status == "waiting":
                load.waiting_patients += 1
            elif entry.status in ("called", "consultation"):
                load.active_patients += 1

    # Calculate estimated clear times and detect delays
    for doc_id, load in doctor_loads.items():
        load.estimated_clear_time_minutes = (
            load.waiting_patients * load.avg_consultation_minutes
        )

        # Check if doctor is running late
        if load.active_patients > 0 and load.waiting_patients > 2:
            load.is_running_late = True
            load.delay_minutes = max(0, (load.waiting_patients - 2) * 5)

    # Build department loads
    dept_loads: dict[int, DepartmentLoad] = {}
    for dept_id, dept in departments.items():
        dept_doctors = [d for d in doctor_loads.values() if d.department_id == dept_id]
        total_waiting = sum(d.waiting_patients for d in dept_doctors)
        total_docs = len(dept_doctors)
        avg_wait = (
            sum(d.estimated_clear_time_minutes for d in dept_doctors) / max(total_docs, 1)
        )

        if total_waiting == 0:
            congestion = "low"
        elif total_waiting <= 3:
            congestion = "moderate"
        elif total_waiting <= 6:
            congestion = "high"
        else:
            congestion = "critical"

        dept_loads[dept_id] = DepartmentLoad(
            department_id=dept_id,
            department_name=dept.name,
            total_waiting=total_waiting,
            total_doctors=total_docs,
            avg_wait_minutes=round(avg_wait, 1),
            congestion_level=congestion,
        )

    total_waiting = sum(d.waiting_patients for d in doctor_loads.values())
    total_consulting = sum(d.active_patients for d in doctor_loads.values())
    avg_wait = (
        sum(d.estimated_clear_time_minutes for d in doctor_loads.values())
        / max(len(doctor_loads), 1)
    )

    sorted_depts = sorted(dept_loads.values(), key=lambda d: d.total_waiting)
    busiest = sorted_depts[-1].department_name if sorted_depts else None
    least_busy = sorted_depts[0].department_name if sorted_depts else None

    emergency_entries = [
        e for e, d in queue_entries
        if e.urgency_level in ("emergency", "critical")
    ]

    return HospitalSnapshot(
        timestamp=now,
        total_waiting=total_waiting,
        total_in_consultation=total_consulting,
        total_completed_today=completed_today,
        doctors=list(doctor_loads.values()),
        departments=list(dept_loads.values()),
        avg_wait_minutes=round(avg_wait, 1),
        busiest_department=busiest,
        least_busy_department=least_busy,
        emergency_count=len(emergency_entries),
    )

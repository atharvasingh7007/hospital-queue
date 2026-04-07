"""
Hospital Queue AI — Database Models
SQLAlchemy models for patients, doctors, departments, queue, chat, and notifications.
"""
from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text,
    ForeignKey, Index, UniqueConstraint, JSON
)
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Shared base with automatic created_at timestamp."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        nullable=False,
    )


# ── Enums ──────────────────────────────────────────────

class QueueStatus(str, PyEnum):
    WAITING = "waiting"
    CALLED = "called"
    IN_CONSULTATION = "consultation"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    CANCELLED = "cancelled"


class AppointmentStatus(str, PyEnum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class NotificationType(str, PyEnum):
    QUEUE_POSITION = "queue_position"
    ESTIMATED_WAIT = "estimated_wait"
    YOUR_TURN = "your_turn"
    APPOINTMENT_REMINDER = "appointment_reminder"
    GENERAL = "general"


# ── Models ─────────────────────────────────────────────

class Department(Base):
    """Hospital department (General Medicine, Pediatrics, etc.)."""
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    doctors: Mapped[list["Doctor"]] = relationship(
        back_populates="department", lazy="selectin"
    )


class Doctor(Base):
    """Doctor with specialty, department, and consultation duration."""
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    specialty: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    department_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("departments.id"), nullable=False
    )
    consultation_duration_minutes: Mapped[int] = mapped_column(
        Integer, default=10, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    department: Mapped["Department"] = relationship(
        back_populates="doctors", lazy="selectin"
    )
    queue_entries: Mapped[list["QueueEntry"]] = relationship(
        back_populates="doctor", lazy="selectin"
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="doctor", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_doctors_specialty_active", "specialty", "is_active"),
    )


class Patient(Base):
    """Patient — phone number is the primary identifier for WhatsApp linking."""
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True, index=True
    )
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    blood_group: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    allergies: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    queue_entries: Mapped[list["QueueEntry"]] = relationship(
        back_populates="patient", lazy="selectin"
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="patient", lazy="selectin"
    )
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="patient", lazy="selectin",
        order_by="ChatMessage.created_at",
    )
    notification_logs: Mapped[list["NotificationLog"]] = relationship(
        back_populates="patient", lazy="selectin"
    )


class QueueEntry(Base):
    """A single patient's spot in a doctor's queue."""
    __tablename__ = "queue_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id"), nullable=False
    )
    doctor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("doctors.id"), nullable=False, index=True
    )

    queue_number: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), default=QueueStatus.WAITING.value, nullable=False, index=True
    )
    priority_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timing
    checked_in_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    called_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consultation_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Wait estimates
    estimated_wait_minutes: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    actual_wait_minutes: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )

    # Triage info
    symptoms: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    triage_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    urgency_level: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )

    patient: Mapped["Patient"] = relationship(
        back_populates="queue_entries", lazy="selectin"
    )
    doctor: Mapped["Doctor"] = relationship(
        back_populates="queue_entries", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_queue_doctor_status", "doctor_id", "status"),
        Index("ix_queue_waiting", "status", "position"),
    )


class ChatMessage(Base):
    """Per-patient conversation history with AI agents."""
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id"), nullable=False, index=True
    )

    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    patient: Mapped["Patient"] = relationship(
        back_populates="chat_messages", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_chat_patient_created", "patient_id", "created_at"),
    )


class Appointment(Base):
    """Scheduled appointment (not walk-in)."""
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id"), nullable=False
    )
    doctor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("doctors.id"), nullable=False
    )

    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=AppointmentStatus.SCHEDULED.value, nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(
        String(20), default="follow_up", nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship(
        back_populates="appointments", lazy="selectin"
    )
    doctor: Mapped["Doctor"] = relationship(
        back_populates="appointments", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("doctor_id", "scheduled_at", name="uq_doctor_timeslot"),
        Index("ix_appointments_patient_status", "patient_id", "status"),
    )


class NotificationLog(Base):
    """Log of every notification sent to a patient (audit trail)."""
    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id"), nullable=False, index=True
    )

    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    channel: Mapped[str] = mapped_column(
        String(20), default="in_app", nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="sent", nullable=False
    )

    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    patient: Mapped["Patient"] = relationship(
        back_populates="notification_logs", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_notifications_patient_type", "patient_id", "notification_type"),
    )


class User(Base):
    """Application user — linked to either a Patient or Doctor record."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), default="patient", nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Link to the patient or doctor record
    patient_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("patients.id"), nullable=True
    )
    doctor_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("doctors.id"), nullable=True
    )


class AgentActivity(Base):
    """Log of every agent action — makes the multi-agent system transparent."""
    __tablename__ = "agent_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    session_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    patient_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("patients.id"), nullable=True, index=True
    )

    agent_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # thinking, handoff, response, classification, routing, error

    # Content of the action
    thinking_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Handoff tracking
    handed_off_from: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    handed_off_to: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Classification data
    detected_intent: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(nullable=True)

    meta_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_agent_activity_session", "session_id", "created_at"),
        Index("ix_agent_activity_patient", "patient_id", "created_at"),
    )

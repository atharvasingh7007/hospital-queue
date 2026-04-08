"""
SQLAlchemy ORM models for the Hospital Queue AI system.

Models for persistence in AlloyDB (PostgreSQL) or SQLite (local dev).
These mirror the in-memory shared_state but provide persistence.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    capacity = Column(Integer, default=10)
    current_load = Column(Integer, default=0)
    avg_consultation_mins = Column(Integer, default=15)
    created_at = Column(DateTime, default=datetime.utcnow)


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    department_key = Column(String(50), nullable=False)
    specialization = Column(String(100))
    available = Column(Boolean, default=True)
    patients_seen_today = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    age = Column(Integer)
    registered_at = Column(DateTime, default=datetime.utcnow)


class QueueEntry(Base):
    __tablename__ = "queue_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    queue_number = Column(Integer, unique=True, nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    patient_name = Column(String(100), nullable=False)
    department_key = Column(String(50), nullable=False)
    priority = Column(String(20), default="NORMAL")
    status = Column(String(20), default="WAITING")  # WAITING, IN_CONSULTATION, COMPLETED, CANCELLED
    checked_in_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    appointment_id = Column(String(20), unique=True, nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    patient_name = Column(String(100), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"))
    doctor_name = Column(String(100), nullable=False)
    department = Column(String(100))
    reason = Column(Text)
    status = Column(String(20), default="SCHEDULED")
    booked_at = Column(DateTime, default=datetime.utcnow)
    estimated_time = Column(String(20))


class TriageRecord(Base):
    __tablename__ = "triage_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    patient_name = Column(String(100), nullable=False)
    age = Column(Integer)
    symptoms = Column(Text)
    severity_score = Column(Integer)
    urgency_level = Column(String(20))
    recommended_department = Column(String(50))
    assessed_at = Column(DateTime, default=datetime.utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    notification_id = Column(String(20), unique=True)
    recipient = Column(String(100), nullable=False)
    message = Column(Text)
    notification_type = Column(String(20), default="INFO")
    urgency = Column(String(20), default="NORMAL")
    status = Column(String(20), default="SENT")
    sent_at = Column(DateTime, default=datetime.utcnow)
    read = Column(Boolean, default=False)


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(50), nullable=False)
    event_data = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

"""
Hospital Queue AI — Database Seeder
Populates departments, doctors, patients, and sample queue entries for demo/testing.
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")

from database import get_db_context, init_db
from models import Patient, Doctor, Department, QueueEntry, User
from auth import hash_password


async def seed():
    """Populate the database with realistic demo data."""

    # Make sure tables exist
    await init_db()

    async with get_db_context() as db:
        print("[SEED] Populating Hospital Queue AI database...")

        # Skip if already seeded
        from sqlalchemy import select, func
        count = await db.execute(select(func.count()).select_from(Patient))
        if count.scalar_one() > 0:
            print("[WARN] Database already has data, skipping seed")
            return

        now = datetime.now(timezone.utc)

        # ── Departments ────────────────────────────────────
        departments = [
            Department(name="General Medicine", description="General health, fever, cold, common ailments"),
            Department(name="Cardiology", description="Heart and cardiovascular conditions"),
            Department(name="Orthopedics", description="Bones, joints, musculoskeletal issues"),
            Department(name="Pediatrics", description="Children's health and development"),
            Department(name="Gynecology", description="Women's health and maternity"),
            Department(name="Dermatology", description="Skin conditions and allergies"),
            Department(name="Emergency", description="Trauma, accidents, and critical care"),
        ]
        for dept in departments:
            db.add(dept)
        await db.flush()
        print(f"[OK] {len(departments)} departments created")

        # ── Doctors ────────────────────────────────────────
        doctors = [
            Doctor(
                name="Dr. Priya Sharma", phone="+919876543210",
                specialty="General Medicine", department_id=1,
                consultation_duration_minutes=10,
            ),
            Doctor(
                name="Dr. Rajesh Kumar", phone="+919876543211",
                specialty="General Medicine", department_id=1,
                consultation_duration_minutes=8,
            ),
            Doctor(
                name="Dr. Ananya Patel", phone="+919876543212",
                specialty="Cardiology", department_id=2,
                consultation_duration_minutes=15,
            ),
            Doctor(
                name="Dr. Vikram Singh", phone="+919876543213",
                specialty="Orthopedics", department_id=3,
                consultation_duration_minutes=12,
            ),
            Doctor(
                name="Dr. Sunita Gupta", phone="+919876543214",
                specialty="Pediatrics", department_id=4,
                consultation_duration_minutes=10,
            ),
            Doctor(
                name="Dr. Amit Verma", phone="+919876543215",
                specialty="Dermatology", department_id=6,
                consultation_duration_minutes=7,
            ),
        ]
        for doc in doctors:
            db.add(doc)
        await db.flush()
        print(f"[OK] {len(doctors)} doctors created")

        # ── Patients ───────────────────────────────────────
        patients = [
            Patient(name="Ramesh Kumar", phone="+919988776655", age=45, gender="male", blood_group="O+"),
            Patient(name="Sunita Devi", phone="+919988776656", age=32, gender="female", blood_group="A+"),
            Patient(name="Amit Singh", phone="+919988776657", age=28, gender="male", blood_group="B+"),
            Patient(name="Priya Verma", phone="+919988776658", age=35, gender="female", blood_group="AB+"),
            Patient(name="Vikram Patel", phone="+919988776659", age=52, gender="male", blood_group="O-"),
            Patient(name="Meera Joshi", phone="+919988776660", age=67, gender="female", blood_group="A-"),
            Patient(name="Ravi Tiwari", phone="+919988776661", age=8, gender="male", blood_group="B+"),
        ]
        for pat in patients:
            db.add(pat)
        await db.flush()
        print(f"[OK] {len(patients)} patients created")

        # ── Queue entries (today's queue for Dr. Priya Sharma) ──
        queue_entries = [
            QueueEntry(
                patient_id=1, doctor_id=1,
                queue_number=1, position=1, status="waiting",
                priority_score=30, symptoms="Fever and headache for 2 days",
                checked_in_at=now - timedelta(minutes=40),
                estimated_wait_minutes=0,
            ),
            QueueEntry(
                patient_id=2, doctor_id=1,
                queue_number=2, position=2, status="waiting",
                priority_score=20, symptoms="Persistent cough, mild cold",
                checked_in_at=now - timedelta(minutes=25),
                estimated_wait_minutes=10,
            ),
            QueueEntry(
                patient_id=6, doctor_id=1,
                queue_number=3, position=3, status="waiting",
                priority_score=50, symptoms="Dizziness and fatigue, senior citizen",
                urgency_level="urgent",
                checked_in_at=now - timedelta(minutes=15),
                estimated_wait_minutes=20,
            ),
            QueueEntry(
                patient_id=3, doctor_id=2,
                queue_number=1, position=1, status="waiting",
                priority_score=40, symptoms="Chest discomfort after exertion",
                checked_in_at=now - timedelta(minutes=18),
                estimated_wait_minutes=0,
            ),
            QueueEntry(
                patient_id=4, doctor_id=4,
                queue_number=1, position=1, status="waiting",
                priority_score=25, symptoms="Joint pain in both knees",
                checked_in_at=now - timedelta(minutes=12),
                estimated_wait_minutes=0,
            ),
        ]
        for entry in queue_entries:
            db.add(entry)
        print(f"[OK] {len(queue_entries)} queue entries created")

        # ── Demo Users ─────────────────────────────────────
        demo_password = hash_password("demo123")
        users = [
            User(
                name="Ramesh Kumar", email="patient@demo.com",
                hashed_password=demo_password, phone="+919988776655",
                role="patient", patient_id=1,
            ),
            User(
                name="Dr. Priya Sharma", email="doctor@demo.com",
                hashed_password=demo_password, phone="+919876543210",
                role="doctor", doctor_id=1,
            ),
            User(
                name="Admin User", email="admin@demo.com",
                hashed_password=demo_password, phone="+919000000000",
                role="admin",
            ),
        ]
        for user in users:
            db.add(user)
        print(f"[OK] {len(users)} demo users created (password: demo123)")

        await db.commit()
        print("[DONE] Database seeded successfully!")



if __name__ == "__main__":
    asyncio.run(seed())

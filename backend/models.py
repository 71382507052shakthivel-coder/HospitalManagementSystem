"""
models.py
---------
Handles the SQLite database connection, schema creation and seed data
for the Hospital Management System (HMS).

Using Python's built-in sqlite3 module keeps the project dependency-free
and easy to run anywhere, while still demonstrating a proper relational
schema (foreign keys, constraints, indexes) as described in the project
abstract.
"""

import sqlite3
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "hms.db")

SCHEMA = """
PRAGMA foreign_keys = ON;

-- ===================== USERS / RBAC =====================
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    full_name       TEXT NOT NULL,
    role            TEXT NOT NULL CHECK(role IN
                      ('admin','doctor','nurse','receptionist',
                       'billing_staff','pharmacist','lab_tech')),
    linked_doctor_id INTEGER,           -- if role='doctor', link to doctors.id
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL
);

-- ===================== PATIENTS =====================
CREATE TABLE IF NOT EXISTS patients (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_code    TEXT UNIQUE NOT NULL,      -- e.g. PT-000123 (unique patient id)
    full_name       TEXT NOT NULL,
    dob             TEXT,
    gender          TEXT CHECK(gender IN ('Male','Female','Other')),
    phone           TEXT,
    address         TEXT,
    blood_group     TEXT,
    allergies       TEXT,
    emergency_contact TEXT,
    created_at      TEXT NOT NULL
);

-- Electronic Health Record entries (visit notes / diagnoses / history)
CREATE TABLE IF NOT EXISTS medical_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id      INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id       INTEGER REFERENCES doctors(id),
    visit_date      TEXT NOT NULL,
    diagnosis       TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL
);

-- ===================== STAFF / DOCTORS =====================
CREATE TABLE IF NOT EXISTS doctors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name       TEXT NOT NULL,
    specialization  TEXT NOT NULL,
    phone           TEXT,
    email           TEXT,
    department      TEXT,
    schedule        TEXT,          -- free-text / JSON e.g. Mon-Fri 9am-5pm
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL
);

-- ===================== APPOINTMENTS =====================
CREATE TABLE IF NOT EXISTS appointments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id      INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id       INTEGER NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    appt_date       TEXT NOT NULL,
    appt_time       TEXT NOT NULL,
    reason          TEXT,
    status          TEXT NOT NULL DEFAULT 'Scheduled'
                      CHECK(status IN ('Scheduled','Completed','Cancelled','No-Show')),
    created_at      TEXT NOT NULL
);

-- ===================== BILLING / FINANCE =====================
CREATE TABLE IF NOT EXISTS bills (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_no         TEXT UNIQUE NOT NULL,
    patient_id      INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    appointment_id  INTEGER REFERENCES appointments(id),
    total_amount    REAL NOT NULL DEFAULT 0,
    paid_amount     REAL NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'Unpaid'
                      CHECK(status IN ('Unpaid','Partially Paid','Paid','Insurance Pending')),
    insurance_provider TEXT,
    insurance_claim_status TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bill_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id         INTEGER NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
    description     TEXT NOT NULL,
    quantity        INTEGER NOT NULL DEFAULT 1,
    unit_price      REAL NOT NULL DEFAULT 0
);

-- ===================== PHARMACY =====================
CREATE TABLE IF NOT EXISTS drugs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    manufacturer    TEXT,
    unit_price      REAL NOT NULL DEFAULT 0,
    stock_qty       INTEGER NOT NULL DEFAULT 0,
    reorder_level   INTEGER NOT NULL DEFAULT 10,
    expiry_date     TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prescriptions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id      INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id       INTEGER NOT NULL REFERENCES doctors(id),
    drug_id         INTEGER NOT NULL REFERENCES drugs(id),
    quantity        INTEGER NOT NULL DEFAULT 1,
    dosage_instructions TEXT,
    status          TEXT NOT NULL DEFAULT 'Pending'
                      CHECK(status IN ('Pending','Dispensed','Cancelled')),
    prescribed_date TEXT NOT NULL,
    dispensed_date  TEXT
);

-- ===================== LABORATORY =====================
CREATE TABLE IF NOT EXISTS lab_tests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id      INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id       INTEGER REFERENCES doctors(id),
    test_name       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'Ordered'
                      CHECK(status IN ('Ordered','Sample Collected','In Progress','Completed','Cancelled')),
    result          TEXT,
    ordered_date    TEXT NOT NULL,
    completed_date  TEXT
);

-- ===================== WARD / BED MANAGEMENT =====================
CREATE TABLE IF NOT EXISTS wards (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    ward_type       TEXT,          -- General, ICU, Maternity, Pediatric...
    capacity        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS beds (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ward_id         INTEGER NOT NULL REFERENCES wards(id) ON DELETE CASCADE,
    bed_number      TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'Available'
                      CHECK(status IN ('Available','Occupied','Cleaning','Maintenance')),
    patient_id      INTEGER REFERENCES patients(id),
    admitted_at     TEXT,
    UNIQUE(ward_id, bed_number)
);

-- ===================== AUDIT TRAIL =====================
CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER REFERENCES users(id),
    username        TEXT,
    action          TEXT NOT NULL,
    entity          TEXT,
    entity_id       INTEGER,
    details         TEXT,
    timestamp       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_appt_date ON appointments(appt_date);
CREATE INDEX IF NOT EXISTS idx_patient_name ON patients(full_name);
CREATE INDEX IF NOT EXISTS idx_bills_status ON bills(status);
"""


def get_db():
    """Return a sqlite3 connection with row access by column name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(seed=True):
    """Create tables if they don't exist, and optionally seed demo data."""
    first_time = not os.path.exists(DB_PATH)
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()

    if seed and first_time:
        _seed(conn)
    conn.close()


def _seed(conn):
    """Populate the database with an admin account and realistic sample
    data so the system is demoable immediately after setup."""
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.cursor()

    # ---- Users (one per role, demonstrating RBAC) ----
    users = [
        ("admin", "admin123", "System Administrator", "admin", None),
        ("dr.rao", "doctor123", "Dr. Anjali Rao", "doctor", 1),
        ("dr.menon", "doctor123", "Dr. Suresh Menon", "doctor", 2),
        ("nurse.priya", "nurse123", "Priya Nair", "nurse", None),
        ("reception1", "reception123", "Divya S.", "receptionist", None),
        ("billing1", "billing123", "Ramesh Kumar", "billing_staff", None),
        ("pharmacist1", "pharma123", "Anu Thomas", "pharmacist", None),
        ("labtech1", "lab123", "Vinod P.", "lab_tech", None),
    ]
    for username, pwd, full_name, role, doc_id in users:
        cur.execute(
            """INSERT INTO users (username, password_hash, full_name, role,
                linked_doctor_id, created_at) VALUES (?,?,?,?,?,?)""",
            (username, generate_password_hash(pwd), full_name, role, doc_id, now),
        )

    # ---- Doctors ----
    doctors = [
        ("Dr. Anjali Rao", "Cardiology", "9876500001", "anjali.rao@hospital.com", "Cardiology", "Mon-Fri 9am-4pm"),
        ("Dr. Suresh Menon", "Orthopedics", "9876500002", "suresh.menon@hospital.com", "Orthopedics", "Mon-Sat 10am-5pm"),
        ("Dr. Kavya Pillai", "Pediatrics", "9876500003", "kavya.pillai@hospital.com", "Pediatrics", "Mon-Fri 9am-3pm"),
        ("Dr. Faizal Ahmed", "General Medicine", "9876500004", "faizal.ahmed@hospital.com", "General Medicine", "Mon-Sun 8am-2pm"),
    ]
    for d in doctors:
        cur.execute(
            """INSERT INTO doctors (full_name, specialization, phone, email,
                department, schedule, created_at) VALUES (?,?,?,?,?,?,?)""",
            (*d, now),
        )

    # ---- Patients ----
    patients = [
        ("PT-000001", "Arjun Nair", "1990-04-12", "Male", "9995512345", "Kollam, Kerala", "O+", "None", "9995512399"),
        ("PT-000002", "Meera Krishnan", "1985-11-02", "Female", "9995512346", "Trivandrum, Kerala", "A+", "Penicillin", "9995512398"),
        ("PT-000003", "Rahul Varma", "2001-07-19", "Male", "9995512347", "Kochi, Kerala", "B+", "None", "9995512397"),
        ("PT-000004", "Sneha George", "1978-02-27", "Female", "9995512348", "Kollam, Kerala", "AB+", "Dust", "9995512396"),
    ]
    for p in patients:
        cur.execute(
            """INSERT INTO patients (patient_code, full_name, dob, gender, phone,
                address, blood_group, allergies, emergency_contact, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (*p, now),
        )

    # ---- Appointments ----
    today = datetime.now().date()
    appts = [
        (1, 1, str(today), "10:00", "Chest pain follow-up", "Scheduled"),
        (2, 2, str(today), "11:30", "Knee pain evaluation", "Scheduled"),
        (3, 3, str(today + timedelta(days=1)), "09:00", "Routine child checkup", "Scheduled"),
        (4, 4, str(today - timedelta(days=2)), "14:00", "Fever and cold", "Completed"),
    ]
    for a in appts:
        cur.execute(
            """INSERT INTO appointments (patient_id, doctor_id, appt_date,
                appt_time, reason, status, created_at) VALUES (?,?,?,?,?,?,?)""",
            (*a, now),
        )

    # ---- Drugs ----
    drugs = [
        ("Paracetamol 500mg", "Cipla", 2.5, 500, 50, "2027-06-30"),
        ("Amoxicillin 250mg", "Sun Pharma", 5.0, 200, 30, "2026-12-31"),
        ("Cetirizine 10mg", "GSK", 1.5, 300, 40, "2027-03-31"),
        ("Insulin Glargine", "Sanofi", 450.0, 40, 10, "2026-11-30"),
    ]
    for dr in drugs:
        cur.execute(
            """INSERT INTO drugs (name, manufacturer, unit_price, stock_qty,
                reorder_level, expiry_date, created_at) VALUES (?,?,?,?,?,?,?)""",
            (*dr, now),
        )

    # ---- Wards & Beds ----
    wards = [("General Ward", "General", 10), ("ICU", "ICU", 4), ("Maternity Ward", "Maternity", 6)]
    for w in wards:
        cur.execute("INSERT INTO wards (name, ward_type, capacity) VALUES (?,?,?)", w)

    for ward_id, capacity in [(1, 10), (2, 4), (3, 6)]:
        for i in range(1, capacity + 1):
            cur.execute(
                "INSERT INTO beds (ward_id, bed_number, status) VALUES (?,?, 'Available')",
                (ward_id, f"{ward_id}-{i:02d}"),
            )
    # occupy a couple of beds for realism
    cur.execute("UPDATE beds SET status='Occupied', patient_id=1, admitted_at=? WHERE id=1", (now,))
    cur.execute("UPDATE beds SET status='Occupied', patient_id=2, admitted_at=? WHERE id=11", (now,))

    conn.commit()


if __name__ == "__main__":
    init_db()
    print(f"Database initialised at {DB_PATH}")

# MediCore — Hospital Management System (HMS)

A full-stack, web-based Hospital Management System built to the project
abstract: a centralized platform that digitizes patient records,
scheduling, billing, pharmacy, laboratory and ward/bed operations, with
role-based access control (RBAC) protecting sensitive data.

## Tech Stack

| Layer            | Technology                                            |
|-------------------|--------------------------------------------------------|
| Backend / API     | Python 3 + Flask (REST APIs, session-based auth)       |
| Database          | SQLite (relational, file-based — swap-in ready for MySQL/PostgreSQL) |
| Frontend          | Server-rendered HTML (Jinja2) + vanilla JavaScript (fetch-based SPA-style pages) |
| Auth              | Server-side sessions, hashed passwords (Werkzeug), RBAC decorators |

The backend follows a modular, client-server REST architecture — the
frontend never touches the database directly, only the JSON API — so it
can later be swapped for a React/mobile client or extended to
microservices without touching business logic.

## Project Structure

```
hms/
├── backend/
│   ├── app.py                 # Flask entrypoint, page routes, blueprint registration
│   ├── models.py              # SQLite schema (DDL) + demo data seeding
│   ├── auth.py                # Session auth + RBAC decorators + audit logging
│   ├── requirements.txt
│   └── routes/                # One blueprint per module (REST API)
│       ├── auth_routes.py         # /api/auth/*        login, logout, session
│       ├── patient_routes.py      # /api/patients/*    registration + EHR
│       ├── doctor_routes.py       # /api/doctors/*, /api/staff/*  staff & RBAC accounts
│       ├── appointment_routes.py  # /api/appointments/* scheduling, double-booking guard
│       ├── billing_routes.py      # /api/bills/*       invoices, payments, insurance
│       ├── pharmacy_routes.py     # /api/pharmacy/*    drug inventory + prescriptions
│       ├── lab_routes.py          # /api/lab-tests/*   test orders + results
│       ├── ward_routes.py         # /api/wards/*       bed occupancy/admission
│       └── dashboard_routes.py    # /api/dashboard/stats
├── frontend/
│   ├── templates/             # Jinja2 page shells (one per module)
│   └── static/
│       ├── css/style.css
│       └── js/api.js          # shared fetch wrapper + formatting helpers
└── README.md
```

## Database Schema (core tables)

`users` (RBAC) · `patients` · `medical_records` (EHR) · `doctors` ·
`appointments` · `bills` / `bill_items` · `drugs` · `prescriptions` ·
`lab_tests` · `wards` / `beds` · `audit_log`

Foreign keys enforce referential integrity (e.g. an appointment cannot
reference a non-existent patient or doctor), and indexes are added on
frequently-filtered columns (appointment date, patient name, bill status).

## Modules Implemented

1. **Patient Management** — registration with an auto-generated unique
   patient code (`PT-000001…`), demographics, and an electronic health
   record (EHR) of visit notes/diagnoses, visible only to clinical roles.
2. **Doctor & Staff Management** — doctor directory + admin-managed staff
   accounts, each assigned exactly one RBAC role.
3. **Appointment Scheduling** — book/reschedule/cancel; doctors see only
   their own calendar; a real-time clash check blocks double-booking a
   doctor at the same date/time.
4. **Billing & Finance** — itemized invoices, partial/full payment
   tracking, and an insurance-provider/claim-status field per bill.
5. **Pharmacy Management** — drug inventory with reorder-level flags, and
   a prescribe → dispense workflow that decrements stock automatically
   (and blocks dispensing if stock is insufficient).
6. **Laboratory Management** — test ordering and status/result tracking
   (Ordered → Sample Collected → In Progress → Completed).
7. **Ward / Bed Management** — visual bed grid per ward, admit/discharge,
   and live occupancy percentage on the dashboard.
8. **Audit Trail** — every create/update/payment/login is logged with
   user, action, entity and timestamp, and shown on the dashboard.

## Role-Based Access Control (RBAC)

Enforced **server-side** on every route (never trust the client alone),
via `@login_required` / `@roles_required(...)` in `auth.py`:

| Role            | Can do |
|-----------------|--------|
| `admin`         | Everything, incl. managing doctors and staff accounts |
| `doctor`        | View/manage own appointments, add EHR notes & prescriptions, order labs |
| `nurse`         | Register patients, add EHR notes, manage ward/bed admission |
| `receptionist`  | Register patients, book appointments, view billing, manage beds |
| `billing_staff` | Manage invoices, payments, insurance claims (no clinical data) |
| `pharmacist`    | Manage drug inventory and dispense prescriptions |
| `lab_tech`      | Order/update lab tests |

Billing/reception roles, for example, receive patient records **without**
the `allergies` field — clinical detail is stripped server-side, not just
hidden in the UI. Frontend pages also hide navigation links and 403 for
roles that shouldn't see them, as a UX layer on top of the server checks.

## Setup & Running

```bash
cd backend
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000** — the SQLite database (`hms.db`) and
demo data are created automatically on first run.

### Demo accounts (all created on first run)

| Username        | Password       | Role                  |
|------------------|---------------|------------------------|
| `admin`          | `admin123`    | Administrator          |
| `dr.rao`         | `doctor123`   | Doctor (Cardiology)    |
| `dr.menon`       | `doctor123`   | Doctor (Orthopedics)   |
| `nurse.priya`    | `nurse123`    | Nurse                  |
| `reception1`     | `reception123`| Receptionist           |
| `billing1`       | `billing123`  | Billing staff          |
| `pharmacist1`    | `pharma123`   | Pharmacist             |
| `labtech1`       | `lab123`      | Lab technician         |

To reset the database, stop the server and delete `backend/hms.db`, then
restart — it will be recreated and reseeded automatically.

## Notes on Production Hardening

This is a project/demo build. For production deployment you would
additionally want to:
- Move `SECRET_KEY` to an environment variable / secrets manager (a
  placeholder is already read from `HMS_SECRET_KEY`) and disable
  `debug=True`.
- Swap SQLite for MySQL/PostgreSQL (schema in `models.py` is standard SQL
  and ports over with minimal changes) and run behind a WSGI server
  (gunicorn/uWSGI) + reverse proxy.
- Add HTTPS/TLS, CSRF protection on state-changing requests, and rate
  limiting on `/api/auth/login`.
- Encrypt sensitive fields at rest and add field-level audit logging in
  line with healthcare data-protection standards (e.g. HIPAA/GDPR as
  applicable to your jurisdiction).
- Add automated tests (the routes were validated via Flask's test client
  during development — a `tests/` suite using `pytest` is a natural next
  step).

## Future Enhancements (per the project abstract)

- Mobile app (companion to this web frontend, same REST API)
- AI-driven predictive analytics for admission trends
- Wearable device integration
- Telemedicine module (video consultation scheduling)

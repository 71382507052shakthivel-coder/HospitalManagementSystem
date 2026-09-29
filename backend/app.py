"""
app.py
------
Entry point for the Hospital Management System (HMS) Flask application.

Run with:   python app.py
Then open:  http://127.0.0.1:5000

Default login (created on first run):
    username: admin       password: admin123      (System Administrator)
    username: dr.rao      password: doctor123     (Doctor)
    username: reception1  password: reception123  (Receptionist)
    username: billing1    password: billing123    (Billing staff)
    username: pharmacist1 password: pharma123     (Pharmacist)
    username: labtech1    password: lab123        (Lab technician)
    username: nurse.priya password: nurse123      (Nurse)
"""

import os
import sys
from flask import Flask, render_template, session, redirect, url_for

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import init_db  # noqa: E402
from routes.auth_routes import bp as auth_bp  # noqa: E402
from routes.patient_routes import bp as patient_bp  # noqa: E402
from routes.doctor_routes import bp as doctor_bp  # noqa: E402
from routes.appointment_routes import bp as appointment_bp  # noqa: E402
from routes.billing_routes import bp as billing_bp  # noqa: E402
from routes.pharmacy_routes import bp as pharmacy_bp  # noqa: E402
from routes.lab_routes import bp as lab_bp  # noqa: E402
from routes.ward_routes import bp as ward_bp  # noqa: E402
from routes.dashboard_routes import bp as dashboard_bp  # noqa: E402

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), "frontend")

app = Flask(
    __name__,
    template_folder=os.path.join(FRONTEND_DIR, "templates"),
    static_folder=os.path.join(FRONTEND_DIR, "static"),
)
app.secret_key = os.environ.get("HMS_SECRET_KEY", "dev-secret-key-change-in-production")

# Register API blueprints
for bp in (auth_bp, patient_bp, doctor_bp, appointment_bp, billing_bp,
           pharmacy_bp, lab_bp, ward_bp, dashboard_bp):
    app.register_blueprint(bp)


# ---------------- Page (view) routes ----------------
# These simply serve the HTML shell; all data is loaded client-side via the
# JSON APIs above, and every page enforces login/role checks again in JS
# (with the server-side @login_required / @roles_required as the real
# source of truth).

PAGE_ROLES = {
    "patients.html": None,                     # everyone logged in
    "doctors.html": {"admin"},
    "staff.html": {"admin"},
    "appointments.html": None,
    "billing.html": {"admin", "billing_staff", "receptionist"},
    "pharmacy.html": {"admin", "pharmacist", "doctor"},
    "lab.html": {"admin", "lab_tech", "doctor"},
    "wards.html": {"admin", "nurse", "receptionist"},
}


@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    return redirect(url_for("dashboard_page"))


@app.route("/login")
def login_page():
    if "user_id" in session:
        return redirect(url_for("dashboard_page"))
    return render_template("login.html")


@app.route("/dashboard")
def dashboard_page():
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    return render_template("dashboard.html", role=session.get("role"), full_name=session.get("full_name"))


def _page(name):
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    allowed = PAGE_ROLES.get(name)
    if allowed is not None and session.get("role") not in allowed:
        return render_template("forbidden.html"), 403
    return render_template(name, role=session.get("role"), full_name=session.get("full_name"))


@app.route("/patients")
def patients_page():
    return _page("patients.html")


@app.route("/doctors")
def doctors_page():
    return _page("doctors.html")


@app.route("/staff")
def staff_page():
    return _page("staff.html")


@app.route("/appointments")
def appointments_page():
    return _page("appointments.html")


@app.route("/billing")
def billing_page():
    return _page("billing.html")


@app.route("/pharmacy")
def pharmacy_page():
    return _page("pharmacy.html")


@app.route("/lab")
def lab_page():
    return _page("lab.html")


@app.route("/wards")
def wards_page():
    return _page("wards.html")


if __name__ == "__main__":
    init_db(seed=True)
    print("=" * 60)
    print(" Hospital Management System")
    print(" Running at: http://127.0.0.1:5000")
    print(" Default admin login -> admin / admin123")
    print("=" * 60)
    app.run(debug=True, host="0.0.0.0", port=5000)

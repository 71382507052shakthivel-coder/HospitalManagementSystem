from flask import Blueprint, jsonify, session
from datetime import date
from models import get_db
from auth import login_required

bp = Blueprint("dashboard_routes", __name__, url_prefix="/api/dashboard")


@bp.get("/stats")
@login_required
def stats():
    conn = get_db()
    today = date.today().isoformat()

    total_patients = conn.execute("SELECT COUNT(*) c FROM patients").fetchone()["c"]
    total_doctors = conn.execute("SELECT COUNT(*) c FROM doctors WHERE is_active=1").fetchone()["c"]
    todays_appts = conn.execute(
        "SELECT COUNT(*) c FROM appointments WHERE appt_date=? AND status='Scheduled'", (today,)
    ).fetchone()["c"]
    pending_bills = conn.execute(
        "SELECT COUNT(*) c FROM bills WHERE status IN ('Unpaid','Partially Paid')"
    ).fetchone()["c"]
    revenue_today = conn.execute(
        "SELECT COALESCE(SUM(paid_amount),0) s FROM bills WHERE created_at LIKE ?", (f"{today}%",)
    ).fetchone()["s"]
    low_stock = conn.execute(
        "SELECT COUNT(*) c FROM drugs WHERE stock_qty <= reorder_level"
    ).fetchone()["c"]
    pending_labs = conn.execute(
        "SELECT COUNT(*) c FROM lab_tests WHERE status NOT IN ('Completed','Cancelled')"
    ).fetchone()["c"]
    beds_total = conn.execute("SELECT COUNT(*) c FROM beds").fetchone()["c"]
    beds_occupied = conn.execute("SELECT COUNT(*) c FROM beds WHERE status='Occupied'").fetchone()["c"]
    pending_rx = conn.execute("SELECT COUNT(*) c FROM prescriptions WHERE status='Pending'").fetchone()["c"]

    recent_activity = conn.execute(
        "SELECT * FROM audit_log ORDER BY id DESC LIMIT 8"
    ).fetchall()
    conn.close()

    return jsonify(
        total_patients=total_patients,
        total_doctors=total_doctors,
        todays_appointments=todays_appts,
        pending_bills=pending_bills,
        revenue_today=revenue_today,
        low_stock_drugs=low_stock,
        pending_lab_tests=pending_labs,
        beds_total=beds_total,
        beds_occupied=beds_occupied,
        bed_occupancy_pct=round((beds_occupied / beds_total * 100) if beds_total else 0, 1),
        pending_prescriptions=pending_rx,
        role=session.get("role"),
        recent_activity=[dict(r) for r in recent_activity],
    )

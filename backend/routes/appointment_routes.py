from flask import Blueprint, request, jsonify, session
from datetime import datetime
from models import get_db
from auth import login_required, roles_required, log_action

bp = Blueprint("appointment_routes", __name__, url_prefix="/api/appointments")


def row_to_dict(r):
    return dict(r)


@bp.get("")
@login_required
def list_appointments():
    date_filter = request.args.get("date")
    doctor_filter = request.args.get("doctor_id")

    query = """
        SELECT a.*, p.full_name AS patient_name, p.patient_code,
               d.full_name AS doctor_name, d.specialization
        FROM appointments a
        JOIN patients p ON p.id = a.patient_id
        JOIN doctors d ON d.id = a.doctor_id
        WHERE 1=1
    """
    params = []

    # Doctors only see their own calendar unless admin/receptionist
    if session.get("role") == "doctor" and session.get("linked_doctor_id"):
        query += " AND a.doctor_id = ?"
        params.append(session["linked_doctor_id"])
    elif doctor_filter:
        query += " AND a.doctor_id = ?"
        params.append(doctor_filter)

    if date_filter:
        query += " AND a.appt_date = ?"
        params.append(date_filter)

    query += " ORDER BY a.appt_date, a.appt_time"
    conn = get_db()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([row_to_dict(r) for r in rows])


@bp.post("")
@roles_required("admin", "receptionist", "doctor", "nurse")
def create_appointment():
    d = request.get_json(force=True)
    for f in ("patient_id", "doctor_id", "appt_date", "appt_time"):
        if not d.get(f):
            return jsonify(error=f"'{f}' is required"), 400

    conn = get_db()
    # Real-time availability check: prevent double-booking a doctor at the same slot
    clash = conn.execute(
        """SELECT id FROM appointments WHERE doctor_id=? AND appt_date=? AND appt_time=?
           AND status='Scheduled'""",
        (d["doctor_id"], d["appt_date"], d["appt_time"]),
    ).fetchone()
    if clash:
        conn.close()
        return jsonify(error="Doctor already has an appointment at that time"), 409

    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        """INSERT INTO appointments (patient_id, doctor_id, appt_date, appt_time,
            reason, status, created_at) VALUES (?,?,?,?,?,?,?)""",
        (d["patient_id"], d["doctor_id"], d["appt_date"], d["appt_time"],
         d.get("reason"), "Scheduled", now),
    )
    conn.commit()
    conn.close()
    log_action("CREATE", "appointments", cur.lastrowid)
    return jsonify(id=cur.lastrowid), 201


@bp.put("/<int:aid>")
@roles_required("admin", "receptionist", "doctor", "nurse")
def update_appointment(aid):
    d = request.get_json(force=True)
    fields = ["appt_date", "appt_time", "reason", "status"]
    updates, values = [], []
    for f in fields:
        if f in d:
            updates.append(f"{f}=?")
            values.append(d[f])
    if not updates:
        return jsonify(error="No fields to update"), 400
    values.append(aid)
    conn = get_db()
    conn.execute(f"UPDATE appointments SET {', '.join(updates)} WHERE id=?", values)
    conn.commit()
    conn.close()
    log_action("UPDATE", "appointments", aid, str(d))
    return jsonify(ok=True)


@bp.delete("/<int:aid>")
@roles_required("admin", "receptionist", "doctor")
def cancel_appointment(aid):
    conn = get_db()
    conn.execute("UPDATE appointments SET status='Cancelled' WHERE id=?", (aid,))
    conn.commit()
    conn.close()
    log_action("CANCEL", "appointments", aid)
    return jsonify(ok=True)

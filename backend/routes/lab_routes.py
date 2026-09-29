from flask import Blueprint, request, jsonify, session
from datetime import datetime
from models import get_db
from auth import login_required, roles_required, log_action

bp = Blueprint("lab_routes", __name__, url_prefix="/api/lab-tests")


@bp.get("")
@login_required
def list_tests():
    conn = get_db()
    rows = conn.execute(
        """SELECT lt.*, p.full_name AS patient_name, p.patient_code,
                  d.full_name AS doctor_name
           FROM lab_tests lt
           JOIN patients p ON p.id = lt.patient_id
           LEFT JOIN doctors d ON d.id = lt.doctor_id
           ORDER BY lt.id DESC"""
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.post("")
@roles_required("admin", "doctor", "lab_tech")
def order_test():
    d = request.get_json(force=True)
    for f in ("patient_id", "test_name"):
        if not d.get(f):
            return jsonify(error=f"'{f}' is required"), 400
    doctor_id = d.get("doctor_id") or session.get("linked_doctor_id")
    conn = get_db()
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        """INSERT INTO lab_tests (patient_id, doctor_id, test_name, status,
            ordered_date) VALUES (?,?,?,?,?)""",
        (d["patient_id"], doctor_id, d["test_name"], "Ordered", now[:10]),
    )
    conn.commit()
    conn.close()
    log_action("CREATE", "lab_tests", cur.lastrowid)
    return jsonify(id=cur.lastrowid), 201


@bp.put("/<int:tid>")
@roles_required("admin", "lab_tech")
def update_test(tid):
    d = request.get_json(force=True)
    fields = ["status", "result"]
    updates, values = [], []
    for f in fields:
        if f in d:
            updates.append(f"{f}=?")
            values.append(d[f])
    if not updates:
        return jsonify(error="No fields to update"), 400
    if d.get("status") == "Completed":
        updates.append("completed_date=?")
        values.append(datetime.now().date().isoformat())
    values.append(tid)
    conn = get_db()
    conn.execute(f"UPDATE lab_tests SET {', '.join(updates)} WHERE id=?", values)
    conn.commit()
    conn.close()
    log_action("UPDATE", "lab_tests", tid, str(d))
    return jsonify(ok=True)

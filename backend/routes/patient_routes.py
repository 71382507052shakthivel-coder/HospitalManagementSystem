from flask import Blueprint, request, jsonify, session
from datetime import datetime
from models import get_db
from auth import login_required, roles_required, log_action, CLINICAL_ROLES

bp = Blueprint("patient_routes", __name__, url_prefix="/api/patients")


def next_patient_code(conn):
    row = conn.execute("SELECT COUNT(*) c FROM patients").fetchone()
    return f"PT-{row['c'] + 1:06d}"


def strip_clinical_fields(patient_dict):
    """RBAC: non-clinical roles (e.g. billing/reception) see identity &
    contact info only, not allergies or blood group history context."""
    limited = dict(patient_dict)
    if session.get("role") not in CLINICAL_ROLES:
        limited.pop("allergies", None)
    return limited


@bp.get("")
@login_required
def list_patients():
    q = request.args.get("q", "").strip()
    conn = get_db()
    if q:
        rows = conn.execute(
            """SELECT * FROM patients WHERE full_name LIKE ? OR patient_code LIKE ?
               ORDER BY id DESC""",
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM patients ORDER BY id DESC").fetchall()
    conn.close()
    return jsonify([strip_clinical_fields(dict(r)) for r in rows])


@bp.get("/<int:pid>")
@login_required
def get_patient(pid):
    conn = get_db()
    p = conn.execute("SELECT * FROM patients WHERE id=?", (pid,)).fetchone()
    if not p:
        conn.close()
        return jsonify(error="Patient not found"), 404
    records = conn.execute(
        """SELECT mr.*, d.full_name as doctor_name FROM medical_records mr
           LEFT JOIN doctors d ON d.id = mr.doctor_id
           WHERE mr.patient_id=? ORDER BY mr.visit_date DESC""",
        (pid,),
    ).fetchall()
    conn.close()
    result = strip_clinical_fields(dict(p))
    if session.get("role") in CLINICAL_ROLES:
        result["medical_records"] = [dict(r) for r in records]
    return jsonify(result)


@bp.post("")
@roles_required("admin", "receptionist", "nurse")
def create_patient():
    d = request.get_json(force=True)
    required = ["full_name"]
    for f in required:
        if not d.get(f):
            return jsonify(error=f"'{f}' is required"), 400

    conn = get_db()
    code = next_patient_code(conn)
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        """INSERT INTO patients (patient_code, full_name, dob, gender, phone,
            address, blood_group, allergies, emergency_contact, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (code, d["full_name"], d.get("dob"), d.get("gender"), d.get("phone"),
         d.get("address"), d.get("blood_group"), d.get("allergies"),
         d.get("emergency_contact"), now),
    )
    pid = cur.lastrowid
    conn.commit()
    conn.close()
    log_action("CREATE", "patients", pid, f"Registered patient {code}")
    return jsonify(id=pid, patient_code=code), 201


@bp.put("/<int:pid>")
@roles_required("admin", "receptionist", "nurse")
def update_patient(pid):
    d = request.get_json(force=True)
    fields = ["full_name", "dob", "gender", "phone", "address", "blood_group",
              "allergies", "emergency_contact"]
    updates, values = [], []
    for f in fields:
        if f in d:
            updates.append(f"{f}=?")
            values.append(d[f])
    if not updates:
        return jsonify(error="No fields to update"), 400
    values.append(pid)
    conn = get_db()
    conn.execute(f"UPDATE patients SET {', '.join(updates)} WHERE id=?", values)
    conn.commit()
    conn.close()
    log_action("UPDATE", "patients", pid)
    return jsonify(ok=True)


@bp.delete("/<int:pid>")
@roles_required("admin")
def delete_patient(pid):
    conn = get_db()
    conn.execute("DELETE FROM patients WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    log_action("DELETE", "patients", pid)
    return jsonify(ok=True)


@bp.post("/<int:pid>/records")
@roles_required("admin", "doctor", "nurse")
def add_record(pid):
    d = request.get_json(force=True)
    if not d.get("diagnosis") and not d.get("notes"):
        return jsonify(error="Provide diagnosis or notes"), 400
    conn = get_db()
    now = datetime.now().isoformat(timespec="seconds")
    doctor_id = d.get("doctor_id") or session.get("linked_doctor_id")
    cur = conn.execute(
        """INSERT INTO medical_records (patient_id, doctor_id, visit_date,
            diagnosis, notes, created_at) VALUES (?,?,?,?,?,?)""",
        (pid, doctor_id, d.get("visit_date", now[:10]), d.get("diagnosis"),
         d.get("notes"), now),
    )
    conn.commit()
    conn.close()
    log_action("CREATE", "medical_records", cur.lastrowid, f"For patient {pid}")
    return jsonify(id=cur.lastrowid), 201

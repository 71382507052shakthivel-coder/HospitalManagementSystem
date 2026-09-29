from flask import Blueprint, request, jsonify
from datetime import datetime
from models import get_db
from auth import login_required, roles_required, log_action

bp = Blueprint("ward_routes", __name__, url_prefix="/api/wards")


@bp.get("")
@login_required
def list_wards():
    conn = get_db()
    wards = conn.execute("SELECT * FROM wards ORDER BY name").fetchall()
    result = []
    for w in wards:
        beds = conn.execute(
            """SELECT b.*, p.full_name AS patient_name FROM beds b
               LEFT JOIN patients p ON p.id=b.patient_id
               WHERE b.ward_id=? ORDER BY b.bed_number""",
            (w["id"],),
        ).fetchall()
        wd = dict(w)
        wd["beds"] = [dict(b) for b in beds]
        wd["occupied"] = sum(1 for b in beds if b["status"] == "Occupied")
        wd["available"] = sum(1 for b in beds if b["status"] == "Available")
        result.append(wd)
    conn.close()
    return jsonify(result)


@bp.post("")
@roles_required("admin")
def create_ward():
    d = request.get_json(force=True)
    if not d.get("name") or not d.get("capacity"):
        return jsonify(error="name and capacity are required"), 400
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO wards (name, ward_type, capacity) VALUES (?,?,?)",
        (d["name"], d.get("ward_type"), d["capacity"]),
    )
    ward_id = cur.lastrowid
    for i in range(1, int(d["capacity"]) + 1):
        conn.execute(
            "INSERT INTO beds (ward_id, bed_number, status) VALUES (?,?, 'Available')",
            (ward_id, f"{ward_id}-{i:02d}"),
        )
    conn.commit()
    conn.close()
    log_action("CREATE", "wards", ward_id)
    return jsonify(id=ward_id), 201


@bp.post("/beds/<int:bed_id>/admit")
@roles_required("admin", "nurse", "receptionist")
def admit_patient(bed_id):
    d = request.get_json(force=True)
    if not d.get("patient_id"):
        return jsonify(error="patient_id is required"), 400
    conn = get_db()
    bed = conn.execute("SELECT * FROM beds WHERE id=?", (bed_id,)).fetchone()
    if not bed:
        conn.close()
        return jsonify(error="Bed not found"), 404
    if bed["status"] != "Available":
        conn.close()
        return jsonify(error=f"Bed is currently {bed['status']}"), 409
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "UPDATE beds SET status='Occupied', patient_id=?, admitted_at=? WHERE id=?",
        (d["patient_id"], now, bed_id),
    )
    conn.commit()
    conn.close()
    log_action("ADMIT", "beds", bed_id, f"patient={d['patient_id']}")
    return jsonify(ok=True)


@bp.post("/beds/<int:bed_id>/discharge")
@roles_required("admin", "nurse", "receptionist")
def discharge_patient(bed_id):
    conn = get_db()
    conn.execute(
        "UPDATE beds SET status='Cleaning', patient_id=NULL, admitted_at=NULL WHERE id=?",
        (bed_id,),
    )
    conn.commit()
    conn.close()
    log_action("DISCHARGE", "beds", bed_id)
    return jsonify(ok=True)


@bp.post("/beds/<int:bed_id>/ready")
@roles_required("admin", "nurse")
def mark_ready(bed_id):
    """Move a bed from Cleaning/Maintenance back to Available."""
    conn = get_db()
    conn.execute("UPDATE beds SET status='Available' WHERE id=?", (bed_id,))
    conn.commit()
    conn.close()
    log_action("BED_READY", "beds", bed_id)
    return jsonify(ok=True)

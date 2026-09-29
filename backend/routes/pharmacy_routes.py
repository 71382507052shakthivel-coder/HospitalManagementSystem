from flask import Blueprint, request, jsonify, session
from datetime import datetime
from models import get_db
from auth import login_required, roles_required, log_action

bp = Blueprint("pharmacy_routes", __name__, url_prefix="/api/pharmacy")


@bp.get("/drugs")
@login_required
def list_drugs():
    conn = get_db()
    rows = conn.execute("SELECT * FROM drugs ORDER BY name").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.post("/drugs")
@roles_required("admin", "pharmacist")
def create_drug():
    d = request.get_json(force=True)
    if not d.get("name"):
        return jsonify(error="'name' is required"), 400
    conn = get_db()
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        """INSERT INTO drugs (name, manufacturer, unit_price, stock_qty,
            reorder_level, expiry_date, created_at) VALUES (?,?,?,?,?,?,?)""",
        (d["name"], d.get("manufacturer"), d.get("unit_price", 0),
         d.get("stock_qty", 0), d.get("reorder_level", 10), d.get("expiry_date"), now),
    )
    conn.commit()
    conn.close()
    log_action("CREATE", "drugs", cur.lastrowid)
    return jsonify(id=cur.lastrowid), 201


@bp.put("/drugs/<int:did>")
@roles_required("admin", "pharmacist")
def update_drug(did):
    d = request.get_json(force=True)
    fields = ["name", "manufacturer", "unit_price", "stock_qty", "reorder_level", "expiry_date"]
    updates, values = [], []
    for f in fields:
        if f in d:
            updates.append(f"{f}=?")
            values.append(d[f])
    if not updates:
        return jsonify(error="No fields to update"), 400
    values.append(did)
    conn = get_db()
    conn.execute(f"UPDATE drugs SET {', '.join(updates)} WHERE id=?", values)
    conn.commit()
    conn.close()
    log_action("UPDATE", "drugs", did)
    return jsonify(ok=True)


@bp.get("/prescriptions")
@login_required
def list_prescriptions():
    conn = get_db()
    rows = conn.execute(
        """SELECT pr.*, p.full_name AS patient_name, p.patient_code,
                  dr.full_name AS doctor_name, d.name AS drug_name, d.unit_price
           FROM prescriptions pr
           JOIN patients p ON p.id = pr.patient_id
           JOIN doctors dr ON dr.id = pr.doctor_id
           JOIN drugs d ON d.id = pr.drug_id
           ORDER BY pr.id DESC"""
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.post("/prescriptions")
@roles_required("admin", "doctor")
def create_prescription():
    d = request.get_json(force=True)
    for f in ("patient_id", "drug_id", "quantity"):
        if not d.get(f):
            return jsonify(error=f"'{f}' is required"), 400
    doctor_id = d.get("doctor_id") or session.get("linked_doctor_id")
    if not doctor_id:
        return jsonify(error="doctor_id is required"), 400

    conn = get_db()
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        """INSERT INTO prescriptions (patient_id, doctor_id, drug_id, quantity,
            dosage_instructions, status, prescribed_date) VALUES (?,?,?,?,?,?,?)""",
        (d["patient_id"], doctor_id, d["drug_id"], d["quantity"],
         d.get("dosage_instructions"), "Pending", now[:10]),
    )
    conn.commit()
    conn.close()
    log_action("CREATE", "prescriptions", cur.lastrowid)
    return jsonify(id=cur.lastrowid), 201


@bp.post("/prescriptions/<int:pid>/dispense")
@roles_required("admin", "pharmacist")
def dispense_prescription(pid):
    conn = get_db()
    pres = conn.execute("SELECT * FROM prescriptions WHERE id=?", (pid,)).fetchone()
    if not pres:
        conn.close()
        return jsonify(error="Prescription not found"), 404
    if pres["status"] != "Pending":
        conn.close()
        return jsonify(error=f"Prescription already {pres['status']}"), 400

    drug = conn.execute("SELECT * FROM drugs WHERE id=?", (pres["drug_id"],)).fetchone()
    if drug["stock_qty"] < pres["quantity"]:
        conn.close()
        return jsonify(error="Insufficient stock to dispense"), 409

    now = datetime.now().isoformat(timespec="seconds")
    conn.execute("UPDATE drugs SET stock_qty = stock_qty - ? WHERE id=?",
                 (pres["quantity"], drug["id"]))
    conn.execute(
        "UPDATE prescriptions SET status='Dispensed', dispensed_date=? WHERE id=?",
        (now[:10], pid),
    )
    conn.commit()
    conn.close()
    log_action("DISPENSE", "prescriptions", pid)
    return jsonify(ok=True)

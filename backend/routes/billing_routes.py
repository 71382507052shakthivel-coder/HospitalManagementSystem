from flask import Blueprint, request, jsonify
from datetime import datetime
from models import get_db
from auth import login_required, roles_required, log_action

bp = Blueprint("billing_routes", __name__, url_prefix="/api/bills")


def next_bill_no(conn):
    row = conn.execute("SELECT COUNT(*) c FROM bills").fetchone()
    return f"INV-{row['c'] + 1:06d}"


@bp.get("")
@roles_required("admin", "billing_staff", "receptionist")
def list_bills():
    conn = get_db()
    rows = conn.execute(
        """SELECT b.*, p.full_name AS patient_name, p.patient_code
           FROM bills b JOIN patients p ON p.id=b.patient_id
           ORDER BY b.id DESC"""
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.get("/<int:bid>")
@roles_required("admin", "billing_staff", "receptionist")
def get_bill(bid):
    conn = get_db()
    bill = conn.execute(
        """SELECT b.*, p.full_name AS patient_name, p.patient_code
           FROM bills b JOIN patients p ON p.id=b.patient_id WHERE b.id=?""",
        (bid,),
    ).fetchone()
    if not bill:
        conn.close()
        return jsonify(error="Bill not found"), 404
    items = conn.execute("SELECT * FROM bill_items WHERE bill_id=?", (bid,)).fetchall()
    conn.close()
    result = dict(bill)
    result["items"] = [dict(i) for i in items]
    return jsonify(result)


@bp.post("")
@roles_required("admin", "billing_staff")
def create_bill():
    d = request.get_json(force=True)
    if not d.get("patient_id") or not d.get("items"):
        return jsonify(error="patient_id and at least one item are required"), 400

    total = sum(float(i.get("unit_price", 0)) * int(i.get("quantity", 1)) for i in d["items"])
    conn = get_db()
    bill_no = next_bill_no(conn)
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        """INSERT INTO bills (bill_no, patient_id, appointment_id, total_amount,
            paid_amount, status, insurance_provider, insurance_claim_status, created_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
        (bill_no, d["patient_id"], d.get("appointment_id"), total, 0, "Unpaid",
         d.get("insurance_provider"),
         "Pending" if d.get("insurance_provider") else None, now),
    )
    bill_id = cur.lastrowid
    for i in d["items"]:
        conn.execute(
            "INSERT INTO bill_items (bill_id, description, quantity, unit_price) VALUES (?,?,?,?)",
            (bill_id, i.get("description", "Item"), i.get("quantity", 1), i.get("unit_price", 0)),
        )
    conn.commit()
    conn.close()
    log_action("CREATE", "bills", bill_id, f"{bill_no} total={total}")
    return jsonify(id=bill_id, bill_no=bill_no, total_amount=total), 201


@bp.post("/<int:bid>/pay")
@roles_required("admin", "billing_staff")
def record_payment(bid):
    d = request.get_json(force=True)
    amount = float(d.get("amount", 0))
    if amount <= 0:
        return jsonify(error="Payment amount must be positive"), 400

    conn = get_db()
    bill = conn.execute("SELECT * FROM bills WHERE id=?", (bid,)).fetchone()
    if not bill:
        conn.close()
        return jsonify(error="Bill not found"), 404

    new_paid = bill["paid_amount"] + amount
    if new_paid >= bill["total_amount"]:
        status = "Paid"
    elif new_paid > 0:
        status = "Partially Paid"
    else:
        status = "Unpaid"

    conn.execute("UPDATE bills SET paid_amount=?, status=? WHERE id=?", (new_paid, status, bid))
    conn.commit()
    conn.close()
    log_action("PAYMENT", "bills", bid, f"amount={amount}")
    return jsonify(ok=True, paid_amount=new_paid, status=status)


@bp.put("/<int:bid>/insurance")
@roles_required("admin", "billing_staff")
def update_insurance(bid):
    d = request.get_json(force=True)
    conn = get_db()
    conn.execute(
        "UPDATE bills SET insurance_provider=?, insurance_claim_status=? WHERE id=?",
        (d.get("insurance_provider"), d.get("insurance_claim_status"), bid),
    )
    conn.commit()
    conn.close()
    log_action("UPDATE", "bills", bid, "insurance claim updated")
    return jsonify(ok=True)

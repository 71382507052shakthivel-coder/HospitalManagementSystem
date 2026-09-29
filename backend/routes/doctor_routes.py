from flask import Blueprint, request, jsonify, session
from datetime import datetime
from werkzeug.security import generate_password_hash
from models import get_db
from auth import login_required, roles_required, log_action

bp = Blueprint("doctor_routes", __name__, url_prefix="/api")


@bp.get("/doctors")
@login_required
def list_doctors():
    conn = get_db()
    rows = conn.execute("SELECT * FROM doctors WHERE is_active=1 ORDER BY full_name").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.post("/doctors")
@roles_required("admin")
def create_doctor():
    d = request.get_json(force=True)
    if not d.get("full_name") or not d.get("specialization"):
        return jsonify(error="full_name and specialization are required"), 400
    conn = get_db()
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        """INSERT INTO doctors (full_name, specialization, phone, email,
            department, schedule, created_at) VALUES (?,?,?,?,?,?,?)""",
        (d["full_name"], d["specialization"], d.get("phone"), d.get("email"),
         d.get("department"), d.get("schedule"), now),
    )
    conn.commit()
    conn.close()
    log_action("CREATE", "doctors", cur.lastrowid)
    return jsonify(id=cur.lastrowid), 201


@bp.put("/doctors/<int:did>")
@roles_required("admin")
def update_doctor(did):
    d = request.get_json(force=True)
    fields = ["full_name", "specialization", "phone", "email", "department", "schedule", "is_active"]
    updates, values = [], []
    for f in fields:
        if f in d:
            updates.append(f"{f}=?")
            values.append(d[f])
    if not updates:
        return jsonify(error="No fields to update"), 400
    values.append(did)
    conn = get_db()
    conn.execute(f"UPDATE doctors SET {', '.join(updates)} WHERE id=?", values)
    conn.commit()
    conn.close()
    log_action("UPDATE", "doctors", did)
    return jsonify(ok=True)


@bp.delete("/doctors/<int:did>")
@roles_required("admin")
def delete_doctor(did):
    conn = get_db()
    conn.execute("UPDATE doctors SET is_active=0 WHERE id=?", (did,))
    conn.commit()
    conn.close()
    log_action("DEACTIVATE", "doctors", did)
    return jsonify(ok=True)


# ---------------- Staff / user accounts (admin only) ----------------

@bp.get("/staff")
@roles_required("admin")
def list_staff():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, username, full_name, role, linked_doctor_id, is_active FROM users ORDER BY role, full_name"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.post("/staff")
@roles_required("admin")
def create_staff():
    d = request.get_json(force=True)
    required = ["username", "password", "full_name", "role"]
    for f in required:
        if not d.get(f):
            return jsonify(error=f"'{f}' is required"), 400
    conn = get_db()
    now = datetime.now().isoformat(timespec="seconds")
    try:
        cur = conn.execute(
            """INSERT INTO users (username, password_hash, full_name, role,
                linked_doctor_id, created_at) VALUES (?,?,?,?,?,?)""",
            (d["username"], generate_password_hash(d["password"]), d["full_name"],
             d["role"], d.get("linked_doctor_id"), now),
        )
    except Exception as e:
        conn.close()
        return jsonify(error=f"Could not create user: {e}"), 400
    conn.commit()
    conn.close()
    log_action("CREATE", "users", cur.lastrowid, f"role={d['role']}")
    return jsonify(id=cur.lastrowid), 201


@bp.put("/staff/<int:uid>/toggle")
@roles_required("admin")
def toggle_staff(uid):
    conn = get_db()
    row = conn.execute("SELECT is_active FROM users WHERE id=?", (uid,)).fetchone()
    if not row:
        conn.close()
        return jsonify(error="User not found"), 404
    new_status = 0 if row["is_active"] else 1
    conn.execute("UPDATE users SET is_active=? WHERE id=?", (new_status, uid))
    conn.commit()
    conn.close()
    log_action("TOGGLE_ACTIVE", "users", uid, f"is_active={new_status}")
    return jsonify(ok=True, is_active=new_status)

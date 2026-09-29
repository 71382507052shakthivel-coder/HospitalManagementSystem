from flask import Blueprint, request, jsonify, session
from werkzeug.security import check_password_hash
from models import get_db
from auth import log_action, login_required

bp = Blueprint("auth_routes", __name__, url_prefix="/api/auth")


@bp.post("/login")
def login():
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()

    if not user or not check_password_hash(user["password_hash"], password) or not user["is_active"]:
        return jsonify(error="Invalid username or password"), 401

    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user["role"]
    session["full_name"] = user["full_name"]
    session["linked_doctor_id"] = user["linked_doctor_id"]

    log_action("LOGIN", "users", user["id"])

    return jsonify(
        id=user["id"], username=user["username"], full_name=user["full_name"],
        role=user["role"], linked_doctor_id=user["linked_doctor_id"],
    )


@bp.post("/logout")
@login_required
def logout():
    log_action("LOGOUT", "users", session.get("user_id"))
    session.clear()
    return jsonify(ok=True)


@bp.get("/me")
def me():
    if "user_id" not in session:
        return jsonify(user=None)
    return jsonify(user={
        "id": session["user_id"], "username": session["username"],
        "full_name": session["full_name"], "role": session["role"],
        "linked_doctor_id": session.get("linked_doctor_id"),
    })

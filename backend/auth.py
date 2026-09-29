"""
auth.py
-------
Session-based authentication and Role-Based Access Control (RBAC) helpers.

Design principle (per project abstract): sensitive patient data must only
be reachable by authorized roles. Every protected API route is wrapped
with @login_required and, where relevant, @roles_required(...) to enforce
this at the server layer (never trust the frontend alone).
"""

from functools import wraps
from flask import session, jsonify, request
from datetime import datetime
from models import get_db

# Roles allowed to see full clinical detail (diagnoses, notes, prescriptions)
CLINICAL_ROLES = {"admin", "doctor", "nurse"}
# Roles allowed to manage billing/finance
BILLING_ROLES = {"admin", "billing_staff"}
# Roles allowed to manage pharmacy
PHARMACY_ROLES = {"admin", "pharmacist", "doctor"}
# Roles allowed to manage lab
LAB_ROLES = {"admin", "lab_tech", "doctor"}
# Roles allowed to manage wards/beds
WARD_ROLES = {"admin", "nurse", "receptionist"}
# Roles allowed to manage staff/doctors and users
ADMIN_ROLES = {"admin"}


def current_user():
    if "user_id" not in session:
        return None
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    conn.close()
    return user


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify(error="Authentication required"), 401
        return f(*args, **kwargs)
    return wrapper


def roles_required(*allowed_roles):
    allowed = set(allowed_roles)

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return jsonify(error="Authentication required"), 401
            if session.get("role") not in allowed:
                return jsonify(error="You do not have permission to perform this action"), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator


def log_action(action, entity=None, entity_id=None, details=None):
    """Write an audit trail entry for the currently logged-in user."""
    conn = get_db()
    conn.execute(
        """INSERT INTO audit_log (user_id, username, action, entity, entity_id,
            details, timestamp) VALUES (?,?,?,?,?,?,?)""",
        (
            session.get("user_id"),
            session.get("username"),
            action,
            entity,
            entity_id,
            details,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    conn.close()

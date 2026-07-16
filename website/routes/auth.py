"""Authentication: sign-up and sign-in (JWT)."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

from app import db
from models import User

bp = Blueprint("auth", __name__)


def _valid_email(email: str) -> bool:
    return bool(email) and "@" in email and "." in email.split("@")[-1]


@bp.post("/api/auth/signup")
def signup():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not _valid_email(email):
        return jsonify(error="Invalid email"), 400
    if len(password) < 8:
        return jsonify(error="Password must be at least 8 characters"), 400

    if User.query.filter_by(email=email).first():
        return jsonify(error="Email already registered"), 409

    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify(token=token, user=user.to_dict()), 201


@bp.post("/api/auth/signin")
def signin():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify(error="Invalid credentials"), 401

    token = create_access_token(identity=str(user.id))
    return jsonify(token=token, user=user.to_dict()), 200


@bp.get("/api/auth/me")
@jwt_required()
def me():
    user = db.session.get(User, int(get_jwt_identity()))
    if not user:
        return jsonify(error="User not found"), 404
    return jsonify(user=user.to_dict())

"""Houses: create a home, register the router's API key, manage Pro tier."""
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from models import User, House

bp = Blueprint("houses", __name__)


def _current_user():
    return db.session.get(User, int(get_jwt_identity()))


@bp.get("/api/houses")
@jwt_required()
def list_houses():
    user = _current_user()
    return jsonify(houses=[h.to_dict() for h in user.houses])


@bp.post("/api/houses")
@jwt_required()
def create_house():
    user = _current_user()
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "My Home").strip()[:120]
    house = House(name=name, owner_id=user.id)
    db.session.add(house)
    db.session.commit()
    return jsonify(house=house.to_dict()), 201


@bp.post("/api/houses/<int:house_id>/key")
@jwt_required()
def set_key(house_id):
    """Register the router's single house API key for this house."""
    user = _current_user()
    house = House.query.filter_by(id=house_id, owner_id=user.id).first()
    if not house:
        return jsonify(error="House not found"), 404

    data = request.get_json(silent=True) or {}
    key = (data.get("api_key") or "").strip()
    if not key.startswith("hng_house_"):
        return jsonify(error="Invalid house API key"), 400

    # Key must be unique across all houses (one router = one house).
    existing = House.query.filter_by(api_key=key).first()
    if existing and existing.id != house.id:
        return jsonify(error="This key is already linked to another house"), 409

    house.api_key = key
    if not house.api_key_set_at:
        house.api_key_set_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(house=house.to_dict()), 200


@bp.delete("/api/houses/<int:house_id>/key")
@jwt_required()
def clear_key(house_id):
    user = _current_user()
    house = House.query.filter_by(id=house_id, owner_id=user.id).first()
    if not house:
        return jsonify(error="House not found"), 404
    house.api_key = None
    house.api_key_set_at = None
    db.session.commit()
    return jsonify(house=house.to_dict()), 200


@bp.post("/api/houses/<int:house_id>/upgrade")
@jwt_required()
def upgrade(house_id):
    """Activate Pro tier for the owner (mock payment — wire to Stripe later)."""
    user = _current_user()
    house = House.query.filter_by(id=house_id, owner_id=user.id).first()
    if not house:
        return jsonify(error="House not found"), 404
    user.plan = "pro"
    db.session.commit()
    return jsonify(user=user.to_dict(), house=house.to_dict()), 200

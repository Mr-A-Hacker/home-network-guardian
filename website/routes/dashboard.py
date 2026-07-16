"""Dashboard data for the signed-in user's houses."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from models import User, House, Device, AlertEvent, Report

bp = Blueprint("dashboard", __name__)


def _current_user():
    return db.session.get(User, int(get_jwt_identity()))


@bp.get("/api/dashboard")
@jwt_required()
def dashboard():
    user = _current_user()
    houses = []
    for h in user.houses:
        devices = [d.to_dict() for d in
                   Device.query.filter_by(house_id=h.id).all()]
        alerts = [a.to_dict() for a in
                  AlertEvent.query.filter_by(house_id=h.id)
                  .order_by(AlertEvent.id.desc()).limit(50).all()]
        houses.append({
            **h.to_dict(),
            "device_count": len(devices),
            "devices": devices,
            "alerts": alerts,
        })
    return jsonify(user=user.to_dict(), houses=houses)


@bp.get("/api/houses/<int:house_id>/history")
@jwt_required()
def history(house_id):
    user = _current_user()
    house = House.query.filter_by(id=house_id, owner_id=user.id).first()
    if not house:
        return jsonify(error="House not found"), 404

    limit = 500 if user.is_pro else 50
    reports = (Report.query.filter_by(house_id=house.id)
               .order_by(Report.id.desc()).limit(limit).all())
    return jsonify(reports=[{
        "id": r.id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "payload": r.payload,
    } for r in reports])

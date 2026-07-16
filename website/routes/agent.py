"""Agent-facing endpoint: the router POSTs reports here with its house key."""
import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app import db
from models import House, Device, AlertEvent, Report

bp = Blueprint("agent", __name__)


@bp.post("/api/v1/report")
def report():
    api_key = (request.headers.get("X-API-Key")
               or request.headers.get("Authorization", "").removeprefix("Bearer ").strip())
    if not api_key:
        return jsonify(error="missing API key"), 401

    house = House.query.filter_by(api_key=api_key).first()
    if not house:
        return jsonify(error="unknown or unregistered API key"), 403

    payload = request.get_json(silent=True) or {}
    now = datetime.now(timezone.utc)

    # Upsert devices from the latest snapshot.
    devices = payload.get("devices", {})
    present = {d["mac"]: d for d in devices.get("present", []) if d.get("mac")}
    for d in devices.get("joined", []):
        if d.get("mac"):
            present[d["mac"]] = d
    for mac, d in present.items():
        dev = Device.query.filter_by(house_id=house.id, mac=mac).first()
        if not dev:
            dev = Device(house_id=house.id, mac=mac)
        dev.ip = d.get("ip")
        dev.vendor = d.get("vendor")
        dev.last_seen = now
        dev.status = "present"
        db.session.add(dev)
    # Mark devices that left as offline.
    if devices.get("left"):
        left_macs = {d["mac"] for d in devices["left"] if d.get("mac")}
        for dev in Device.query.filter_by(house_id=house.id, status="present"):
            if dev.mac in left_macs:
                dev.status = "offline"

    # Store alerts from this report.
    for a in payload.get("ids_alerts", []):
        db.session.add(AlertEvent(
            house_id=house.id, type="ids_alert",
            severity=str(a.get("severity")), detail=json.dumps(a),
        ))
    for ev in payload.get("flows", {}).get("scan_like_sources", []):
        db.session.add(AlertEvent(
            house_id=house.id, type="scan_like_activity", detail=ev))

    # Roll the report log (free tier: keep last 50, pro: 500).
    rep = Report(house_id=house.id, payload=json.dumps(payload))
    db.session.add(rep)
    house.last_seen = now
    db.session.commit()

    # Trim history for the plan.
    limit = 500 if house.owner.is_pro else 50
    excess = Report.query.filter_by(house_id=house.id).order_by(
        Report.id.desc()).offset(limit).all()
    for r in excess:
        db.session.delete(r)
    db.session.commit()

    return jsonify(status="accepted"), 202

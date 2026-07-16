"""Database models for the website backend."""
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash, check_password_hash

from app import db


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    # Pro tier: free users get limited history; pro gets full + alerts.
    plan = db.Column(db.String(20), default="free")  # "free" | "pro"
    created_at = db.Column(db.DateTime, default=_now)

    houses = db.relationship("House", back_populates="owner",
                             cascade="all, delete-orphan")

    def set_password(self, pw: str) -> None:
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw: str) -> bool:
        return check_password_hash(self.password_hash, pw)

    @property
    def is_pro(self) -> bool:
        return self.plan == "pro"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "plan": self.plan,
            "is_pro": self.is_pro,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class House(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), default="My Home")
    # The single key the router agent uses (hng_house_...).
    api_key = db.Column(db.String(64), unique=True, nullable=True, index=True)
    api_key_set_at = db.Column(db.DateTime, nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=_now)
    # Last successful report timestamp from the router.
    last_seen = db.Column(db.DateTime, nullable=True)

    owner = db.relationship("User", back_populates="houses")
    devices = db.relationship("Device", back_populates="house",
                              cascade="all, delete-orphan")
    alerts = db.relationship("AlertEvent", back_populates="house",
                             cascade="all, delete-orphan")
    reports = db.relationship("Report", back_populates="house",
                              cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "api_key": self.api_key,
            "has_key": bool(self.api_key),
            "owner_id": self.owner_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }


class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    house_id = db.Column(db.Integer, db.ForeignKey("house.id"), nullable=False)
    mac = db.Column(db.String(32), nullable=False)
    ip = db.Column(db.String(64))
    vendor = db.Column(db.String(120))
    first_seen = db.Column(db.DateTime, default=_now)
    last_seen = db.Column(db.DateTime, default=_now)
    # Populated by the latest report: present / joined / left.
    status = db.Column(db.String(20), default="present")

    house = db.relationship("House", back_populates="devices")

    __table_args__ = (db.UniqueConstraint("house_id", "mac", name="uq_house_mac"),)

    def to_dict(self) -> dict:
        return {
            "mac": self.mac,
            "ip": self.ip,
            "vendor": self.vendor,
            "status": self.status,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }


class AlertEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    house_id = db.Column(db.Integer, db.ForeignKey("house.id"), nullable=False)
    type = db.Column(db.String(40))          # device_joined, ids_alert, ...
    severity = db.Column(db.String(20))
    detail = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)

    house = db.relationship("House", back_populates="alerts")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "severity": self.severity,
            "detail": self.detail,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Report(db.Model):
    """Rolling log of agent status reports (free tier keeps last 50)."""
    id = db.Column(db.Integer, primary_key=True)
    house_id = db.Column(db.Integer, db.ForeignKey("house.id"), nullable=False)
    payload = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)

    house = db.relationship("House", back_populates="reports")

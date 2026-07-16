"""Home Network Guardian — Website backend.

Connects the router agent (via its house API key) to a user account with
sign-up / sign-in, houses, and a Pro tier.

Stack: Flask + Flask-JWT-Extended + Flask-SQLAlchemy (SQLite by default,
swap to Postgres via DATABASE_URL for production).

Run:
    pip install -r requirements.txt
    flask --app app run --host 0.0.0.0 --port 5000
"""
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
jwt = JWTManager()


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_mapping(
        SECRET_KEY="change-me-in-production",
        JWT_SECRET_KEY="change-me-in-production",
        SQLALCHEMY_DATABASE_URI="sqlite:///guardian.db",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_ACCESS_TOKEN_EXPIRES=60 * 60 * 24 * 7,  # 7 days
    )

    # Allow the agent (server-to-server, no cookie) and the SPA to talk.
    CORS(app, origins="*", expose_headers=["X-API-Key"])

    db.init_app(app)
    jwt.init_app(app)

    with app.app_context():
        from models import User, House, Device, AlertEvent, Report  # noqa: F401
        db.create_all()

    from routes import auth, houses, agent, dashboard
    app.register_blueprint(auth.bp)
    app.register_blueprint(houses.bp)
    app.register_blueprint(agent.bp)
    app.register_blueprint(dashboard.bp)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()

from pathlib import Path

from flask import Flask, g, redirect, render_template, session, url_for

from admin import admin_bp
from auth import auth_bp
from config import BASE_DIR, Config
from complaints import complaints_bp
from database import AnonymousUser, Notification, User
from extensions import csrf, db
from notifications import notifications_bp
from seed import init_demo_accounts, seed_demo_complaints
from utils import ensure_upload_folders


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    ensure_upload_folders(Path(app.config["UPLOAD_FOLDER"]))

    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:///smartcity.db"):
        db_path = Path(app.instance_path) / "smartcity.db"
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + db_path.as_posix()

    db.init_app(app)
    csrf.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(complaints_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(notifications_bp)

    @app.context_processor
    def inject_globals():
        unread = 0
        if g.current_user.is_authenticated:
            unread = Notification.query.filter_by(user_id=g.current_user.id, is_read=False).count()
        return {
            "current_user": g.current_user,
            "unread_count": unread,
            "mail_configured": bool(app.config.get("MAIL_SERVER") and app.config.get("MAIL_USERNAME")),
            "nominatim_enabled": bool(app.config.get("NOMINATIM_ENABLED")),
        }

    @app.before_request
    def load_user():
        user_id = session.get("user_id")
        user = db.session.get(User, user_id) if user_id else None
        g.current_user = user if user else AnonymousUser()

    @app.route("/")
    def index():
        if g.current_user.is_authenticated and g.current_user.email_verified:
            return redirect(url_for("complaints.home_redirect"))
        return render_template("index.html")

    @app.cli.command("init-db")
    def init_db():
        db.create_all()
        print("Database tables created.")

    @app.cli.command("init-demo")
    def init_demo():
        db.create_all()
        accounts = init_demo_accounts()
        seeded = seed_demo_complaints()
        print("Demo accounts:", accounts)
        print("Demo complaints created:", seeded)
        print("Admin login:", app.config["DEMO_ADMIN_EMAIL"])
        print("Worker login:", app.config["DEMO_WORKER_EMAIL"])
        print("Citizen login:", app.config["DEMO_CITIZEN_EMAIL"])
        print("Passwords come from your .env file.")

    with app.app_context():
        db.create_all()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)

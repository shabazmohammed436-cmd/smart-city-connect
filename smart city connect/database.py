from datetime import datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db

CATEGORIES = {
    "pothole": {
        "key": "pothole",
        "label": "Road Pothole",
        "icon": "road",
        "description": "Report damaged roads, potholes, and unsafe street surfaces.",
    },
    "garbage": {
        "key": "garbage",
        "label": "Overflowing Garbage",
        "icon": "trash",
        "description": "Report overflowing bins, dumped waste, and unclean public spots.",
    },
    "water": {
        "key": "water",
        "label": "Water Leakage",
        "icon": "droplet",
        "description": "Report leaking pipes, overflowing drains, and wasted water.",
    },
    "streetlight": {
        "key": "streetlight",
        "label": "Broken Streetlight",
        "icon": "light",
        "description": "Report dark streets, damaged poles, and non-working lights.",
    },
}

STATUSES = ["Pending", "Assigned", "In Progress", "Resolved", "Reopened"]


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="citizen")
    email_verified = db.Column(db.Boolean, nullable=False, default=False)
    is_demo = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    complaints = db.relationship("Complaint", backref="citizen", foreign_keys="Complaint.user_id")
    assigned_complaints = db.relationship(
        "Complaint", backref="worker", foreign_keys="Complaint.assigned_worker_id"
    )
    notifications = db.relationship("Notification", backref="user", lazy="dynamic")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_worker(self) -> bool:
        return self.role in {"worker", "admin"}

    @property
    def is_authenticated(self) -> bool:
        return True


class AnonymousUser:
    is_authenticated = False
    is_admin = False
    is_worker = False
    role = None
    id = None
    email_verified = False
    full_name = ""
    is_demo = False


class EmailVerification(db.Model):
    __tablename__ = "email_verifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    code_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    delivery_method = db.Column(db.String(40), nullable=False, default="dev_screen")

    user = db.relationship("User")

    def is_valid(self) -> bool:
        return (not self.used) and datetime.utcnow() < self.expires_at


class PasswordReset(db.Model):
    __tablename__ = "password_resets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    code_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    delivery_method = db.Column(db.String(40), nullable=False, default="dev_screen")

    user = db.relationship("User")

    def is_valid(self) -> bool:
        return (not self.used) and datetime.utcnow() < self.expires_at


class Complaint(db.Model):
    __tablename__ = "complaints"

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(32), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assigned_worker_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    category = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    admin_notes = db.Column(db.Text, nullable=True)
    address = db.Column(db.String(255), nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    location_source = db.Column(db.String(40), nullable=True)
    original_photo = db.Column(db.String(255), nullable=False)
    watermarked_photo = db.Column(db.String(255), nullable=True)
    capture_time = db.Column(db.DateTime, nullable=True)
    upload_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(30), nullable=False, default="Pending")
    resolution_photo = db.Column(db.String(255), nullable=True)
    resolution_note = db.Column(db.Text, nullable=True)
    resolution_at = db.Column(db.DateTime, nullable=True)
    is_demo = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    history = db.relationship(
        "ComplaintHistory",
        backref="complaint",
        order_by="ComplaintHistory.created_at",
        cascade="all, delete-orphan",
    )

    @property
    def category_label(self) -> str:
        return CATEGORIES.get(self.category, {}).get("label", self.category)

    @property
    def latest_update(self) -> str:
        if self.history:
            return self.history[-1].message
        return "Complaint created."

    @property
    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None


class ComplaintHistory(db.Model):
    __tablename__ = "complaint_history"

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    status = db.Column(db.String(30), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    actor = db.relationship("User")


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=True)
    title = db.Column(db.String(160), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


def otp_expiry(minutes: int = 15) -> datetime:
    return datetime.utcnow() + timedelta(minutes=minutes)

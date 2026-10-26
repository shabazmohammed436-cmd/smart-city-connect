from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, url_for

from database import Notification
from extensions import db
from utils import login_required

notifications_bp = Blueprint("notifications", __name__)


FRIENDLY_MESSAGES = {
    "submitted": (
        "Report received",
        "Your report has been received. Every improvement starts with someone who cares.",
    ),
    "assigned": (
        "Worker assigned",
        "An update is available for your complaint. Check its latest progress.",
    ),
    "in_progress": (
        "Work has started",
        "An update is available for your complaint. Check its latest progress.",
    ),
    "resolved": (
        "Complaint resolved",
        "Great news! Your complaint has been marked as resolved. Thank you for helping make our city better!",
    ),
    "reopened": (
        "Complaint reopened",
        "An update is available for your complaint. Check its latest progress.",
    ),
    "thanks": (
        "Thank you",
        "Thank you for being a responsible citizen. Together, we can build a cleaner and safer city.",
    ),
}


def create_notification(user_id: int, event_key: str, complaint_id: int | None = None, extra: str | None = None) -> None:
    title, message = FRIENDLY_MESSAGES.get(event_key, ("Update", extra or "There is a new update."))
    if extra and event_key not in FRIENDLY_MESSAGES:
        message = extra
    note = Notification(
        user_id=user_id,
        complaint_id=complaint_id,
        title=title,
        message=message,
    )
    db.session.add(note)


@notifications_bp.route("/notifications")
@login_required
def inbox():
    items = (
        Notification.query.filter_by(user_id=g.current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    return render_template("notifications.html", items=items)


@notifications_bp.post("/notifications/<int:note_id>/read")
@login_required
def mark_read(note_id: int):
    note = Notification.query.filter_by(id=note_id, user_id=g.current_user.id).first_or_404()
    note.is_read = True
    db.session.commit()
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify({"ok": True})
    return redirect(url_for("notifications.inbox"))


@notifications_bp.post("/notifications/read-all")
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=g.current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    flash("All notifications marked as read.", "success")
    return redirect(url_for("notifications.inbox"))


@notifications_bp.get("/api/notifications/unread")
@login_required
def unread_count():
    count = Notification.query.filter_by(user_id=g.current_user.id, is_read=False).count()
    return jsonify({"count": count})

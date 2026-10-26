import re
import secrets
import uuid
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import current_app, flash, g, redirect, url_for
from PIL import Image, ImageDraw, ImageFont
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from database import ComplaintHistory
from extensions import db


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.current_user.is_authenticated:
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def login_required_role(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not g.current_user.is_authenticated:
                flash("Please log in to continue.", "error")
                return redirect(url_for("auth.login"))
            if g.current_user.role not in roles:
                flash("You do not have permission to open that page.", "error")
                return redirect(url_for("complaints.home_redirect"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


def verified_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.current_user.is_authenticated and not g.current_user.email_verified:
            flash("Please verify your email before using the dashboard.", "error")
            return redirect(url_for("auth.verify_email"))
        return view(*args, **kwargs)

    return wrapped


def generate_complaint_id() -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d")
    return f"SCC-{stamp}-{secrets.token_hex(3).upper()}"


def allowed_image(filename: str) -> bool:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]


def save_upload(file: FileStorage, folder: str) -> str:
    if not file or not file.filename:
        raise ValueError("Please choose a photograph.")
    filename = secure_filename(file.filename)
    if not allowed_image(filename):
        raise ValueError("Please upload a JPG, PNG, or WEBP image.")
    ext = filename.rsplit(".", 1)[-1].lower()
    stored = f"{uuid.uuid4().hex}.{ext}"
    dest_dir = Path(current_app.config["UPLOAD_FOLDER"]) / folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / stored
    file.save(path)
    try:
        with Image.open(path) as image:
            image.verify()
    except Exception as exc:
        path.unlink(missing_ok=True)
        raise ValueError("That file does not look like a valid image.") from exc
    return stored


def watermark_image(
    filename: str,
    category_label: str,
    capture_time: datetime | None,
    latitude: float | None,
    longitude: float | None,
) -> str:
    source = Path(current_app.config["UPLOAD_FOLDER"]) / "complaints" / filename
    dest_name = f"wm_{filename.rsplit('.', 1)[0]}.jpg"
    dest = Path(current_app.config["UPLOAD_FOLDER"]) / "complaints" / dest_name

    with Image.open(source) as img:
        img = img.convert("RGB")
        max_width = 1600
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, int(img.height * ratio)))

        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        font = ImageFont.load_default()
        when = capture_time.strftime("%Y-%m-%d %H:%M UTC") if capture_time else "Capture time not recorded"
        coords = (
            f"{latitude:.5f}, {longitude:.5f}"
            if latitude is not None and longitude is not None
            else "Coordinates not recorded"
        )
        lines = [
            "SmartCity Connect",
            f"Category: {category_label}",
            f"Captured: {when}",
            f"Location: {coords}",
            "Prototype watermark — not official municipal evidence",
        ]
        padding = 12
        box_height = 18 * len(lines) + padding * 2
        draw.rectangle((0, img.height - box_height, img.width, img.height), fill=(11, 61, 145, 170))
        y = img.height - box_height + padding
        for line in lines:
            draw.text((padding, y), line, fill=(255, 255, 255, 255), font=font)
            y += 18
        marked = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        marked.save(dest, "JPEG", quality=88)
    return dest_name


def add_history(complaint, actor_id: int | None, status: str, message: str) -> None:
    complaint.status = status
    complaint.updated_at = datetime.utcnow()
    db.session.add(
        ComplaintHistory(
            complaint_id=complaint.id,
            actor_id=actor_id,
            status=status,
            message=message,
        )
    )


def notify_status(complaint, new_status: str) -> None:
    from notifications import create_notification

    mapping = {
        "Pending": "submitted",
        "Assigned": "assigned",
        "In Progress": "in_progress",
        "Resolved": "resolved",
        "Reopened": "reopened",
    }
    key = mapping.get(new_status, "assigned")
    create_notification(complaint.user_id, key, complaint.id)
    if new_status == "Resolved":
        create_notification(complaint.user_id, "thanks", complaint.id)


def parse_optional_float(value: str | None):
    if value is None or str(value).strip() == "":
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    if abs(number) > 180:
        return None
    return number


def parse_datetime(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def strong_password(password: str) -> str | None:
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password must include letters and numbers."
    return None


def ensure_upload_folders(upload_folder: Path) -> None:
    for folder in ("complaints", "resolutions"):
        (Path(upload_folder) / folder).mkdir(parents=True, exist_ok=True)

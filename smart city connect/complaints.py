from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from sqlalchemy import or_

from ai_features import ai_status
from database import CATEGORIES, STATUSES, Complaint, Notification, User
from extensions import db
from notifications import create_notification
from utils import (
    add_history,
    generate_complaint_id,
    login_required,
    parse_datetime,
    parse_optional_float,
    save_upload,
    verified_required,
    watermark_image,
)

complaints_bp = Blueprint("complaints", __name__)


def _home_for(user: User) -> str:
    if user.role == "admin":
        return url_for("admin.dashboard")
    if user.role == "worker":
        return url_for("admin.worker_dashboard")
    return url_for("complaints.dashboard")


@complaints_bp.route("/home-redirect")
def home_redirect():
    if not g.current_user.is_authenticated:
        return redirect(url_for("auth.welcome"))
    return redirect(_home_for(g.current_user))


@complaints_bp.route("/dashboard")
@login_required
@verified_required
def dashboard():
    if g.current_user.role != "citizen":
        return redirect(_home_for(g.current_user))
    query = Complaint.query.filter_by(user_id=g.current_user.id)
    total = query.count()
    pending = query.filter(Complaint.status.in_(["Pending", "Reopened"])).count()
    in_progress = query.filter(Complaint.status.in_(["Assigned", "In Progress"])).count()
    resolved = query.filter_by(status="Resolved").count()
    recent = query.order_by(Complaint.created_at.desc()).limit(5).all()
    return render_template(
        "dashboard.html",
        categories=CATEGORIES.values(),
        stats={"total": total, "pending": pending, "in_progress": in_progress, "resolved": resolved},
        recent=recent,
        ai=ai_status(),
    )


@complaints_bp.route("/report/<category>", methods=["GET", "POST"])
@login_required
@verified_required
def report_complaint(category: str):
    if g.current_user.role != "citizen":
        flash("Only citizen accounts can submit complaints.", "error")
        return redirect(_home_for(g.current_user))
    info = CATEGORIES.get(category)
    if not info:
        flash("Please choose a valid complaint category.", "error")
        return redirect(url_for("complaints.dashboard"))

    if request.method == "POST":
        token = request.form.get("submission_token")
        if token and session.get("last_submission_token") == token:
            flash("That complaint was already submitted.", "info")
            return redirect(url_for("complaints.my_complaints"))

        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        address = (request.form.get("address") or "").strip()
        notes = (request.form.get("notes") or "").strip() or None
        latitude = parse_optional_float(request.form.get("latitude"))
        longitude = parse_optional_float(request.form.get("longitude"))
        location_source = (request.form.get("location_source") or "manual").strip()
        capture_time = parse_datetime(request.form.get("capture_time"))
        photo = request.files.get("photo")

        errors = []
        if len(title) < 4:
            errors.append("Please add a short title.")
        if len(description) < 10:
            errors.append("Please describe the problem in a little more detail.")
        if len(address) < 4:
            errors.append("Please enter an address or nearby landmark.")
        if location_source not in {"browser", "manual", "unavailable"}:
            location_source = "manual"
        if (latitude is None) != (longitude is None):
            errors.append("Latitude and longitude must both be filled, or both left empty.")
        if latitude is None and longitude is None:
            location_source = "unavailable"

        stored = None
        try:
            stored = save_upload(photo, "complaints")
        except ValueError as exc:
            errors.append(str(exc))

        if errors:
            for item in errors:
                flash(item, "error")
            return render_template("report_complaint.html", category=info, now=datetime.utcnow())

        public_id = generate_complaint_id()
        upload_time = datetime.utcnow()
        watermarked = None
        try:
            watermarked = watermark_image(
                stored, info["label"], capture_time, latitude, longitude
            )
        except Exception:
            watermarked = None

        complaint = Complaint(
            public_id=public_id,
            user_id=g.current_user.id,
            category=category,
            title=title,
            description=description,
            notes=notes,
            address=address,
            latitude=latitude,
            longitude=longitude,
            location_source=location_source,
            original_photo=stored,
            watermarked_photo=watermarked,
            capture_time=capture_time,
            upload_time=upload_time,
            status="Pending",
            is_demo=False,
        )
        db.session.add(complaint)
        db.session.flush()
        add_history(
            complaint,
            g.current_user.id,
            "Pending",
            "Citizen submitted this complaint. Status set to Pending.",
        )
        create_notification(g.current_user.id, "submitted", complaint.id)
        db.session.commit()
        if token:
            session["last_submission_token"] = token
        flash("Your complaint was submitted successfully.", "success")
        return redirect(url_for("complaints.complaint_details", public_id=public_id, submitted=1))

    return render_template("report_complaint.html", category=info, now=datetime.utcnow())


@complaints_bp.route("/my-complaints")
@login_required
@verified_required
def my_complaints():
    items = (
        Complaint.query.filter_by(user_id=g.current_user.id)
        .order_by(Complaint.created_at.desc())
        .all()
    )
    return render_template("my_complaints.html", items=items, statuses=STATUSES)


@complaints_bp.route("/complaints/<public_id>")
@login_required
@verified_required
def complaint_details(public_id: str):
    complaint = Complaint.query.filter_by(public_id=public_id).first_or_404()
    user = g.current_user
    allowed = (
        complaint.user_id == user.id
        or user.role == "admin"
        or (user.role == "worker" and complaint.assigned_worker_id == user.id)
    )
    if not allowed:
        flash("You can only view complaints that belong to your account.", "error")
        return redirect(url_for("complaints.my_complaints"))
    submitted = request.args.get("submitted") == "1"
    return render_template(
        "complaint_details.html",
        complaint=complaint,
        statuses=STATUSES,
        submitted=submitted,
    )


@complaints_bp.get("/api/complaints/<public_id>")
@login_required
def complaint_poll(public_id: str):
    complaint = Complaint.query.filter_by(public_id=public_id).first_or_404()
    if complaint.user_id != g.current_user.id and g.current_user.role not in {"admin", "worker"}:
        return jsonify({"error": "forbidden"}), 403
    if g.current_user.role == "worker" and complaint.assigned_worker_id != g.current_user.id:
        return jsonify({"error": "forbidden"}), 403
    return jsonify(
        {
            "public_id": complaint.public_id,
            "status": complaint.status,
            "updated_at": complaint.updated_at.isoformat() + "Z",
            "latest_update": complaint.latest_update,
        }
    )


@complaints_bp.get("/map")
@login_required
@verified_required
def city_map():
    query = Complaint.query.filter(Complaint.latitude.isnot(None), Complaint.longitude.isnot(None))
    if g.current_user.role == "citizen":
        query = query.filter_by(user_id=g.current_user.id)
    elif g.current_user.role == "worker":
        query = query.filter_by(assigned_worker_id=g.current_user.id)
    category = request.args.get("category") or ""
    status = request.args.get("status") or ""
    if category in CATEGORIES:
        query = query.filter_by(category=category)
    if status in STATUSES:
        query = query.filter_by(status=status)
    markers = []
    for item in query.all():
        markers.append(
            {
                "public_id": item.public_id,
                "category": item.category_label,
                "status": item.status,
                "lat": item.latitude,
                "lng": item.longitude,
                "is_demo": item.is_demo,
                "title": item.title if g.current_user.role != "citizen" or item.user_id == g.current_user.id else item.category_label,
            }
        )
    return render_template(
        "map.html",
        markers=markers,
        categories=CATEGORIES,
        statuses=STATUSES,
        selected_category=category,
        selected_status=status,
    )


@complaints_bp.post("/api/reverse-geocode")
@login_required
def reverse_geocode():
    if not current_app.config.get("NOMINATIM_ENABLED"):
        return jsonify(
            {
                "ok": False,
                "reason": "Reverse geocoding is turned off. Enter the address manually.",
            }
        )
    payload = request.get_json(silent=True) or request.form
    lat = parse_optional_float(payload.get("lat"))
    lon = parse_optional_float(payload.get("lng"))
    if lat is None or lon is None:
        return jsonify({"ok": False, "reason": "Coordinates are missing."})
    params = urlencode({"lat": lat, "lon": lon, "format": "json"})
    url = f"https://nominatim.openstreetmap.org/reverse?{params}"
    req = Request(url, headers={"User-Agent": current_app.config["NOMINATIM_USER_AGENT"]})
    try:
        with urlopen(req, timeout=8) as response:
            payload = response.read().decode("utf-8")
        import json

        data = json.loads(payload)
        address = data.get("display_name")
        if not address:
            return jsonify({"ok": False, "reason": "No address was found for those coordinates."})
        return jsonify({"ok": True, "address": address})
    except Exception:
        return jsonify({"ok": False, "reason": "The address lookup service is unavailable."})


@complaints_bp.get("/media/<folder>/<filename>")
@login_required
def media(folder: str, filename: str):
    if folder not in {"complaints", "resolutions"}:
        return "Not found", 404
    safe_name = Path(filename).name
    complaint = None
    if folder == "complaints":
        complaint = Complaint.query.filter(
            or_(Complaint.original_photo == safe_name, Complaint.watermarked_photo == safe_name)
        ).first()
    else:
        complaint = Complaint.query.filter_by(resolution_photo=safe_name).first()
    if not complaint:
        return "Not found", 404
    user = g.current_user
    allowed = (
        complaint.user_id == user.id
        or user.role == "admin"
        or (user.role == "worker" and complaint.assigned_worker_id == user.id)
    )
    if not allowed:
        return "Forbidden", 403
    directory = Path(current_app.config["UPLOAD_FOLDER"]) / folder
    return send_from_directory(directory, safe_name)

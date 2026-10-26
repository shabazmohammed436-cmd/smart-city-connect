from datetime import datetime

from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from sqlalchemy import or_

from ai_features import summarise_complaints, ai_status
from database import CATEGORIES, STATUSES, Complaint, User
from extensions import db
from utils import add_history, login_required_role, notify_status, save_upload, verified_required

admin_bp = Blueprint("admin", __name__)


def _workers():
    return User.query.filter(User.role.in_(["worker", "admin"]), User.email_verified.is_(True)).all()


@admin_bp.route("/admin")
@login_required_role("admin")
@verified_required
def dashboard():
    q = (request.args.get("q") or "").strip()
    category = request.args.get("category") or ""
    status = request.args.get("status") or ""
    query = Complaint.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Complaint.public_id.ilike(like), Complaint.address.ilike(like), Complaint.title.ilike(like)))
    if category in CATEGORIES:
        query = query.filter_by(category=category)
    if status in STATUSES:
        query = query.filter_by(status=status)
    items = query.order_by(Complaint.created_at.desc()).all()
    counts = {
        "total": Complaint.query.count(),
        "pending": Complaint.query.filter_by(status="Pending").count(),
        "assigned": Complaint.query.filter_by(status="Assigned").count(),
        "progress": Complaint.query.filter_by(status="In Progress").count(),
        "resolved": Complaint.query.filter_by(status="Resolved").count(),
        "demo": Complaint.query.filter_by(is_demo=True).count(),
    }
    return render_template(
        "admin_dashboard.html",
        items=items,
        counts=counts,
        categories=CATEGORIES,
        statuses=STATUSES,
        q=q,
        selected_category=category,
        selected_status=status,
        workers=_workers(),
        ai=ai_status(),
        ai_summary=summarise_complaints(items),
    )


@admin_bp.route("/admin/complaints/<public_id>", methods=["GET", "POST"])
@login_required_role("admin")
@verified_required
def complaint_admin(public_id: str):
    complaint = Complaint.query.filter_by(public_id=public_id).first_or_404()
    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "assign":
                worker_id = request.form.get("worker_id")
                worker = User.query.filter(User.id == int(worker_id), User.role.in_(["worker", "admin"])).first()
                if not worker:
                    raise ValueError("Please choose a valid worker.")
                complaint.assigned_worker_id = worker.id
                add_history(
                    complaint,
                    g.current_user.id,
                    "Assigned",
                    f"Administrator assigned this complaint to {worker.full_name}.",
                )
                notify_status(complaint, "Assigned")
                flash("Complaint assigned.", "success")
            elif action == "status":
                new_status = request.form.get("status")
                if new_status not in STATUSES:
                    raise ValueError("Invalid status.")
                if new_status == "Resolved" and not complaint.resolution_photo:
                    raise ValueError("Upload resolution evidence before marking this complaint Resolved.")
                note = (request.form.get("admin_note") or "").strip()
                complaint.admin_notes = note or complaint.admin_notes
                add_history(
                    complaint,
                    g.current_user.id,
                    new_status,
                    note or f"Administrator updated status to {new_status}.",
                )
                if new_status == "Resolved":
                    complaint.resolution_at = complaint.resolution_at or datetime.utcnow()
                notify_status(complaint, new_status)
                flash("Status updated.", "success")
            elif action == "note":
                note = (request.form.get("admin_note") or "").strip()
                if not note:
                    raise ValueError("Please enter a note.")
                complaint.admin_notes = note
                add_history(complaint, g.current_user.id, complaint.status, f"Administrator note: {note}")
                flash("Note saved.", "success")
            elif action == "resolution":
                photo = request.files.get("resolution_photo")
                note = (request.form.get("resolution_note") or "").strip()
                stored = save_upload(photo, "resolutions")
                complaint.resolution_photo = stored
                complaint.resolution_note = note or complaint.resolution_note
                complaint.resolution_at = datetime.utcnow()
                add_history(
                    complaint,
                    g.current_user.id,
                    complaint.status,
                    "Administrator uploaded a resolution photograph. This is staff-submitted evidence, not independently verified proof.",
                )
                flash("Resolution photograph saved.", "success")
            else:
                raise ValueError("Unknown action.")
            db.session.commit()
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "error")
        return redirect(url_for("admin.complaint_admin", public_id=public_id))

    return render_template(
        "complaint_details.html",
        complaint=complaint,
        statuses=STATUSES,
        workers=_workers(),
        admin_mode=True,
        submitted=False,
    )


@admin_bp.route("/worker")
@login_required_role("worker", "admin")
@verified_required
def worker_dashboard():
    if g.current_user.role == "admin":
        items = Complaint.query.filter(Complaint.assigned_worker_id.isnot(None)).order_by(Complaint.updated_at.desc()).all()
    else:
        items = (
            Complaint.query.filter_by(assigned_worker_id=g.current_user.id)
            .order_by(Complaint.updated_at.desc())
            .all()
        )
    return render_template("worker_dashboard.html", items=items, statuses=STATUSES)


@admin_bp.route("/worker/complaints/<public_id>", methods=["GET", "POST"])
@login_required_role("worker", "admin")
@verified_required
def worker_complaint(public_id: str):
    complaint = Complaint.query.filter_by(public_id=public_id).first_or_404()
    if g.current_user.role == "worker" and complaint.assigned_worker_id != g.current_user.id:
        flash("This complaint is not assigned to you.", "error")
        return redirect(url_for("admin.worker_dashboard"))

    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "status":
                new_status = request.form.get("status")
                if new_status not in {"Assigned", "In Progress"}:
                    raise ValueError("Workers can set status to Assigned or In Progress from this form.")
                add_history(
                    complaint,
                    g.current_user.id,
                    new_status,
                    f"Worker updated status to {new_status}.",
                )
                notify_status(complaint, new_status)
                flash("Status updated.", "success")
            elif action == "resolve":
                photo = request.files.get("resolution_photo")
                note = (request.form.get("resolution_note") or "").strip()
                stored = save_upload(photo, "resolutions")
                if len(note) < 5:
                    raise ValueError("Please add a short resolution note.")
                complaint.resolution_photo = stored
                complaint.resolution_note = note
                complaint.resolution_at = datetime.utcnow()
                add_history(
                    complaint,
                    g.current_user.id,
                    "Resolved",
                    "Worker submitted resolution evidence. This image is staff-submitted evidence, not independently verified proof.",
                )
                notify_status(complaint, "Resolved")
                flash("Resolution submitted.", "success")
            else:
                raise ValueError("Unknown action.")
            db.session.commit()
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "error")
        return redirect(url_for("admin.worker_complaint", public_id=public_id))

    return render_template(
        "complaint_details.html",
        complaint=complaint,
        statuses=STATUSES,
        worker_mode=True,
        submitted=False,
    )

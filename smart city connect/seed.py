from datetime import datetime, timedelta
from pathlib import Path

from flask import current_app
from PIL import Image, ImageDraw, ImageFont

from database import Complaint, User
from extensions import db
from notifications import create_notification
from utils import add_history, generate_complaint_id, watermark_image


def _demo_photo(filename: str, label: str, color: tuple[int, int, int]) -> str:
    folder = Path(current_app.config["UPLOAD_FOLDER"]) / "complaints"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / filename
    image = Image.new("RGB", (960, 640), color)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.rectangle((30, 30, 930, 610), outline=(255, 255, 255), width=3)
    draw.text((60, 80), "DEMO PHOTO", fill=(255, 255, 255), font=font)
    draw.text((60, 120), label, fill=(255, 255, 255), font=font)
    draw.text((60, 160), "Fictional sample for hackathon demonstration", fill=(255, 255, 255), font=font)
    image.save(path, "JPEG", quality=85)
    return filename


def init_demo_accounts() -> dict:
    created = {}
    specs = [
        ("admin", current_app.config["DEMO_ADMIN_EMAIL"], current_app.config["DEMO_ADMIN_PASSWORD"], "Demo Administrator"),
        ("worker", current_app.config["DEMO_WORKER_EMAIL"], current_app.config["DEMO_WORKER_PASSWORD"], "Demo Field Worker"),
        ("citizen", current_app.config["DEMO_CITIZEN_EMAIL"], current_app.config["DEMO_CITIZEN_PASSWORD"], "Demo Citizen"),
    ]
    for role, email, password, name in specs:
        user = User.query.filter_by(email=email.lower()).first()
        if user is None:
            user = User(
                full_name=name,
                email=email.lower(),
                role=role,
                email_verified=True,
                is_demo=True,
            )
            user.set_password(password)
            db.session.add(user)
            created[role] = "created"
        else:
            user.role = role
            user.email_verified = True
            user.is_demo = True
            user.set_password(password)
            created[role] = "updated"
    db.session.commit()
    return created


def seed_demo_complaints() -> int:
    citizen = User.query.filter_by(email=current_app.config["DEMO_CITIZEN_EMAIL"].lower()).first()
    worker = User.query.filter_by(email=current_app.config["DEMO_WORKER_EMAIL"].lower()).first()
    admin = User.query.filter_by(email=current_app.config["DEMO_ADMIN_EMAIL"].lower()).first()
    if not all([citizen, worker, admin]):
        return 0
    if Complaint.query.filter_by(is_demo=True).count() >= 4:
        return 0

    samples = [
        {
            "category": "pothole",
            "title": "Deep pothole near college gate",
            "description": "A large pothole is collecting water beside the main college entrance. Two-wheelers are swerving into traffic.",
            "address": "Demo Street, Near North Gate, Fictional Ward 12",
            "lat": 17.3850,
            "lng": 78.4867,
            "color": (90, 80, 70),
            "status": "Pending",
        },
        {
            "category": "garbage",
            "title": "Overflowing bin at market lane",
            "description": "The community bin has been overflowing for two days. Waste is spreading onto the footpath.",
            "address": "Demo Market Lane, Fictional Ward 4",
            "lat": 17.4065,
            "lng": 78.4772,
            "color": (70, 90, 60),
            "status": "Assigned",
        },
        {
            "category": "water",
            "title": "Leaking public tap",
            "description": "A roadside tap is leaking continuously. The nearby path is slippery.",
            "address": "Demo Park Road, Fictional Ward 8",
            "lat": 17.3616,
            "lng": 78.4747,
            "color": (40, 90, 130),
            "status": "In Progress",
        },
        {
            "category": "streetlight",
            "title": "Dark stretch near bus stop",
            "description": "The streetlight above the demo bus stop has been dark for several evenings.",
            "address": "Demo Bus Stop, Fictional Ward 2",
            "lat": 17.4483,
            "lng": 78.3915,
            "color": (30, 40, 70),
            "status": "Resolved",
        },
    ]

    now = datetime.utcnow()
    created = 0
    for index, sample in enumerate(samples):
        filename = _demo_photo(f"demo_{sample['category']}.jpg", sample["title"], sample["color"])
        capture = now - timedelta(days=3 - index, hours=2)
        watermarked = watermark_image(filename, sample["title"], capture, sample["lat"], sample["lng"])
        complaint = Complaint(
            public_id=generate_complaint_id(),
            user_id=citizen.id,
            category=sample["category"],
            title=sample["title"],
            description=sample["description"] + " This is fictional demonstration data, not a real municipal case.",
            notes="Created by demo seed. Not from a real citizen report.",
            address=sample["address"],
            latitude=sample["lat"],
            longitude=sample["lng"],
            location_source="manual",
            original_photo=filename,
            watermarked_photo=watermarked,
            capture_time=capture,
            upload_time=capture + timedelta(minutes=8),
            status="Pending",
            is_demo=True,
            created_at=capture + timedelta(minutes=8),
        )
        if sample["status"] in {"Assigned", "In Progress", "Resolved"}:
            complaint.assigned_worker_id = worker.id
        db.session.add(complaint)
        db.session.flush()
        add_history(complaint, citizen.id, "Pending", "Demonstration complaint created for hackathon testing.")
        create_notification(citizen.id, "submitted", complaint.id)
        if sample["status"] in {"Assigned", "In Progress", "Resolved"}:
            add_history(complaint, admin.id, "Assigned", f"Demo administrator assigned this sample to {worker.full_name}.")
            create_notification(citizen.id, "assigned", complaint.id)
        if sample["status"] in {"In Progress", "Resolved"}:
            add_history(complaint, worker.id, "In Progress", "Demo worker marked work as started.")
            create_notification(citizen.id, "in_progress", complaint.id)
        if sample["status"] == "Resolved":
            res_name = f"demo_resolved_{sample['category']}.jpg"
            _demo_photo(res_name, "DEMO RESOLUTION PHOTO", (20, 120, 100))
            res_folder = Path(current_app.config["UPLOAD_FOLDER"]) / "resolutions"
            res_folder.mkdir(parents=True, exist_ok=True)
            src = Path(current_app.config["UPLOAD_FOLDER"]) / "complaints" / res_name
            dest = res_folder / res_name
            dest.write_bytes(src.read_bytes())
            src.unlink(missing_ok=True)
            complaint.resolution_photo = res_name
            complaint.resolution_note = "Demo resolution evidence uploaded by the sample worker. Not independently verified proof."
            complaint.resolution_at = now - timedelta(hours=6)
            add_history(
                complaint,
                worker.id,
                "Resolved",
                "Demo worker submitted resolution evidence. This is fictional sample data.",
            )
            create_notification(citizen.id, "resolved", complaint.id)
            create_notification(citizen.id, "thanks", complaint.id)
        created += 1
    db.session.commit()
    return created

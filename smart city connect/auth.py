import secrets

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from database import EmailVerification, PasswordReset, User, otp_expiry
from email_service import send_email
from extensions import db
from utils import login_required, strong_password

auth_bp = Blueprint("auth", __name__)


def _create_code() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def _issue_verification(user: User) -> tuple[EmailVerification, str, str]:
    EmailVerification.query.filter_by(user_id=user.id, used=False).update({"used": True})
    code = _create_code()
    mail_ok = bool(current_app.config.get("MAIL_SERVER") and current_app.config.get("MAIL_USERNAME"))
    method = "smtp" if mail_ok else "dev_screen"
    record = EmailVerification(
        user_id=user.id,
        code_hash=generate_password_hash(code),
        expires_at=otp_expiry(15),
        delivery_method=method,
    )
    db.session.add(record)
    db.session.commit()

    shown_code = None
    if mail_ok:
        sent, reason = send_email(
            user.email,
            "Verify your SmartCity Connect account",
            f"Your verification code is {code}. It expires in 15 minutes.",
        )
        if sent:
            flash("A verification code was sent to your email address.", "success")
        else:
            record.delivery_method = "dev_screen"
            db.session.commit()
            shown_code = code
            flash(reason + " Showing a development-only code instead.", "error")
    else:
        shown_code = code
        flash(
            "Email delivery is not configured. Use the development-only code shown on this page.",
            "info",
        )
    return record, shown_code, method


@auth_bp.route("/welcome")
def welcome():
    if g.current_user.is_authenticated and g.current_user.email_verified:
        return redirect(url_for("complaints.home_redirect"))
    return render_template("welcome.html")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if g.current_user.is_authenticated:
        return redirect(url_for("complaints.home_redirect"))

    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        errors = []
        if len(full_name) < 2:
            errors.append("Please enter your full name.")
        if "@" not in email or "." not in email:
            errors.append("Please enter a valid email address.")
        if password != confirm:
            errors.append("Passwords do not match.")
        pwd_error = strong_password(password)
        if pwd_error:
            errors.append(pwd_error)
        if User.query.filter_by(email=email).first():
            errors.append("That email is already registered. Try logging in.")

        if errors:
            for item in errors:
                flash(item, "error")
            return render_template("signup.html")

        user = User(full_name=full_name, email=email, role="citizen", email_verified=False)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        session.clear()
        session["user_id"] = user.id
        session.permanent = True
        _, code, _method = _issue_verification(user)
        if code:
            session["dev_otp"] = code
        session["pending_verify_user"] = user.id
        return redirect(url_for("auth.verify_email"))

    return render_template("signup.html")


@auth_bp.route("/verify-email", methods=["GET", "POST"])
def verify_email():
    user = g.current_user if g.current_user.is_authenticated else None
    if user is None:
        pending_id = session.get("pending_verify_user")
        user = db.session.get(User, pending_id) if pending_id else None
    if user is None:
        flash("Please sign up or log in first.", "error")
        return redirect(url_for("auth.signup"))
    if user.email_verified:
        return redirect(url_for("complaints.home_redirect"))

    latest = (
        EmailVerification.query.filter_by(user_id=user.id)
        .order_by(EmailVerification.created_at.desc())
        .first()
    )
    shown_code = session.get("dev_otp")

    if request.method == "POST":
        if request.form.get("action") == "resend":
            _, code, method = _issue_verification(user)
            if method == "dev_screen" and code:
                session["dev_otp"] = code
            return redirect(url_for("auth.verify_email"))

        code = (request.form.get("code") or "").strip()
        if not latest or not latest.is_valid() or not check_password_hash(latest.code_hash, code):
            flash("That code is incorrect or has expired.", "error")
            return render_template(
                "verify_email.html",
                user=user,
                latest=latest,
                shown_code=shown_code,
                mail_configured=bool(current_app.config.get("MAIL_SERVER")),
            )
        latest.used = True
        user.email_verified = True
        db.session.commit()
        session["user_id"] = user.id
        session.pop("dev_otp", None)
        session.pop("pending_verify_user", None)
        flash("Your email is verified. Welcome to SmartCity Connect.", "success")
        return redirect(url_for("complaints.dashboard"))

    if latest and latest.delivery_method == "dev_screen" and not shown_code:
        # A code exists but we cannot show the original plaintext. Issue a fresh one.
        _, code, method = _issue_verification(user)
        if method == "dev_screen":
            session["dev_otp"] = code
            shown_code = code

    return render_template(
        "verify_email.html",
        user=user,
        latest=latest,
        shown_code=session.get("dev_otp"),
        mail_configured=bool(
            current_app.config.get("MAIL_SERVER") and current_app.config.get("MAIL_USERNAME")
        ),
    )


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if g.current_user.is_authenticated and g.current_user.email_verified:
        return redirect(url_for("complaints.home_redirect"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Incorrect email or password.", "error")
            return render_template("login.html")
        session.clear()
        session["user_id"] = user.id
        session.permanent = True
        if not user.email_verified:
            flash("Please verify your email before continuing.", "info")
            return redirect(url_for("auth.verify_email"))
        flash(f"Welcome back, {user.full_name.split()[0]}!", "success")
        if user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        if user.role == "worker":
            return redirect(url_for("admin.worker_dashboard"))
        return redirect(url_for("complaints.dashboard"))

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.welcome"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    shown_code = None
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if not user:
            flash("If that account exists, a reset option will be shown.", "info")
            return render_template("forgot_password.html", shown_code=None)

        PasswordReset.query.filter_by(user_id=user.id, used=False).update({"used": True})
        code = _create_code()
        mail_ok = bool(current_app.config.get("MAIL_SERVER") and current_app.config.get("MAIL_USERNAME"))
        method = "smtp" if mail_ok else "dev_screen"
        reset = PasswordReset(
            user_id=user.id,
            code_hash=generate_password_hash(code),
            expires_at=otp_expiry(20),
            delivery_method=method,
        )
        db.session.add(reset)
        db.session.commit()
        session["reset_user"] = user.id

        if mail_ok:
            sent, reason = send_email(
                user.email,
                "Reset your SmartCity Connect password",
                f"Your password reset code is {code}. It expires in 20 minutes.",
            )
            if sent:
                flash("A reset code was sent to your email.", "success")
            else:
                shown_code = code
                flash(reason + " Showing a development-only code instead.", "error")
        else:
            shown_code = code
            flash(
                "Email delivery is not configured. Local prototype: a development-only reset code is shown below.",
                "info",
            )
        return render_template("forgot_password.html", shown_code=shown_code, ready=True)

    return render_template("forgot_password.html", shown_code=None, ready=False)


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    user_id = session.get("reset_user")
    user = db.session.get(User, user_id) if user_id else None
    if request.method == "POST":
        if not user:
            flash("Start from the forgot password page.", "error")
            return redirect(url_for("auth.forgot_password"))
        code = (request.form.get("code") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        latest = (
            PasswordReset.query.filter_by(user_id=user.id)
            .order_by(PasswordReset.created_at.desc())
            .first()
        )
        error = strong_password(password)
        if password != confirm:
            flash("Passwords do not match.", "error")
        elif error:
            flash(error, "error")
        elif not latest or not latest.is_valid() or not check_password_hash(latest.code_hash, code):
            flash("That reset code is incorrect or has expired.", "error")
        else:
            latest.used = True
            user.set_password(password)
            db.session.commit()
            session.pop("reset_user", None)
            flash("Your password was updated. You can log in now.", "success")
            return redirect(url_for("auth.login"))
    return render_template("reset_password.html")

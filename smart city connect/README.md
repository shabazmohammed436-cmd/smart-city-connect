# SmartCity Connect

A college hackathon prototype for reporting and tracking local infrastructure problems.

**Website name:** SmartCity Connect  
**Tagline:** Report It. Track It. Improve Your City.

This is a student demonstration. It is **not** connected to real municipal authorities. Sample records are labelled **Demo data**.

## What this app does

Citizens can:

1. Create an account and verify it
2. Report a pothole, overflowing garbage, water leak, or broken streetlight
3. Add a photograph (camera or file upload)
4. Add a location (GPS or typed address)
5. Track complaint status
6. Read in-app notifications

Administrators can view all complaints, assign workers, change status, and upload resolution photos.

Workers can see assigned complaints, mark work in progress, and submit resolution evidence.

## Technology

- Python and Flask
- HTML, CSS, and vanilla JavaScript
- SQLite
- Pillow for photo watermarks
- Leaflet and OpenStreetMap for maps

## How to run (Windows, Cursor terminal)

Open a terminal in this project folder.

### 1. Create a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then activate again.

### 2. Install packages

```powershell
pip install -r requirements.txt
```

### 3. Create your configuration file

A local `.env` file is already included for hackathon use. If you need a fresh copy:

```powershell
copy .env.example .env
```

Change `SECRET_KEY` and the demo passwords if you share the laptop with other people.

### 4. Create demo accounts and sample complaints

```powershell
python -m flask --app app init-demo
```

This creates:

| Role | Email | Password (from `.env`) |
| --- | --- | --- |
| Administrator | admin@smartcity.local | ChangeThisAdmin123! |
| Worker | worker@smartcity.local | ChangeThisWorker123! |
| Citizen | citizen@smartcity.local | ChangeThisCitizen123! |

These accounts are already email-verified so you can log in immediately.

### 5. Start the website

```powershell
python -m flask --app app run
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

## How to test for the hackathon

1. Open the splash page, then the welcome page.
2. Log in as the demo citizen.
3. Submit a new complaint with a photo. You can deny camera/GPS and still upload a file and type an address.
4. Open **My Complaints** and confirm the new ID.
5. Log out, then log in as the administrator.
6. Assign the complaint to the demo worker and change the status.
7. Log in as the worker, upload a resolution photo, and submit evidence.
8. Log back in as the citizen and check notifications and the new status.

Do not say the sample complaints came from real residents or a real city office.

## Email verification

- If `MAIL_SERVER`, `MAIL_USERNAME`, and `MAIL_PASSWORD` are set, the app tries to send a 6-digit code.
- If they are empty, the app **does not pretend an email was sent**. It shows a labelled development-only code on the verification page.
- New accounts stay unverified until the correct code is entered.

## Password recovery

Same rule as email verification. With no SMTP settings, a development-only reset code is shown. That local shortcut is for the prototype only.

## Optional features that need extra setup

| Feature | Status without extra setup |
| --- | --- |
| SMTP email | Development-only on-screen codes |
| Nominatim reverse geocoding | Manual address entry |
| AI category/priority/summary | Clearly labelled unavailable |
| Browser push notifications | Not included; in-app notifications work |

To try reverse geocoding, set `NOMINATIM_ENABLED=1` and a contact `NOMINATIM_USER_AGENT`. Follow OpenStreetMap usage policy.

## Security notes for a beginner

- Passwords and OTPs are stored as hashes, not plain text.
- Admin and worker pages are checked on the server, not only hidden in the menu.
- Citizens cannot change official status or upload resolution evidence.
- Uploaded photos are served only to the owner, assigned worker, or admin.
- CSRF protection is enabled on forms.

**Local development:** `SESSION_COOKIE_SECURE=0` because `http://127.0.0.1` is not HTTPS.  
**If you ever put this on a public HTTPS site:** set a long random `SECRET_KEY`, change all demo passwords, and set `SESSION_COOKIE_SECURE=1`.

## Project files

- `app.py` — starts Flask
- `auth.py` — sign up, login, verification, password reset
- `complaints.py` — citizen reports, tracking, map, photo serving
- `admin.py` — administrator and worker dashboards
- `database.py` — SQLite tables
- `notifications.py` — in-app alerts
- `seed.py` — demo accounts and fictional sample complaints
- `templates/` — HTML pages
- `static/` — CSS and JavaScript

## Demo versus real data

Sample complaints created by `init-demo` have `is_demo = true` and show a **Demo data** tag. Complaints you submit while logged in as a new citizen are stored as normal user submissions, still only inside this local prototype.

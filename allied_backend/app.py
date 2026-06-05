"""
Allied Industries – Flask Backend
Handles: Contact enquiries, Career applications, Admin dashboard
"""
from dotenv import load_dotenv
load_dotenv()
from flask_cors import CORS
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import os
import re

# ─────────────────────────────────────────
#  APP SETUP
# ─────────────────────────────────────────
app = Flask(__name__)
CORS(app)   
app.config.update(
    SECRET_KEY                = os.environ.get("SECRET_KEY", "change-this-in-production-please"),
    SQLALCHEMY_DATABASE_URI   = os.environ.get("DATABASE_URL", "sqlite:///allied.db"),
    SQLALCHEMY_TRACK_MODIFICATIONS = False,

    # ── Email (Gmail SMTP) ──
    # Set these as environment variables on your server, or edit directly here.
    MAIL_SERVER   = os.environ.get("MAIL_SERVER",   "smtp.gmail.com"),
    MAIL_PORT     = int(os.environ.get("MAIL_PORT", 587)),
    MAIL_USE_TLS  = True,
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "info@alliedindustries.in"),
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "your-app-password-here"),
    MAIL_DEFAULT_SENDER = ("Allied Industries", os.environ.get("MAIL_USERNAME", "info@alliedindustries.in")),
    ADMIN_NOTIFY_EMAIL  = os.environ.get("ADMIN_NOTIFY_EMAIL", "info@alliedindustries.in"),
)

db   = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = "admin_login"


# ─────────────────────────────────────────
#  MODELS
# ─────────────────────────────────────────

class Enquiry(db.Model):
    """Contact / product enquiry form submission"""
    __tablename__ = "enquiries"

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(120), nullable=False)
    email       = db.Column(db.String(180), nullable=False)
    phone       = db.Column(db.String(30))
    company     = db.Column(db.String(120))
    product     = db.Column(db.String(120))
    message     = db.Column(db.Text)
    status      = db.Column(db.String(20), default="new")   # new | read | replied
    ip_address  = db.Column(db.String(45))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id":         self.id,
            "name":       self.name,
            "email":      self.email,
            "phone":      self.phone or "—",
            "company":    self.company or "—",
            "product":    self.product or "—",
            "message":    self.message or "—",
            "status":     self.status,
            "created_at": self.created_at.strftime("%d %b %Y, %I:%M %p"),
        }


class Application(db.Model):
    """Career / job application form submission"""
    __tablename__ = "applications"

    id          = db.Column(db.Integer, primary_key=True)
    first_name  = db.Column(db.String(80),  nullable=False)
    last_name   = db.Column(db.String(80),  nullable=False)
    email       = db.Column(db.String(180), nullable=False)
    phone       = db.Column(db.String(30))
    position    = db.Column(db.String(120), nullable=False)
    cv_text     = db.Column(db.Text)
    status      = db.Column(db.String(20), default="new")   # new | reviewed | shortlisted | rejected
    ip_address  = db.Column(db.String(45))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def to_dict(self):
        return {
            "id":         self.id,
            "full_name":  self.full_name,
            "email":      self.email,
            "phone":      self.phone or "—",
            "position":   self.position,
            "cv_text":    self.cv_text or "—",
            "status":     self.status,
            "created_at": self.created_at.strftime("%d %b %Y, %I:%M %p"),
        }


class AdminUser(UserMixin, db.Model):
    """Admin login credentials"""
    __tablename__ = "admin_users"

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(60), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return AdminUser.query.get(int(user_id))


# ─────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────

def is_valid_email(email):
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email)

def send_email_safe(subject, recipients, html_body):
    """Send email; silently log on failure so forms still save."""
    try:
        msg = Message(subject=subject, recipients=recipients, html=html_body)
        mail.send(msg)
        return True
    except Exception as e:
        app.logger.warning(f"Email send failed: {e}")
        return False

def get_client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr)


# ─────────────────────────────────────────
#  API – CONTACT ENQUIRY
# ─────────────────────────────────────────

@app.route("/api/enquiry", methods=["POST"])
def submit_enquiry():
    data = request.get_json(silent=True) or request.form.to_dict()

    # Validate required fields
    name  = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    if not name or not email:
        return jsonify({"ok": False, "error": "Name and email are required."}), 400
    if not is_valid_email(email):
        return jsonify({"ok": False, "error": "Please enter a valid email address."}), 400

    # Save to DB
    enquiry = Enquiry(
        name       = name,
        email      = email,
        phone      = (data.get("phone") or "").strip() or None,
        company    = (data.get("company") or "").strip() or None,
        product    = (data.get("product") or "").strip() or None,
        message    = (data.get("message") or "").strip() or None,
        ip_address = get_client_ip(),
    )
    db.session.add(enquiry)
    db.session.commit()

    # Email to admin
    send_email_safe(
        subject    = f"[Allied Industries] New Enquiry from {name}",
        recipients = [app.config["ADMIN_NOTIFY_EMAIL"]],
        html_body  = render_enquiry_email(enquiry, admin=True),
    )
    # Auto-reply to customer
    send_email_safe(
        subject    = "We received your enquiry – Allied Industries",
        recipients = [email],
        html_body  = render_enquiry_email(enquiry, admin=False),
    )

    return jsonify({"ok": True, "message": "Enquiry submitted successfully! We'll respond within 24 hours."})


# ─────────────────────────────────────────
#  API – CAREER APPLICATION
# ─────────────────────────────────────────

@app.route("/api/application", methods=["POST"])
def submit_application():
    data = request.get_json(silent=True) or request.form.to_dict()

    first_name = (data.get("first_name") or "").strip()
    last_name  = (data.get("last_name")  or "").strip()
    email      = (data.get("email")      or "").strip()
    position   = (data.get("position")   or "").strip()

    if not first_name or not email or not position:
        return jsonify({"ok": False, "error": "First name, email and position are required."}), 400
    if not is_valid_email(email):
        return jsonify({"ok": False, "error": "Please enter a valid email address."}), 400

    app_obj = Application(
        first_name = first_name,
        last_name  = last_name,
        email      = email,
        phone      = (data.get("phone")    or "").strip() or None,
        position   = position,
        cv_text    = (data.get("cv_text")  or "").strip() or None,
        ip_address = get_client_ip(),
    )
    db.session.add(app_obj)
    db.session.commit()

    send_email_safe(
        subject    = f"[Allied Industries] New Application – {position} ({first_name} {last_name})",
        recipients = [app.config["ADMIN_NOTIFY_EMAIL"]],
        html_body  = render_application_email(app_obj, admin=True),
    )
    send_email_safe(
        subject    = "Application received – Allied Industries",
        recipients = [email],
        html_body  = render_application_email(app_obj, admin=False),
    )

    return jsonify({"ok": True, "message": "Application submitted! We'll be in touch shortly."})


# ─────────────────────────────────────────
#  ADMIN – LOGIN / LOGOUT
# ─────────────────────────────────────────

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for("admin_dashboard"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = AdminUser.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("admin_dashboard"))
        error = "Invalid username or password."

    return render_template_string(LOGIN_HTML, error=error)


@app.route("/admin/logout")
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for("admin_login"))


# ─────────────────────────────────────────
#  ADMIN – DASHBOARD
# ─────────────────────────────────────────

@app.route("/admin")
@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    eq_new   = Enquiry.query.filter_by(status="new").count()
    eq_total = Enquiry.query.count()
    ap_new   = Application.query.filter_by(status="new").count()
    ap_total = Application.query.count()

    recent_enquiries   = Enquiry.query.order_by(Enquiry.created_at.desc()).limit(5).all()
    recent_applications = Application.query.order_by(Application.created_at.desc()).limit(5).all()

    return render_template_string(DASHBOARD_HTML,
        eq_new=eq_new, eq_total=eq_total,
        ap_new=ap_new, ap_total=ap_total,
        recent_enquiries=recent_enquiries,
        recent_applications=recent_applications,
    )


# ─────────────────────────────────────────
#  ADMIN – ENQUIRIES LIST
# ─────────────────────────────────────────

@app.route("/admin/enquiries")
@login_required
def admin_enquiries():
    status = request.args.get("status", "all")
    q = Enquiry.query.order_by(Enquiry.created_at.desc())
    if status != "all":
        q = q.filter_by(status=status)
    enquiries = q.all()
    return render_template_string(ENQUIRIES_HTML, enquiries=enquiries, filter=status)


@app.route("/admin/enquiries/<int:eid>")
@login_required
def admin_enquiry_detail(eid):
    e = Enquiry.query.get_or_404(eid)
    if e.status == "new":
        e.status = "read"
        db.session.commit()
    return render_template_string(ENQUIRY_DETAIL_HTML, e=e)


@app.route("/admin/enquiries/<int:eid>/status", methods=["POST"])
@login_required
def admin_enquiry_status(eid):
    e = Enquiry.query.get_or_404(eid)
    e.status = request.form.get("status", e.status)
    db.session.commit()
    return redirect(url_for("admin_enquiry_detail", eid=eid))


@app.route("/admin/enquiries/<int:eid>/delete", methods=["POST"])
@login_required
def admin_enquiry_delete(eid):
    e = Enquiry.query.get_or_404(eid)
    db.session.delete(e)
    db.session.commit()
    return redirect(url_for("admin_enquiries"))


# ─────────────────────────────────────────
#  ADMIN – APPLICATIONS LIST
# ─────────────────────────────────────────

@app.route("/admin/applications")
@login_required
def admin_applications():
    status = request.args.get("status", "all")
    q = Application.query.order_by(Application.created_at.desc())
    if status != "all":
        q = q.filter_by(status=status)
    applications = q.all()
    return render_template_string(APPLICATIONS_HTML, applications=applications, filter=status)


@app.route("/admin/applications/<int:aid>")
@login_required
def admin_application_detail(aid):
    a = Application.query.get_or_404(aid)
    if a.status == "new":
        a.status = "reviewed"
        db.session.commit()
    return render_template_string(APPLICATION_DETAIL_HTML, a=a)


@app.route("/admin/applications/<int:aid>/status", methods=["POST"])
@login_required
def admin_application_status(aid):
    a = Application.query.get_or_404(aid)
    a.status = request.form.get("status", a.status)
    db.session.commit()
    return redirect(url_for("admin_application_detail", aid=aid))


@app.route("/admin/applications/<int:aid>/delete", methods=["POST"])
@login_required
def admin_application_delete(aid):
    a = Application.query.get_or_404(aid)
    db.session.delete(a)
    db.session.commit()
    return redirect(url_for("admin_applications"))


# ─────────────────────────────────────────
#  API – JSON ENDPOINTS (for dashboard stats)
# ─────────────────────────────────────────

@app.route("/api/admin/stats")
@login_required
def api_stats():
    return jsonify({
        "enquiries": {
            "total":     Enquiry.query.count(),
            "new":       Enquiry.query.filter_by(status="new").count(),
            "read":      Enquiry.query.filter_by(status="read").count(),
            "replied":   Enquiry.query.filter_by(status="replied").count(),
        },
        "applications": {
            "total":       Application.query.count(),
            "new":         Application.query.filter_by(status="new").count(),
            "reviewed":    Application.query.filter_by(status="reviewed").count(),
            "shortlisted": Application.query.filter_by(status="shortlisted").count(),
            "rejected":    Application.query.filter_by(status="rejected").count(),
        },
    })


# ─────────────────────────────────────────
#  EMAIL TEMPLATES
# ─────────────────────────────────────────

def render_enquiry_email(e, admin=True):
    if admin:
        subject_line = f"New enquiry from {e.name}"
        body = f"""
        <p>A new product enquiry has been submitted on the website.</p>
        <table style="border-collapse:collapse;width:100%;font-family:sans-serif;font-size:14px">
          <tr><td style="padding:8px 12px;background:#f5f0eb;font-weight:600;width:160px">Name</td><td style="padding:8px 12px;border-bottom:1px solid #e8e0d8">{e.name}</td></tr>
          <tr><td style="padding:8px 12px;background:#f5f0eb;font-weight:600">Email</td><td style="padding:8px 12px;border-bottom:1px solid #e8e0d8"><a href="mailto:{e.email}">{e.email}</a></td></tr>
          <tr><td style="padding:8px 12px;background:#f5f0eb;font-weight:600">Phone</td><td style="padding:8px 12px;border-bottom:1px solid #e8e0d8">{e.phone or '—'}</td></tr>
          <tr><td style="padding:8px 12px;background:#f5f0eb;font-weight:600">Company</td><td style="padding:8px 12px;border-bottom:1px solid #e8e0d8">{e.company or '—'}</td></tr>
          <tr><td style="padding:8px 12px;background:#f5f0eb;font-weight:600">Product</td><td style="padding:8px 12px;border-bottom:1px solid #e8e0d8">{e.product or '—'}</td></tr>
          <tr><td style="padding:8px 12px;background:#f5f0eb;font-weight:600;vertical-align:top">Message</td><td style="padding:8px 12px">{e.message or '—'}</td></tr>
        </table>
        <p style="margin-top:20px"><a href="http://yoursite.com/admin/enquiries/{e.id}" style="background:#b87333;color:white;padding:10px 20px;border-radius:4px;text-decoration:none;font-weight:600">View in Admin Panel →</a></p>
        """
    else:
        body = f"""
        <p>Dear {e.name},</p>
        <p>Thank you for reaching out to <strong>Allied Industries</strong>. We have received your enquiry and our team will get back to you within <strong>24 business hours</strong>.</p>
        <p>Here's a summary of what you submitted:</p>
        <table style="border-collapse:collapse;width:100%;font-family:sans-serif;font-size:14px">
          <tr><td style="padding:8px 12px;background:#f5f0eb;font-weight:600;width:140px">Product</td><td style="padding:8px 12px;border-bottom:1px solid #e8e0d8">{e.product or '—'}</td></tr>
          <tr><td style="padding:8px 12px;background:#f5f0eb;font-weight:600">Message</td><td style="padding:8px 12px">{e.message or '—'}</td></tr>
        </table>
        <p style="margin-top:20px">If you need to reach us urgently:</p>
        <p>📞 <strong>+91 11 41845231</strong> / <strong>+91 98116 97031</strong> (Mr. Dinesh)<br>
        ✉️ <a href="mailto:info@alliedindustries.in">info@alliedindustries.in</a></p>
        """
    return _email_wrapper(subject_line if admin else "We received your enquiry", body)


def render_application_email(a, admin=True):
    if admin:
        subject_line = f"New application – {a.position}"
        body = f"""
        <p>A new job application has been submitted.</p>
        <table style="border-collapse:collapse;width:100%;font-family:sans-serif;font-size:14px">
          <tr><td style="padding:8px 12px;background:#f5f0eb;font-weight:600;width:160px">Name</td><td style="padding:8px 12px;border-bottom:1px solid #e8e0d8">{a.full_name}</td></tr>
          <tr><td style="padding:8px 12px;background:#f5f0eb;font-weight:600">Email</td><td style="padding:8px 12px;border-bottom:1px solid #e8e0d8"><a href="mailto:{a.email}">{a.email}</a></td></tr>
          <tr><td style="padding:8px 12px;background:#f5f0eb;font-weight:600">Phone</td><td style="padding:8px 12px;border-bottom:1px solid #e8e0d8">{a.phone or '—'}</td></tr>
          <tr><td style="padding:8px 12px;background:#f5f0eb;font-weight:600">Position</td><td style="padding:8px 12px;border-bottom:1px solid #e8e0d8"><strong>{a.position}</strong></td></tr>
          <tr><td style="padding:8px 12px;background:#f5f0eb;font-weight:600;vertical-align:top">CV / Note</td><td style="padding:8px 12px;white-space:pre-wrap">{a.cv_text or '—'}</td></tr>
        </table>
        <p style="margin-top:20px"><a href="http://yoursite.com/admin/applications/{a.id}" style="background:#b87333;color:white;padding:10px 20px;border-radius:4px;text-decoration:none;font-weight:600">View in Admin Panel →</a></p>
        """
    else:
        body = f"""
        <p>Dear {a.first_name},</p>
        <p>Thank you for applying to <strong>Allied Industries</strong> for the <strong>{a.position}</strong> role. We have received your application and will review it carefully.</p>
        <p>If your profile matches our requirements, our team will contact you to schedule an interview.</p>
        <p style="margin-top:20px">For any queries: <a href="mailto:info@alliedindustries.in">info@alliedindustries.in</a></p>
        """
    return _email_wrapper(subject_line if admin else "Application received", body)


def _email_wrapper(title, body):
    return f"""
    <!DOCTYPE html><html><body style="margin:0;padding:0;background:#f5f0eb;font-family:'Helvetica Neue',Arial,sans-serif">
    <div style="max-width:600px;margin:40px auto;background:white;border-radius:8px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08)">
      <div style="background:#1a1f2e;padding:28px 36px;display:flex;align-items:center">
        <div style="width:8px;height:8px;background:#b87333;border-radius:50%;margin-right:10px"></div>
        <span style="font-family:Georgia,serif;font-size:22px;letter-spacing:4px;color:white"><span style="color:#b87333">ALLIED</span> INDUSTRIES</span>
      </div>
      <div style="padding:36px;color:#3d4252;line-height:1.7;font-size:15px">
        <h2 style="font-family:Georgia,serif;color:#111318;margin-top:0">{title}</h2>
        {body}
      </div>
      <div style="background:#1a1f2e;padding:20px 36px;text-align:center">
        <p style="color:rgba(255,255,255,0.4);font-size:12px;margin:0">
          A-15, Mayapuri Industrial Area, Phase-2, Delhi – 110 064, India<br>
          +91 11 41845231 &nbsp;|&nbsp; info@alliedindustries.in
        </p>
      </div>
    </div>
    </body></html>
    """


# ─────────────────────────────────────────
#  SHARED CSS FOR ADMIN PAGES
# ─────────────────────────────────────────

ADMIN_CSS = """
<style>
  *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
  :root{
    --copper:#b87333;--copper-l:#d4956a;--copper-d:#8a5220;
    --steel:#1a1f2e;--steel-m:#2d3449;--steel-l:#4a5270;
    --cream:#f8f5f0;--warm:#fdfbf8;
    --td:#111318;--tm:#3d4252;--tl:#6b7194;
    --border:rgba(184,115,51,0.18);
  }
  body{font-family:'Segoe UI',system-ui,sans-serif;background:#f0ece6;color:var(--td);min-height:100vh}

  /* SIDEBAR */
  .layout{display:flex;min-height:100vh}
  .sidebar{width:240px;background:var(--steel);flex-shrink:0;display:flex;flex-direction:column;position:fixed;top:0;left:0;bottom:0;z-index:100}
  .sidebar-logo{padding:24px 20px 16px;border-bottom:1px solid rgba(184,115,51,0.2)}
  .sidebar-logo span{font-family:Georgia,serif;font-size:1.1rem;letter-spacing:3px;color:white}
  .sidebar-logo span b{color:var(--copper)}
  .sidebar-nav{padding:12px 0;flex:1}
  .nav-item{display:flex;align-items:center;gap:10px;padding:11px 20px;color:rgba(255,255,255,0.6);
    text-decoration:none;font-size:0.875rem;font-weight:500;transition:0.2s;border-left:3px solid transparent}
  .nav-item:hover{background:rgba(184,115,51,0.1);color:var(--copper-l);border-left-color:var(--copper)}
  .nav-item.active{background:rgba(184,115,51,0.15);color:var(--copper-l);border-left-color:var(--copper)}
  .nav-item .icon{width:18px;text-align:center;font-size:1rem}
  .sidebar-footer{padding:16px 20px;border-top:1px solid rgba(255,255,255,0.07)}
  .sidebar-footer a{color:rgba(255,255,255,0.4);font-size:0.78rem;text-decoration:none}
  .sidebar-footer a:hover{color:var(--copper-l)}

  /* MAIN */
  .main{margin-left:240px;flex:1;display:flex;flex-direction:column}
  .topbar{background:white;border-bottom:1px solid var(--border);padding:0 32px;
    height:60px;display:flex;align-items:center;justify-content:space-between;
    position:sticky;top:0;z-index:50;box-shadow:0 1px 4px rgba(0,0,0,0.04)}
  .topbar h1{font-size:1.1rem;font-weight:600;color:var(--td)}
  .topbar-right{display:flex;align-items:center;gap:16px;font-size:0.85rem;color:var(--tl)}
  .content{padding:32px;flex:1}

  /* CARDS */
  .stats-row{display:grid;grid-template-columns:repeat(4,1fr);gap:20px;margin-bottom:32px}
  .stat-card{background:white;border-radius:10px;padding:24px;border:1px solid var(--border);
    box-shadow:0 2px 8px rgba(0,0,0,0.04)}
  .stat-card .label{font-size:0.72rem;letter-spacing:0.1em;text-transform:uppercase;
    color:var(--tl);font-weight:600;margin-bottom:8px}
  .stat-card .value{font-size:2.4rem;font-weight:700;color:var(--td);line-height:1}
  .stat-card .sub{font-size:0.78rem;color:var(--tl);margin-top:4px}
  .stat-card.highlight .value{color:var(--copper)}

  /* TABLE */
  .table-card{background:white;border-radius:10px;border:1px solid var(--border);
    box-shadow:0 2px 8px rgba(0,0,0,0.04);overflow:hidden;margin-bottom:28px}
  .table-card-header{padding:18px 24px;border-bottom:1px solid var(--border);
    display:flex;align-items:center;justify-content:space-between}
  .table-card-header h2{font-size:0.95rem;font-weight:600;color:var(--td)}
  table{width:100%;border-collapse:collapse;font-size:0.875rem}
  th{background:#faf7f3;padding:11px 16px;text-align:left;font-size:0.72rem;
    letter-spacing:0.08em;text-transform:uppercase;color:var(--tl);font-weight:600;
    border-bottom:1px solid var(--border)}
  td{padding:12px 16px;border-bottom:1px solid rgba(184,115,51,0.08);color:var(--tm);vertical-align:middle}
  tr:last-child td{border-bottom:none}
  tr:hover td{background:#fdf9f5}

  /* BADGES */
  .badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:0.72rem;font-weight:600;letter-spacing:0.04em;text-transform:uppercase}
  .badge-new{background:#fff3e0;color:#b87333}
  .badge-read{background:#e8f5e9;color:#2e7d32}
  .badge-replied{background:#e3f2fd;color:#1565c0}
  .badge-reviewed{background:#f3e5f5;color:#6a1b9a}
  .badge-shortlisted{background:#e8f5e9;color:#2e7d32}
  .badge-rejected{background:#ffebee;color:#c62828}

  /* BUTTONS */
  .btn{display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:5px;
    font-size:0.82rem;font-weight:600;cursor:pointer;border:none;text-decoration:none;transition:0.2s}
  .btn-primary{background:var(--copper);color:white}
  .btn-primary:hover{background:var(--copper-d)}
  .btn-outline{background:white;color:var(--tm);border:1px solid var(--border)}
  .btn-outline:hover{border-color:var(--copper);color:var(--copper)}
  .btn-danger{background:#ffebee;color:#c62828;border:1px solid #ffcdd2}
  .btn-danger:hover{background:#c62828;color:white}
  .btn-sm{padding:5px 12px;font-size:0.78rem}

  /* DETAIL PAGE */
  .detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}
  .detail-field{background:#faf7f3;border-radius:6px;padding:14px 16px}
  .detail-field .key{font-size:0.72rem;letter-spacing:0.1em;text-transform:uppercase;
    color:var(--tl);font-weight:600;margin-bottom:4px}
  .detail-field .val{font-size:0.9rem;color:var(--td)}
  .detail-full{grid-column:span 2}
  .message-box{background:#faf7f3;border-radius:6px;padding:16px;
    font-size:0.9rem;color:var(--tm);line-height:1.7;white-space:pre-wrap;margin-bottom:24px}

  /* FORM */
  .form-card{background:white;border-radius:10px;border:1px solid var(--border);padding:28px;margin-bottom:24px}
  select,input[type=text],input[type=password]{padding:8px 12px;border:1px solid var(--border);
    border-radius:5px;font-size:0.875rem;background:white;color:var(--td);outline:none}
  select:focus,input:focus{border-color:var(--copper);box-shadow:0 0 0 3px rgba(184,115,51,0.1)}

  /* FILTERS */
  .filters{display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap}
  .filter-btn{padding:6px 14px;border-radius:20px;font-size:0.78rem;font-weight:600;
    cursor:pointer;text-decoration:none;border:1px solid var(--border);
    background:white;color:var(--tl);transition:0.2s}
  .filter-btn:hover,.filter-btn.active{background:var(--copper);color:white;border-color:var(--copper)}

  /* ALERTS */
  .alert{padding:12px 18px;border-radius:6px;font-size:0.875rem;margin-bottom:20px;border-left:4px solid}
  .alert-info{background:#e8f4fd;border-color:#1976d2;color:#0d47a1}

  /* LOGIN */
  .login-wrap{min-height:100vh;display:flex;align-items:center;justify-content:center;background:#f0ece6}
  .login-box{background:white;border-radius:12px;padding:48px 40px;width:380px;
    box-shadow:0 8px 32px rgba(0,0,0,0.08);border:1px solid var(--border)}
  .login-box .logo-row{text-align:center;margin-bottom:32px}
  .login-box label{display:block;font-size:0.75rem;letter-spacing:0.1em;text-transform:uppercase;
    font-weight:600;color:var(--tl);margin-bottom:6px}
  .login-box input{width:100%;margin-bottom:16px}
  .error-msg{color:#c62828;font-size:0.82rem;background:#ffebee;padding:10px 14px;
    border-radius:5px;margin-bottom:16px;border-left:3px solid #c62828}

  @media(max-width:768px){
    .sidebar{transform:translateX(-100%)}
    .main{margin-left:0}
    .stats-row{grid-template-columns:1fr 1fr}
    .detail-grid{grid-template-columns:1fr}
    .detail-full{grid-column:span 1}
  }
</style>
"""


def sidebar(active="dashboard"):
    items = [
        ("dashboard",    "📊", "Dashboard",    "/admin/dashboard"),
        ("enquiries",    "📩", "Enquiries",     "/admin/enquiries"),
        ("applications", "👤", "Applications",  "/admin/applications"),
    ]
    links = ""
    for key, icon, label, href in items:
        cls = "active" if active == key else ""
        # Show badge for unread counts
        badge = ""
        if key == "enquiries":
            n = Enquiry.query.filter_by(status="new").count()
            if n: badge = f'<span style="margin-left:auto;background:var(--copper);color:white;border-radius:10px;padding:1px 7px;font-size:0.7rem">{n}</span>'
        if key == "applications":
            n = Application.query.filter_by(status="new").count()
            if n: badge = f'<span style="margin-left:auto;background:#1976d2;color:white;border-radius:10px;padding:1px 7px;font-size:0.7rem">{n}</span>'
        links += f'<a href="{href}" class="nav-item {cls}"><span class="icon">{icon}</span>{label}{badge}</a>'

    return f"""
    <div class="sidebar">
      <div class="sidebar-logo">
        <span><b>ALLIED</b> INDUSTRIES</span><br>
        <span style="font-size:0.7rem;color:rgba(255,255,255,0.35);letter-spacing:1px">ADMIN PANEL</span>
      </div>
      <nav class="sidebar-nav">{links}</nav>
      <div class="sidebar-footer">
        <a href="/admin/logout">⎋ &nbsp;Logout ({current_user.username})</a>
      </div>
    </div>
    """


# ─────────────────────────────────────────
#  HTML TEMPLATES
# ─────────────────────────────────────────

LOGIN_HTML = """<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Admin Login – Allied Industries</title>""" + ADMIN_CSS + """
</head><body>
<div class="login-wrap">
  <div class="login-box">
    <div class="logo-row">
      <div style="font-family:Georgia,serif;font-size:1.3rem;letter-spacing:4px;color:#1a1f2e">
        <span style="color:#b87333">ALLIED</span> INDUSTRIES
      </div>
      <div style="font-size:0.75rem;color:#6b7194;margin-top:6px;letter-spacing:2px;text-transform:uppercase">Admin Panel</div>
    </div>
    {% if error %}<div class="error-msg">{{ error }}</div>{% endif %}
    <form method="POST">
      <label>Username</label>
      <input type="text" name="username" placeholder="admin" autofocus>
      <label>Password</label>
      <input type="password" name="password" placeholder="••••••••">
      <button type="submit" class="btn btn-primary" style="width:100%;justify-content:center;padding:11px">
        Sign In →
      </button>
    </form>
  </div>
</div>
</body></html>"""


DASHBOARD_HTML = """<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Dashboard – Allied Industries Admin</title>""" + ADMIN_CSS + """
</head><body>
<div class="layout">
  {{ sidebar|safe }}
  <div class="main">
    <div class="topbar">
      <h1>Dashboard</h1>
      <div class="topbar-right">
        <span>{{ now }}</span>
        <a href="/admin/logout" class="btn btn-outline btn-sm">Logout</a>
      </div>
    </div>
    <div class="content">
      <div class="stats-row">
        <div class="stat-card highlight">
          <div class="label">New Enquiries</div>
          <div class="value">{{ eq_new }}</div>
          <div class="sub">{{ eq_total }} total</div>
        </div>
        <div class="stat-card">
          <div class="label">Total Enquiries</div>
          <div class="value">{{ eq_total }}</div>
          <div class="sub">All time</div>
        </div>
        <div class="stat-card highlight">
          <div class="label">New Applications</div>
          <div class="value">{{ ap_new }}</div>
          <div class="sub">{{ ap_total }} total</div>
        </div>
        <div class="stat-card">
          <div class="label">Total Applications</div>
          <div class="value">{{ ap_total }}</div>
          <div class="sub">All time</div>
        </div>
      </div>

      <div class="table-card">
        <div class="table-card-header">
          <h2>📩 Recent Enquiries</h2>
          <a href="/admin/enquiries" class="btn btn-outline btn-sm">View All</a>
        </div>
        <table>
          <thead><tr><th>Name</th><th>Email</th><th>Product</th><th>Status</th><th>Date</th><th></th></tr></thead>
          <tbody>
          {% for e in recent_enquiries %}
          <tr>
            <td><strong>{{ e.name }}</strong></td>
            <td>{{ e.email }}</td>
            <td>{{ e.product or '—' }}</td>
            <td><span class="badge badge-{{ e.status }}">{{ e.status }}</span></td>
            <td style="color:#6b7194;font-size:0.8rem">{{ e.created_at.strftime('%d %b %Y') }}</td>
            <td><a href="/admin/enquiries/{{ e.id }}" class="btn btn-outline btn-sm">View</a></td>
          </tr>
          {% else %}
          <tr><td colspan="6" style="text-align:center;color:#6b7194;padding:28px">No enquiries yet.</td></tr>
          {% endfor %}
          </tbody>
        </table>
      </div>

      <div class="table-card">
        <div class="table-card-header">
          <h2>👤 Recent Applications</h2>
          <a href="/admin/applications" class="btn btn-outline btn-sm">View All</a>
        </div>
        <table>
          <thead><tr><th>Name</th><th>Email</th><th>Position</th><th>Status</th><th>Date</th><th></th></tr></thead>
          <tbody>
          {% for a in recent_applications %}
          <tr>
            <td><strong>{{ a.full_name }}</strong></td>
            <td>{{ a.email }}</td>
            <td>{{ a.position }}</td>
            <td><span class="badge badge-{{ a.status }}">{{ a.status }}</span></td>
            <td style="color:#6b7194;font-size:0.8rem">{{ a.created_at.strftime('%d %b %Y') }}</td>
            <td><a href="/admin/applications/{{ a.id }}" class="btn btn-outline btn-sm">View</a></td>
          </tr>
          {% else %}
          <tr><td colspan="6" style="text-align:center;color:#6b7194;padding:28px">No applications yet.</td></tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>
</body></html>"""


ENQUIRIES_HTML = """<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Enquiries – Allied Industries Admin</title>""" + ADMIN_CSS + """
</head><body>
<div class="layout">
  {{ sidebar|safe }}
  <div class="main">
    <div class="topbar">
      <h1>📩 Enquiries</h1>
      <div class="topbar-right">
        <span>{{ enquiries|length }} showing</span>
      </div>
    </div>
    <div class="content">
      <div class="filters">
        <a href="/admin/enquiries" class="filter-btn {% if filter=='all' %}active{% endif %}">All</a>
        <a href="/admin/enquiries?status=new" class="filter-btn {% if filter=='new' %}active{% endif %}">New</a>
        <a href="/admin/enquiries?status=read" class="filter-btn {% if filter=='read' %}active{% endif %}">Read</a>
        <a href="/admin/enquiries?status=replied" class="filter-btn {% if filter=='replied' %}active{% endif %}">Replied</a>
      </div>
      <div class="table-card">
        <table>
          <thead><tr><th>#</th><th>Name</th><th>Email</th><th>Company</th><th>Product</th><th>Status</th><th>Date</th><th></th></tr></thead>
          <tbody>
          {% for e in enquiries %}
          <tr>
            <td style="color:#6b7194">{{ e.id }}</td>
            <td><strong>{{ e.name }}</strong></td>
            <td>{{ e.email }}</td>
            <td>{{ e.company or '—' }}</td>
            <td style="font-size:0.82rem">{{ e.product or '—' }}</td>
            <td><span class="badge badge-{{ e.status }}">{{ e.status }}</span></td>
            <td style="color:#6b7194;font-size:0.8rem">{{ e.created_at.strftime('%d %b %Y') }}</td>
            <td><a href="/admin/enquiries/{{ e.id }}" class="btn btn-outline btn-sm">View</a></td>
          </tr>
          {% else %}
          <tr><td colspan="8" style="text-align:center;color:#6b7194;padding:32px">No enquiries found.</td></tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>
</body></html>"""


ENQUIRY_DETAIL_HTML = """<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Enquiry #{{ e.id }} – Allied Industries Admin</title>""" + ADMIN_CSS + """
</head><body>
<div class="layout">
  {{ sidebar|safe }}
  <div class="main">
    <div class="topbar">
      <h1>Enquiry #{{ e.id }} — {{ e.name }}</h1>
      <div class="topbar-right">
        <a href="/admin/enquiries" class="btn btn-outline btn-sm">← Back</a>
      </div>
    </div>
    <div class="content">
      <div class="form-card">
        <div class="detail-grid">
          <div class="detail-field"><div class="key">Name</div><div class="val">{{ e.name }}</div></div>
          <div class="detail-field"><div class="key">Email</div><div class="val"><a href="mailto:{{ e.email }}" style="color:#b87333">{{ e.email }}</a></div></div>
          <div class="detail-field"><div class="key">Phone</div><div class="val">{{ e.phone or '—' }}</div></div>
          <div class="detail-field"><div class="key">Company</div><div class="val">{{ e.company or '—' }}</div></div>
          <div class="detail-field"><div class="key">Product Interest</div><div class="val">{{ e.product or '—' }}</div></div>
          <div class="detail-field"><div class="key">Submitted</div><div class="val">{{ e.created_at.strftime('%d %b %Y, %I:%M %p') }} UTC</div></div>
        </div>
        {% if e.message %}
        <div style="margin-bottom:8px;font-size:0.72rem;letter-spacing:0.1em;text-transform:uppercase;color:#6b7194;font-weight:600">Message</div>
        <div class="message-box">{{ e.message }}</div>
        {% endif %}

        <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
          <form method="POST" action="/admin/enquiries/{{ e.id }}/status" style="display:flex;gap:8px;align-items:center">
            <label style="font-size:0.82rem;font-weight:600;color:#6b7194">Status:</label>
            <select name="status">
              <option value="new"     {% if e.status=='new'     %}selected{% endif %}>New</option>
              <option value="read"    {% if e.status=='read'    %}selected{% endif %}>Read</option>
              <option value="replied" {% if e.status=='replied' %}selected{% endif %}>Replied</option>
            </select>
            <button type="submit" class="btn btn-primary btn-sm">Update</button>
          </form>
          <a href="mailto:{{ e.email }}" class="btn btn-outline btn-sm">✉ Reply by Email</a>
          <form method="POST" action="/admin/enquiries/{{ e.id }}/delete"
            onsubmit="return confirm('Delete this enquiry? This cannot be undone.')">
            <button type="submit" class="btn btn-danger btn-sm">🗑 Delete</button>
          </form>
        </div>
      </div>
    </div>
  </div>
</div>
</body></html>"""


APPLICATIONS_HTML = """<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Applications – Allied Industries Admin</title>""" + ADMIN_CSS + """
</head><body>
<div class="layout">
  {{ sidebar|safe }}
  <div class="main">
    <div class="topbar">
      <h1>👤 Applications</h1>
      <div class="topbar-right"><span>{{ applications|length }} showing</span></div>
    </div>
    <div class="content">
      <div class="filters">
        <a href="/admin/applications" class="filter-btn {% if filter=='all' %}active{% endif %}">All</a>
        <a href="/admin/applications?status=new" class="filter-btn {% if filter=='new' %}active{% endif %}">New</a>
        <a href="/admin/applications?status=reviewed" class="filter-btn {% if filter=='reviewed' %}active{% endif %}">Reviewed</a>
        <a href="/admin/applications?status=shortlisted" class="filter-btn {% if filter=='shortlisted' %}active{% endif %}">Shortlisted</a>
        <a href="/admin/applications?status=rejected" class="filter-btn {% if filter=='rejected' %}active{% endif %}">Rejected</a>
      </div>
      <div class="table-card">
        <table>
          <thead><tr><th>#</th><th>Name</th><th>Email</th><th>Position</th><th>Status</th><th>Date</th><th></th></tr></thead>
          <tbody>
          {% for a in applications %}
          <tr>
            <td style="color:#6b7194">{{ a.id }}</td>
            <td><strong>{{ a.full_name }}</strong></td>
            <td>{{ a.email }}</td>
            <td>{{ a.position }}</td>
            <td><span class="badge badge-{{ a.status }}">{{ a.status }}</span></td>
            <td style="color:#6b7194;font-size:0.8rem">{{ a.created_at.strftime('%d %b %Y') }}</td>
            <td><a href="/admin/applications/{{ a.id }}" class="btn btn-outline btn-sm">View</a></td>
          </tr>
          {% else %}
          <tr><td colspan="7" style="text-align:center;color:#6b7194;padding:32px">No applications found.</td></tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>
</body></html>"""


APPLICATION_DETAIL_HTML = """<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Application #{{ a.id }} – Allied Industries Admin</title>""" + ADMIN_CSS + """
</head><body>
<div class="layout">
  {{ sidebar|safe }}
  <div class="main">
    <div class="topbar">
      <h1>Application #{{ a.id }} — {{ a.full_name }}</h1>
      <div class="topbar-right">
        <a href="/admin/applications" class="btn btn-outline btn-sm">← Back</a>
      </div>
    </div>
    <div class="content">
      <div class="form-card">
        <div class="detail-grid">
          <div class="detail-field"><div class="key">Full Name</div><div class="val">{{ a.full_name }}</div></div>
          <div class="detail-field"><div class="key">Email</div><div class="val"><a href="mailto:{{ a.email }}" style="color:#b87333">{{ a.email }}</a></div></div>
          <div class="detail-field"><div class="key">Phone</div><div class="val">{{ a.phone or '—' }}</div></div>
          <div class="detail-field"><div class="key">Position Applied</div><div class="val"><strong>{{ a.position }}</strong></div></div>
          <div class="detail-field"><div class="key">Submitted</div><div class="val">{{ a.created_at.strftime('%d %b %Y, %I:%M %p') }} UTC</div></div>
          <div class="detail-field"><div class="key">Current Status</div><div class="val"><span class="badge badge-{{ a.status }}">{{ a.status }}</span></div></div>
        </div>
        {% if a.cv_text %}
        <div style="margin-bottom:8px;font-size:0.72rem;letter-spacing:0.1em;text-transform:uppercase;color:#6b7194;font-weight:600">CV / Cover Letter</div>
        <div class="message-box">{{ a.cv_text }}</div>
        {% endif %}

        <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
          <form method="POST" action="/admin/applications/{{ a.id }}/status" style="display:flex;gap:8px;align-items:center">
            <label style="font-size:0.82rem;font-weight:600;color:#6b7194">Status:</label>
            <select name="status">
              <option value="new"         {% if a.status=='new'         %}selected{% endif %}>New</option>
              <option value="reviewed"    {% if a.status=='reviewed'    %}selected{% endif %}>Reviewed</option>
              <option value="shortlisted" {% if a.status=='shortlisted' %}selected{% endif %}>Shortlisted</option>
              <option value="rejected"    {% if a.status=='rejected'    %}selected{% endif %}>Rejected</option>
            </select>
            <button type="submit" class="btn btn-primary btn-sm">Update</button>
          </form>
          <a href="mailto:{{ a.email }}" class="btn btn-outline btn-sm">✉ Email Applicant</a>
          <form method="POST" action="/admin/applications/{{ a.id }}/delete"
            onsubmit="return confirm('Delete this application? This cannot be undone.')">
            <button type="submit" class="btn btn-danger btn-sm">🗑 Delete</button>
          </form>
        </div>
      </div>
    </div>
  </div>
</div>
</body></html>"""


# Add `sidebar` and `now` to every admin template context
@app.context_processor
def inject_globals():
    return {
        "sidebar": sidebar() if current_user.is_authenticated else "",
        "now": datetime.utcnow().strftime("%d %b %Y"),
    }


# ─────────────────────────────────────────
#  INIT DB + DEFAULT ADMIN
# ─────────────────────────────────────────

def init_db():
    with app.app_context():
        db.create_all()
        if not AdminUser.query.filter_by(username="admin").first():
            admin = AdminUser(username="admin")
            admin.set_password("allied@2024")   # ← Change this after first login!
            db.session.add(admin)
            db.session.commit()
            print("✅ Default admin created — username: admin | password: allied@2024")
            print("   ⚠️  Change the password immediately after first login!")


# ─────────────────────────────────────────
#  RUN
# ─────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print("\n🚀 Allied Industries Backend running at http://127.0.0.1:5000")
    print("   Admin panel: http://127.0.0.1:5000/admin")
    print("   API endpoints:")
    print("     POST /api/enquiry      – Contact form")
    print("     POST /api/application  – Career form\n")
    app.run(debug=True, port=5000)

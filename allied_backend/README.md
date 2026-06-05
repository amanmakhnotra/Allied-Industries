# Allied Industries – Flask Backend

Complete backend for the Allied Industries website.
Handles contact enquiries, career applications, email notifications, and an admin dashboard.

---

## Project Structure

```
allied_backend/
├── app.py                 # Main Flask application (all-in-one)
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variables template
├── html_integration.js    # JS snippet to paste into your HTML
├── README.md
└── allied.db              # SQLite database (auto-created on first run)
```

---

## Quick Start (Local)

### 1. Install Python dependencies
```bash
cd allied_backend
pip install -r requirements.txt
```

### 2. Configure environment variables
```bash
cp .env.example .env
# Edit .env with your real email credentials
```

### 3. Run the server
```bash
python app.py
```

Server starts at: **http://127.0.0.1:5000**
Admin panel at:  **http://127.0.0.1:5000/admin**

Default login:
- Username: `admin`
- Password: `allied@2024`
⚠️ **Change this password immediately after first login.**

---

## Connecting to the HTML Website

### Step 1 – Wire the Contact form button
In `allied_industries_website.html`, find the Send Enquiry button:
```html
onclick="showToast('✅ Enquiry sent! ...')"
```
Replace with:
```html
onclick="submitEnquiry()"
```

### Step 2 – Wire the Careers form button
Find the Submit Application button:
```html
onclick="showToast('✅ Application submitted! ...')"
```
Replace with:
```html
onclick="submitApplication()"
```

### Step 3 – Paste the JS integration script
Copy the contents of `html_integration.js` and paste it inside
the `<script>` tag at the bottom of your HTML file.

Update this line to your live server URL:
```javascript
const BACKEND_URL = "http://127.0.0.1:5000"; // ← change for production
```

---

## Email Setup (Gmail)

1. Go to [myaccount.google.com](https://myaccount.google.com)
2. Security → 2-Step Verification → App passwords
3. Generate a password for "Mail"
4. Put it in your `.env` as `MAIL_PASSWORD`

---

## Admin Dashboard Features

| Feature | URL |
|---------|-----|
| Dashboard | `/admin/dashboard` |
| All Enquiries | `/admin/enquiries` |
| Enquiry Detail | `/admin/enquiries/<id>` |
| All Applications | `/admin/applications` |
| Application Detail | `/admin/applications/<id>` |

**Status workflow:**
- Enquiries: `new` → `read` → `replied`
- Applications: `new` → `reviewed` → `shortlisted` / `rejected`

---

## API Endpoints

### POST `/api/enquiry`
```json
{
  "name":    "Rahul Sharma",
  "email":   "rahul@company.com",
  "phone":   "+91 98765 43210",
  "company": "ABC Motors",
  "product": "Metal Rivets – Semi Tubular",
  "message": "Need 50,000 units, 3mm head diameter..."
}
```

### POST `/api/application`
```json
{
  "first_name": "Priya",
  "last_name":  "Gupta",
  "email":      "priya@gmail.com",
  "phone":      "+91 98765 43210",
  "position":   "Quality Inspector",
  "cv_text":    "5 years experience in QC..."
}
```

Both return:
```json
{ "ok": true, "message": "..." }
// or
{ "ok": false, "error": "..." }
```

---

## Deploying to a Live Server

### Option A – PythonAnywhere (easiest, free tier)
1. Upload files to PythonAnywhere
2. Set environment variables in the Web tab
3. WSGI file: `from app import app as application`

### Option B – VPS (DigitalOcean / Hetzner)
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```
Use Nginx as a reverse proxy in front of Gunicorn.

### Option C – Railway / Render (free hosting)
- Add a `Procfile`: `web: gunicorn app:app`
- Set environment variables in the dashboard
- Both support free tiers with auto-deploy from GitHub

---

## Security Checklist Before Going Live

- [ ] Change default admin password
- [ ] Set a strong `SECRET_KEY` in `.env`
- [ ] Use HTTPS (free with Let's Encrypt)
- [ ] Set `debug=False` in `app.run()`
- [ ] Consider rate-limiting `/api/enquiry` and `/api/application`

---

## Changing the Admin Password
```python
from app import app, db, AdminUser
with app.app_context():
    user = AdminUser.query.filter_by(username='admin').first()
    user.set_password('your-new-secure-password')
    db.session.commit()
    print("Password updated.")
```

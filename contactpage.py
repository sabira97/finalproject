from flask import Flask, request, jsonify, render_template
from pathlib import Path
from ipaddress import ip_address
import json
import re
import smtplib
from email.mime.text import MIMEText
import time
import traceback

app = Flask(__name__)

PRIMARY = "#2A314D"
JSON_PATH = Path("messages.json")
last_submit_by_ip = {}

# SMTP konfigurasiya
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = "shahpelengovaz@gmail.com"          # Buraya öz gmail ünvanını yaz
EMAIL_PASS = "app_password_here"        # Buraya Gmail App Password yaz
EMAIL_TO = "ruslan.hamidov@holberton.us"   # Mesajı qəbul edən email

# JSON faylını yoxla və yarat
def init_json():
    if not JSON_PATH.exists():
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)

# Mesajı JSON fayla yaz
def save_message_json(first_name, last_name, email, message, ip):
    init_json()
    with open(JSON_PATH, "r+", encoding="utf-8") as f:
        data = json.load(f)
        data.append({
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "message": message,
            "ip": str(ip),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        })
        f.seek(0)
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.truncate()

# Validatorlar
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
FIRST_NAME_RE = re.compile(r"^[A-ZƏİÖÜÇŞĞ][a-zəiöüçşğ]+$")
LAST_NAME_RE = re.compile(r"^[A-ZƏİÖÜÇŞĞ][a-zəiöüçşğ]+$")

def validate_payload(data: dict):
    errors = {}
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    email = (data.get("email") or "").strip()
    message = (data.get("message") or "").strip()
    hp = (data.get("hp") or "").strip()

    if not FIRST_NAME_RE.match(first_name):
        errors["first_name"] = "Ad düzgün deyil."
    if not LAST_NAME_RE.match(last_name):
        errors["last_name"] = "Soyad düzgün deyil."
    if not EMAIL_RE.match(email):
        errors["email"] = "Email düzgün deyil."
    if not (10 <= len(message) <= 2000):
        errors["message"] = "Mesaj 10–2000 simvol olmalıdır."
    if hp:
        errors["hp"] = "Bot şübhəsi (honeypot doludur)."
    return errors

# Email göndərən funksiya
def send_email(first_name, last_name, email, message):
    subject = f"Yeni mesaj: {first_name} {last_name}"
    body = f"Ad: {first_name}\nSoyad: {last_name}\nEmail: {email}\nMesaj:\n{message}"
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO
    # message_body = request.form.get('message')
    # msg.attach(MIMEText(message_body, 'plain'))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
            print("Email göndərildi.")
    except Exception as e:
        print("Email göndərilərkən xəta:")
        traceback.print_exc()

# Kontakt səhifəsi
@app.get("/contact")
def contact_page():
    return render_template("contact.html", primary=PRIMARY)

# API POST — Əlaqə formu
@app.post("/api/contact")
def api_contact():
    data = request.get_json(force=True, silent=True) or {}
    errors = validate_payload(data)
    if errors:
        return jsonify({"error": "; ".join(f"{k}: {v}" for k, v in errors.items())}), 400

    # IP və Rate Limit
    try:
        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr).split(",")[0].strip()
        client_ip = ip_address(client_ip)
    except Exception:
        client_ip = "0.0.0.0"

    now = time.time()
    last = last_submit_by_ip.get(client_ip)
    if last and (now - last) < 15:
        return jsonify({"error": "Çox tez-tez göndərirsiniz. 15 saniyə sonra yenidən cəhd edin."}), 429
    last_submit_by_ip[client_ip] = now

    # JSON yaddaşa yaz
    save_message_json(
        first_name=data["first_name"].strip(),
        last_name=data["last_name"].strip(),
        email=data["email"].strip(),
        message=data["message"].strip(),
        ip=client_ip
    )

    # Email göndər
    send_email(
        first_name=data["first_name"].strip(),
        last_name=data["last_name"].strip(),
        email=data["email"].strip(),
        message=data["message"].strip()
    )

    return jsonify({"ok": True})

# Admin mesajlara baxış
@app.get("/admin/messages")
def admin_messages():
    init_json()
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        messages = json.load(f)
    return render_template("admin_messages.html", messages=messages, primary=PRIMARY)

# Serveri işə sal
if __name__ == "__main__":
    app.run(debug=True, host="localhost", port=5550)

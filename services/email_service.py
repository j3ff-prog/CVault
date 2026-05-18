"""
services/email_service.py
Gmail SMTP email sending.
"""
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5000")


def _send(to_email: str, subject: str, html_body: str) -> bool:
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("[EMAIL] Credentials not set — skipping.")
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"CVault <{GMAIL_USER}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, to_email, msg.as_string())
        print(f"[EMAIL] Sent '{subject}' to {to_email}")
        return True
    except Exception as e:
        print(f"[EMAIL] Failed: {e}")
        return False


def send_password_reset(to_email: str, first_name: str, token: str) -> bool:
    reset_url = f"{FRONTEND_URL}/cvault-reset-password.html?token={token}"
    html = f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <style>
      body{{font-family:'Segoe UI',Arial,sans-serif;background:#f4f4f4;margin:0;padding:0}}
      .wrap{{max-width:560px;margin:40px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)}}
      .hd{{background:#0A1628;padding:32px;text-align:center}}
      .hd h1{{font-family:Georgia,serif;color:#C9A84C;font-size:28px;margin:0;letter-spacing:1px}}
      .hd h1 span{{color:#fff}}
      .bd{{padding:36px 40px}}
      .bd p{{color:#444;font-size:15px;line-height:1.7;margin:0 0 16px}}
      .btn{{display:block;width:fit-content;margin:28px auto;padding:14px 36px;background:#C9A84C;color:#0A1628;text-decoration:none;border-radius:8px;font-weight:700;font-size:15px}}
      .note{{font-size:12px;color:#999;text-align:center;margin-top:20px}}
      .ft{{background:#f9f9f9;padding:20px;text-align:center;font-size:12px;color:#aaa;border-top:1px solid #eee}}
    </style></head><body>
    <div class="wrap">
      <div class="hd"><h1>C<span>Vault</span></h1></div>
      <div class="bd">
        <p>Hi {first_name},</p>
        <p>We received a request to reset your CVault password. Click below to set a new one.</p>
        <a href="{reset_url}" class="btn">Reset My Password →</a>
        <p>This link expires in <strong>30 minutes</strong>. If you didn't request this, ignore this email.</p>
        <p class="note">Link: {reset_url}</p>
      </div>
      <div class="ft">© 2025 CVault. Built for Kenya.</div>
    </div></body></html>
    """
    return _send(to_email, "Reset your CVault password", html)


def send_welcome(to_email: str, first_name: str) -> bool:
    dashboard_url = f"{FRONTEND_URL}/cvault-dashboard.html"
    html = f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8">
    <style>
      body{{font-family:'Segoe UI',Arial,sans-serif;background:#f4f4f4;margin:0;padding:0}}
      .wrap{{max-width:560px;margin:40px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)}}
      .hd{{background:#0A1628;padding:32px;text-align:center}}
      .hd h1{{font-family:Georgia,serif;color:#C9A84C;font-size:28px;margin:0;letter-spacing:1px}}
      .hd h1 span{{color:#fff}}
      .bd{{padding:36px 40px}}
      .bd p{{color:#444;font-size:15px;line-height:1.7;margin:0 0 16px}}
      .steps{{background:#f9f9f9;border-radius:8px;padding:20px 24px;margin:20px 0}}
      .steps p{{margin:0 0 8px;font-size:14px;color:#555}}
      .steps p:last-child{{margin:0}}
      .btn{{display:block;width:fit-content;margin:28px auto;padding:14px 36px;background:#C9A84C;color:#0A1628;text-decoration:none;border-radius:8px;font-weight:700;font-size:15px}}
      .ft{{background:#f9f9f9;padding:20px;text-align:center;font-size:12px;color:#aaa;border-top:1px solid #eee}}
    </style></head><body>
    <div class="wrap">
      <div class="hd"><h1>C<span>Vault</span></h1></div>
      <div class="bd">
        <p>Hi {first_name}, welcome to CVault! 🎉</p>
        <p>Your account is ready. Here's how to get your first tailored CV:</p>
        <div class="steps">
          <p>💳 <strong>Step 1:</strong> Buy credits — from just KES 49</p>
          <p>📄 <strong>Step 2:</strong> Upload your CV and paste a job description</p>
          <p>⬇️ <strong>Step 3:</strong> Download your tailored CV + cover letter as a Word doc</p>
        </div>
        <a href="{dashboard_url}" class="btn">Go to My Dashboard →</a>
      </div>
      <div class="ft">© 2025 CVault. Built for Kenya.</div>
    </div></body></html>
    """
    return _send(to_email, "Welcome to CVault — you're all set!", html)

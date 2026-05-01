import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from src.notifications.base import NotificationChannel


class EmailChannel(NotificationChannel):
    def __init__(self):
        self.gmail_address = os.environ.get("GMAIL_ADDRESS", "")
        self.app_password = os.environ.get("GMAIL_APP_PASSWORD", "")
        self.default_recipient = os.environ.get("EMAIL_RECIPIENT", "")

    def is_configured(self) -> bool:
        return bool(self.gmail_address and self.app_password)

    def send(self, subject: str, body: str, recipient: str = "") -> bool:
        recipient = recipient or self.default_recipient
        if not recipient:
            print("[Email] No recipient configured.")
            return False
        if not self.is_configured():
            print("[Email] Gmail credentials not set in .env")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.gmail_address
        msg["To"] = recipient

        # Plain text part (primary — preserves ASCII formatting)
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # HTML part — wraps content in a styled block with readable font
        html_body = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="background:#f0f2f5; padding:24px 12px; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <div style="max-width:720px; margin:0 auto; background:#ffffff; border-radius:10px;
              padding:32px 36px; box-shadow:0 2px 12px rgba(0,0,0,0.10);">
    <pre style="font-family:Menlo,Monaco,Consolas,'Liberation Mono','Courier New',monospace;
                font-size:14px; line-height:1.75; white-space:pre-wrap;
                word-wrap:break-word; color:#1c1c1e; margin:0;
                background:#fafafa; border-radius:6px; padding:20px;">{body}</pre>
    <hr style="margin-top:28px; border:none; border-top:1px solid #e5e5ea;">
    <p style="color:#8e8e93; font-size:12px; margin:12px 0 0; text-align:center;">
      The Signal Desk · Daily Stock Alert System
    </p>
  </div>
</body>
</html>"""
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self.gmail_address, self.app_password)
                server.sendmail(self.gmail_address, recipient, msg.as_string())
            print(f"[Email] Sent to {recipient}")
            return True
        except Exception as e:
            print(f"[Email] Failed: {e}")
            return False

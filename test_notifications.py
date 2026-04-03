import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from twilio.rest import Client
from datetime import datetime

# ─────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────
GMAIL_USER     = os.environ.get("GMAIL_USER", "")
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD", "")
NOTIFY_EMAIL   = os.environ.get("NOTIFY_EMAIL", "")

TWILIO_SID     = os.environ.get("TWILIO_SID", "")
TWILIO_TOKEN   = os.environ.get("TWILIO_TOKEN", "")
TWILIO_FROM    = os.environ.get("TWILIO_FROM", "")
WHATSAPP_TO    = os.environ.get("WHATSAPP_TO", "")

# ─────────────────────────────────────────
# FAKE BILL FOR TESTING
# ─────────────────────────────────────────
test_bill = {
    "source": "GEPCO (TEST)",
    "amount": "3,450",
    "due_date": "25-Apr-2026"
}

# ─────────────────────────────────────────
# SEND EMAIL
# ─────────────────────────────────────────
def send_email(bill):
    subject = f"💡 [TEST] New {bill['source']} Bill — PKR {bill['amount']} due {bill['due_date']}"
    body = f"""
Hello,

This is a TEST notification from your Bill Notifier system.

  Provider  : {bill['source']}
  Amount    : PKR {bill['amount']}
  Due Date  : {bill['due_date']}

If you received this, your email notifications are working perfectly! ✅

Checked on: {datetime.now().strftime('%Y-%m-%d %H:%M')}
    """
    msg = MIMEMultipart()
    msg["From"]    = GMAIL_USER
    msg["To"]      = NOTIFY_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, NOTIFY_EMAIL, msg.as_string())
    print("[Email] ✅ Test email sent successfully!")

# ─────────────────────────────────────────
# SEND WHATSAPP
# ─────────────────────────────────────────
def send_whatsapp(bill):
    client = Client(TWILIO_SID, TWILIO_TOKEN)
    message = (
        f"🔔 *[TEST] {bill['source']} Bill Notifier*\n"
        f"Amount  : PKR {bill['amount']}\n"
        f"Due Date: {bill['due_date']}\n\n"
        f"If you got this, WhatsApp notifications are working! ✅"
    )
    client.messages.create(body=message, from_=TWILIO_FROM, to=WHATSAPP_TO)
    print("[WhatsApp] ✅ Test message sent successfully!")

# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
print(f"[{datetime.now()}] Running notification test...")

try:
    send_email(test_bill)
except Exception as e:
    print(f"[Email] ❌ Failed: {e}")

try:
    send_whatsapp(test_bill)
except Exception as e:
    print(f"[WhatsApp] ❌ Failed: {e}")

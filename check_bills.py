import os
import json
import smtplib
import requests
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from twilio.rest import Client
from datetime import datetime

# ─────────────────────────────────────────
# CONFIGURATION — fill these in
# ─────────────────────────────────────────
GEPCO_REF_NO = os.environ.get("GEPCO_REF_NO", "")        # Your 14-digit GEPCO reference number
SNGPL_REF_NO = os.environ.get("SNGPL_REF_NO", "")        # Your SNGPL consumer number

GMAIL_USER     = os.environ.get("GMAIL_USER", "")         # your Gmail address
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD", "")     # Gmail App Password (not your real password)
NOTIFY_EMAIL   = os.environ.get("NOTIFY_EMAIL", "")       # Where to send the email (can be same as above)

TWILIO_SID     = os.environ.get("TWILIO_SID", "")
TWILIO_TOKEN   = os.environ.get("TWILIO_TOKEN", "")
TWILIO_FROM    = os.environ.get("TWILIO_FROM", "")        # Twilio WhatsApp number e.g. whatsapp:+14155238886
WHATSAPP_TO    = os.environ.get("WHATSAPP_TO", "")        # Your number e.g. whatsapp:+923001234567

STATE_FILE = "bill_state.json"

# ─────────────────────────────────────────
# STATE MANAGEMENT (track seen bills)
# ─────────────────────────────────────────
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"gepco": None, "sngpl": None}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# ─────────────────────────────────────────
# GEPCO BILL FETCHER
# ─────────────────────────────────────────
def check_gepco(ref_no):
    """Fetch latest GEPCO bill info using their online portal."""
    try:
        url = "https://bill.gepco.com.pk/bill.php"
        payload = {"refno": ref_no}
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.post(url, data=payload, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract bill amount and due date from the page
        amount_tag = soup.find("td", string=lambda t: t and "Payable" in t)
        due_tag    = soup.find("td", string=lambda t: t and "Due Date" in t)

        amount = amount_tag.find_next_sibling("td").text.strip() if amount_tag else "N/A"
        due    = due_tag.find_next_sibling("td").text.strip()    if due_tag    else "N/A"

        # Use due date as unique bill identifier
        return {"amount": amount, "due_date": due, "source": "GEPCO"}
    except Exception as e:
        print(f"[GEPCO] Error: {e}")
        return None

# ─────────────────────────────────────────
# SNGPL BILL FETCHER
# ─────────────────────────────────────────
def check_sngpl(consumer_no):
    """Fetch latest SNGPL bill info."""
    try:
        url = "https://www.sngpl.com.pk/onlinebill.php"
        payload = {"consno": consumer_no}
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.post(url, data=payload, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        amount_tag = soup.find("td", string=lambda t: t and "Payable" in t)
        due_tag    = soup.find("td", string=lambda t: t and "Due Date" in t)

        amount = amount_tag.find_next_sibling("td").text.strip() if amount_tag else "N/A"
        due    = due_tag.find_next_sibling("td").text.strip()    if due_tag    else "N/A"

        return {"amount": amount, "due_date": due, "source": "SNGPL"}
    except Exception as e:
        print(f"[SNGPL] Error: {e}")
        return None

# ─────────────────────────────────────────
# NOTIFICATIONS
# ─────────────────────────────────────────
def send_email(bill):
    subject = f"💡 New {bill['source']} Bill — PKR {bill['amount']} due {bill['due_date']}"
    body = f"""
Hello,

A new utility bill has been issued:

  Provider  : {bill['source']}
  Amount    : PKR {bill['amount']}
  Due Date  : {bill['due_date']}

Please pay before the due date to avoid late surcharges.

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
    print(f"[Email] Sent for {bill['source']}")

def send_whatsapp(bill):
    client = Client(TWILIO_SID, TWILIO_TOKEN)
    message = (
        f"🔔 *New {bill['source']} Bill*\n"
        f"Amount  : PKR {bill['amount']}\n"
        f"Due Date: {bill['due_date']}\n\n"
        f"Please pay before the due date! ✅"
    )
    client.messages.create(body=message, from_=TWILIO_FROM, to=WHATSAPP_TO)
    print(f"[WhatsApp] Sent for {bill['source']}")

def notify(bill):
    try:
        send_email(bill)
    except Exception as e:
        print(f"[Email Error] {e}")
    try:
        send_whatsapp(bill)
    except Exception as e:
        print(f"[WhatsApp Error] {e}")

# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
def main():
    state = load_state()
    changed = False

    print(f"[{datetime.now()}] Checking bills...")

    # Check GEPCO
    if GEPCO_REF_NO:
        gepco = check_gepco(GEPCO_REF_NO)
        if gepco and gepco["due_date"] != state.get("gepco"):
            print(f"[GEPCO] New bill found! Due: {gepco['due_date']}, Amount: {gepco['amount']}")
            notify(gepco)
            state["gepco"] = gepco["due_date"]
            changed = True
        else:
            print("[GEPCO] No new bill.")

    # Check SNGPL
    if SNGPL_REF_NO:
        sngpl = check_sngpl(SNGPL_REF_NO)
        if sngpl and sngpl["due_date"] != state.get("sngpl"):
            print(f"[SNGPL] New bill found! Due: {sngpl['due_date']}, Amount: {sngpl['amount']}")
            notify(sngpl)
            state["sngpl"] = sngpl["due_date"]
            changed = True
        else:
            print("[SNGPL] No new bill.")

    if changed:
        save_state(state)

if __name__ == "__main__":
    main()

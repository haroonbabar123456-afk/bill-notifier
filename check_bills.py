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
# CONFIGURATION
# ─────────────────────────────────────────
GEPCO_REF_NO = os.environ.get("GEPCO_REF_NO", "")
SNGPL_REF_NO = os.environ.get("SNGPL_REF_NO", "")

GMAIL_USER     = os.environ.get("GMAIL_USER", "")
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD", "")
NOTIFY_EMAIL   = os.environ.get("NOTIFY_EMAIL", "")

TWILIO_SID     = os.environ.get("TWILIO_SID", "")
TWILIO_TOKEN   = os.environ.get("TWILIO_TOKEN", "")
TWILIO_FROM    = os.environ.get("TWILIO_FROM", "")
WHATSAPP_TO    = os.environ.get("WHATSAPP_TO", "")

STATE_FILE = "bill_state.json"

# ─────────────────────────────────────────
# STATE MANAGEMENT
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
# GEPCO BILL FETCHER (correct URL)
# ─────────────────────────────────────────
def check_gepco(ref_no):
    try:
        url = f"https://bill.pitc.com.pk/gepcobill/general?refno={ref_no}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        print(f"[GEPCO] Page fetched, status: {resp.status_code}")

        amount = "N/A"
        due    = "N/A"
        bill_month = "N/A"

        all_tds = soup.find_all("td")
        for i, td in enumerate(all_tds):
            text = td.get_text(strip=True).upper()
            if "DUE DATE" in text and i + 1 < len(all_tds):
                due = all_tds[i + 1].get_text(strip=True)
            if "BILL MONTH" in text and i + 1 < len(all_tds):
                bill_month = all_tds[i + 1].get_text(strip=True)
            if "PAYABLE" in text and i + 1 < len(all_tds):
                amount = all_tds[i + 1].get_text(strip=True)

        if amount == "N/A":
            for tag in soup.find_all(["td", "div", "span", "th"]):
                t = tag.get_text(strip=True)
                if "payable" in t.lower() or "net payable" in t.lower():
                    nxt = tag.find_next_sibling()
                    if nxt:
                        amount = nxt.get_text(strip=True)

        print(f"[GEPCO] Bill Month: {bill_month}, Due: {due}, Amount: {amount}")
        return {"amount": amount, "due_date": due, "bill_month": bill_month, "source": "GEPCO"}

    except Exception as e:
        print(f"[GEPCO] Error: {e}")
        return None

# ─────────────────────────────────────────
# SNGPL BILL FETCHER
# ─────────────────────────────────────────
def check_sngpl(consumer_no):
    try:
        url = "https://www.sngpl.com.pk/onlinebill.php"
        payload = {"consno": consumer_no}
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.post(url, data=payload, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        amount = "N/A"
        due    = "N/A"

        all_tds = soup.find_all("td")
        for i, td in enumerate(all_tds):
            text = td.get_text(strip=True).upper()
            if "DUE DATE" in text and i + 1 < len(all_tds):
                due = all_tds[i + 1].get_text(strip=True)
            if "PAYABLE" in text and i + 1 < len(all_tds):
                amount = all_tds[i + 1].get_text(strip=True)

        print(f"[SNGPL] Due: {due}, Amount: {amount}")
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

  Provider   : {bill['source']}
  Amount     : PKR {bill['amount']}
  Due Date   : {bill['due_date']}

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
    print(f"[Email] ✅ Sent for {bill['source']}")

def send_whatsapp(bill):
    client = Client(TWILIO_SID, TWILIO_TOKEN)
    message = (
        f"🔔 *New {bill['source']} Bill*\n"
        f"Amount  : PKR {bill['amount']}\n"
        f"Due Date: {bill['due_date']}\n\n"
        f"Please pay before the due date! ✅"
    )
    client.messages.create(body=message, from_=TWILIO_FROM, to=WHATSAPP_TO)
    print(f"[WhatsApp] ✅ Sent for {bill['source']}")

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

    if GEPCO_REF_NO:
        gepco = check_gepco(GEPCO_REF_NO)
        if gepco and gepco["due_date"] != "N/A" and gepco["due_date"] != state.get("gepco"):
            print(f"[GEPCO] New bill found!")
            notify(gepco)
            state["gepco"] = gepco["due_date"]
            changed = True
        else:
            print("[GEPCO] No new bill or already notified.")
    else:
        print("[GEPCO] No reference number set, skipping.")

    if SNGPL_REF_NO:
        sngpl = check_sngpl(SNGPL_REF_NO)
        if sngpl and sngpl["due_date"] != "N/A" and sngpl["due_date"] != state.get("sngpl"):
            print(f"[SNGPL] New bill found!")
            notify(sngpl)
            state["sngpl"] = sngpl["due_date"]
            changed = True
        else:
            print("[SNGPL] No new bill or already notified.")
    else:
        print("[SNGPL] No consumer number set, skipping.")

    if changed:
        save_state(state)

if __name__ == "__main__":
    main()

"""
Nifty Brief — Subscriber Broadcast
Reads subscribers from Google Sheet, sends email + Telegram to each
"""

import os, json, re, time, smtplib
import urllib.request, urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta

# ── SECRETS ───────────────────────────────────────────────────────────────────
GMAIL_USER            = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD    = os.environ["GMAIL_APP_PASSWORD"]
TELEGRAM_BOT_TOKEN    = os.environ["TELEGRAM_BOT_TOKEN"]
SHEET_ID              = os.environ["SHEET_ID"]
SA_JSON               = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]  # full JSON string
DASHBOARD_URL         = "https://Sameerxceed.github.io/nifty-dashboard/"

IST     = timezone(timedelta(hours=5, minutes=30))
now_ist = datetime.now(IST)
DATE    = now_ist.strftime("%d %b %Y")
TIME    = now_ist.strftime("%I:%M %p")

SESSION_LABELS = {
    "morning_brief": "Morning Brief",
    "session_1":     "Market Open",
    "session_2":     "Mid-Morning",
    "session_3":     "Post-Lunch",
    "closing":       "Pre-Close",
}

def get_session():
    t = now_ist.hour*60+now_ist.minute
    if t < 9*60+15:  return "morning_brief"
    if t < 11*60+15: return "session_1"
    if t < 13*60+15: return "session_2"
    if t < 15*60+15: return "session_3"
    return "closing"

SESSION    = get_session()
SESS_LABEL = SESSION_LABELS.get(SESSION, "Update")

# ── LOAD MARKET DATA ──────────────────────────────────────────────────────────
with open("data.json") as f:
    data = json.load(f)

n         = data.get("nifty", {})
s         = data.get("sentiment", {})
g         = data.get("gift", {})
vix_d     = data.get("vix", {})
p         = data.get("pivot", {})
news      = data.get("news", [])[:3]
persp     = data.get("perspectives", {})
score     = int(s.get("score", 50))
brief     = data.get("brief","")
verdict_m = re.search(r"TRADING VERDICT:?(.*?)(?:\n\n|\Z)", brief, re.IGNORECASE|re.DOTALL)
verdict   = verdict_m.group(1).strip().replace("\n"," ")[:280] if verdict_m else ""

nifty_p   = str(n.get("price","N/A"))
nifty_c   = str(n.get("change","+0"))
nifty_pct = str(n.get("pct",""))
sent_lbl  = str(s.get("label","Neutral"))
gift_gap  = str(g.get("gap_pts","—"))
gift_sig  = str(g.get("signal","flat")).replace("_"," ").upper()
vix_v     = str(vix_d.get("value","—"))
vix_lev   = str(vix_d.get("level","moderate")).upper()
pp_       = str(p.get("pp","—"))
r1_       = str(p.get("r1","—"))
s1_       = str(p.get("s1","—"))

score_color  = "#00e676" if score>55 else "#ff1744" if score<45 else "#ffd600"
change_color = "#00e676" if nifty_c.startswith("+") else "#ff1744"
gap_color    = "#00e676" if "UP" in gift_sig else "#ff1744" if "DOWN" in gift_sig else "#ffd600"
sent_emoji   = "🟢" if score>55 else "🔴" if score<45 else "🟡"

# ── GOOGLE SHEETS AUTH (service account via JWT) ──────────────────────────────
def get_sheets_token():
    """Get OAuth token using service account JSON."""
    import base64, hashlib, hmac, struct, time as t_

    sa = json.loads(SA_JSON)
    now_ = int(t_.time())
    header  = base64.urlsafe_b64encode(json.dumps({"alg":"RS256","typ":"JWT"}).encode()).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({
        "iss": sa["client_email"],
        "scope": "https://www.googleapis.com/auth/spreadsheets.readonly",
        "aud": "https://oauth2.googleapis.com/token",
        "exp": now_+3600, "iat": now_
    }).encode()).rstrip(b"=").decode()

    # Sign with RSA private key using cryptography library
    try:
        from cryptography.hazmat.primitives import serialization, hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        key = serialization.load_pem_private_key(sa["private_key"].encode(), password=None)
        sig = key.sign((header+"."+payload).encode(), padding.PKCS1v15(), hashes.SHA256())
        sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    except ImportError:
        # fallback: use subprocess openssl
        import subprocess, tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as f:
            f.write(sa["private_key"].encode())
            keyfile = f.name
        proc = subprocess.run(
            ["openssl","dgst","-sha256","-sign",keyfile],
            input=(header+"."+payload).encode(),
            capture_output=True
        )
        sig_b64 = base64.urlsafe_b64encode(proc.stdout).rstrip(b"=").decode()

    jwt = header+"."+payload+"."+sig_b64
    payload_data = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token",
                                  data=payload_data, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["access_token"]

def get_subscribers():
    """Read subscriber list from Google Sheet."""
    print("Reading subscribers from Google Sheet...")
    token = get_sheets_token()
    url   = "https://sheets.googleapis.com/v4/spreadsheets/" + SHEET_ID + "/values/A:D"
    req   = urllib.request.Request(url, headers={"Authorization":"Bearer "+token})
    with urllib.request.urlopen(req, timeout=15) as r:
        result = json.loads(r.read())

    rows = result.get("values",[])
    if len(rows) < 2:
        print("No subscribers found")
        return []

    # First row is header: Timestamp | Name | Email | Telegram Username
    subscribers = []
    for row in rows[1:]:  # skip header
        if len(row) >= 3:
            name     = str(row[1]).strip() if len(row)>1 else "Subscriber"
            email    = str(row[2]).strip() if len(row)>2 else ""
            telegram = str(row[3]).strip() if len(row)>3 else ""
            if email and "@" in email:
                subscribers.append({"name":name,"email":email,"telegram":telegram})

    print("Subscribers found: " + str(len(subscribers)))
    return subscribers

# ── EMAIL SENDER ──────────────────────────────────────────────────────────────
def build_email_html(name):
    news_rows = ""
    imp_color = {"positive":"#00e676","negative":"#ff1744","neutral":"#b0bec5"}
    imp_sym   = {"positive":"▲","negative":"▼","neutral":"●"}
    for item in news:
        ic  = imp_color.get(item.get("impact","neutral"),"#b0bec5")
        sym = imp_sym.get(item.get("impact","neutral"),"●")
        news_rows += (
            "<tr style='border-bottom:1px solid #1e3050'>"
            "<td style='padding:7px 12px;font-size:11px;font-weight:700;color:" + ic + "'>" + item.get("tag","") + "</td>"
            "<td style='padding:7px 12px;font-size:13px;color:#cdd9e5'>" + item.get("headline","") + "</td>"
            "<td style='padding:7px 12px;color:" + ic + ";text-align:right'>" + sym + "</td>"
            "</tr>"
        )

    persp_section = ""
    if persp.get("key_event") and SESSION == "morning_brief":
        persp_section = (
            "<div style='background:#0d1a2e;border:1px solid #1e3050;border-radius:12px;padding:18px;margin-top:14px'>"
            "<div style='font-size:11px;color:#00c8ff;font-weight:700;letter-spacing:1px;margin-bottom:8px'>3-VIEW ANALYSIS</div>"
            "<div style='font-size:14px;font-weight:700;color:#e8f4ff;margin-bottom:14px'>" + str(persp.get("key_event","")) + "</div>"
            "<div style='background:#003318;border-left:3px solid #00e676;border-radius:6px;padding:10px;margin-bottom:8px'>"
            "<div style='font-size:10px;font-weight:700;color:#00e676;margin-bottom:4px'>BULL CASE</div>"
            "<div style='font-size:13px;color:#cdd9e5;line-height:1.6'>" + str(persp.get("bull_view","")) + "</div></div>"
            "<div style='background:#1a1a00;border-left:3px solid #ffd600;border-radius:6px;padding:10px;margin-bottom:8px'>"
            "<div style='font-size:10px;font-weight:700;color:#ffd600;margin-bottom:4px'>NEUTRAL CASE</div>"
            "<div style='font-size:13px;color:#cdd9e5;line-height:1.6'>" + str(persp.get("neutral_view","")) + "</div></div>"
            "<div style='background:#330008;border-left:3px solid #ff1744;border-radius:6px;padding:10px'>"
            "<div style='font-size:10px;font-weight:700;color:#ff1744;margin-bottom:4px'>BEAR CASE</div>"
            "<div style='font-size:13px;color:#cdd9e5;line-height:1.6'>" + str(persp.get("bear_view","")) + "</div></div>"
            "</div>"
        )

    return (
        "<!DOCTYPE html><html><head><meta charset='UTF-8'></head>"
        "<body style='margin:0;padding:0;background:#060c16;font-family:Arial,sans-serif'>"
        "<div style='max-width:600px;margin:0 auto;padding:16px'>"
        # Header
        "<div style='background:#0d1a2e;border-radius:12px 12px 0 0;padding:18px 22px;"
        "border-top:3px solid #00c8ff;border-bottom:1px solid #1e3050'>"
        "<div style='font-size:11px;color:#5a7a9f;margin-bottom:2px'>" + sent_emoji + " " + SESS_LABEL.upper() + " · " + TIME + " · " + DATE + "</div>"
        "<div style='font-size:22px;font-weight:700;color:#e8f4ff'>Hi " + name + ", here's your Nifty brief</div>"
        "</div>"
        # Hero
        "<div style='background:#0d1a2e;padding:20px 22px;border-bottom:1px solid #1e3050'>"
        "<div style='display:flex;justify-content:space-between;align-items:center'>"
        "<div>"
        "<div style='font-size:11px;color:#5a7a9f;font-weight:700;letter-spacing:1px;margin-bottom:4px'>NIFTY 50</div>"
        "<div style='font-size:44px;font-weight:700;color:" + change_color + ";line-height:1'>" + nifty_p + "</div>"
        "<div style='font-size:20px;font-weight:700;color:" + change_color + ";margin-top:4px'>" + nifty_c + " " + nifty_pct + "</div>"
        "</div>"
        "<div style='text-align:center;background:#111e35;border:2px solid " + score_color + ";"
        "border-radius:12px;padding:14px 18px'>"
        "<div style='font-size:10px;color:" + score_color + ";font-weight:700;letter-spacing:1px'>SENTIMENT</div>"
        "<div style='font-size:40px;font-weight:700;color:" + score_color + ";line-height:1.1'>" + str(score) + "</div>"
        "<div style='font-size:13px;color:" + score_color + ";font-weight:700'>" + sent_lbl.upper() + "</div>"
        "</div></div></div>"
        # Gift + VIX
        "<div style='display:flex;border-bottom:1px solid #1e3050'>"
        "<div style='flex:1;background:#0d1a2e;padding:14px 22px;border-right:1px solid #1e3050'>"
        "<div style='font-size:10px;color:#00c8ff;font-weight:700;letter-spacing:1px'>GIFT NIFTY GAP</div>"
        "<div style='font-size:26px;font-weight:700;color:" + gap_color + ";margin-top:3px'>" + gift_gap + " pts</div>"
        "<div style='font-size:12px;color:#5a7a9f'>" + gift_sig + "</div></div>"
        "<div style='flex:1;background:#0d1a2e;padding:14px 22px'>"
        "<div style='font-size:10px;color:#b388ff;font-weight:700;letter-spacing:1px'>INDIA VIX</div>"
        "<div style='font-size:26px;font-weight:700;color:#e8f4ff;margin-top:3px'>" + vix_v + "</div>"
        "<div style='font-size:12px;color:#5a7a9f'>" + vix_lev + "</div></div></div>"
        # Pivots
        "<div style='background:#0d1a2e;padding:14px 22px;border-bottom:1px solid #1e3050'>"
        "<div style='font-size:10px;color:#5a7a9f;font-weight:700;letter-spacing:1px;margin-bottom:8px'>KEY PIVOT LEVELS</div>"
        "<div style='display:flex;gap:8px'>"
        "<div style='flex:1;text-align:center;background:#2a0a0a;border:1px solid #ff174440;border-radius:8px;padding:8px'>"
        "<div style='font-size:10px;color:#ff1744;font-weight:700'>R1</div>"
        "<div style='font-size:16px;font-weight:700;color:#ff1744'>" + r1_ + "</div></div>"
        "<div style='flex:1;text-align:center;background:#0a1a2e;border:2px solid #00c8ff60;border-radius:8px;padding:8px'>"
        "<div style='font-size:10px;color:#00c8ff;font-weight:700'>PP</div>"
        "<div style='font-size:16px;font-weight:700;color:#00c8ff'>" + pp_ + "</div></div>"
        "<div style='flex:1;text-align:center;background:#002a12;border:1px solid #00e67640;border-radius:8px;padding:8px'>"
        "<div style='font-size:10px;color:#00e676;font-weight:700'>S1</div>"
        "<div style='font-size:16px;font-weight:700;color:#00e676'>" + s1_ + "</div></div>"
        "</div></div>"
        # News
        "<div style='background:#0d1a2e;border-bottom:1px solid #1e3050'>"
        "<div style='padding:10px 22px 4px;font-size:10px;color:#5a7a9f;font-weight:700;letter-spacing:1px'>MARKET NEWS</div>"
        "<table style='width:100%;border-collapse:collapse'>" + news_rows + "</table></div>"
        # Verdict
        "<div style='background:#001a08;border-left:4px solid #00e676;padding:14px 22px;border-bottom:1px solid #1e3050'>"
        "<div style='font-size:10px;color:#00e676;font-weight:700;letter-spacing:1px;margin-bottom:6px'>TRADING VERDICT</div>"
        "<div style='font-size:14px;color:#cdd9e5;line-height:1.7'>" + verdict + "</div></div>"
        + persp_section +
        # CTA
        "<div style='background:#0d1a2e;padding:20px;text-align:center;border-radius:0 0 12px 12px;margin-top:14px'>"
        "<a href='" + DASHBOARD_URL + "' style='display:inline-block;background:linear-gradient(135deg,#0066cc,#00c8ff);"
        "color:#fff;font-weight:700;font-size:15px;padding:14px 36px;border-radius:8px;"
        "text-decoration:none'>Open Live Dashboard →</a>"
        "<div style='font-size:11px;color:#3a5a7f;margin-top:14px'>AI-generated brief · Not financial advice"
        "<br><a href='UNSUBSCRIBE_LINK' style='color:#3a5a7f;font-size:10px'>Unsubscribe</a></div>"
        "</div></div></body></html>"
    )

def send_email_to(name, email):
    subject = sent_emoji + " Nifty " + SESS_LABEL + " | " + nifty_p + " (" + nifty_c + ") | " + sent_lbl + " " + str(score) + "/100"
    msg            = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = "Nifty Live <" + GMAIL_USER + ">"
    msg["To"]      = email
    plain = ("Nifty " + SESS_LABEL + " | " + DATE + " " + TIME + "\n\n"
             "Nifty 50: " + nifty_p + " (" + nifty_c + ")\nSentiment: " + sent_lbl + " " + str(score) + "/100\n"
             "Verdict: " + verdict[:200] + "\n\nDashboard: " + DASHBOARD_URL)
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(build_email_html(name), "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
        srv.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        srv.sendmail(GMAIL_USER, email, msg.as_string())

# ── TELEGRAM SENDER ───────────────────────────────────────────────────────────
def get_telegram_chat_id(username):
    """
    We can't look up chat ID from username directly.
    Subscribers must message the bot first — their chat ID is stored in the sheet.
    Column D in the sheet should contain their numeric Telegram chat ID
    (tell users to message your bot and you'll read from getUpdates).
    """
    try:
        return int(username.strip())
    except:
        return None

def send_telegram_to(chat_id, name):
    imp_e  = {"positive":"🟢","negative":"🔴","neutral":"⚪"}
    news_l = ""
    for item in news:
        ie     = imp_e.get(item.get("impact","neutral"),"⚪")
        news_l += ie + " " + item.get("headline","") + "\n"

    persp_block = ""
    if persp.get("key_event") and SESSION == "morning_brief":
        persp_block = (
            "\n<b>3-VIEW ANALYSIS</b>\n"
            "📌 <i>" + str(persp.get("key_event","")) + "</i>\n"
            "🟢 " + str(persp.get("bull_view",""))[:120] + "...\n"
            "🟡 " + str(persp.get("neutral_view",""))[:120] + "...\n"
            "🔴 " + str(persp.get("bear_view",""))[:120] + "...\n"
        )

    msg = (
        "<b>" + sent_emoji + " Hi " + name + "! Nifty " + SESS_LABEL.upper() + " | " + DATE + "</b>\n\n"
        "<b>Nifty 50: <code>" + nifty_p + "</code> (" + nifty_c + " " + nifty_pct + ")</b>\n"
        "Sentiment: <b>" + sent_lbl + " " + str(score) + "/100</b>\n\n"
        "Gift Gap: <code>" + gift_gap + " pts</code> · VIX: <code>" + vix_v + "</code>\n"
        "R1: <code>" + r1_ + "</code> · PP: <code>" + pp_ + "</code> · S1: <code>" + s1_ + "</code>\n\n"
        "<b>News:</b>\n" + news_l + "\n"
        "<b>Verdict:</b>\n" + verdict[:250] + "\n"
        + persp_block +
        "\n━━━━━━━━━━━━━━━━━━━━\n"
        "🔗 <a href='" + DASHBOARD_URL + "'>Open Live Dashboard</a>\n"
        "<i>Not financial advice</i>"
    )

    url     = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage"
    payload = urllib.parse.urlencode({
        "chat_id":    chat_id,
        "text":       msg,
        "parse_mode": "HTML",
    }).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        result = json.loads(r.read())
        if not result.get("ok"):
            raise Exception(str(result))

# ── RUN BROADCAST ─────────────────────────────────────────────────────────────
try:
    subscribers = get_subscribers()
except Exception as e:
    print("Could not read sheet: " + str(e))
    subscribers = []

email_ok, email_fail = 0, 0
tg_ok, tg_fail       = 0, 0

for sub in subscribers:
    name     = sub["name"]
    email    = sub["email"]
    telegram = sub.get("telegram","")

    # Email
    try:
        send_email_to(name, email)
        email_ok += 1
        print("Email sent: " + email)
    except Exception as e:
        email_fail += 1
        print("Email failed: " + email + " - " + str(e)[:60])
    time.sleep(1.2)  # ~1 email/sec to stay within Gmail limits

    # Telegram
    chat_id = get_telegram_chat_id(telegram)
    if chat_id:
        try:
            send_telegram_to(chat_id, name)
            tg_ok += 1
            print("Telegram sent: " + name)
        except Exception as e:
            tg_fail += 1
            print("Telegram failed: " + name + " - " + str(e)[:60])
        time.sleep(0.05)  # 20/sec max

print("")
print("Broadcast complete!")
print("Emails: " + str(email_ok) + " sent, " + str(email_fail) + " failed")
print("Telegram: " + str(tg_ok) + " sent, " + str(tg_fail) + " failed")

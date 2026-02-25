"""
Nifty Brief — Telegram + Email Notifier
Sends a summary + dashboard link at each market session
"""

import os, json, re, urllib.request, urllib.parse, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta

# ── SECRETS (add to GitHub) ───────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]   # from @BotFather
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]     # your personal chat ID
GMAIL_USER         = os.environ["GMAIL_USER"]           # your.email@gmail.com
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]   # Gmail App Password (not login password)
NOTIFY_EMAIL       = os.environ.get("NOTIFY_EMAIL", os.environ["GMAIL_USER"])  # where to send

DASHBOARD_URL = "https://Sameerxceed.github.io/nifty-dashboard/"

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

SESSION     = get_session()
SESS_LABEL  = SESSION_LABELS.get(SESSION, "Update")

# ── LOAD DATA ─────────────────────────────────────────────────────────────────
with open("data.json") as f:
    data = json.load(f)

n       = data.get("nifty", {})
s       = data.get("sentiment", {})
g       = data.get("gift", {})
vix_d   = data.get("vix", {})
p       = data.get("pivot", {})
news    = data.get("news", [])[:3]
score   = int(s.get("score", 50))
brief   = data.get("brief", "")
persp   = data.get("perspectives", {})

verdict_m = re.search(r"TRADING VERDICT:?(.*?)(?:\n\n|\Z)", brief, re.IGNORECASE|re.DOTALL)
verdict   = verdict_m.group(1).strip().replace("\n"," ")[:300] if verdict_m else ""

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

# Emoji helpers
def sent_emoji(score):
    if score > 65: return "🟢"
    if score > 55: return "🟡"
    if score < 35: return "🔴"
    if score < 45: return "🟠"
    return "⚪"

def chg_emoji(v):
    return "📈" if str(v).startswith("+") else "📉"

def gap_emoji(sig):
    if "up"   in sig.lower(): return "⬆️"
    if "down" in sig.lower(): return "⬇️"
    return "➡️"

SE  = sent_emoji(score)
CE  = chg_emoji(nifty_c)
GE  = gap_emoji(gift_sig)

# ── TELEGRAM ──────────────────────────────────────────────────────────────────
def send_telegram(message):
    url     = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage"
    payload = urllib.parse.urlencode({
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       message,
        "parse_mode": "HTML",
        "disable_web_page_preview": "false",
    }).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        result = json.loads(r.read())
    if result.get("ok"):
        print("Telegram: sent successfully")
    else:
        print("Telegram error: " + str(result))

# Build Telegram message — rich HTML formatting
news_lines = ""
imp_e = {"positive":"🟢","negative":"🔴","neutral":"⚪"}
for item in news:
    ie = imp_e.get(item.get("impact","neutral"),"⚪")
    news_lines += ie + " " + item.get("headline","") + "\n"

tg_msg = (
    "<b>" + SE + " NIFTY " + SESS_LABEL.upper() + " | " + DATE + "</b>\n"
    "⏰ " + TIME + " IST\n\n"
    "<b>" + CE + " Nifty 50</b>\n"
    "  Price:  <code>" + nifty_p + "</code>\n"
    "  Change: <code>" + nifty_c + "  " + nifty_pct + "</code>\n"
    "  Mood:   <b>" + sent_lbl + " " + str(score) + "/100</b>\n\n"
)

if SESSION == "morning_brief":
    tg_msg += (
        "<b>" + GE + " Gift Nifty Gap</b>\n"
        "  Gap: <code>" + gift_gap + " pts</code>  (" + gift_sig + ")\n\n"
        "<b>📊 India VIX</b>\n"
        "  <code>" + vix_v + "</code>  — " + vix_lev + "\n\n"
        "<b>🎯 Key Pivots</b>\n"
        "  R1: <code>" + r1_ + "</code>  |  PP: <code>" + pp_ + "</code>  |  S1: <code>" + s1_ + "</code>\n\n"
    )

if news_lines:
    tg_msg += "<b>📰 Market News</b>\n" + news_lines + "\n"

if verdict:
    tg_msg += "<b>⚡ Trading Verdict</b>\n" + verdict + "\n\n"

if persp.get("key_event") and SESSION == "morning_brief":
    tg_msg += (
        "<b>3-VIEW ANALYSIS</b>\n"
        "📌 <i>" + str(persp.get("key_event","")) + "</i>\n"
        "🟢 Bull: " + str(persp.get("bull_view",""))[:120] + "...\n"
        "⚪ Neutral: " + str(persp.get("neutral_view",""))[:120] + "...\n"
        "🔴 Bear: " + str(persp.get("bear_view",""))[:120] + "...\n\n"
    )

tg_msg += (
    "━━━━━━━━━━━━━━━━━━━━\n"
    "🔗 <a href='" + DASHBOARD_URL + "'>Open Live Dashboard</a>\n"
    "<i>Not financial advice</i>"
)

# ── EMAIL ─────────────────────────────────────────────────────────────────────
def send_email(subject, html_body, text_body):
    msg                   = MIMEMultipart("alternative")
    msg["Subject"]        = subject
    msg["From"]           = GMAIL_USER
    msg["To"]             = NOTIFY_EMAIL
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, NOTIFY_EMAIL, msg.as_string())
    print("Email: sent to " + NOTIFY_EMAIL)

score_color   = "#00e676" if score>55 else "#ff1744" if score<45 else "#ffd600"
change_color  = "#00e676" if nifty_c.startswith("+") else "#ff1744"
gap_color     = "#00e676" if "UP" in gift_sig else "#ff1744" if "DOWN" in gift_sig else "#ffd600"

news_rows = ""
imp_color = {"positive":"#00e676","negative":"#ff1744","neutral":"#b0bec5"}
for item in news:
    ic = imp_color.get(item.get("impact","neutral"),"#b0bec5")
    news_rows += (
        "<tr style='border-bottom:1px solid #1e3050'>"
        "<td style='padding:8px 12px;font-size:11px;font-weight:700;color:" + ic + ";white-space:nowrap'>"
        + item.get("tag","") + "</td>"
        "<td style='padding:8px 12px;font-size:13px;color:#cdd9e5'>" + item.get("headline","") + "</td>"
        "<td style='padding:8px 12px;font-size:16px;color:" + ic + ";text-align:right'>"
        + ("▲" if item.get("impact")=="positive" else "▼" if item.get("impact")=="negative" else "●") + "</td>"
        "</tr>"
    )

persp_section = ""
if persp.get("key_event") and SESSION == "morning_brief":
    persp_section = """
    <div style='background:#0d1a2e;border:1px solid #1e3050;border-radius:12px;padding:20px;margin-top:16px'>
      <div style='font-size:11px;color:#00c8ff;font-weight:700;letter-spacing:1px;margin-bottom:10px'>3-VIEW ANALYSIS</div>
      <div style='font-size:14px;font-weight:700;color:#e8f4ff;margin-bottom:16px'>""" + str(persp.get("key_event","")) + """</div>
      <div style='background:#003318;border-left:3px solid #00e676;border-radius:6px;padding:12px;margin-bottom:10px'>
        <div style='font-size:11px;font-weight:700;color:#00e676;margin-bottom:6px'>BULL CASE</div>
        <div style='font-size:13px;color:#cdd9e5;line-height:1.6'>""" + str(persp.get("bull_view","")) + """</div>
      </div>
      <div style='background:#1a1a00;border-left:3px solid #ffd600;border-radius:6px;padding:12px;margin-bottom:10px'>
        <div style='font-size:11px;font-weight:700;color:#ffd600;margin-bottom:6px'>NEUTRAL CASE</div>
        <div style='font-size:13px;color:#cdd9e5;line-height:1.6'>""" + str(persp.get("neutral_view","")) + """</div>
      </div>
      <div style='background:#330008;border-left:3px solid #ff1744;border-radius:6px;padding:12px'>
        <div style='font-size:11px;font-weight:700;color:#ff1744;margin-bottom:6px'>BEAR CASE</div>
        <div style='font-size:13px;color:#cdd9e5;line-height:1.6'>""" + str(persp.get("bear_view","")) + """</div>
      </div>
    </div>"""

email_html = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style='margin:0;padding:0;background:#060c16;font-family:Arial,sans-serif'>
<div style='max-width:600px;margin:0 auto;padding:20px'>

  <!-- Header -->
  <div style='background:#0d1a2e;border-radius:12px 12px 0 0;padding:20px 24px;border-bottom:2px solid #00c8ff'>
    <div style='display:flex;justify-content:space-between;align-items:center'>
      <div>
        <div style='font-size:20px;font-weight:700;color:#e8f4ff'>NIFTY LIVE</div>
        <div style='font-size:12px;color:#5a7a9f;margin-top:2px'>AI Market Intelligence · NSE India</div>
      </div>
      <div style='text-align:right'>
        <div style='font-size:13px;color:#00c8ff;font-weight:700'>""" + SESS_LABEL.upper() + """</div>
        <div style='font-size:12px;color:#5a7a9f'>""" + TIME + " · " + DATE + """</div>
      </div>
    </div>
  </div>

  <!-- Nifty Hero -->
  <div style='background:#0d1a2e;padding:24px;border-bottom:1px solid #1e3050'>
    <div style='display:flex;justify-content:space-between;align-items:center'>
      <div>
        <div style='font-size:11px;color:#5a7a9f;font-weight:700;letter-spacing:1px;margin-bottom:6px'>NIFTY 50</div>
        <div style='font-size:42px;font-weight:700;color:""" + change_color + """;line-height:1'>""" + nifty_p + """</div>
        <div style='font-size:18px;font-weight:700;color:""" + change_color + """;margin-top:4px'>""" + nifty_c + " " + nifty_pct + """</div>
      </div>
      <div style='text-align:center;background:#111e35;border:2px solid """ + score_color + """;border-radius:12px;padding:16px 20px'>
        <div style='font-size:11px;color:""" + score_color + """;font-weight:700;letter-spacing:1px'>SENTIMENT</div>
        <div style='font-size:38px;font-weight:700;color:""" + score_color + """;line-height:1.1'>""" + str(score) + """</div>
        <div style='font-size:13px;color:""" + score_color + """;font-weight:700'>""" + sent_lbl.upper() + """</div>
      </div>
    </div>
  </div>

  <!-- Gift + VIX -->
  <div style='display:flex;gap:0;border-bottom:1px solid #1e3050'>
    <div style='flex:1;background:#0d1a2e;padding:16px 24px;border-right:1px solid #1e3050'>
      <div style='font-size:11px;color:#00c8ff;font-weight:700;letter-spacing:1px'>GIFT NIFTY GAP</div>
      <div style='font-size:26px;font-weight:700;color:""" + gap_color + """;margin-top:4px'>""" + gift_gap + """ pts</div>
      <div style='font-size:13px;color:#5a7a9f;margin-top:2px'>""" + gift_sig + """</div>
    </div>
    <div style='flex:1;background:#0d1a2e;padding:16px 24px'>
      <div style='font-size:11px;color:#b388ff;font-weight:700;letter-spacing:1px'>INDIA VIX</div>
      <div style='font-size:26px;font-weight:700;color:#e8f4ff;margin-top:4px'>""" + vix_v + """</div>
      <div style='font-size:13px;color:#5a7a9f;margin-top:2px'>""" + vix_lev + """</div>
    </div>
  </div>

  <!-- Pivots -->
  <div style='background:#0d1a2e;padding:16px 24px;border-bottom:1px solid #1e3050'>
    <div style='font-size:11px;color:#5a7a9f;font-weight:700;letter-spacing:1px;margin-bottom:10px'>KEY PIVOT LEVELS</div>
    <div style='display:flex;gap:8px'>
      <div style='flex:1;text-align:center;background:#2a0a0a;border:1px solid #ff174440;border-radius:8px;padding:8px'>
        <div style='font-size:10px;color:#ff1744;font-weight:700'>R1</div>
        <div style='font-size:16px;font-weight:700;color:#ff1744'>""" + r1_ + """</div>
      </div>
      <div style='flex:1;text-align:center;background:#0a1a2e;border:2px solid #00c8ff60;border-radius:8px;padding:8px'>
        <div style='font-size:10px;color:#00c8ff;font-weight:700'>PP</div>
        <div style='font-size:16px;font-weight:700;color:#00c8ff'>""" + pp_ + """</div>
      </div>
      <div style='flex:1;text-align:center;background:#002a12;border:1px solid #00e67640;border-radius:8px;padding:8px'>
        <div style='font-size:10px;color:#00e676;font-weight:700'>S1</div>
        <div style='font-size:16px;font-weight:700;color:#00e676'>""" + s1_ + """</div>
      </div>
    </div>
  </div>

  <!-- News -->
  <div style='background:#0d1a2e;border-bottom:1px solid #1e3050'>
    <div style='padding:12px 24px 4px;font-size:11px;color:#5a7a9f;font-weight:700;letter-spacing:1px'>MARKET NEWS</div>
    <table style='width:100%;border-collapse:collapse'>""" + news_rows + """</table>
  </div>

  <!-- Verdict -->
  <div style='background:#001a08;border-left:4px solid #00e676;padding:16px 24px;border-bottom:1px solid #1e3050'>
    <div style='font-size:11px;color:#00e676;font-weight:700;letter-spacing:1px;margin-bottom:8px'>TRADING VERDICT</div>
    <div style='font-size:14px;color:#cdd9e5;line-height:1.7'>""" + verdict + """</div>
  </div>

  """ + persp_section + """

  <!-- CTA Button -->
  <div style='background:#0d1a2e;padding:24px;text-align:center;border-radius:0 0 12px 12px'>
    <a href='""" + DASHBOARD_URL + """'
       style='display:inline-block;background:linear-gradient(135deg,#0066cc,#00c8ff);
              color:#fff;font-weight:700;font-size:15px;padding:14px 36px;
              border-radius:8px;text-decoration:none;letter-spacing:0.5px'>
      Open Live Dashboard →
    </a>
    <div style='font-size:11px;color:#3a5a7f;margin-top:16px'>
      This is an automated AI-generated brief. Not financial advice.
    </div>
  </div>

</div></body></html>"""

# Plain text fallback
email_text = (
    "NIFTY " + SESS_LABEL.upper() + " | " + DATE + " " + TIME + "\n\n"
    "Nifty 50: " + nifty_p + " (" + nifty_c + " " + nifty_pct + ")\n"
    "Sentiment: " + sent_lbl + " " + str(score) + "/100\n"
    "Gift Nifty Gap: " + gift_gap + " pts (" + gift_sig + ")\n"
    "India VIX: " + vix_v + " (" + vix_lev + ")\n\n"
    "Pivots: R1=" + r1_ + " | PP=" + pp_ + " | S1=" + s1_ + "\n\n"
    "Trading Verdict:\n" + verdict + "\n\n"
    "Dashboard: " + DASHBOARD_URL + "\n"
    "Not financial advice."
)

email_subject = (
    SE + " Nifty " + SESS_LABEL + " | " + nifty_p + " (" + nifty_c + ") | " + sent_lbl + " " + str(score) + "/100"
)

# ── SEND BOTH ─────────────────────────────────────────────────────────────────
try:
    send_telegram(tg_msg)
except Exception as e:
    print("Telegram ERROR: " + str(e))

try:
    send_email(email_subject, email_html, email_text)
except Exception as e:
    print("Email ERROR: " + str(e))

print("Notifications done! " + TIME + " IST")

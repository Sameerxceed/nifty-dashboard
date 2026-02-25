"""
Nifty Brief — Instagram & Facebook Auto-Poster
Posts TWO cards: main brief + 3-perspective analysis
"""

import os, json, urllib.request, urllib.parse, base64, time, re
from datetime import datetime, timezone, timedelta
from card_generator import generate_card, generate_perspective_card

META_ACCESS_TOKEN     = os.environ["META_ACCESS_TOKEN"]
INSTAGRAM_ACCOUNT_ID  = os.environ["INSTAGRAM_ACCOUNT_ID"]
FACEBOOK_PAGE_ID      = os.environ["FACEBOOK_PAGE_ID"]
IMGBB_API_KEY         = os.environ["IMGBB_API_KEY"]

IST     = timezone(timedelta(hours=5, minutes=30))
now_ist = datetime.now(IST)
DATE    = now_ist.strftime("%d %b %Y")
TIME    = now_ist.strftime("%I:%M %p IST")

def get_session():
    t = now_ist.hour*60+now_ist.minute
    if t < 9*60+15:  return "morning_brief"
    if t < 11*60+15: return "session_1"
    if t < 13*60+15: return "session_2"
    if t < 15*60+15: return "session_3"
    return "closing"

SESSION = get_session()
SESSION_NAMES = {
    "morning_brief":"Morning Brief","session_1":"Market Open",
    "session_2":"Mid-Morning","session_3":"Post-Lunch","closing":"Pre-Close"
}

print("Loading market data...")
with open("data.json") as f:
    data = json.load(f)

def upload_image(path, name):
    print("Uploading: " + name)
    with open(path,"rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    payload = urllib.parse.urlencode({"key":IMGBB_API_KEY,"image":b64,"name":name}).encode()
    req = urllib.request.Request("https://api.imgbb.com/1/upload",data=payload,method="POST")
    with urllib.request.urlopen(req,timeout=30) as r:
        return json.loads(r.read())["data"]["url"]

def ig_post(image_url, caption):
    base = "https://graph.facebook.com/v18.0/"
    p1 = urllib.parse.urlencode({"image_url":image_url,"caption":caption,"access_token":META_ACCESS_TOKEN}).encode()
    req1 = urllib.request.Request(base+INSTAGRAM_ACCOUNT_ID+"/media",data=p1,method="POST")
    with urllib.request.urlopen(req1,timeout=30) as r:
        cid = json.loads(r.read()).get("id")
    p2 = urllib.parse.urlencode({"creation_id":cid,"access_token":META_ACCESS_TOKEN}).encode()
    req2 = urllib.request.Request(base+INSTAGRAM_ACCOUNT_ID+"/media_publish",data=p2,method="POST")
    with urllib.request.urlopen(req2,timeout=30) as r:
        return json.loads(r.read()).get("id")

def fb_post(image_url, caption):
    base = "https://graph.facebook.com/v18.0/"
    p = urllib.parse.urlencode({"url":image_url,"caption":caption,"access_token":META_ACCESS_TOKEN}).encode()
    req = urllib.request.Request(base+FACEBOOK_PAGE_ID+"/photos",data=p,method="POST")
    with urllib.request.urlopen(req,timeout=30) as r:
        return json.loads(r.read()).get("id")

# ── CARD 1: Main Market Brief ─────────────────────────────────────────────────
print("Generating main card...")
generate_card(data, SESSION, "nifty_card.png")
img_url = upload_image("nifty_card.png", "nifty_brief_"+now_ist.strftime("%Y%m%d_%H%M"))

n       = data.get("nifty",{})
s       = data.get("sentiment",{})
g       = data.get("gift",{})
news    = data.get("news",[])[:3]
score   = s.get("score",50)
verdict_m = re.search(r"TRADING VERDICT:?(.*?)(?:\n\n|\Z)", data.get("brief",""), re.IGNORECASE|re.DOTALL)
verdict   = verdict_m.group(1).strip().replace("\n"," ")[:220] if verdict_m else ""
emoji_s   = "BULL" if score>55 else "BEAR" if score<45 else "NEUTRAL"
emoji_g   = "GAP UP" if "up" in g.get("signal","") else "GAP DOWN" if "down" in g.get("signal","") else "FLAT"

news_lines = ""
for item in news:
    sym = "UP" if item.get("impact")=="positive" else "DOWN" if item.get("impact")=="negative" else "-"
    news_lines += "[" + sym + "] " + item.get("headline","") + "\n"

caption1 = (
    emoji_s + " NIFTY " + SESSION_NAMES.get(SESSION,"UPDATE") + " | " + DATE + "\n\n"
    "Nifty 50: " + str(n.get("price","")) + " (" + str(n.get("change","")) + ")\n"
    "Gift Nifty Gap: " + str(g.get("gap_pts","")) + " pts (" + emoji_g + ")\n"
    "Sentiment: " + str(s.get("label","")) + " " + str(score) + "/100\n\n"
    "KEY NEWS:\n" + news_lines.strip() + "\n\n"
    "TRADING VERDICT:\n" + verdict + "\n\n"
    "Full dashboard: sameerxceed.github.io/nifty-dashboard\n\n"
    "#Nifty50 #StockMarket #NSE #TradingIndia #NiftyLive #MarketBrief\n"
    "#IndianStockMarket #Sensex #Trading #OptionsTrading #TechnicalAnalysis"
)

# ── CARD 2: 3-Perspective Analysis ───────────────────────────────────────────
persp_url = None
if data.get("perspectives"):
    print("Generating perspectives card...")
    generate_perspective_card(data, SESSION, "nifty_perspectives.png")
    persp_url = upload_image("nifty_perspectives.png", "nifty_persp_"+now_ist.strftime("%Y%m%d_%H%M"))

    persp = data["perspectives"]
    caption2 = (
        "3 VIEWS ON TODAY'S KEY EVENT\n\n"
        + str(persp.get("key_event","")) + "\n\n"
        "BULL CASE:\n" + str(persp.get("bull_view",""))[:180] + "\n\n"
        "NEUTRAL:\n"   + str(persp.get("neutral_view",""))[:180] + "\n\n"
        "BEAR CASE:\n" + str(persp.get("bear_view",""))[:180] + "\n\n"
        "Full analysis: sameerxceed.github.io/nifty-dashboard\n\n"
        "#Nifty50 #BullVsBear #MarketAnalysis #NSE #TradingIndia\n"
        "#IndianStockMarket #NiftyLive #MarketViews #StockMarket"
    )

# ── POST BOTH ─────────────────────────────────────────────────────────────────
for label, url, cap in [
    ("Instagram Card 1", img_url, caption1),
    ("Facebook Card 1",  img_url, caption1),
]:
    try:
        if "Instagram" in label:
            pid = ig_post(url, cap)
        else:
            pid = fb_post(url, cap)
        print(label + ": SUCCESS - " + str(pid))
    except Exception as e:
        print(label + " ERROR: " + str(e))

if persp_url:
    time.sleep(6)
    for label, url, cap in [
        ("Instagram Perspectives", persp_url, caption2),
        ("Facebook Perspectives",  persp_url, caption2),
    ]:
        try:
            if "Instagram" in label:
                pid = ig_post(url, cap)
            else:
                pid = fb_post(url, cap)
            print(label + ": SUCCESS - " + str(pid))
        except Exception as e:
            print(label + " ERROR: " + str(e))

print("All done! " + TIME)

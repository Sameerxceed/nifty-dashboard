import os, json, re, urllib.request
from datetime import datetime
import pytz

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent?key=" + GEMINI_API_KEY
)

IST     = pytz.timezone("Asia/Kolkata")
now_ist = datetime.now(IST)
TODAY   = now_ist.strftime("%A, %d %B %Y")
TIME    = now_ist.strftime("%H:%M")
HOUR    = now_ist.hour
MINUTE  = now_ist.minute

def get_session():
    t = HOUR * 60 + MINUTE
    if t < 9*60+15:  return "morning_brief"
    if t < 11*60+15: return "session_1"
    if t < 13*60+15: return "session_2"
    if t < 15*60+15: return "session_3"
    return "closing"

SESSION = get_session()
SESSION_LABELS = {
    "morning_brief": "Morning Brief 8:00 AM",
    "session_1":     "Market Open 9:15 AM",
    "session_2":     "Mid-Morning 11:15 AM",
    "session_3":     "Post-Lunch 1:15 PM",
    "closing":       "Pre-Close 3:15 PM",
}
SESSION_EMOJIS = {
    "morning_brief": "Sunrise",
    "session_1":     "Chart Up",
    "session_2":     "Sun",
    "session_3":     "Cloud Sun",
    "closing":       "Bell",
}

print("Session: " + SESSION + " | " + TODAY + " " + TIME + " IST")

def call_gemini(prompt, json_mode=False):
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1500},
    }
    if json_mode:
        payload["generationConfig"]["responseMimeType"] = "application/json"
    body = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(GEMINI_URL, data=body,
               headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        result = json.loads(r.read().decode("utf-8"))
    try:
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise ValueError("Bad Gemini response: " + str(result)[:200])

def ask_json(prompt):
    raw = call_gemini(prompt + "\n\nReturn ONLY valid JSON. No markdown, no explanation.", json_mode=True)
    raw = raw.replace("```json","").replace("```","").strip()
    m   = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", raw)
    if not m: raise ValueError("No JSON found")
    return json.loads(m.group(1))

def ask_prose(prompt):
    import time
    for attempt in range(3):
        try:
            result = call_gemini(prompt)
            time.sleep(4)
            return result
        except Exception as e:
            if "429" in str(e):
                wait = 15 * (attempt + 1)
                print("    rate limit on prose, waiting " + str(wait) + "s...")
                time.sleep(wait)
            else:
                print("    prose warning: " + str(e)[:80])
                return ""
    return ""

def safe(key, default, label, prompt):
    import time
    print("  " + label + "...")
    for attempt in range(3):
        try:
            result = ask_json(prompt)
            time.sleep(4)
            return result
        except Exception as e:
            msg = str(e)[:120]
            if "429" in msg:
                wait = 15 * (attempt + 1)
                print("    rate limit, waiting " + str(wait) + "s...")
                time.sleep(wait)
            else:
                print("    warning: " + msg)
                time.sleep(4)
                return default
    print("    failed after 3 attempts")
    return default

# Load previous data
prev_data = {}
if os.path.exists("data.json"):
    with open("data.json") as f:
        prev_data = json.load(f)

morning_prediction = prev_data.get("morning_prediction", {})
data = {}

# Always fetch
data["nifty"] = safe("nifty",
    {"price":"N/A","change":"+0","pct":"+0%","high":"N/A","low":"N/A","trend":"neutral"},
    "Nifty Live",
    "Search Nifty 50 current price today change high low as of " + TODAY + " " + TIME + " IST. "
    'Return JSON: {"price":"XXXXX","change":"+/-XX.XX","pct":"+/-X.XX%","high":"XXXXX","low":"XXXXX","trend":"bullish/bearish/neutral"}')

data["vix"] = safe("vix",
    {"value":"N/A","change":"0","level":"moderate"},
    "India VIX",
    "Search India VIX current value today " + TODAY + ". "
    'Return JSON: {"value":"XX.XX","change":"+/-X.XX","level":"low/moderate/elevated/high"}')

data["news"] = safe("news", [],
    "Breaking News",
    "Search latest 4 breaking news affecting Indian Nifty market now " + TODAY + " " + TIME + ". "
    'Return JSON array: [{"tag":"GEO/MARKET/MACRO","headline":"under 15 words","impact":"positive/negative/neutral","time":"HH:MM"}]')

if SESSION == "morning_brief":
    data["gift"] = safe("gift",
        {"value":"N/A","change":"0","pct":"0%","gap_pts":"0","signal":"flat"},
        "Gift Nifty",
        "Search Gift Nifty pre-market value " + TODAY + ". "
        'Return JSON: {"value":"XXXXX","change":"+/-XX","pct":"+/-X.XX%","gap_pts":"+/-XX","signal":"gap_up/gap_down/flat"}')

    data["crude"] = safe("crude",
        {"price":"N/A","change":"0","pct":"0%","signal":"neutral"},
        "Crude",
        "Search WTI crude oil price " + TODAY + ". "
        'Return JSON: {"price":"XX.XX","change":"+/-X.XX","pct":"+/-X.XX%","signal":"bullish/bearish/neutral"}')

    data["inr"] = safe("inr",
        {"rate":"N/A","change":"0","signal":"stable"},
        "USD/INR",
        "Search USD INR exchange rate today " + TODAY + ". "
        'Return JSON: {"rate":"XX.XX","change":"+/-X.XX","signal":"rupee_strong/rupee_weak/stable"}')

    data["fiidii"] = safe("fiidii",
        {"fii":{"buy":"N/A","sell":"N/A","net":"N/A"},"dii":{"buy":"N/A","sell":"N/A","net":"N/A"},"signal":"mixed"},
        "FII/DII",
        "Search FII DII activity NSE India " + TODAY + ". "
        'Return JSON: {"fii":{"buy":"XXXX","sell":"XXXX","net":"+/-XXXX"},"dii":{"buy":"XXXX","sell":"XXXX","net":"+/-XXXX"},"signal":"both_buying/both_selling/mixed"}')

    data["pivot"] = safe("pivot",
        {"prev_high":"N/A","prev_low":"N/A","prev_close":"N/A","r3":"N/A","r2":"N/A","r1":"N/A","pp":"N/A","s1":"N/A","s2":"N/A","s3":"N/A"},
        "Pivots",
        "Search Nifty 50 yesterday OHLC calculate standard pivot points " + TODAY + ". "
        'Return JSON: {"prev_high":"XXXXX","prev_low":"XXXXX","prev_close":"XXXXX","r3":"XXXXX","r2":"XXXXX","r1":"XXXXX","pp":"XXXXX","s1":"XXXXX","s2":"XXXXX","s3":"XXXXX"}')

    data["oi"] = safe("oi",
        {"max_pain":"N/A","pcr":"N/A","pcr_signal":"neutral","top_ce_strike":"N/A","top_pe_strike":"N/A"},
        "OI/MaxPain",
        "Search Nifty 50 options max pain PCR weekly expiry " + TODAY + ". "
        'Return JSON: {"max_pain":"XXXXX","pcr":"X.XX","pcr_signal":"bullish/bearish/neutral","top_ce_strike":"XXXXX","top_pe_strike":"XXXXX"}')

    data["global_mkts"] = safe("global_mkts", [],
        "Global Markets",
        "Search overnight Dow Jones Nasdaq Nikkei Hang Seng FTSE " + TODAY + ". "
        'Return JSON array: [{"name":"...","value":"...","change":"+/-XXX","pct":"+/-X.XX%"}]')

    data["sentiment"] = safe("sentiment",
        {"score":50,"label":"Neutral","summary":"Market analysis pending."},
        "Sentiment",
        "Rate overall Nifty 50 opening sentiment " + TODAY + " based on Gift Nifty crude VIX FII global USD/INR. "
        'Return JSON: {"score":50,"label":"Bullish","summary":"2 sentences"}')

    data["morning_prediction"] = {
        "bias":       data["sentiment"].get("label","Neutral"),
        "score":      data["sentiment"].get("score", 50),
        "pivot_pp":   data["pivot"].get("pp","N/A"),
        "nifty_open": data["nifty"].get("price","N/A"),
        "time":       TIME,
    }

    data["brief"] = ask_prose(
        "Write concise Nifty 50 morning brief for " + TODAY + ". "
        "Sections: GIFT NIFTY: | CRUDE OIL: | USD/INR: | INDIA VIX: | GLOBAL MARKETS: | "
        "FII+DII FLOWS: | PIVOT LEVELS: | OI & MAX PAIN: | TRADING VERDICT: "
        "2-3 sentences each with numbers. TRADING VERDICT: gap, bias, key levels, trade idea."
    )

else:
    # carry forward morning data
    for k in ["gift","crude","inr","fiidii","pivot","oi","global_mkts","sentiment"]:
        data[k] = prev_data.get(k, {})
    data["morning_prediction"] = prev_data.get("morning_prediction", {})
    data["brief"] = prev_data.get("brief", "Morning brief not yet generated.")

    # Accuracy tracker
    mp = data["morning_prediction"]
    try:
        cur  = float(str(data["nifty"]["price"]).replace(",",""))
        opn  = float(str(mp.get("nifty_open","0")).replace(",",""))
        bias = mp.get("bias","Neutral")
        scr  = mp.get("score", 50)
        mv   = cur - opn
        ok   = (mv > 0 and scr > 55) or (mv < 0 and scr < 45) or (abs(mv) < 30 and 45 <= scr <= 55)
        sign = "+" if mv >= 0 else ""
        data["accuracy"] = {
            "morning_bias": bias, "open_price": mp.get("nifty_open","N/A"),
            "current_price": data["nifty"]["price"],
            "move_pts": sign + str(round(mv)), "correct": ok,
            "verdict": "On Track" if ok else "Reversed",
        }
    except:
        data["accuracy"] = {
            "morning_bias": mp.get("bias","N/A"), "open_price": mp.get("nifty_open","N/A"),
            "current_price": data["nifty"].get("price","N/A"),
            "move_pts": "N/A", "correct": None, "verdict": "Tracking",
        }

    # Pivot breach alerts
    try:
        cp = float(str(data["nifty"]["price"]).replace(",",""))
        pv = data.get("pivot",{})
        breaches = []
        for lbl, key in [("R3","r3"),("R2","r2"),("R1","r1"),("PP","pp"),("S1","s1"),("S2","s2"),("S3","s3")]:
            val = pv.get(key,"N/A")
            if val != "N/A":
                fv = float(str(val).replace(",",""))
                if abs(cp - fv) / fv * 100 < 0.3:
                    breaches.append({"level": lbl, "value": val, "type": "AT"})
                elif cp > fv and lbl.startswith("R"):
                    breaches.append({"level": lbl, "value": val, "type": "ABOVE"})
                elif cp < fv and lbl.startswith("S"):
                    breaches.append({"level": lbl, "value": val, "type": "BELOW"})
        data["pivot_alerts"] = breaches[:3]
    except:
        data["pivot_alerts"] = []

    data["intraday_analysis"] = ask_prose(
        "Nifty 50 intraday update " + SESSION_LABELS.get(SESSION, SESSION) + " on " + TODAY + ". "
        "Current Nifty: " + str(data["nifty"].get("price","N/A")) + " (" + str(data["nifty"].get("change","N/A")) + "). "
        "Morning prediction was " + str(data["morning_prediction"].get("bias","N/A")) + " score " + str(data["morning_prediction"].get("score","N/A")) + ". "
        "VIX: " + str(data["vix"].get("value","N/A")) + ". "
        "In 3-4 sentences: Was morning prediction correct? Current trend? What to watch next session? Key pivot levels?"
    )

# Session timeline
data["session"]       = SESSION
data["session_label"] = SESSION_LABELS.get(SESSION, SESSION)
data["updated_time"]  = TIME
data["updated_date"]  = TODAY

prev_sessions = prev_data.get("all_sessions", [])
new_entry = {
    "time": TIME, "session": SESSION,
    "label": SESSION_LABELS.get(SESSION, SESSION),
    "nifty": data["nifty"].get("price","N/A"),
    "change": data["nifty"].get("change","N/A"),
    "trend": data["nifty"].get("trend","neutral"),
}
data["all_sessions"] = [s for s in prev_sessions if s.get("session") != SESSION] + [new_entry]

with open("data.json","w") as f:
    json.dump(data, f, indent=2)
print("data.json saved")

# ── HTML BUILDER ──────────────────────────────────────────────────────────────

def sig_color(v):
    s = str(v).lower()
    if any(x in s for x in ["bull","gap_up","strong","buy","low","positive","complacent","above","rupee_str"]):
        return "#00f088"
    if any(x in s for x in ["bear","gap_down","weak","sell","elevated","high","negative","panic","below","rupee_weak"]):
        return "#ff3355"
    return "#ffcc00"

def chg_color(v):
    return "#00f088" if str(v).startswith("+") else "#ff3355"

def esc(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def badge(text, color):
    bg = color + "18"
    return (
        '<span style="display:inline-block;font-size:9px;font-weight:700;padding:2px 8px;'
        'border-radius:20px;border:1px solid ' + color + '44;'
        'background:' + bg + ';color:' + color + '">' + esc(text).upper() + '</span>'
    )

def metric_card(icon, label, value, sub, sig):
    sc = sig_color(sig)
    return (
        '<div style="background:#0d1422;border:1px solid #182236;border-radius:12px;padding:14px 16px">'
        '<div style="font-size:9px;color:#2a3d58;font-weight:700;text-transform:uppercase;'
        'letter-spacing:0.8px;margin-bottom:8px">' + icon + ' ' + label + '</div>'
        '<div style="font-size:22px;font-weight:700;font-family:monospace;color:#d8eeff;'
        'line-height:1;margin-bottom:4px">' + esc(value) + '</div>'
        '<div style="font-size:10px;color:#7a9cbf;margin-bottom:6px">' + sub + '</div>'
        + badge(str(sig).replace("_"," "), sc) +
        '</div>'
    )

def global_rows(markets):
    if not markets:
        return '<tr><td colspan="3" style="text-align:center;color:#2a3d58;padding:12px;font-size:12px">No data</td></tr>'
    rows = ""
    for m in markets:
        c = chg_color(m.get("change",""))
        rows += (
            '<tr style="border-bottom:1px solid #182236">'
            '<td style="padding:7px 10px;font-size:11px;font-weight:700;color:#d8eeff">' + esc(m.get("name","")) + '</td>'
            '<td style="padding:7px 10px;font-size:11px;font-family:monospace;color:#d8eeff;text-align:right">' + esc(m.get("value","")) + '</td>'
            '<td style="padding:7px 10px;font-size:11px;font-family:monospace;color:' + c + ';text-align:right;font-weight:700">' + esc(m.get("change","")) + ' ' + esc(m.get("pct","")) + '</td>'
            '</tr>'
        )
    return rows

def news_items(items):
    if not items:
        return '<div style="font-size:12px;color:#2a3d58;text-align:center;padding:16px">No news</div>'
    tag_c = {"GEO":"#ff6b35","MARKET":"#00c8ff","MACRO":"#b388ff"}
    imp_s = {"positive":"▲","negative":"▼","neutral":"●"}
    imp_c = {"positive":"#00f088","negative":"#ff3355","neutral":"#7a9cbf"}
    out = ""
    for n in items:
        tag = n.get("tag","MARKET")
        imp = n.get("impact","neutral")
        tc  = tag_c.get(tag,"#00c8ff")
        out += (
            '<div style="padding:9px 0;border-bottom:1px solid #182236;font-size:12px;color:#7a9cbf;line-height:1.5">'
            '<span style="font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;'
            'margin-right:6px;background:' + tc + '22;color:' + tc + '">' + esc(tag) + '</span>'
            + esc(n.get("headline","")) +
            '<span style="color:' + imp_c.get(imp,"#7a9cbf") + ';margin-left:6px">' + imp_s.get(imp,"●") + '</span>'
            + ('<span style="font-size:9px;color:#2a3d58;margin-left:8px">' + esc(n.get("time","")) + '</span>' if n.get("time") else "")
            + '</div>'
        )
    return out

def pivot_cells(p):
    items = [("R3","r3","#ff3355"),("R2","r2","#ff3355"),("R1","r1","#ff3355"),
             ("PP","pp","#00d4ff"),("S1","s1","#00f088"),("S2","s2","#00f088"),("S3","s3","#00f088")]
    out = ""
    for lbl, key, col in items:
        bg = "rgba(255,51,85,0.07)" if lbl[0]=="R" else ("rgba(0,212,255,0.07)" if lbl=="PP" else "rgba(0,240,136,0.07)")
        bd = "rgba(255,51,85,0.25)" if lbl[0]=="R" else ("rgba(0,212,255,0.3)" if lbl=="PP" else "rgba(0,240,136,0.25)")
        out += (
            '<div style="text-align:center;background:' + bg + ';border:1px solid ' + bd + ';'
            'border-radius:8px;padding:8px 2px">'
            '<div style="font-size:8px;font-weight:700;color:' + col + ';margin-bottom:3px">' + lbl + '</div>'
            '<div style="font-size:12px;font-weight:700;font-family:monospace;color:' + col + '">' + esc(p.get(key,"—")) + '</div>'
            '</div>'
        )
    return out

def session_timeline(sessions):
    if not sessions:
        return '<div style="font-size:12px;color:#2a3d58;text-align:center;padding:16px">No sessions yet</div>'
    tc = {"bullish":"#00f088","bearish":"#ff3355","neutral":"#ffcc00"}
    out = ""
    for s in sessions:
        c   = tc.get(s.get("trend","neutral"),"#ffcc00")
        chg = s.get("change","")
        cc  = chg_color(chg)
        out += (
            '<div style="display:flex;gap:12px;padding:10px 0;border-bottom:1px solid #182236">'
            '<div style="width:10px;height:10px;border-radius:50%;background:' + c + ';margin-top:4px;flex-shrink:0"></div>'
            '<div style="flex:1">'
            '<div style="font-size:9px;color:#2a3d58;font-weight:700">' + esc(s.get("time","")) + ' IST</div>'
            '<div style="font-size:11px;color:#7a9cbf;margin-top:1px">' + esc(s.get("label","")) + '</div>'
            '<div style="font-size:13px;font-weight:700;margin-top:2px;font-family:monospace;color:#d8eeff">'
            + esc(s.get("nifty","—")) + ' <span style="color:' + cc + '">' + esc(chg) + '</span></div>'
            '</div></div>'
        )
    return out

def accuracy_card(acc):
    if not acc: return ""
    correct = acc.get("correct")
    vc = "#00f088" if correct else "#ff3355" if correct is False else "#ffcc00"
    mv = acc.get("move_pts","N/A")
    mvcol = chg_color(str(mv))
    return (
        '<div style="background:rgba(0,212,255,0.05);border:1px solid rgba(0,212,255,0.15);'
        'border-radius:12px;padding:14px 16px;margin-bottom:10px">'
        '<div style="font-size:10px;font-weight:700;color:#00d4ff;text-transform:uppercase;'
        'letter-spacing:1px;margin-bottom:10px">Prediction Accuracy</div>'
        '<div style="display:flex;justify-content:space-between;font-size:11px;color:#7a9cbf;'
        'padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.04)">Morning Bias'
        '<strong style="color:' + sig_color(acc.get("morning_bias","")) + '">' + esc(acc.get("morning_bias","N/A")) + '</strong></div>'
        '<div style="display:flex;justify-content:space-between;font-size:11px;color:#7a9cbf;'
        'padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.04)">Open Price'
        '<strong style="color:#d8eeff">' + esc(acc.get("open_price","N/A")) + '</strong></div>'
        '<div style="display:flex;justify-content:space-between;font-size:11px;color:#7a9cbf;'
        'padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.04)">Current'
        '<strong style="color:#d8eeff">' + esc(acc.get("current_price","N/A")) + '</strong></div>'
        '<div style="display:flex;justify-content:space-between;font-size:11px;color:#7a9cbf;'
        'padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.04)">Move'
        '<strong style="color:' + mvcol + '">' + esc(mv) + ' pts</strong></div>'
        '<div style="text-align:center;font-size:15px;font-weight:700;margin-top:10px;'
        'padding:8px;background:rgba(255,255,255,0.03);border-radius:8px;color:' + vc + '">'
        + esc(acc.get("verdict","Tracking")) + '</div>'
        '</div>'
    )

def pivot_alerts_html(alerts):
    if not alerts: return ""
    tc = {"AT":"#ffcc00","ABOVE":"#00f088","BELOW":"#ff3355"}
    items = ""
    for a in alerts:
        t   = a.get("type","AT")
        col = tc.get(t,"#ffcc00")
        items += (
            '<div style="font-size:12px;font-weight:700;padding:4px 0;'
            'border-bottom:1px solid rgba(255,255,255,0.04);color:' + col + '">'
            + esc(t) + " " + esc(a.get("level","")) + " - " + esc(a.get("value","")) + '</div>'
        )
    return (
        '<div style="background:rgba(255,204,0,0.06);border:1px solid rgba(255,204,0,0.2);'
        'border-radius:12px;padding:14px 16px">'
        '<div style="font-size:10px;font-weight:700;color:#ffcc00;text-transform:uppercase;'
        'letter-spacing:1px;margin-bottom:10px">Pivot Alerts</div>'
        + items + '</div>'
    )

def format_brief(text):
    keys = ["GIFT NIFTY","CRUDE OIL","USD/INR","INDIA VIX","GLOBAL MARKETS",
            "FII+DII FLOWS","PIVOT LEVELS","OI & MAX PAIN","TRADING VERDICT"]
    em   = {"GIFT NIFTY":"Gift","CRUDE OIL":"Oil","USD/INR":"Currency","INDIA VIX":"Chart",
            "GLOBAL MARKETS":"Globe","FII+DII FLOWS":"Bank","PIVOT LEVELS":"Ruler",
            "OI & MAX PAIN":"Target","TRADING VERDICT":"Lightning"}
    out  = text
    for h in keys:
        color = "#ff8c00" if "VERDICT" in h else "#00c8ff"
        out = re.sub(
            "(" + re.escape(h) + ":?)",
            '<span style="display:block;font-size:9px;font-weight:700;color:' + color + ';'
            'text-transform:uppercase;letter-spacing:1.5px;margin-top:14px;margin-bottom:3px">\\1</span>',
            out, flags=re.IGNORECASE
        )
    nl2 = "\n\n"
    nl1 = "\n"
    out = out.replace(nl2, "</p><p style='margin:4px 0;line-height:1.8;color:#8aadc8;font-size:13px'>")
    out = out.replace(nl1, " ")
    return "<p style='margin:0;line-height:1.8;color:#8aadc8;font-size:13px'>" + out + "</p>"

# ── ASSEMBLE PAGE ─────────────────────────────────────────────────────────────
n       = data["nifty"]
s       = data["sentiment"] if "sentiment" in data else {"score":50,"label":"Neutral","summary":""}
p       = data.get("pivot",{})
oi_d    = data.get("oi",{})
f_d     = data.get("fiidii",{"fii":{"buy":"N/A","sell":"N/A","net":"N/A"},"dii":{"buy":"N/A","sell":"N/A","net":"N/A"}})
g_d     = data.get("gift",{"value":"N/A","change":"0","pct":"0%","gap_pts":"0","signal":"flat"})
crude_d = data.get("crude",{"price":"N/A","change":"0","pct":"0%","signal":"neutral"})
inr_d   = data.get("inr",{"rate":"N/A","change":"0","signal":"stable"})
score   = int(s.get("score",50))
sc_col  = "#00f088" if score > 55 else "#ff3355" if score < 45 else "#ffcc00"
nifty_c = chg_color(n.get("change",""))
is_intraday = SESSION != "morning_brief"
acc     = data.get("accuracy",{})
alerts  = data.get("pivot_alerts",[])
intra   = data.get("intraday_analysis","")
brief   = data.get("brief","")
tl      = data.get("all_sessions",[])

# intraday block (pre-built, no f-string issues)
if is_intraday:
    _intra_html = intra.replace("\n\n","</p><p style='margin:4px 0;line-height:1.8;color:#8aadc8;font-size:13px'>").replace("\n"," ")
    intraday_section = (
        '<div style="font-size:10px;font-weight:700;color:#2a3d58;font-family:monospace;'
        'text-transform:uppercase;letter-spacing:1.5px;display:flex;align-items:center;gap:8px;margin:20px 0 10px">'
        'Intraday Update'
        '<span style="flex:1;height:1px;background:#182236;display:block"></span></div>'
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px">'
        '<div style="background:#0d1422;border:1px solid #182236;border-radius:12px;padding:16px 20px">'
        '<div style="font-size:10px;font-weight:700;color:#00d4ff;text-transform:uppercase;'
        'letter-spacing:1px;margin-bottom:10px">' + esc(SESSION_LABELS.get(SESSION,"")) + '</div>'
        "<p style='margin:0;line-height:1.8;color:#8aadc8;font-size:13px'>" + _intra_html + '</p>'
        '</div>'
        '<div>' + accuracy_card(acc) + pivot_alerts_html(alerts) + '</div>'
        '</div>'
    )
else:
    intraday_section = ""

# FII/DII rows
fii = f_d.get("fii",{})
dii = f_d.get("dii",{})
fii_net_col = chg_color(fii.get("net",""))
dii_net_col = chg_color(dii.get("net",""))
fiidii_signal = f_d.get("signal","mixed")

css = """
:root{--bg:#070b12;--bg2:#0b1018;--card:#0d1422;--border:#182236;--border2:#1e2e4a;
  --accent:#00d4ff;--green:#00f088;--red:#ff3355;--yellow:#ffcc00;--text:#d8eeff;--muted:#2a3d58;}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'JetBrains Mono',monospace;background:var(--bg);color:var(--text);min-height:100vh;
  background-image:radial-gradient(ellipse 80% 40% at 50% -10%,rgba(0,150,255,0.07),transparent),
  radial-gradient(ellipse 60% 30% at 80% 100%,rgba(0,200,100,0.04),transparent)}
.hdr{background:var(--bg2);border-bottom:1px solid var(--border);padding:14px 20px;
  display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;
  position:sticky;top:0;z-index:100;backdrop-filter:blur(10px)}
.logo{width:38px;height:38px;background:linear-gradient(135deg,var(--accent),#0044ff);
  border-radius:9px;display:flex;align-items:center;justify-content:center;font-weight:700;
  font-size:13px;color:#000;box-shadow:0 0 16px rgba(0,212,255,0.3)}
.main{max-width:1100px;margin:0 auto;padding:16px 16px 40px}
.g4{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.g2{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px 16px}
.sec{font-size:10px;font-weight:700;color:var(--muted);font-family:monospace;
  text-transform:uppercase;letter-spacing:1.5px;display:flex;align-items:center;
  gap:8px;margin:20px 0 10px}
.sec::after{content:'';flex:1;height:1px;background:var(--border)}
table{width:100%;border-collapse:collapse}
.hero{padding:20px;background:var(--bg2);border-bottom:1px solid var(--border)}
@media(max-width:800px){.g4{grid-template-columns:repeat(2,1fr)}.g3{grid-template-columns:1fr 1fr}}
@media(max-width:500px){.g2,.g3,.g4{grid-template-columns:1fr}}
"""

html_parts = [
    '<!DOCTYPE html><html lang="en"><head>',
    '<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">',
    '<meta http-equiv="refresh" content="3600">',
    '<title>Nifty Live Dashboard - ' + TODAY + '</title>',
    '<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">',
    '<style>' + css + '</style>',
    '</head><body>',

    # HEADER
    '<div class="hdr">',
    '<div style="display:flex;align-items:center;gap:12px">',
    '<div class="logo">NB</div>',
    '<div><div style="font-size:15px;font-weight:700">Nifty Live Dashboard</div>',
    '<div style="font-size:9px;color:#2a3d58;margin-top:1px">9-Factor AI - NSE - Gemini + Google Search</div></div>',
    '</div>',
    '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">',
    '<span style="background:rgba(0,212,255,0.08);border:1px solid rgba(0,212,255,0.2);color:#00d4ff;'
    'font-size:10px;font-weight:700;padding:4px 10px;border-radius:20px">' + esc(SESSION_LABELS.get(SESSION,"")) + '</span>',
    '<span style="font-size:10px;color:#7a9cbf;background:#0d1422;padding:4px 10px;border-radius:6px;'
    'border:1px solid #182236">Updated ' + TIME + ' IST - ' + now_ist.strftime("%d %b %Y") + '</span>',
    '</div></div>',

    # HERO
    '<div class="hero"><div style="max-width:1100px;margin:0 auto;display:flex;'
    'align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px">',
    '<div>',
    '<div style="font-size:10px;color:#2a3d58;font-weight:700;text-transform:uppercase;'
    'letter-spacing:1.5px;margin-bottom:8px">Nifty 50 - Live</div>',
    '<div style="font-size:52px;font-weight:700;line-height:1;letter-spacing:-2px;color:' + nifty_c + '">' + esc(n.get("price","—")) + '</div>',
    '<div style="font-size:18px;font-weight:700;margin-top:4px;color:' + nifty_c + '">' + esc(n.get("change","—")) + ' (' + esc(n.get("pct","—")) + ')</div>',
    '<div style="display:flex;gap:16px;margin-top:8px">',
    '<span style="font-size:11px;color:#7a9cbf">H: <strong style="color:#d8eeff">' + esc(n.get("high","—")) + '</strong></span>',
    '<span style="font-size:11px;color:#7a9cbf">L: <strong style="color:#d8eeff">' + esc(n.get("low","—")) + '</strong></span>',
    '<span style="font-size:11px;color:#7a9cbf">VIX: <strong style="color:' + sig_color(data["vix"].get("level","")) + '">' + esc(data["vix"].get("value","—")) + '</strong></span>',
    '</div></div>',
    '<div style="text-align:right">',
    '<div style="font-size:10px;color:#2a3d58;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">Sentiment</div>',
    '<div style="font-size:48px;font-weight:700;line-height:1;color:' + sc_col + '">' + str(score) + '</div>',
    '<div style="font-size:12px;color:#7a9cbf;margin-top:2px">' + esc(s.get("label","—")) + '</div>',
    '<div style="width:140px;margin:8px 0 0 auto">',
    '<div style="background:rgba(255,255,255,0.05);border-radius:3px;height:6px;overflow:hidden">',
    '<div style="height:6px;width:' + str(score) + '%;background:linear-gradient(90deg,#ff3355,#ffcc00,#00f088);border-radius:3px"></div>',
    '</div>',
    '<div style="display:flex;justify-content:space-between;font-size:8px;color:#2a3d58;margin-top:3px"><span>BEAR</span><span>NEUTRAL</span><span>BULL</span></div>',
    '</div></div>',
    '</div></div>',

    '<div class="main">',
    intraday_section,

    '<div class="sec">Pre-Market Pulse</div>',
    '<div class="g4">',
    metric_card("Gift", "Gift Nifty", g_d.get("value","—"),
        esc(g_d.get("change","—")) + " (" + esc(g_d.get("pct","—")) + ") Gap: " + esc(g_d.get("gap_pts","—")) + "pts",
        g_d.get("signal","flat")),
    metric_card("FX", "USD/INR", "Rs." + str(inr_d.get("rate","—")),
        "Change: " + esc(inr_d.get("change","—")), inr_d.get("signal","stable")),
    metric_card("Oil", "Crude WTI", "$" + str(crude_d.get("price","—")),
        esc(crude_d.get("change","—")) + " (" + esc(crude_d.get("pct","—")) + ")", crude_d.get("signal","neutral")),
    metric_card("VIX", "India VIX", str(data["vix"].get("value","—")),
        "Change: " + esc(data["vix"].get("change","—")), data["vix"].get("level","moderate")),
    '</div>',

    '<div class="sec">Global Markets &amp; Institutional Flows</div>',
    '<div class="g2">',
    '<div class="card"><div style="font-size:9px;color:#2a3d58;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:10px">Global Markets (Overnight)</div>',
    '<table>' + global_rows(data.get("global_mkts",[])) + '</table></div>',
    '<div class="card"><div style="font-size:9px;color:#2a3d58;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:10px">FII + DII Combined Flow</div>',
    '<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid #182236;font-size:11px">',
    '<span style="color:#00d4ff;font-weight:700">FII</span>',
    '<span>Buy <strong style="color:#00f088">Rs.' + esc(fii.get("buy","—")) + 'Cr</strong></span>',
    '<span>Sell <strong style="color:#ff3355">Rs.' + esc(fii.get("sell","—")) + 'Cr</strong></span>',
    '<strong style="color:' + fii_net_col + '">Net Rs.' + esc(fii.get("net","—")) + 'Cr</strong></div>',
    '<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid #182236;font-size:11px">',
    '<span style="color:#ffcc00;font-weight:700">DII</span>',
    '<span>Buy <strong style="color:#00f088">Rs.' + esc(dii.get("buy","—")) + 'Cr</strong></span>',
    '<span>Sell <strong style="color:#ff3355">Rs.' + esc(dii.get("sell","—")) + 'Cr</strong></span>',
    '<strong style="color:' + dii_net_col + '">Net Rs.' + esc(dii.get("net","—")) + 'Cr</strong></div>',
    '<div style="margin-top:10px;font-size:11px;color:#7a9cbf">Signal: <strong style="color:' + sig_color(fiidii_signal) + '">' + esc(fiidii_signal).replace("_"," ").upper() + '</strong></div>',
    '</div></div>',

    '<div class="sec">Nifty Pivot Levels - H:' + esc(p.get("prev_high","—")) + ' L:' + esc(p.get("prev_low","—")) + ' C:' + esc(p.get("prev_close","—")) + '</div>',
    '<div class="card">',
    '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:5px">' + pivot_cells(p) + '</div>',
    '<div style="margin-top:10px;font-size:10px;color:#7a9cbf">Above ' + esc(p.get("pp","—")) + ' = Bullish - Below = Bearish - Current: <strong style="color:' + nifty_c + '">' + esc(n.get("price","—")) + '</strong></div>',
    '</div>',

    '<div class="sec">Options Data &amp; Breaking News</div>',
    '<div class="g2">',
    '<div class="card"><div style="font-size:9px;color:#2a3d58;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:10px">OI &amp; Max Pain</div>',
    '<div class="g3">',
    '<div style="text-align:center;background:rgba(179,136,255,0.08);border:1px solid rgba(179,136,255,0.2);border-radius:10px;padding:12px">',
    '<div style="font-size:9px;color:#b388ff;font-weight:700;margin-bottom:4px">MAX PAIN</div>',
    '<div style="font-size:22px;font-weight:700;font-family:monospace;color:#b388ff">' + esc(oi_d.get("max_pain","—")) + '</div>',
    '<div style="font-size:10px;color:#7a9cbf;margin-top:4px">PCR: <strong>' + esc(oi_d.get("pcr","—")) + '</strong></div>',
    '</div>',
    '<div style="text-align:center;background:rgba(255,51,85,0.08);border:1px solid rgba(255,51,85,0.2);border-radius:10px;padding:12px">',
    '<div style="font-size:9px;color:#ff3355;font-weight:700;margin-bottom:4px">MAX CALL OI</div>',
    '<div style="font-size:22px;font-weight:700;font-family:monospace;color:#ff3355">' + esc(oi_d.get("top_ce_strike","—")) + '</div>',
    '<div style="font-size:10px;color:#7a9cbf;margin-top:4px">Resistance</div>',
    '</div>',
    '<div style="text-align:center;background:rgba(0,240,136,0.08);border:1px solid rgba(0,240,136,0.2);border-radius:10px;padding:12px">',
    '<div style="font-size:9px;color:#00f088;font-weight:700;margin-bottom:4px">MAX PUT OI</div>',
    '<div style="font-size:22px;font-weight:700;font-family:monospace;color:#00f088">' + esc(oi_d.get("top_pe_strike","—")) + '</div>',
    '<div style="font-size:10px;color:#7a9cbf;margin-top:4px">Support</div>',
    '</div></div></div>',
    '<div class="card"><div style="font-size:9px;color:#2a3d58;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:10px">Breaking News</div>',
    news_items(data.get("news",[])),
    '</div></div>',

    '<div class="sec">Session Timeline &amp; Morning Brief</div>',
    '<div class="g2">',
    '<div class="card"><div style="font-size:9px;color:#2a3d58;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:10px">Todays Sessions</div>',
    session_timeline(tl),
    '</div>',
    '<div class="card"><div style="font-size:9px;color:#2a3d58;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:10px">Morning Brief - Gemini AI</div>',
    format_brief(brief),
    '</div></div>',

    '<div style="text-align:center;padding:24px 0 0;font-size:10px;color:#2a3d58">',
    'Nifty Live Dashboard - Auto-generated at ' + TIME + ' IST - Powered by Gemini AI + Google Search<br>',
    '<span style="margin-top:4px;display:block">For informational purposes only. Not financial advice.</span>',
    '</div>',
    '</div></body></html>'
]

html_output = "".join(html_parts)

with open("index.html","w",encoding="utf-8") as f2:
    f2.write(html_output)
print("index.html built successfully")

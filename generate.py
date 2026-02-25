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
            time.sleep(2)
            return result
        except Exception as e:
            if "429" in str(e):
                wait = 12 * (attempt + 1)
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
            time.sleep(2)
            return result
        except Exception as e:
            msg = str(e)[:120]
            if "429" in msg:
                wait = 12 * (attempt + 1)
                print("    rate limit, waiting " + str(wait) + "s...")
                time.sleep(wait)
            else:
                print("    warning: " + msg)
                time.sleep(2)
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
    "Breaking News + 3 Views",
    "Search latest 4 most important breaking news events affecting Indian Nifty 50 market right now " + TODAY + " " + TIME + ". "
    "For each news item also provide a bull, neutral, and bear interpretation for Nifty traders. "
    'Return JSON array: ['
    '  {"tag":"GEO/MARKET/MACRO/SECTOR","headline":"under 12 words","impact":"positive/negative/neutral","time":"HH:MM",'
    '   "bull":"1 sentence bullish take for Nifty with level/target",'
    '   "neutral":"1 sentence neutral take and what to watch",'
    '   "bear":"1 sentence bearish risk for Nifty with level"}'
    ']' )

if SESSION == "morning_brief":
    import concurrent.futures, threading

    # Run all 8 data fetches in parallel (4 threads) to cut time from ~80s to ~25s
    def fetch_all():
        tasks = {
            "gift":    ("Gift Nifty",
                "Search Gift Nifty pre-market value " + TODAY + ". "
                'Return JSON: {"value":"XXXXX","change":"+/-XX","pct":"+/-X.XX%","gap_pts":"+/-XX","signal":"gap_up/gap_down/flat"}',
                {"value":"N/A","change":"0","pct":"0%","gap_pts":"0","signal":"flat"}),
            "crude":   ("Crude Oil",
                "Search WTI crude oil price " + TODAY + ". "
                'Return JSON: {"price":"XX.XX","change":"+/-X.XX","pct":"+/-X.XX%","signal":"bullish/bearish/neutral"}',
                {"price":"N/A","change":"0","pct":"0%","signal":"neutral"}),
            "inr":     ("USD/INR",
                "Search USD INR exchange rate today " + TODAY + ". "
                'Return JSON: {"rate":"XX.XX","change":"+/-X.XX","signal":"rupee_strong/rupee_weak/stable"}',
                {"rate":"N/A","change":"0","signal":"stable"}),
            "fiidii":  ("FII/DII",
                "Search FII DII cash market activity NSE India " + TODAY + ". "
                'Return JSON: {"fii":{"buy":"XXXX","sell":"XXXX","net":"+/-XXXX"},"dii":{"buy":"XXXX","sell":"XXXX","net":"+/-XXXX"},"signal":"both_buying/both_selling/mixed"}',
                {"fii":{"buy":"N/A","sell":"N/A","net":"N/A"},"dii":{"buy":"N/A","sell":"N/A","net":"N/A"},"signal":"mixed"}),
            "pivot":   ("Pivots",
                "Search Nifty 50 yesterday high low close calculate standard pivot points " + TODAY + ". "
                'Return JSON: {"prev_high":"XXXXX","prev_low":"XXXXX","prev_close":"XXXXX","r3":"XXXXX","r2":"XXXXX","r1":"XXXXX","pp":"XXXXX","s1":"XXXXX","s2":"XXXXX","s3":"XXXXX"}',
                {"prev_high":"N/A","prev_low":"N/A","prev_close":"N/A","r3":"N/A","r2":"N/A","r1":"N/A","pp":"N/A","s1":"N/A","s2":"N/A","s3":"N/A"}),
            "oi":      ("OI/MaxPain",
                "Search Nifty 50 options max pain PCR weekly expiry " + TODAY + ". "
                'Return JSON: {"max_pain":"XXXXX","pcr":"X.XX","pcr_signal":"bullish/bearish/neutral","top_ce_strike":"XXXXX","top_pe_strike":"XXXXX"}',
                {"max_pain":"N/A","pcr":"N/A","pcr_signal":"neutral","top_ce_strike":"N/A","top_pe_strike":"N/A"}),
            "global_mkts": ("Global Markets",
                "Search overnight Dow Jones Nasdaq Nikkei Hang Seng FTSE performance " + TODAY + ". "
                'Return JSON array: [{"name":"...","value":"...","change":"+/-XXX","pct":"+/-X.XX%"}]',
                []),
            "sentiment": ("Sentiment",
                "Rate overall Nifty 50 opening sentiment " + TODAY + " based on Gift Nifty crude VIX FII global USD/INR. "
                'Return JSON: {"score":50,"label":"Bullish","summary":"2 sentences"}',
                {"score":50,"label":"Neutral","summary":"Market analysis pending."}),
        }
        lock = threading.Lock()
        results = {}

        def do_fetch(key):
            label, prompt, default = tasks[key]
            val = safe(key, default, label, prompt)
            with lock:
                results[key] = val

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            futs = {ex.submit(do_fetch, k): k for k in tasks}
            concurrent.futures.wait(futs, timeout=300)
        return results

    fetched = fetch_all()
    for k, v in fetched.items():
        data[k] = v

    data["morning_prediction"] = {
        "bias":       data["sentiment"].get("label","Neutral"),
        "score":      data["sentiment"].get("score", 50),
        "pivot_pp":   data["pivot"].get("pp","N/A"),
        "nifty_open": data["nifty"].get("price","N/A"),
        "time":       TIME,
    }

    # 3-perspective analysis for Instagram
    data["perspectives"] = safe("perspectives",
        {"key_event":"Market Summary",
         "bull_view":"Bullish case pending.",
         "neutral_view":"Neutral case pending.",
         "bear_view":"Bearish case pending."},
        "3 Perspectives",
        "Identify the single most important market event or data point for Nifty today " + TODAY + ". "
        "Write 3 perspectives — bull, neutral, bear — on how traders should interpret it. "
        'Return JSON: {"key_event":"headline under 12 words",'
        ' "bull_view":"2-3 sentences bullish take with price targets",'
        ' "neutral_view":"2-3 sentences neutral take with range estimate",'
        ' "bear_view":"2-3 sentences bearish take with downside levels"}'
    )

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

# Always save whatever data we have, even partial
try:
    with open("data.json","w") as f:
        json.dump(data, f, indent=2)
    print("data.json saved")
except Exception as e:
    print("Warning: could not save data.json: " + str(e))

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
    tag_c = {"GEO":"#ff6b35","MARKET":"#00c8ff","MACRO":"#b388ff","SECTOR":"#ffd600"}
    imp_s = {"positive":"▲","negative":"▼","neutral":"●"}
    imp_c = {"positive":"#00f088","negative":"#ff3355","neutral":"#7a9cbf"}
    out   = ""
    uid   = 0
    for n in items:
        uid  += 1
        tag   = n.get("tag","MARKET")
        imp   = n.get("impact","neutral")
        tc    = tag_c.get(tag,"#00c8ff")
        bull  = n.get("bull","")
        neut  = n.get("neutral","")
        bear  = n.get("bear","")
        has3  = bull or neut or bear
        nid   = "nv" + str(uid)
        # main headline row
        out += (
            '<div style="padding:10px 0;border-bottom:1px solid #182236">'
            # tag + headline row
            '<div style="display:flex;align-items:flex-start;gap:6px;flex-wrap:wrap">'
            '<span style="font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px;white-space:nowrap;'
            'background:' + tc + '22;color:' + tc + '">' + esc(tag) + '</span>'
            '<span style="font-size:12px;color:#d8eeff;line-height:1.5;flex:1">' + esc(n.get("headline","")) + '</span>'
            '<span style="color:' + imp_c.get(imp,"#7a9cbf") + ';font-size:13px;font-weight:700">'
            + imp_s.get(imp,"●") + '</span>'
            + ('<span style="font-size:9px;color:#2a3d58;white-space:nowrap">'
               + esc(n.get("time","")) + '</span>' if n.get("time") else "")
            + '</div>'
        )
        # 3-view pills row
        if has3:
            out += (
                '<div style="display:flex;gap:5px;margin-top:7px;flex-wrap:wrap">'
            )
            if bull:
                out += (
                    '<div style="flex:1;min-width:120px;background:rgba(0,240,136,0.06);border:1px solid rgba(0,240,136,0.2);'
                    'border-radius:6px;padding:5px 8px">'
                    '<div style="font-size:8px;font-weight:700;color:#00f088;letter-spacing:0.8px;margin-bottom:3px">▲ BULL</div>'
                    '<div style="font-size:10px;color:#8abf9a;line-height:1.5">' + esc(bull) + '</div>'
                    '</div>'
                )
            if neut:
                out += (
                    '<div style="flex:1;min-width:120px;background:rgba(255,214,0,0.06);border:1px solid rgba(255,214,0,0.2);'
                    'border-radius:6px;padding:5px 8px">'
                    '<div style="font-size:8px;font-weight:700;color:#ffd600;letter-spacing:0.8px;margin-bottom:3px">● NEUTRAL</div>'
                    '<div style="font-size:10px;color:#bfb870;line-height:1.5">' + esc(neut) + '</div>'
                    '</div>'
                )
            if bear:
                out += (
                    '<div style="flex:1;min-width:120px;background:rgba(255,51,85,0.06);border:1px solid rgba(255,51,85,0.2);'
                    'border-radius:6px;padding:5px 8px">'
                    '<div style="font-size:8px;font-weight:700;color:#ff3355;letter-spacing:0.8px;margin-bottom:3px">▼ BEAR</div>'
                    '<div style="font-size:10px;color:#bf8a8a;line-height:1.5">' + esc(bear) + '</div>'
                    '</div>'
                )
            out += '</div>'
        out += '</div>'
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


# ── LIVE DATA JAVASCRIPT VARIABLE ─────────────────────────────────────────────
live_js_script = """<script>
(function(){
"use strict";
const YF_QUOTE="https://query1.finance.yahoo.com/v7/finance/quote?symbols=";
const CORS="https://corsproxy.io/?";
function fmt(n,d=2){return n==null?"\u2014":Number(n).toLocaleString("en-IN",{minimumFractionDigits:d,maximumFractionDigits:d});}
function fmtChg(n){if(n==null)return"\u2014";return(n>=0?"+":"")+fmt(n,2);}
function fmtPct(n){if(n==null)return"\u2014";return(n>=0?"+":"")+fmt(n,2)+"%";}
function col(n){return n>0?"#00f088":n<0?"#ff3355":"#7a9cbf";}
function setEl(id,v){const e=document.getElementById(id);if(e)e.textContent=v;}
function setHTML(id,v){const e=document.getElementById(id);if(e)e.innerHTML=v;}
function setC(id,c){const e=document.getElementById(id);if(e)e.style.color=c;}

function stamp(){
  const n=new Date();
  const ist=new Date(n.getTime()+(5.5*3600000)-n.getTimezoneOffset()*60000);
  const p=x=>String(x).padStart(2,"0");
  setEl("live-stamp","Updated "+p(ist.getHours())+":"+p(ist.getMinutes())+":"+p(ist.getSeconds())+" IST");
}

function market(){
  const n=new Date(),ist=new Date(n.getTime()+5.5*3600000);
  const h=ist.getUTCHours(),m=ist.getUTCMinutes(),d=ist.getUTCDay();
  if(d===0||d===6)return false;
  const t=h*60+m;return t>=9*15&&t<=15*30;
}

async function fetch_yf(syms){
  const url=YF_QUOTE+syms+"&fields=regularMarketPrice,regularMarketChange,regularMarketChangePercent,regularMarketDayHigh,regularMarketDayLow,shortName,symbol";
  try{const r=await fetch(url);if(!r.ok)throw 0;const d=await r.json();return d.quoteResponse.result||[];}
  catch(e){
    try{const r=await fetch(CORS+encodeURIComponent(url));const d=await r.json();return d.quoteResponse.result||[];}
    catch(e2){return[];}
  }
}

async function poll(){
  stamp();
  try{
    const qs=await fetch_yf("%5ENSEI,%5ENSEBANK,%5EINDIAVIX");
    if(!qs.length)return;
    const nifty=qs.find(q=>q.symbol.includes("NSEI")&&!q.symbol.includes("BANK"))||qs[0];
    const bank =qs.find(q=>q.symbol.includes("BANK"));
    const vix  =qs.find(q=>q.symbol.includes("INDIAVIX"));
    const c=col(nifty.regularMarketChange);
    setEl("live-price", fmt(nifty.regularMarketPrice,2));
    setEl("live-chg",   fmtChg(nifty.regularMarketChange)+" ("+fmtPct(nifty.regularMarketChangePercent)+")");
    setEl("live-high",  fmt(nifty.regularMarketDayHigh,2));
    setEl("live-low",   fmt(nifty.regularMarketDayLow,2));
    setC("live-price",c); setC("live-chg",c);
    if(vix){
      const vc=vix.regularMarketPrice>16?"#ff3355":vix.regularMarketPrice>12?"#ffcc00":"#00f088";
      setEl("live-vix",fmt(vix.regularMarketPrice,2)); setC("live-vix",vc);
    }
    // ticker strip
    const parts=qs.map(q=>{
      const qc=col(q.regularMarketChange);
      return "<span style='margin-right:20px;white-space:nowrap'>"
        +"<span style='color:#4a6a8a;font-size:9px'>"+( q.shortName||q.symbol)+"</span> "
        +"<span style='color:"+qc+";font-weight:700'>"+fmt(q.regularMarketPrice,2)+"</span>"
        +" <span style='color:"+qc+";font-size:10px'>"+fmtChg(q.regularMarketChange)+" ("+fmtPct(q.regularMarketChangePercent)+")</span>"
        +"</span>";
    });
    setHTML("live-ticker",parts.join("<span style='color:#182236'>|</span>"));
    const b=document.getElementById("live-badge");
    if(b){b.style.display="inline-flex";b.textContent="● LIVE";b.style.color="#00f088";}
  }catch(e){
    const b=document.getElementById("live-badge");
    if(b){b.style.color="#ffcc00";b.textContent="○ Delayed";}
  }
}

function countdown(){
  const sessions=[[8,0,"Morning Brief"],[9,15,"Market Open"],[11,15,"Mid-Morning"],[13,15,"Post-Lunch"],[15,15,"Pre-Close"]];
  const n=new Date(),ist=new Date(n.getTime()+5.5*3600000);
  const h=ist.getUTCHours(),m=ist.getUTCMinutes(),s=ist.getUTCSeconds();
  const cur=h*3600+m*60+s;
  let nxt=null,lbl="";
  for(const[sh,sm,sl]of sessions){const t=sh*3600+sm*60;if(t>cur){nxt=t;lbl=sl;break;}}
  if(!nxt){setEl("next-session","All sessions done for today");return;}
  const d=nxt-cur,rh=Math.floor(d/3600),rm=Math.floor((d%3600)/60),rs=d%60;
  const p=x=>String(x).padStart(2,"0");
  setEl("next-session","Next: "+lbl+" in "+(rh>0?rh+"h ":"")+p(rm)+"m "+p(rs)+"s");
}

// Stale data warning
function checkStale(){
  const genTimeEl = document.getElementById("gen-time");
  if(!genTimeEl) return;
  const genTimeStr = genTimeEl.getAttribute("data-ts");
  if(!genTimeStr) return;
  const genTime = new Date(parseInt(genTimeStr)*1000);
  const ageHours = (Date.now() - genTime.getTime()) / 3600000;
  const bannerEl = document.getElementById("stale-banner");
  if(bannerEl && ageHours > 2){
    bannerEl.style.display = "block";
    bannerEl.innerHTML = "⚠ Dashboard data is " + Math.floor(ageHours) + "h old — last GitHub Actions run may have failed. "
      + "Live price is fetched directly below. "
      + "<a href=\"https://github.com/Sameerxceed/nifty-morning-brief/actions\" target=\"_blank\" "
      + "style=\"color:#00c8ff\">Check Actions log →</a>";
  }
}

window.addEventListener("DOMContentLoaded",function(){
  poll();
  checkStale();
  setInterval(function(){if(market())poll();else stamp();},60000);
  setInterval(countdown,1000);
  countdown();
});
})();
</script>"""



def perspectives_section(data):
    """Render the 3-view analysis card on the dashboard."""
    p = data.get("perspectives", {})
    if not p or not p.get("key_event"):
        return ""
    bull  = esc(p.get("bull_view",""))
    neut  = esc(p.get("neutral_view",""))
    bear  = esc(p.get("bear_view",""))
    event = esc(p.get("key_event",""))
    return (
        '<div class="sec">3-View Analysis &#x2014; Key Event</div>'
        '<div style="background:#0b1220;border:1px solid #1e3050;border-radius:12px;padding:16px 20px;margin-bottom:16px">'
        '<div style="font-size:10px;color:#2a3d58;font-weight:700;letter-spacing:1px;margin-bottom:4px">KEY EVENT</div>'
        '<div style="font-size:14px;font-weight:700;color:#d8eeff;margin-bottom:16px">' + event + '</div>'
        '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px">'
        # Bull
        '<div style="background:rgba(0,240,136,0.05);border:1px solid rgba(0,240,136,0.2);border-radius:10px;padding:14px">'
        '<div style="font-size:9px;font-weight:700;color:#00f088;letter-spacing:1px;margin-bottom:8px">▲ BULL CASE</div>'
        '<div style="font-size:12px;color:#7abf8a;line-height:1.7">' + bull + '</div>'
        '</div>'
        # Neutral
        '<div style="background:rgba(255,214,0,0.05);border:1px solid rgba(255,214,0,0.2);border-radius:10px;padding:14px">'
        '<div style="font-size:9px;font-weight:700;color:#ffd600;letter-spacing:1px;margin-bottom:8px">● NEUTRAL CASE</div>'
        '<div style="font-size:12px;color:#bfb080;line-height:1.7">' + neut + '</div>'
        '</div>'
        # Bear
        '<div style="background:rgba(255,51,85,0.05);border:1px solid rgba(255,51,85,0.2);border-radius:10px;padding:14px">'
        '<div style="font-size:9px;font-weight:700;color:#ff3355;letter-spacing:1px;margin-bottom:8px">▼ BEAR CASE</div>'
        '<div style="font-size:12px;color:#bf7a7a;line-height:1.7">' + bear + '</div>'
        '</div>'
        '</div>'
        '</div>'
    )

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
    'border:1px solid #182236"><span id="live-stamp">Updated ' + TIME + ' IST</span> - ' + now_ist.strftime("%d %b %Y") + '</span>',
    '<span id="live-badge" style="display:none;font-size:10px;font-weight:700;color:#00f088;'
    'background:rgba(0,240,136,0.08);border:1px solid rgba(0,240,136,0.3);'
    'padding:4px 10px;border-radius:6px">● LIVE</span>',
    '</div></div>',

    # Stale-data banner (hidden by default, shown by JS if data > 2h old)
    '<div id="stale-banner" style="display:none;background:#1a0a00;border-left:4px solid #ff8c00;'
    'padding:10px 20px;font-size:12px;color:#ff8c00;line-height:1.5"></div>',
    # Hidden gen-time element so JS can compute data age
    '<span id="gen-time" data-ts="' + str(int(now_ist.timestamp())) + '" style="display:none"></span>',

    # HERO
    '<div class="hero"><div style="max-width:1100px;margin:0 auto;display:flex;'
    'align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px">',
    '<div>',
    '<div style="font-size:10px;color:#2a3d58;font-weight:700;text-transform:uppercase;'
    'letter-spacing:1.5px;margin-bottom:8px">Nifty 50 - Live</div>',
    '<div id="live-price" style="font-size:52px;font-weight:700;line-height:1;letter-spacing:-2px;color:' + nifty_c + '">' + esc(n.get("price","—")) + '</div>',
    '<div id="live-chg" style="font-size:18px;font-weight:700;margin-top:4px;color:' + nifty_c + '">' + esc(n.get("change","—")) + ' (' + esc(n.get("pct","—")) + ')</div>',
    '<div style="display:flex;gap:16px;margin-top:8px">',
    '<span style="font-size:11px;color:#7a9cbf">H: <strong id="live-high" style="color:#d8eeff">' + esc(n.get("high","—")) + '</strong></span>',
    '<span style="font-size:11px;color:#7a9cbf">L: <strong id="live-low" style="color:#d8eeff">' + esc(n.get("low","—")) + '</strong></span>',
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

    # Live ticker strip + next session countdown
    '<div style="background:#070d17;border-bottom:1px solid #0d1422;padding:8px 20px;'    'display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;overflow:hidden">',
    '<div id="live-ticker" style="font-size:11px;color:#4a6a8a;overflow:hidden;white-space:nowrap">',
    '<span style="color:#4a6a8a">Fetching live data...</span>',
    '</div>',
    '<div id="next-session" style="font-size:10px;color:#4a6a8a;white-space:nowrap;'    'background:#0d1422;padding:4px 10px;border-radius:6px;border:1px solid #182236">',
    'Calculating...</div>',
    '</div>',

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

    perspectives_section(data),

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
    live_js_script,
    '</div></body></html>'
]

html_output = "".join(html_parts)

with open("index.html","w",encoding="utf-8") as f2:
    f2.write(html_output)
print("index.html built successfully")

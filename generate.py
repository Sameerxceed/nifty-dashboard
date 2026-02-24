import os
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime
import pytz

# ── CONFIG ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
)

IST     = pytz.timezone("Asia/Kolkata")
now_ist = datetime.now(IST)
TODAY   = now_ist.strftime("%A, %d %B %Y")
TIME    = now_ist.strftime("%H:%M")
HOUR    = now_ist.hour
MINUTE  = now_ist.minute

# Determine session type
def get_session():
    t = HOUR * 60 + MINUTE
    if t < 9*60+15:    return "morning_brief"
    if t < 11*60+15:   return "session_1"
    if t < 13*60+15:   return "session_2"
    if t < 15*60+15:   return "session_3"
    return "closing"

SESSION = get_session()
SESSION_LABELS = {
    "morning_brief": "🌅 Morning Brief  ·  8:00 AM",
    "session_1":     "📈 Mid-Morning Update  ·  9:15 AM",
    "session_2":     "☀️ Afternoon Update  ·  11:15 AM",
    "session_3":     "🌤 Post-Lunch Update  ·  1:15 PM",
    "closing":       "🔔 Pre-Close Update  ·  3:15 PM",
}

print(f"Session: {SESSION} | {TODAY} {TIME} IST")

# ── GEMINI CALL ───────────────────────────────────────────────────────────────
def call_gemini(prompt: str, json_mode=False) -> str:
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
        raise ValueError(f"Bad Gemini response: {str(result)[:200]}")

def ask_json(prompt: str):
    raw = call_gemini(prompt + "\n\nReturn ONLY valid JSON. No markdown, no explanation.", json_mode=True)
    raw = raw.replace("```json","").replace("```","").strip()
    m   = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", raw)
    if not m: raise ValueError("No JSON")
    return json.loads(m.group(1))

def ask_prose(prompt: str) -> str:
    return call_gemini(prompt)

def safe(key, default, label, prompt):
    print(f"  {label}...")
    try:
        return ask_json(prompt)
    except Exception as e:
        print(f"    ⚠ {e}")
        return default

# ── LOAD PREVIOUS DATA (for accuracy tracker) ─────────────────────────────────
prev_data = {}
if os.path.exists("data.json"):
    with open("data.json") as f:
        prev_data = json.load(f)

morning_prediction = prev_data.get("morning_prediction", {})

# ── FETCH DATA ────────────────────────────────────────────────────────────────
data = {}

# Always fetch these
data["nifty"] = safe("nifty",
    {"price":"N/A","change":"+/-XX","pct":"+/-X.XX%","high":"N/A","low":"N/A","trend":"neutral"},
    "Nifty Live",
    f"Search Nifty 50 current price, today's change, high, low as of {TODAY} {TIME} IST. "
    f'Return JSON: {{"price":"XXXXX","change":"+/-XX.XX","pct":"+/-X.XX%","high":"XXXXX","low":"XXXXX","trend":"bullish/bearish/neutral"}}')

data["vix"] = safe("vix",
    {"value":"N/A","change":"N/A","level":"moderate"},
    "India VIX",
    f"Search India VIX current value today {TODAY}. "
    f'Return JSON: {{"value":"XX.XX","change":"+/-X.XX","level":"low/moderate/elevated/high"}}')

data["news"] = safe("news", [],
    "Breaking News",
    f"Search latest 4 breaking news affecting Indian Nifty market right now {TODAY} {TIME}. "
    f'Return JSON array: [{{"tag":"GEO/MARKET/MACRO","headline":"under 15 words","impact":"positive/negative/neutral","time":"HH:MM"}}]')

# Morning brief — full data fetch
if SESSION == "morning_brief":
    print("  Full morning brief fetch...")

    data["gift"] = safe("gift",
        {"value":"N/A","change":"N/A","pct":"N/A","gap_pts":"N/A","signal":"flat"},
        "Gift Nifty",
        f"Search Gift Nifty pre-market value {TODAY}. "
        f'Return JSON: {{"value":"XXXXX","change":"+/-XX","pct":"+/-X.XX%","gap_pts":"+/-XX","signal":"gap_up/gap_down/flat"}}')

    data["crude"] = safe("crude",
        {"price":"N/A","change":"N/A","pct":"N/A","signal":"neutral"},
        "Crude Oil",
        f"Search WTI crude oil price {TODAY}. "
        f'Return JSON: {{"price":"XX.XX","change":"+/-X.XX","pct":"+/-X.XX%","signal":"bullish/bearish/neutral"}}')

    data["inr"] = safe("inr",
        {"rate":"N/A","change":"N/A","signal":"stable"},
        "USD/INR",
        f"Search USD INR exchange rate today {TODAY}. "
        f'Return JSON: {{"rate":"XX.XX","change":"+/-X.XX","signal":"rupee_strong/rupee_weak/stable"}}')

    data["fiidii"] = safe("fiidii",
        {"fii":{"net":"N/A"},"dii":{"net":"N/A"},"signal":"mixed"},
        "FII/DII",
        f"Search FII DII activity NSE India {TODAY}. "
        f'Return JSON: {{"fii":{{"buy":"XXXX","sell":"XXXX","net":"+/-XXXX"}},"dii":{{"buy":"XXXX","sell":"XXXX","net":"+/-XXXX"}},"signal":"both_buying/both_selling/mixed"}}')

    data["pivot"] = safe("pivot",
        {k:"N/A" for k in ["prev_high","prev_low","prev_close","r3","r2","r1","pp","s1","s2","s3"]},
        "Pivots",
        f"Search Nifty 50 yesterday OHLC calculate standard pivot points {TODAY}. "
        f'Return JSON: {{"prev_high":"XXXXX","prev_low":"XXXXX","prev_close":"XXXXX","r3":"XXXXX","r2":"XXXXX","r1":"XXXXX","pp":"XXXXX","s1":"XXXXX","s2":"XXXXX","s3":"XXXXX"}}')

    data["oi"] = safe("oi",
        {"max_pain":"N/A","pcr":"N/A","top_ce_strike":"N/A","top_pe_strike":"N/A"},
        "OI/Max Pain",
        f"Search Nifty 50 options max pain PCR weekly expiry {TODAY}. "
        f'Return JSON: {{"max_pain":"XXXXX","pcr":"X.XX","pcr_signal":"bullish/bearish/neutral","top_ce_strike":"XXXXX","top_pe_strike":"XXXXX"}}')

    data["global"] = safe("global", [],
        "Global Markets",
        f"Search overnight Dow Jones Nasdaq Nikkei Hang Seng FTSE {TODAY}. "
        f'Return JSON array: [{{"name":"...","value":"...","change":"+/-XXX","pct":"+/-X.XX%"}}]')

    data["sentiment"] = safe("sentiment",
        {"score":50,"label":"Neutral","summary":"N/A"},
        "Sentiment",
        f"Rate overall Nifty 50 opening sentiment {TODAY} based on Gift Nifty crude VIX FII global USD/INR. "
        f'Return JSON: {{"score":50,"label":"Bullish","summary":"2 sentences"}}')

    # Morning prediction (saved for accuracy tracking later)
    data["morning_prediction"] = {
        "bias": data["sentiment"].get("label","Neutral"),
        "score": data["sentiment"].get("score", 50),
        "pivot_pp": data["pivot"].get("pp","N/A"),
        "nifty_open": data["nifty"].get("price","N/A"),
        "time": TIME,
    }

    data["brief"] = ask_prose(
        f"Write concise Nifty 50 morning brief for {TODAY}. Sections: "
        f"GIFT NIFTY: | CRUDE OIL: | USD/INR: | INDIA VIX: | GLOBAL MARKETS: | "
        f"FII+DII FLOWS: | PIVOT LEVELS: | OI & MAX PAIN: | TRADING VERDICT: "
        f"2-3 sentences each with numbers. TRADING VERDICT: gap expectation, bias, key levels, trade idea."
    )

else:
    # Intraday sessions — carry forward morning data, add updates
    data["gift"]    = prev_data.get("gift", {"value":"N/A","change":"N/A","pct":"N/A","gap_pts":"N/A","signal":"flat"})
    data["crude"]   = prev_data.get("crude", {"price":"N/A","change":"N/A","pct":"N/A","signal":"neutral"})
    data["inr"]     = prev_data.get("inr", {"rate":"N/A","change":"N/A","signal":"stable"})
    data["fiidii"]  = prev_data.get("fiidii", {"fii":{"net":"N/A"},"dii":{"net":"N/A"},"signal":"mixed"})
    data["pivot"]   = prev_data.get("pivot", {k:"N/A" for k in ["r3","r2","r1","pp","s1","s2","s3"]})
    data["oi"]      = prev_data.get("oi", {"max_pain":"N/A","pcr":"N/A","top_ce_strike":"N/A","top_pe_strike":"N/A"})
    data["global"]  = prev_data.get("global", [])
    data["sentiment"] = prev_data.get("sentiment", {"score":50,"label":"Neutral","summary":"N/A"})
    data["morning_prediction"] = prev_data.get("morning_prediction", {})
    data["brief"]   = prev_data.get("brief","Morning brief not yet generated.")

    # Accuracy tracker
    mp = data["morning_prediction"]
    try:
        current_price = float(str(data["nifty"]["price"]).replace(",",""))
        open_price    = float(str(mp.get("nifty_open","0")).replace(",",""))
        pred_bias     = mp.get("bias","Neutral")
        pred_score    = mp.get("score", 50)
        actual_move   = current_price - open_price
        pred_correct  = (actual_move > 0 and pred_score > 55) or \
                        (actual_move < 0 and pred_score < 45) or \
                        (abs(actual_move) < 30 and 45 <= pred_score <= 55)
        data["accuracy"] = {
            "morning_bias": pred_bias,
            "open_price": mp.get("nifty_open","N/A"),
            "current_price": data["nifty"]["price"],
            "move_pts": f"{'+' if actual_move>=0 else ''}{actual_move:.0f}",
            "correct": pred_correct,
            "verdict": "✅ On Track" if pred_correct else "❌ Reversed",
        }
    except:
        data["accuracy"] = {
            "morning_bias": mp.get("bias","N/A"),
            "open_price": mp.get("nifty_open","N/A"),
            "current_price": data["nifty"].get("price","N/A"),
            "move_pts":"N/A","correct":None,"verdict":"⏳ Tracking"
        }

    # Pivot breach check
    try:
        cp = float(str(data["nifty"]["price"]).replace(",",""))
        pivots = data["pivot"]
        breaches = []
        for lbl, key in [("R3","r3"),("R2","r2"),("R1","r1"),("PP","pp"),("S1","s1"),("S2","s2"),("S3","s3")]:
            val = pivots.get(key,"N/A")
            if val != "N/A":
                pv = float(str(val).replace(",",""))
                diff = abs(cp - pv)
                pct  = diff / pv * 100
                if pct < 0.3:
                    breaches.append({"level": lbl, "value": val, "type": "AT"})
                elif cp > pv and lbl.startswith("R"):
                    breaches.append({"level": lbl, "value": val, "type": "ABOVE"})
                elif cp < pv and lbl.startswith("S"):
                    breaches.append({"level": lbl, "value": val, "type": "BELOW"})
        data["pivot_alerts"] = breaches[:3]
    except:
        data["pivot_alerts"] = []

    # Intraday analysis
    session_name = SESSION_LABELS.get(SESSION, SESSION)
    data["intraday_analysis"] = ask_prose(
        f"Nifty 50 intraday update for {session_name} on {TODAY}. "
        f"Current Nifty: {data['nifty'].get('price','N/A')} ({data['nifty'].get('change','N/A')}). "
        f"Morning prediction was {data['morning_prediction'].get('bias','N/A')} with score {data['morning_prediction'].get('score','N/A')}. "
        f"VIX: {data['vix'].get('value','N/A')}. "
        f"In 3-4 sentences: Was the morning prediction correct? What is the current trend? "
        f"What should traders watch for in the next session? Any key pivot levels being tested?"
    )

# ── SESSION META ──────────────────────────────────────────────────────────────
data["session"]       = SESSION
data["session_label"] = SESSION_LABELS.get(SESSION, SESSION)
data["updated_time"]  = TIME
data["updated_date"]  = TODAY
data["all_sessions"]  = prev_data.get("all_sessions", [])

# append current session to timeline
session_entry = {
    "time": TIME,
    "session": SESSION,
    "label": SESSION_LABELS.get(SESSION, SESSION),
    "nifty": data["nifty"].get("price","N/A"),
    "change": data["nifty"].get("change","N/A"),
    "trend": data["nifty"].get("trend","neutral"),
}
# avoid duplicates
existing = [s for s in data["all_sessions"] if s.get("session") != SESSION]
data["all_sessions"] = existing + [session_entry]

# ── SAVE DATA JSON ────────────────────────────────────────────────────────────
with open("data.json", "w") as f:
    json.dump(data, f, indent=2)
print("✅ data.json saved")

# ── BUILD index.html ──────────────────────────────────────────────────────────
def sc(v):
    s=str(v).lower()
    if any(x in s for x in ["bull","gap_up","strong","buy","low","positive","complacent","above"]): return "#00e87a"
    if any(x in s for x in ["bear","gap_down","weak","sell","high","elevated","negative","panic","below"]): return "#ff3d6e"
    return "#ffd93d"

def cc(v):
    return "#00e87a" if str(v).startswith("+") else "#ff3d6e"

def build_pivot_cells(p):
    cells=""
    items=[("R3","r3"),("R2","r2"),("R1","r1"),("PP","pp"),("S1","s1"),("S2","s2"),("S3","s3")]
    for lbl,key in items:
        val=p.get(key,"—")
        col="#ff3d6e" if lbl[0]=="R" else "#00c8ff" if lbl=="PP" else "#00e87a"
        bg=f"rgba(255,61,110,0.07)" if lbl[0]=="R" else "rgba(0,200,255,0.07)" if lbl=="PP" else "rgba(0,232,122,0.07)"
        bd=f"rgba(255,61,110,0.25)" if lbl[0]=="R" else "rgba(0,200,255,0.3)" if lbl=="PP" else "rgba(0,232,122,0.25)"
        cells+=f'<div class="piv-cell" style="background:{bg};border:1px solid {bd}"><div class="piv-lbl" style="color:{col}">{lbl}</div><div class="piv-val" style="color:{col}">{val}</div></div>'
    return cells

def build_news_items(news):
    if not news: return '<div class="empty-msg">No news items</div>'
    tc={"GEO":"#ff6b35","MARKET":"#00c8ff","MACRO":"#a78bfa"}
    ic={"positive":"#00e87a","negative":"#ff3d6e","neutral":"#8aa4c8"}
    is_={"positive":"▲","negative":"▼","neutral":"●"}
    out=""
    for n in news:
        tag=n.get("tag","MARKET"); imp=n.get("impact","neutral")
        t=n.get("time","")
        out+=f'''<div class="news-item">
          <span class="n-tag" style="background:{tc.get(tag,"#00c8ff")}22;color:{tc.get(tag,"#00c8ff")}">{tag}</span>
          {n.get("headline","")}
          <span style="color:{ic.get(imp,"#8aa4c8")};margin-left:5px">{is_.get(imp,"●")}</span>
          {f'<span class="n-time">{t}</span>' if t else ""}
        </div>'''
    return out

def build_global_rows(markets):
    if not markets: return '<tr><td colspan="3" style="text-align:center;color:#3d5878;padding:12px;font-size:12px">No data</td></tr>'
    out=""
    for m in markets:
        c=cc(m.get("change",""))
        out+=f'<tr><td class="gm-name">{m.get("name","")}</td><td class="gm-val">{m.get("value","")}</td><td class="gm-chg" style="color:{c}">{m.get("change","")} {m.get("pct","")}</td></tr>'
    return out

def build_session_timeline(sessions):
    if not sessions: return ""
    tc={"bullish":"#00e87a","bearish":"#ff3d6e","neutral":"#ffd93d"}
    out=""
    for s in sessions:
        c=tc.get(s.get("trend","neutral"),"#ffd93d")
        chg=s.get("change","")
        cc2=cc(chg)
        out+=f'''<div class="tl-item">
          <div class="tl-dot" style="background:{c}"></div>
          <div class="tl-body">
            <div class="tl-time">{s.get("time","")} IST</div>
            <div class="tl-label">{s.get("label","").split("·")[0].strip()}</div>
            <div class="tl-price">{s.get("nifty","—")} <span style="color:{cc2}">{chg}</span></div>
          </div>
        </div>'''
    return out

def build_accuracy_card(acc):
    if not acc: return ""
    correct=acc.get("correct")
    vc="#00e87a" if correct else "#ff3d6e" if correct is False else "#ffd93d"
    return f'''<div class="acc-card">
      <div class="acc-title">🎯 Prediction Accuracy</div>
      <div class="acc-row"><span>Morning Bias</span><strong style="color:{sc(acc.get('morning_bias',''))}">{acc.get('morning_bias','N/A')}</strong></div>
      <div class="acc-row"><span>Open Price</span><strong>{acc.get('open_price','N/A')}</strong></div>
      <div class="acc-row"><span>Current</span><strong>{acc.get('current_price','N/A')}</strong></div>
      <div class="acc-row"><span>Move</span><strong style="color:{cc(acc.get('move_pts','+0'))}">{acc.get('move_pts','N/A')} pts</strong></div>
      <div class="acc-verdict" style="color:{vc}">{acc.get('verdict','⏳ Tracking')}</div>
    </div>'''

def build_pivot_alerts(alerts):
    if not alerts: return ""
    out='<div class="alert-box"><div class="alert-title">⚡ Pivot Alerts</div>'
    for a in alerts:
        t=a.get("type","AT")
        c="#ffd93d" if t=="AT" else "#00e87a" if t=="ABOVE" else "#ff3d6e"
        out+=f'<div class="alert-item" style="color:{c}">{t} {a.get("level","")} · {a.get("value","")}</div>'
    out+='</div>'
    return out

def build_brief_html(text):
    headers=["GIFT NIFTY","CRUDE OIL","USD/INR","INDIA VIX","GLOBAL MARKETS",
             "FII+DII FLOWS","PIVOT LEVELS","OI & MAX PAIN","TRADING VERDICT",
             "GIFT NIFTY:","CRUDE OIL:","USD/INR:","INDIA VIX:","GLOBAL MARKETS:",
             "FII+DII FLOWS:","PIVOT LEVELS:","OI & MAX PAIN:","TRADING VERDICT:"]
    em={"GIFT NIFTY":"🎁","CRUDE OIL":"🛢️","USD/INR":"💱","INDIA VIX":"📊",
        "GLOBAL MARKETS":"🌐","FII+DII FLOWS":"🏦","FII + DII FLOWS":"🏦",
        "PIVOT LEVELS":"📐","OI & MAX PAIN":"🎯","TRADING VERDICT":"⚡"}
    out=text
    for h in set(headers):
        base=h.rstrip(":")
        e=em.get(base,"●")
        c="#ff8c00" if "VERDICT" in h else "#00c8ff"
        out=re.sub(rf"({re.escape(h)})",
            f'<span class="brief-section" style="color:{c}">{e} \\1</span>',
            out, flags=re.IGNORECASE)
    return out.replace("\n\n","</p><p>").replace("\n"," ")

# build all components
n       = data["nifty"]
s       = data["sentiment"]
p       = data["pivot"]
oi      = data["oi"]
f       = data["fiidii"]
g       = data["gift"]
crude   = data["crude"]
inr_d   = data["inr"]
score   = int(s.get("score",50))
sc_col  = "#00e87a" if score>55 else "#ff3d6e" if score<45 else "#ffd93d"
nifty_c = cc(n.get("change",""))
is_intraday = SESSION != "morning_brief"
acc     = data.get("accuracy",{})
alerts  = data.get("pivot_alerts",[])
intraday_text = data.get("intraday_analysis","")
brief_text = data.get("brief","")
sessions_tl = data.get("all_sessions",[])

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta http-equiv="refresh" content="3600">
<title>Nifty Live Dashboard · {TODAY}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Clash+Display:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {{
  --bg:#070b12; --bg2:#0b1018; --card:#0d1422; --card2:#111928;
  --border:#182236; --border2:#1e2e4a;
  --accent:#00d4ff; --green:#00f088; --red:#ff3355;
  --yellow:#ffcc00; --purple:#b388ff; --orange:#ff8c00;
  --text:#d8eeff; --text2:#7a9cbf; --muted:#2a3d58;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
html{{scroll-behavior:smooth}}
body{{font-family:'JetBrains Mono',monospace;background:var(--bg);color:var(--text);min-height:100vh;
  background-image:radial-gradient(ellipse 80% 40% at 50% -10%,rgba(0,150,255,0.07),transparent),
  radial-gradient(ellipse 60% 30% at 80% 100%,rgba(0,200,100,0.04),transparent);}}

/* HEADER */
.hdr{{background:var(--bg2);border-bottom:1px solid var(--border);padding:14px 20px;
  display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;
  position:sticky;top:0;z-index:100;backdrop-filter:blur(10px);}}
.hdr-left{{display:flex;align-items:center;gap:12px}}
.logo{{width:38px;height:38px;background:linear-gradient(135deg,var(--accent),#0044ff);border-radius:9px;
  display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;color:#000;
  box-shadow:0 0 16px rgba(0,212,255,0.3)}}
.site-title{{font-size:15px;font-weight:700;letter-spacing:-0.3px}}
.site-sub{{font-size:9px;color:var(--muted);margin-top:1px}}
.hdr-right{{display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
.session-pill{{background:rgba(0,212,255,0.08);border:1px solid rgba(0,212,255,0.2);
  color:var(--accent);font-size:10px;font-weight:700;padding:4px 10px;border-radius:20px}}
.update-time{{font-size:10px;color:var(--text2);background:var(--card);
  padding:4px 10px;border-radius:6px;border:1px solid var(--border)}}

/* NIFTY HERO */
.hero{{padding:20px;background:var(--bg2);border-bottom:1px solid var(--border)}}
.hero-inner{{max-width:1100px;margin:0 auto;display:flex;align-items:center;
  justify-content:space-between;flex-wrap:wrap;gap:16px}}
.nifty-price{{font-size:52px;font-weight:700;line-height:1;letter-spacing:-2px}}
.nifty-change{{font-size:18px;font-weight:700;margin-top:4px}}
.nifty-meta{{font-size:11px;color:var(--text2);margin-top:6px}}
.nifty-hl{{display:flex;gap:16px;margin-top:8px}}
.nifty-hl span{{font-size:11px;color:var(--text2)}}
.nifty-hl strong{{color:var(--text)}}
.sent-mini{{text-align:right}}
.sent-score-big{{font-size:48px;font-weight:700;line-height:1}}
.sent-label-big{{font-size:12px;color:var(--text2);margin-top:2px}}
.sent-bar-wrap{{width:140px;margin:8px 0 0 auto}}
.sent-bar-bg{{height:6px;background:rgba(255,255,255,0.06);border-radius:3px;overflow:hidden}}
.sent-bar-fill{{height:100%;background:linear-gradient(90deg,var(--red),var(--yellow),var(--green));border-radius:3px;transition:width 1s ease}}

/* LAYOUT */
.main{{max-width:1100px;margin:0 auto;padding:16px 16px 40px}}
.sec-lbl{{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:2px;
  color:var(--muted);display:flex;align-items:center;gap:8px;margin:20px 0 10px}}
.sec-lbl::after{{content:'';flex:1;height:1px;background:var(--border)}}
.grid4{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}
.grid2{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}}
.grid3{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}

/* CARDS */
.card{{background:var(--card);border:1px solid var(--border);border-radius:12px;
  padding:14px 16px;position:relative;overflow:hidden;transition:border-color 0.2s}}
.card:hover{{border-color:var(--border2)}}
.card.accent-top::before{{content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,transparent,var(--accent),transparent)}}
.card-icon{{font-size:11px;color:var(--muted);font-weight:700;text-transform:uppercase;
  letter-spacing:0.8px;margin-bottom:8px;display:flex;align-items:center;gap:6px}}
.card-val{{font-size:22px;font-weight:700;line-height:1;margin-bottom:4px}}
.card-sub{{font-size:10px;color:var(--text2)}}
.badge{{display:inline-block;font-size:9px;font-weight:700;padding:2px 7px;border-radius:20px;
  margin-top:6px;border:1px solid}}

/* INTRADAY ANALYSIS BOX */
.analysis-box{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px 20px}}
.analysis-box p{{font-size:13px;line-height:1.8;color:#9ab8d8;margin-bottom:8px}}

/* ACCURACY CARD */
.acc-card{{background:rgba(0,212,255,0.05);border:1px solid rgba(0,212,255,0.15);
  border-radius:12px;padding:14px 16px}}
.acc-title{{font-size:10px;font-weight:700;color:var(--accent);text-transform:uppercase;
  letter-spacing:1px;margin-bottom:10px}}
.acc-row{{display:flex;justify-content:space-between;font-size:11px;color:var(--text2);
  padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.04)}}
.acc-row strong{{color:var(--text)}}
.acc-verdict{{text-align:center;font-size:15px;font-weight:700;margin-top:10px;padding:8px;
  background:rgba(255,255,255,0.03);border-radius:8px}}

/* ALERT BOX */
.alert-box{{background:rgba(255,204,0,0.06);border:1px solid rgba(255,204,0,0.2);
  border-radius:12px;padding:14px 16px}}
.alert-title{{font-size:10px;font-weight:700;color:var(--yellow);text-transform:uppercase;
  letter-spacing:1px;margin-bottom:10px}}
.alert-item{{font-size:12px;font-weight:700;padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.04)}}

/* PIVOT */
.piv-grid{{display:grid;grid-template-columns:repeat(7,1fr);gap:5px;margin-top:4px}}
.piv-cell{{text-align:center;border-radius:8px;padding:8px 4px}}
.piv-lbl{{font-size:8px;font-weight:700;margin-bottom:3px;text-transform:uppercase}}
.piv-val{{font-size:12px;font-weight:700}}

/* GLOBAL MARKETS TABLE */
table.gm-table{{width:100%;border-collapse:collapse}}
.gm-name{{padding:7px 10px;font-size:11px;font-weight:700;color:var(--text)}}
.gm-val{{padding:7px 10px;font-size:11px;font-family:monospace;color:var(--text);text-align:right}}
.gm-chg{{padding:7px 10px;font-size:11px;font-family:monospace;text-align:right;font-weight:700}}
table.gm-table tr{{border-bottom:1px solid var(--border)}}
table.gm-table tr:last-child{{border-bottom:none}}

/* FII/DII */
.flow-row{{display:flex;align-items:center;justify-content:space-between;
  padding:8px 0;border-bottom:1px solid var(--border);font-size:11px}}
.flow-row:last-child{{border-bottom:none}}

/* NEWS */
.news-ticker{{overflow:hidden}}
.news-item{{padding:9px 0;border-bottom:1px solid var(--border);font-size:12px;
  line-height:1.5;color:var(--text2)}}
.news-item:last-child{{border-bottom:none}}
.n-tag{{font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;margin-right:6px}}
.n-time{{font-size:9px;color:var(--muted);margin-left:8px}}
.empty-msg{{font-size:12px;color:var(--muted);text-align:center;padding:16px}}

/* BRIEF */
.brief-text{{font-size:12px;line-height:1.85;color:#8aadc8}}
.brief-text p{{margin-bottom:4px}}
.brief-section{{display:block;font-size:9px;font-weight:700;text-transform:uppercase;
  letter-spacing:1.5px;margin-top:14px;margin-bottom:3px}}

/* TIMELINE */
.timeline{{display:flex;flex-direction:column;gap:0}}
.tl-item{{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid var(--border)}}
.tl-item:last-child{{border-bottom:none}}
.tl-dot{{width:10px;height:10px;border-radius:50%;margin-top:4px;flex-shrink:0;
  box-shadow:0 0 8px currentColor}}
.tl-body{{flex:1}}
.tl-time{{font-size:9px;color:var(--muted);font-weight:700}}
.tl-label{{font-size:11px;color:var(--text2);margin-top:1px}}
.tl-price{{font-size:13px;font-weight:700;margin-top:2px}}

/* OI */
.oi-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:4px}}
.oi-cell{{text-align:center;border-radius:10px;padding:12px 8px}}
.oi-lbl{{font-size:9px;font-weight:700;margin-bottom:5px;text-transform:uppercase}}
.oi-val{{font-size:20px;font-weight:700}}

/* RESPONSIVE */
@media(max-width:800px){{
  .grid4{{grid-template-columns:repeat(2,1fr)}}
  .grid3{{grid-template-columns:1fr 1fr}}
  .piv-grid{{grid-template-columns:repeat(4,1fr)}}
  .nifty-price{{font-size:36px}}
  .oi-grid{{grid-template-columns:1fr}}
}}
@media(max-width:500px){{
  .grid2,.grid3,.grid4{{grid-template-columns:1fr}}
  .hero-inner{{flex-direction:column}}
  .sent-mini{{text-align:left}}
  .sent-bar-wrap{{margin:8px 0 0 0;width:100%}}
}}
</style>
</head>
<body>

<!-- STICKY HEADER -->
<div class="hdr">
  <div class="hdr-left">
    <div class="logo">NB</div>
    <div>
      <div class="site-title">Nifty Live Dashboard</div>
      <div class="site-sub">9-Factor AI · NSE · Gemini + Google Search</div>
    </div>
  </div>
  <div class="hdr-right">
    <div class="session-pill">{data.get('session_label','—')}</div>
    <div class="update-time">Updated {TIME} IST · {now_ist.strftime('%d %b %Y')}</div>
  </div>
</div>

<!-- NIFTY HERO -->
<div class="hero">
  <div class="hero-inner">
    <div>
      <div style="font-size:10px;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px">Nifty 50 · Live</div>
      <div class="nifty-price" style="color:{nifty_c}">{n.get('price','—')}</div>
      <div class="nifty-change" style="color:{nifty_c}">{n.get('change','—')} ({n.get('pct','—')})</div>
      <div class="nifty-hl">
        <span>H: <strong>{n.get('high','—')}</strong></span>
        <span>L: <strong>{n.get('low','—')}</strong></span>
        <span>VIX: <strong style="color:{sc(data['vix'].get('level',''))}">{data['vix'].get('value','—')}</strong></span>
      </div>
    </div>
    <div class="sent-mini">
      <div style="font-size:10px;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">Sentiment</div>
      <div class="sent-score-big" style="color:{sc_col}">{score}</div>
      <div class="sent-label-big">{s.get('label','—')}</div>
      <div class="sent-bar-wrap">
        <div class="sent-bar-bg">
          <div class="sent-bar-fill" style="width:{score}%"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:8px;color:var(--muted);margin-top:3px">
          <span>BEAR</span><span>NEUTRAL</span><span>BULL</span>
        </div>
      </div>
    </div>
  </div>
</div>

<div class="main">

{'<!-- INTRADAY UPDATE --><div class="sec-lbl">Intraday Update</div><div class="grid2">' +
  '<div class="analysis-box"><div style="font-size:10px;font-weight:700;color:var(--accent);text-transform:uppercase;letter-spacing:1px;margin-bottom:10px">📊 ' + data.get('session_label','') + '</div><div class="brief-text"><p>' + intraday_text.replace("\n\n","</p><p>").replace("\n"," ") + '</p></div></div>' +
  '<div style="display:flex;flex-direction:column;gap:10px">' + build_accuracy_card(acc) + (build_pivot_alerts(alerts) if alerts else '') + '</div>' +
  '</div>'
  if is_intraday else ''}

<!-- PRE-MARKET CARDS -->
<div class="sec-lbl">Pre-Market Pulse</div>
<div class="grid4">
  <div class="card accent-top">
    <div class="card-icon">🎁 Gift Nifty</div>
    <div class="card-val">{g.get('value','—')}</div>
    <div class="card-sub" style="color:{cc(g.get('change',''))}">{g.get('change','—')} ({g.get('pct','—')})</div>
    <div class="card-sub" style="margin-top:4px">Gap: <strong style="color:{cc(g.get('gap_pts',''))}">{g.get('gap_pts','—')} pts</strong></div>
    <span class="badge" style="color:{sc(g.get('signal',''))};border-color:{sc(g.get('signal',''))}40;background:{sc(g.get('signal',''))}12">{str(g.get('signal','—')).replace('_',' ').upper()}</span>
  </div>
  <div class="card">
    <div class="card-icon">💱 USD/INR</div>
    <div class="card-val">₹{inr_d.get('rate','—')}</div>
    <div class="card-sub" style="color:{cc(inr_d.get('change',''))}">{inr_d.get('change','—')}</div>
    <span class="badge" style="color:{sc(inr_d.get('signal',''))};border-color:{sc(inr_d.get('signal',''))}40;background:{sc(inr_d.get('signal',''))}12">{str(inr_d.get('signal','—')).replace('_',' ').upper()}</span>
  </div>
  <div class="card">
    <div class="card-icon">🛢️ Crude WTI</div>
    <div class="card-val">${crude.get('price','—')}</div>
    <div class="card-sub" style="color:{cc(crude.get('change',''))}">{crude.get('change','—')} ({crude.get('pct','—')})</div>
    <span class="badge" style="color:{sc(crude.get('signal',''))};border-color:{sc(crude.get('signal',''))}40;background:{sc(crude.get('signal',''))}12">{str(crude.get('signal','—')).upper()}</span>
  </div>
  <div class="card">
    <div class="card-icon">📊 India VIX</div>
    <div class="card-val">{data['vix'].get('value','—')}</div>
    <div class="card-sub" style="color:{cc(data['vix'].get('change',''))}">{data['vix'].get('change','—')}</div>
    <span class="badge" style="color:{sc(data['vix'].get('level',''))};border-color:{sc(data['vix'].get('level',''))}40;background:{sc(data['vix'].get('level',''))}12">{str(data['vix'].get('level','—')).upper()}</span>
  </div>
</div>

<!-- GLOBAL + FII/DII -->
<div class="sec-lbl">Global Markets & Institutional Flows</div>
<div class="grid2">
  <div class="card">
    <div class="card-icon">🌐 Global Markets (Overnight)</div>
    <table class="gm-table">{build_global_rows(data.get('global',[]))}</table>
  </div>
  <div class="card">
    <div class="card-icon">🏦 FII + DII Flow</div>
    <div class="flow-row"><span style="color:var(--accent);font-weight:700">FII</span>
      <span>Buy <strong style="color:var(--green)">₹{f['fii'].get('buy','—')}Cr</strong></span>
      <span>Sell <strong style="color:var(--red)">₹{f['fii'].get('sell','—')}Cr</strong></span>
      <strong style="color:{cc(f['fii'].get('net',''))}" >Net ₹{f['fii'].get('net','—')}Cr</strong></div>
    <div class="flow-row"><span style="color:var(--yellow);font-weight:700">DII</span>
      <span>Buy <strong style="color:var(--green)">₹{f['dii'].get('buy','—')}Cr</strong></span>
      <span>Sell <strong style="color:var(--red)">₹{f['dii'].get('sell','—')}Cr</strong></span>
      <strong style="color:{cc(f['dii'].get('net',''))}">Net ₹{f['dii'].get('net','—')}Cr</strong></div>
    <div style="margin-top:10px;font-size:11px;color:var(--text2)">Signal: <strong style="color:{sc(f.get('signal',''))}">{str(f.get('signal','—')).replace('_',' ').upper()}</strong></div>
  </div>
</div>

<!-- PIVOT LEVELS -->
<div class="sec-lbl">Nifty Pivot Levels · H:{p.get('prev_high','—')} L:{p.get('prev_low','—')} C:{p.get('prev_close','—')}</div>
<div class="card">
  <div class="piv-grid">{build_pivot_cells(p)}</div>
  <div style="margin-top:10px;font-size:10px;color:var(--text2)">
    Above {p.get('pp','—')} → Bullish &nbsp;·&nbsp; Below → Bearish &nbsp;·&nbsp; Current: <strong style="color:{nifty_c}">{n.get('price','—')}</strong>
  </div>
</div>

<!-- OI & MAX PAIN + NEWS -->
<div class="sec-lbl">Options Data & Breaking News</div>
<div class="grid2">
  <div class="card">
    <div class="card-icon">🎯 OI & Max Pain</div>
    <div class="oi-grid">
      <div class="oi-cell" style="background:rgba(179,136,255,0.08);border:1px solid rgba(179,136,255,0.2)">
        <div class="oi-lbl" style="color:var(--purple)">Max Pain</div>
        <div class="oi-val" style="color:var(--purple)">{oi.get('max_pain','—')}</div>
        <div style="font-size:10px;color:var(--text2);margin-top:4px">PCR: <strong>{oi.get('pcr','—')}</strong></div>
      </div>
      <div class="oi-cell" style="background:rgba(255,51,85,0.08);border:1px solid rgba(255,51,85,0.2)">
        <div class="oi-lbl" style="color:var(--red)">Max Call OI</div>
        <div class="oi-val" style="color:var(--red)">{oi.get('top_ce_strike','—')}</div>
        <div style="font-size:10px;color:var(--text2);margin-top:4px">Resistance</div>
      </div>
      <div class="oi-cell" style="background:rgba(0,240,136,0.08);border:1px solid rgba(0,240,136,0.2)">
        <div class="oi-lbl" style="color:var(--green)">Max Put OI</div>
        <div class="oi-val" style="color:var(--green)">{oi.get('top_pe_strike','—')}</div>
        <div style="font-size:10px;color:var(--text2);margin-top:4px">Support</div>
      </div>
    </div>
  </div>
  <div class="card">
    <div class="card-icon">🌍 Breaking News</div>
    <div class="news-ticker">{build_news_items(data.get('news',[]))}</div>
  </div>
</div>

<!-- TIMELINE + MORNING BRIEF -->
<div class="sec-lbl">Session Timeline</div>
<div class="grid2">
  <div class="card">
    <div class="card-icon" style="margin-bottom:10px">⏱ Today's Sessions</div>
    <div class="timeline">{build_session_timeline(sessions_tl) or '<div class="empty-msg">No sessions recorded yet</div>'}</div>
  </div>
  <div class="card">
    <div class="card-icon" style="margin-bottom:10px">✦ Morning Brief <span style="background:linear-gradient(135deg,#1a7a4a,#0d5c8a);color:#fff;font-size:8px;padding:2px 6px;border-radius:10px;margin-left:6px">GEMINI AI</span></div>
    <div class="brief-text"><p>{build_brief_html(brief_text)}</p></div>
  </div>
</div>

<!-- FOOTER -->
<div style="text-align:center;padding:24px 0 0;font-size:10px;color:var(--muted)">
  Nifty Live Dashboard · Auto-generated at {TIME} IST · Powered by Gemini AI + Google Search<br>
  <span style="margin-top:4px;display:block">⚠ For informational purposes only. Not financial advice.</span>
</div>

</div><!-- /main -->
</body>
</html>"""

with open("index.html","w",encoding="utf-8") as f2:
    f2.write(html)
print("✅ index.html built")

"""
Nifty Morning Brief — Instagram Card Generator v2
1080x1080px · Poppins font · High readability design
"""

from PIL import Image, ImageDraw, ImageFont
import re, os
from datetime import datetime, timezone, timedelta

PF = "/usr/share/fonts/truetype/google-fonts/"
LF = "/usr/share/fonts/truetype/liberation/"

def fnt(name, size):
    paths = {
        "black":   PF + "Poppins-Bold.ttf",
        "bold":    PF + "Poppins-Bold.ttf",
        "medium":  PF + "Poppins-Medium.ttf",
        "regular": PF + "Poppins-Regular.ttf",
        "light":   PF + "Poppins-Light.ttf",
        "mono":    LF + "LiberationMono-Bold.ttf",
    }
    try:
        return ImageFont.truetype(paths.get(name, paths["regular"]), size)
    except:
        return ImageFont.load_default()

BG     = (8,  12,  22)
CARD   = (14, 22,  40)
CARD2  = (19, 30,  54)
BORDER = (30, 48,  80)
ACCENT = (0,  200, 255)
GREEN  = (0,  230, 120)
RED    = (255, 60,  80)
YELLOW = (255,210,  0)
PURPLE = (180,140, 255)
WHITE  = (255,255, 255)
TEXT   = (230,245, 255)
TEXT2  = (150,180, 210)
MUTED  = (70, 95,  130)

W, H = 1080, 1080

def cc(v):
    return GREEN if str(v).startswith("+") else RED

def sc(v):
    s = str(v).lower()
    if any(x in s for x in ["bull","up","strong","buy","low","positive"]):
        return GREEN
    if any(x in s for x in ["bear","down","weak","sell","high","elevated","negative"]):
        return RED
    return YELLOW

def rr(img, x1, y1, x2, y2, r=14, fill=None, outline=None, ow=1):
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    d  = ImageDraw.Draw(ov)
    if fill:
        fc = fill if len(fill)==4 else fill+(255,)
        d.rounded_rectangle([x1,y1,x2,y2], radius=r, fill=fc)
    if outline:
        oc = outline if len(outline)==4 else outline+(255,)
        d.rounded_rectangle([x1,y1,x2,y2], radius=r, outline=oc, width=ow)
    img.alpha_composite(ov)

def tw(draw, text, f):
    bb = draw.textbbox((0,0), str(text), font=f)
    return bb[2]-bb[0]

def pill(img, draw, x, y, text, color):
    f  = fnt("bold", 15)
    w_ = tw(draw, text, f)+22
    rr(img, x, y, x+w_, y+32, r=16, fill=color+(30,), outline=color+(110,), ow=1)
    draw.text((x+11, y+6), text, font=f, fill=color)
    return w_

def wrap(draw, text, f, max_w):
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        test = (cur+" "+w_).strip()
        if tw(draw, test, f) <= max_w:
            cur = test
        else:
            if cur: lines.append(cur)
            cur = w_
    if cur: lines.append(cur)
    return lines

def make_bg():
    img = Image.new("RGBA", (W,H), BG)
    ov  = Image.new("RGBA", (W,H), (0,0,0,0))
    d   = ImageDraw.Draw(ov)
    for r in range(700,0,-20):
        a = int(18*(1-r/700))
        d.ellipse([-r+200,-r,r+200,r], fill=(0,130,255,a))
    for r in range(500,0,-20):
        a = int(12*(1-r/500))
        d.ellipse([W-r+100,H-r,W+r+100,H+r], fill=(0,180,80,a))
    img.alpha_composite(ov)

    return img

def generate_card(data: dict, session: str, output_path: str = "nifty_card.png"):
    IST     = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(IST)
    TIME    = now_ist.strftime("%I:%M %p")
    DATE    = now_ist.strftime("%d %b %Y")

    SESSION_LABELS = {
        "morning_brief": "MORNING BRIEF",
        "session_1":     "MARKET OPEN",
        "session_2":     "MID-MORNING",
        "session_3":     "POST-LUNCH",
        "closing":       "PRE-CLOSE",
    }
    sess_lbl = SESSION_LABELS.get(session, "MARKET UPDATE")

    n         = data.get("nifty",{})
    nifty_p   = str(n.get("price","N/A"))
    nifty_c   = str(n.get("change","+0"))
    nifty_pct = str(n.get("pct",""))
    s         = data.get("sentiment",{"score":50,"label":"Neutral"})
    score     = int(s.get("score",50))
    sent_lbl  = str(s.get("label","Neutral")).upper()
    score_col = GREEN if score>55 else RED if score<45 else YELLOW
    g         = data.get("gift",{})
    gift_v    = str(g.get("value","—"))
    gift_gap  = str(g.get("gap_pts","—"))
    gift_sig  = str(g.get("signal","flat"))
    vix_d     = data.get("vix",{})
    vix_v     = str(vix_d.get("value","—"))
    vix_lev   = str(vix_d.get("level","moderate"))
    p         = data.get("pivot",{})
    r1        = str(p.get("r1","—"))
    pp_       = str(p.get("pp","—"))
    s1_       = str(p.get("s1","—"))
    r2        = str(p.get("r2","—"))
    s2_       = str(p.get("s2","—"))
    news_list = data.get("news",[])[:3]
    brief     = data.get("brief","")
    m         = re.search(r"TRADING VERDICT:?(.*?)(?:\n\n|\Z)", brief, re.IGNORECASE|re.DOTALL)
    verdict   = m.group(1).strip().replace("\n"," ") if m else "Analysis pending for this session."

    img  = make_bg()
    draw = ImageDraw.Draw(img)

    # ── HEADER ────────────────────────────────────────────────────────────────
    rr(img, 0, 0, W, 88, r=0, fill=CARD+(245,))
    # top accent stripe
    ov2 = Image.new("RGBA",(W,H),(0,0,0,0))
    ds  = ImageDraw.Draw(ov2)
    ds.rectangle([0,0,W,4], fill=ACCENT+(230,))
    img.alpha_composite(ov2)

    rr(img, 24,16,72,72, r=10, fill=(0,50,110,255), outline=ACCENT+(130,), ow=1)
    draw.text((28,18), "NB", font=fnt("black",30), fill=WHITE)
    draw.text((82,16), "NIFTY LIVE", font=fnt("black",30), fill=TEXT)
    draw.text((82,52), "AI Market Intelligence  ·  NSE India", font=fnt("regular",17), fill=TEXT2)

    # session badge
    sf  = fnt("bold",17)
    sw_ = tw(draw, sess_lbl, sf)
    sx  = W-sw_-56
    rr(img, sx-14, 20, sx+sw_+14, 68, r=10, fill=ACCENT+(22,), outline=ACCENT+(100,), ow=1)
    draw.text((sx, 30), sess_lbl, font=sf, fill=ACCENT)

    # date/time
    dt_txt = TIME + "   ·   " + DATE
    dtw_   = tw(draw, dt_txt, fnt("light",16))
    draw.text(((W-dtw_)//2, 94), dt_txt, font=fnt("light",16), fill=MUTED)

    y = 118

    # ── NIFTY PRICE HERO ──────────────────────────────────────────────────────
    rr(img, 24, y, W-24, y+150, r=18, fill=CARD+(240,), outline=BORDER+(180,), ow=1)
    pcol = cc(nifty_c)
    pf   = fnt("black", 88)
    pw_  = tw(draw, nifty_p, pf)
    draw.text(((W-pw_)//2 - 70, y+10), nifty_p, font=pf, fill=pcol)
    chg_txt = nifty_c + "    " + nifty_pct
    cw_     = tw(draw, chg_txt, fnt("bold",28))
    draw.text(((W-cw_)//2 - 70, y+108), chg_txt, font=fnt("bold",28), fill=pcol)

    # sentiment panel
    rr(img, W-218, y+10, W-34, y+140, r=14, fill=score_col+(22,), outline=score_col+(75,), ow=2)
    draw.text((W-198, y+16), "SENTIMENT", font=fnt("medium",14), fill=score_col)
    sf2  = fnt("black",60)
    scw_ = tw(draw, str(score), sf2)
    draw.text((W-218+((184-scw_)//2), y+32), str(score), font=sf2, fill=score_col)
    slw_ = tw(draw, sent_lbl, fnt("bold",16))
    draw.text((W-218+((184-slw_)//2), y+102), sent_lbl, font=fnt("bold",16), fill=score_col)
    # bar
    bx,by,bw_ = W-212,y+126,168
    draw.rounded_rectangle([bx,by,bx+bw_,by+8], radius=4, fill=MUTED+(100,))
    fw = int(bw_*score/100)
    for i in range(fw):
        t  = i/bw_
        r_ = int(255*(1-min(t*2,1)))
        g_ = int(255*min(t*2,1))
        draw.rectangle([bx+i,by,bx+i+1,by+8], fill=(r_,g_,0,200))

    y += 162

    # ── GIFT NIFTY | VIX ──────────────────────────────────────────────────────
    half = (W-78)//2
    rr(img, 24, y, 24+half, y+106, r=14, fill=CARD+(220,), outline=BORDER+(150,), ow=1)
    draw.text((44, y+10), "GIFT NIFTY", font=fnt("bold",18), fill=ACCENT)
    draw.text((44, y+34), gift_v, font=fnt("black",42), fill=TEXT)
    draw.text((44, y+80), "Gap:  " + gift_gap + " pts", font=fnt("medium",18), fill=cc(gift_gap))
    pill(img, draw, 24+half-180, y+10, gift_sig.replace("_"," ").upper(), sc(gift_sig))

    vx = 24+half+28
    rr(img, vx, y, W-24, y+106, r=14, fill=CARD+(220,), outline=BORDER+(150,), ow=1)
    draw.text((vx+20, y+10), "INDIA VIX", font=fnt("bold",18), fill=PURPLE)
    draw.text((vx+20, y+34), vix_v, font=fnt("black",42), fill=TEXT)
    draw.text((vx+20, y+80), "Fear:  " + vix_lev.upper(), font=fnt("medium",18), fill=sc(vix_lev))

    y += 118

    # ── PIVOT LEVELS ──────────────────────────────────────────────────────────
    draw.text((24, y+4), "KEY LEVELS", font=fnt("bold",18), fill=MUTED)
    y += 30

    pivots  = [("R2",r2,RED),("R1",r1,RED),("PP",pp_,ACCENT),("S1",s1_,GREEN),("S2",s2_,GREEN)]
    cw_piv  = (W-52-32)//5
    for i,(lbl_,val,col) in enumerate(pivots):
        cx  = 24+i*(cw_piv+8)
        is_pp = lbl_=="PP"
        rr(img, cx, y, cx+cw_piv, y+82, r=12,
           fill=col+(35 if is_pp else 18,), outline=col+(90 if is_pp else 55,),
           ow=2 if is_pp else 1)
        lw_ = tw(draw, lbl_, fnt("bold",17))
        draw.text((cx+(cw_piv-lw_)//2, y+8), lbl_, font=fnt("bold",17), fill=col)
        # auto-size value
        sz = 24
        vf = fnt("black", sz)
        while tw(draw, val, vf) > cw_piv-12 and sz>14:
            sz -= 1
            vf  = fnt("black", sz)
        vw_ = tw(draw, val, vf)
        draw.text((cx+(cw_piv-vw_)//2, y+34), val, font=vf, fill=col)

    y += 94

    # ── NEWS ──────────────────────────────────────────────────────────────────
    draw.text((24, y+2), "MARKET NEWS", font=fnt("bold",18), fill=MUTED)
    y += 28

    tag_c = {"GEO":(255,120,50),"MARKET":(0,200,255),"MACRO":(180,140,255)}
    imp_s = {"positive":"▲","negative":"▼","neutral":"●"}
    imp_c = {"positive":GREEN,"negative":RED,"neutral":TEXT2}

    for idx, item in enumerate(news_list):
        tag  = item.get("tag","MARKET")
        imp  = item.get("impact","neutral")
        hl   = item.get("headline","")
        tc   = tag_c.get(tag,ACCENT)
        ic   = imp_c.get(imp,TEXT2)
        sym  = imp_s.get(imp,"●")

        rr(img, 24, y, W-24, y+54, r=10,
           fill=(CARD2 if idx%2==0 else CARD)+(210,))
        tf   = fnt("bold",14)
        tw_t = tw(draw,tag,tf)+22
        rr(img, 40,y+11,40+tw_t,y+43, r=10, fill=tc+(28,),outline=tc+(95,),ow=1)
        draw.text((51,y+16), tag, font=tf, fill=tc)

        hf   = fnt("medium",18)
        hmax = W-40-tw_t-24-56
        hl_t = hl
        while tw(draw,hl_t,hf)>hmax and len(hl_t)>6:
            hl_t = hl_t[:-1]
        if hl_t!=hl: hl_t = hl_t.rstrip()+"…"
        draw.text((40+tw_t+12,y+16), hl_t, font=hf, fill=TEXT)
        draw.text((W-52,y+14), sym, font=fnt("black",22), fill=ic)
        y += 58

    # ── TRADING VERDICT ───────────────────────────────────────────────────────
    y += 8
    footer_h = 54
    avail    = H-y-footer_h-14
    rr(img, 24, y, W-24, y+avail, r=16, fill=(8,28,14,235), outline=GREEN+(95,), ow=2)
    draw.text((46, y+12), ">> TRADING VERDICT", font=fnt("bold",20), fill=GREEN)
    vf2    = fnt("regular",18)
    vlines = wrap(draw, verdict, vf2, W-108)
    for li,line in enumerate(vlines[:4]):
        draw.text((46, y+44+li*26), line, font=vf2, fill=TEXT)

    # ── FOOTER ────────────────────────────────────────────────────────────────
    rr(img, 0, H-footer_h, W, H, r=0, fill=CARD+(230,))
    ov3 = Image.new("RGBA",(W,H),(0,0,0,0))
    dl  = ImageDraw.Draw(ov3)
    dl.line([(0,H-footer_h),(W,H-footer_h)], fill=BORDER+(200,), width=1)
    img.alpha_composite(ov3)
    draw.text((40,H-footer_h+14), "sameerxceed.github.io/nifty-dashboard",
              font=fnt("regular",16), fill=MUTED)
    disc = "Not financial advice"
    dw_  = tw(draw, disc, fnt("regular",16))
    draw.text((W-dw_-40,H-footer_h+14), disc, font=fnt("regular",16), fill=MUTED)

    img.convert("RGB").save(output_path, "PNG", optimize=True)
    print("Card saved: " + output_path)
    return output_path


if __name__ == "__main__":
    sample = {
        "nifty":    {"price":"22,450","change":"+185","pct":"+0.83%"},
        "sentiment":{"score":68,"label":"Bullish"},
        "gift":     {"value":"22,520","gap_pts":"+195","signal":"gap_up"},
        "vix":      {"value":"13.45","level":"low"},
        "pivot":    {"r2":"22,850","r1":"22,650","pp":"22,400","s1":"22,200","s2":"21,950"},
        "news": [
            {"tag":"MACRO","headline":"RBI holds rates steady, signals dovish outlook for Q1 2026","impact":"positive"},
            {"tag":"GEO",  "headline":"US-China trade tensions ease after weekend diplomatic talks","impact":"positive"},
            {"tag":"MARKET","headline":"FII net buyers at Rs.2,840 Cr in cash market segment","impact":"positive"},
        ],
        "brief":"TRADING VERDICT: Bullish opening expected with 195pt gap-up. Buy dips near 22,380-22,400 PP zone. Target 22,650 R1. Stop loss at 22,280. Wait for 15-min candle close above 22,450 for confirmation."
    }
    generate_card(sample, "morning_brief", "/home/claude/nifty-insta/test_card_v2.png")


# ══════════════════════════════════════════════════════════════════════════════
# 3-PERSPECTIVE CARD  (separate 1080x1080 image)
# ══════════════════════════════════════════════════════════════════════════════
def generate_perspective_card(data: dict, session: str,
                               output_path: str = "nifty_perspectives.png"):
    """
    Generates a 3-view card: Bull / Neutral / Bear on the day's KEY event.
    data must contain: key_event, bull_view, neutral_view, bear_view
    """
    IST     = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(IST)
    TIME    = now_ist.strftime("%I:%M %p")
    DATE    = now_ist.strftime("%d %b %Y")

    event        = data.get("key_event",  "Market Key Event")
    bull_view    = data.get("bull_view",  "Bullish perspective pending.")
    neutral_view = data.get("neutral_view","Neutral perspective pending.")
    bear_view    = data.get("bear_view",  "Bearish perspective pending.")

    nifty_p = str(data.get("nifty",{}).get("price","—"))
    nifty_c = str(data.get("nifty",{}).get("change","+0"))
    score   = int(data.get("sentiment",{}).get("score",50))
    sent_l  = str(data.get("sentiment",{}).get("label","Neutral")).upper()
    sc_col  = GREEN if score>55 else RED if score<45 else YELLOW

    img  = make_bg()
    draw = ImageDraw.Draw(img)

    # Header
    rr(img, 0, 0, W, 86, r=0, fill=CARD+(248,))
    ov2 = Image.new("RGBA",(W,H),(0,0,0,0))
    ds  = ImageDraw.Draw(ov2)
    ds.rectangle([0,0,W,4], fill=ACCENT+(230,))
    img.alpha_composite(ov2)
    rr(img, 24,14,72,72, r=10, fill=(0,50,110,255), outline=ACCENT+(130,), ow=1)
    draw.text((28,16), "NB", font=fnt("black",30), fill=WHITE)
    draw.text((82,14), "NIFTY LIVE", font=fnt("black",30), fill=TEXT)
    draw.text((82,50), "3-View Market Analysis  ·  NSE India", font=fnt("regular",17), fill=TEXT2)
    pc = GREEN if str(nifty_c).startswith("+") else RED
    draw.text((W-310, 14), nifty_p, font=fnt("black",30), fill=pc)
    draw.text((W-310, 50), nifty_c + "   " + sent_l, font=fnt("medium",17), fill=sc_col)
    dt_txt = TIME + "   ·   " + DATE
    dtw_   = tw(draw, dt_txt, fnt("light",16))
    draw.text(((W-dtw_)//2, 92), dt_txt, font=fnt("light",16), fill=MUTED)

    y = 114

    # Key Event
    rr(img, 24, y, W-24, y+90, r=16, fill=CARD2+(230,), outline=ACCENT+(70,), ow=1)
    draw.text((44, y+10), "KEY EVENT", font=fnt("bold",15), fill=ACCENT)
    ef     = fnt("black", 24)
    elines = wrap(draw, event, ef, W-100)
    for li, line in enumerate(elines[:2]):
        draw.text((44, y+32+li*30), line, font=ef, fill=WHITE)

    y += 102

    footer_h = 54
    avail_h  = H - y - footer_h - 20
    card_h   = (avail_h - 16) // 3

    views = [
        ("BULL CASE",    GREEN,  (0,60,20,240),  (0,180,80,80),   bull_view,   ">"),
        ("NEUTRAL CASE", YELLOW, (40,40,0,240),  (200,160,0,80),  neutral_view,"="),
        ("BEAR CASE",    RED,    (60,10,10,240), (200,40,50,80),   bear_view,   "<"),
    ]

    for i, (title, col, bg_fill, border_col, view_text, arrow) in enumerate(views):
        cy = y + i*(card_h+8)
        rr(img, 24, cy, W-24, cy+card_h, r=18, fill=bg_fill, outline=border_col, ow=2)
        ov_bar = Image.new("RGBA",(W,H),(0,0,0,0))
        db     = ImageDraw.Draw(ov_bar)
        db.rounded_rectangle([24, cy, 36, cy+card_h], radius=18, fill=col+(200,))
        img.alpha_composite(ov_bar)
        d2  = ImageDraw.Draw(img)
        tf  = fnt("black", 20)
        tw_ = tw(d2, title, tf)
        rr(img, 48, cy+14, 48+tw_+24, cy+46, r=10, fill=col+(40,), outline=col+(150,), ow=1)
        d2.text((60, cy+18), title, font=tf, fill=col)
        vf     = fnt("regular", 20)
        vlines = wrap(d2, view_text, vf, W-108)
        text_area = card_h - 68
        max_lines = min(len(vlines), text_area//28)
        lh        = min(text_area // max(max_lines,1), 34)
        for li, line in enumerate(vlines[:max_lines]):
            d2.text((48, cy+56+li*lh), line, font=vf, fill=TEXT)
        aw = tw(d2, arrow, fnt("black",40))
        d2.text((W-50-aw, cy+card_h//2-20), arrow, font=fnt("black",40), fill=col+(60,))

    # Footer
    fy = H - footer_h
    rr(img, 0, fy, W, H, r=0, fill=CARD+(230,))
    ov3 = Image.new("RGBA",(W,H),(0,0,0,0))
    dl  = ImageDraw.Draw(ov3)
    dl.line([(0,fy),(W,fy)], fill=BORDER+(200,), width=1)
    img.alpha_composite(ov3)
    df = ImageDraw.Draw(img)
    df.text((40,fy+14), "sameerxceed.github.io/nifty-dashboard",
            font=fnt("regular",16), fill=MUTED)
    disc = "Not financial advice"
    dw_  = tw(df, disc, fnt("regular",16))
    df.text((W-dw_-40,fy+14), disc, font=fnt("regular",16), fill=MUTED)

    img.convert("RGB").save(output_path, "PNG", optimize=True)
    print("Perspectives card saved: " + output_path)
    return output_path

#!/usr/bin/env python3
"""
jarvis_app.py — LU2COHOUSE Jarvis Command Centre
Deploy:
  cd /root/lu2cohouse && venv/bin/pip install flask
  nohup venv/bin/python3 jarvis_app.py > jarvis.log 2>&1 &
Access: http://146.190.31.63:7777
"""

import os, json, subprocess
import requests as http
from datetime import datetime, date, timedelta
from flask import Flask, render_template_string, jsonify, request, session, redirect

try:
    from config import PINTEREST_ACCESS_TOKEN, PINTEREST_API
except ImportError:
    print("ERROR: config.py not found"); exit(1)

try:
    from config import JARVIS_PASSWORD
except ImportError:
    JARVIS_PASSWORD = "lu2cohouse2026"

PORT = 7777
DIR  = os.path.dirname(os.path.abspath(__file__))

QUEUE_FILE    = os.path.join(DIR, "pins_queue.json")
POSTED_FILE   = os.path.join(DIR, "posted_pins.json")
POSTER_LOG    = os.path.join(DIR, "poster.log")
ANALYTICS_LOG = os.path.join(DIR, "analytics.log")
REPINNER_LOG  = os.path.join(DIR, "repinner.log")
OPT_HIST_FILE = os.path.join(DIR, "optimization_history.json")
POOL_FILE     = os.path.join(DIR, "repin_pool.json")

SCHEDULE = [
    {"time": "08:00", "agent": "A3", "action": "Analytics"},
    {"time": "09:00", "agent": "A2", "action": "Post pin"},
    {"time": "11:00", "agent": "A4", "action": "Repin"},
    {"time": "13:00", "agent": "A2", "action": "Post pin"},
    {"time": "16:00", "agent": "A4", "action": "Repin"},
    {"time": "20:00", "agent": "A2", "action": "Post pin"},
]

app = Flask(__name__)
app.secret_key = "j4rv1s-lu2c0h0us3-2026-s3cr3t!"


def load_json(path, default=None):
    if default is None: default = []
    try:
        with open(path) as f: return json.load(f)
    except: return default

def tail_log(path, n=30):
    try:
        with open(path) as f: lines = f.readlines()
        return [l.rstrip() for l in lines[-n:]]
    except: return []

def auth_headers():
    return {"Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}", "Content-Type": "application/json"}

def get_account_analytics():
    end = date.today(); start = end - timedelta(days=7)
    try:
        r = http.get(f"{PINTEREST_API}/user_account/analytics", headers=auth_headers(),
            params={"start_date": start.strftime("%Y-%m-%d"), "end_date": end.strftime("%Y-%m-%d"),
                    "metric_types": "IMPRESSION,SAVE,OUTBOUND_CLICK,PIN_CLICK"}, timeout=12)
        if r.status_code != 200:
            return {"status": "error", "msg": "Token expired" if r.status_code == 401 else f"API {r.status_code}",
                    "impressions": 0, "saves": 0, "outbound_clicks": 0, "pin_clicks": 0}
        data = r.json(); summary = data.get("all", {}).get("summary_metrics", {})
        if not summary:
            t = {"IMPRESSION": 0, "SAVE": 0, "OUTBOUND_CLICK": 0, "PIN_CLICK": 0}
            for d in data.get("all", {}).get("daily_metrics", []):
                for k in t: t[k] += d.get("metrics", {}).get(k, 0)
            summary = t
        return {"impressions": int(summary.get("IMPRESSION", 0)), "saves": int(summary.get("SAVE", 0)),
                "outbound_clicks": int(summary.get("OUTBOUND_CLICK", 0)), "pin_clicks": int(summary.get("PIN_CLICK", 0)), "status": "ok"}
    except Exception as ex:
        return {"status": "error", "msg": str(ex)[:60], "impressions": 0, "saves": 0, "outbound_clicks": 0, "pin_clicks": 0}

def is_running(name):
    try: return bool(subprocess.run(["pgrep", "-f", name], capture_output=True, text=True).stdout.strip())
    except: return False

def next_event():
    now = datetime.now(); cur = now.hour * 60 + now.minute
    for s in SCHEDULE:
        h, m = map(int, s["time"].split(":"))
        if h * 60 + m > cur: return f"{s['time']}  {s['agent']} {s['action']}"
    return f"{SCHEDULE[0]['time']}  {SCHEDULE[0]['agent']} {SCHEDULE[0]['action']} (tomorrow)"

def require_auth():
    if not session.get("ok"): return redirect("/login")

def api_guard():
    if not session.get("ok"): return jsonify({"error": "unauthorized"}), 401

@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        if request.form.get("password", "") == JARVIS_PASSWORD:
            session["ok"] = True; return redirect("/")
        error = "Incorrect access code"
    return render_template_string(LOGIN_HTML, error=error)

@app.route("/logout")
def logout():
    session.clear(); return redirect("/login")

@app.route("/api/status")
def api_status():
    e = api_guard()
    if e: return e
    q = load_json(QUEUE_FILE, []); p = load_json(POSTED_FILE, [])
    opt = load_json(OPT_HIST_FILE, {"scaled": []}); pool = load_json(POOL_FILE, [])
    return jsonify({"queue_count": len(q), "days_remaining": max(0, len(q)//3),
                    "posted_count": len(p), "variations_made": len(opt.get("scaled", [])),
                    "repin_pool": len(pool), "scheduler": is_running("scheduler.py"),
                    "next_event": next_event()})

@app.route("/api/analytics")
def api_analytics():
    e = api_guard()
    if e: return e
    return jsonify(get_account_analytics())

@app.route("/api/log")
def api_log():
    e = api_guard()
    if e: return e
    raw = tail_log(POSTER_LOG, 40)
    # Filter fixed 400-title errors (root cause resolved in agent2_poster.py)
    poster = [l for l in raw if 'maxLength' not in l and 'is too long' not in l][-18:]
    return jsonify({"poster": poster, "repinner": [], "analytics": tail_log(ANALYTICS_LOG, 10)})

@app.route("/api/chat", methods=["POST"])
def api_chat():
    e = api_guard()
    if e: return e
    msg = (request.json or {}).get("message", "").strip()
    if not msg: return jsonify({"response": "..."})
    q = load_json(QUEUE_FILE, []); p = load_json(POSTED_FILE, [])
    system_prompt = (
        "You are Jarvis, AI for LU2COHOUSE sewing patterns on Etsy.\n"
        f"Status: {len(q)} pins queued (~{len(q)//3} days) | {len(p)} posted.\n"
        "Schedule: 08:00 A3 | 09:00 A2 | 11:00 A4 | 13:00 A2 | 16:00 A4 | 20:00 A2\n"
        "39 products. Q4 paid ads Oct 2026. Target $5k/mo Dec.\nReply in 2-3 sentences."
    )
    try:
        from config import ANTHROPIC_API_KEY
        import anthropic
        resp = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY).messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=200,
            system=system_prompt, messages=[{"role": "user", "content": msg}])
        return jsonify({"response": resp.content[0].text})
    except ImportError:
        return jsonify({"response": "Add ANTHROPIC_API_KEY to config.py to enable chat."})
    except Exception as ex:
        return jsonify({"response": f"Error: {str(ex)[:80]}"})

@app.route("/")
def dashboard():
    e = require_auth()
    if e: return e
    return render_template_string(DASHBOARD_HTML)


LOGIN_HTML = """<!DOCTYPE html>
<html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>JARVIS</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&family=JetBrains+Mono&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#020c14;min-height:100vh;display:grid;place-items:center;font-family:'JetBrains Mono',monospace;color:#a8e8f0;overflow:hidden}
body::before{content:'';position:fixed;inset:0;background:radial-gradient(ellipse at 50% 50%,rgba(13,143,160,.06)0%,transparent 70%);pointer-events:none}
.box{background:rgba(0,8,18,.92);border:1px solid rgba(13,143,160,.35);padding:44px 38px;width:330px;text-align:center;clip-path:polygon(12px 0%,100% 0%,100% calc(100% - 12px),calc(100% - 12px) 100%,0% 100%,0% 12px)}
.logo{font-family:'Orbitron',monospace;font-size:22px;font-weight:900;color:#40cfe0;letter-spacing:.22em;margin-bottom:4px;text-shadow:0 0 22px rgba(64,207,224,.5);display:flex;align-items:center;justify-content:center;gap:9px}
.dot{width:8px;height:8px;background:#40cfe0;border-radius:50%;box-shadow:0 0 10px #40cfe0;animation:p 2s ease-in-out infinite}
@keyframes p{0%,100%{opacity:1}50%{opacity:.2}}
.sub{font-size:9.5px;color:rgba(13,143,160,.5);letter-spacing:.14em;text-transform:uppercase;margin-bottom:32px}
input{width:100%;background:rgba(0,20,35,.6);border:1px solid rgba(13,143,160,.22);border-bottom:1px solid rgba(64,207,224,.3);padding:12px 13px;color:#a8e8f0;font-family:'JetBrains Mono',monospace;font-size:13px;outline:none;transition:border-color .2s;margin-bottom:10px}
input:focus{border-color:rgba(64,207,224,.5)}
input::placeholder{color:rgba(13,143,160,.35)}
button{width:100%;background:rgba(13,143,160,.14);border:1px solid rgba(64,207,224,.3);padding:12px;color:#40cfe0;font-family:'Orbitron',monospace;font-size:10px;font-weight:700;letter-spacing:.2em;cursor:pointer;transition:background .2s,box-shadow .2s;clip-path:polygon(6px 0%,100% 0%,100% calc(100% - 6px),calc(100% - 6px) 100%,0% 100%,0% 6px)}
button:hover{background:rgba(13,143,160,.28);box-shadow:0 0 16px rgba(64,207,224,.18)}
.err{margin-top:11px;color:#ff4444;font-size:11px}
</style></head>
<body><div class="box">
<div class="logo"><div class="dot"></div>JARVIS</div>
<div class="sub">LU2COHOUSE Command Centre</div>
<form method="POST">
<input type="password" name="password" placeholder="Enter access code" autofocus>
<button type="submit">ACCESS SYSTEM</button>
{% if error %}<div class="err">&#9888; {{ error }}</div>{% endif %}
</form>
</div></body></html>"""


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>JARVIS — LU2COHOUSE</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:100%;height:100%;overflow:hidden;background:#020c14;color:#a8e8f0;font-family:'JetBrains Mono',monospace}

/* Full-screen canvas behind everything */
#cv{position:fixed;top:0;left:0;width:100%;height:100%;z-index:0}

/* Topbar */
.tb{position:fixed;top:0;left:0;right:0;height:38px;z-index:10;display:flex;align-items:center;justify-content:space-between;padding:0 16px;background:rgba(0,3,10,.97);border-bottom:1px solid rgba(13,143,160,.5);box-shadow:0 1px 18px rgba(0,0,0,.8)}
.tb-logo{font-family:'Orbitron',monospace;font-size:12px;font-weight:900;color:#40cfe0;letter-spacing:.22em;display:flex;align-items:center;gap:7px;text-shadow:0 0 14px rgba(64,207,224,.4)}
.tb-dot{width:6px;height:6px;background:#40cfe0;border-radius:50%;box-shadow:0 0 8px #40cfe0;animation:bl 2s ease-in-out infinite}
@keyframes bl{0%,100%{opacity:1}50%{opacity:.15}}
.tb-chip{display:flex;align-items:center;gap:6px;font-size:9px;letter-spacing:.14em;background:rgba(13,143,160,.08);border:1px solid rgba(13,143,160,.2);padding:3px 10px}
.live-dot{width:4.5px;height:4.5px;background:#40cfe0;border-radius:50%;box-shadow:0 0 5px #40cfe0;animation:bl 1.4s ease-in-out infinite}
.tb-r{display:flex;align-items:center;gap:12px;font-size:11px}
.logout{font-size:8.5px;color:rgba(13,143,160,.35);text-decoration:none;letter-spacing:.12em;transition:color .2s}
.logout:hover{color:#40cfe0}

/* HUD Panels — floating over canvas */
.panel{position:fixed;z-index:8;background:rgba(0,4,14,.93);border:1px solid rgba(13,143,160,.55);padding:12px 14px;min-width:192px;backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);clip-path:polygon(10px 0%,100% 0%,100% calc(100% - 10px),calc(100% - 10px) 100%,0% 100%,0% 10px);box-shadow:0 0 24px rgba(0,0,0,.7),inset 0 0 1px rgba(13,143,160,.2)}
.panel::before{content:'';position:absolute;top:3px;right:3px;width:6px;height:6px;border-top:1px solid rgba(64,207,224,.5);border-right:1px solid rgba(64,207,224,.5)}
.panel::after{content:'';position:absolute;bottom:3px;left:3px;width:6px;height:6px;border-bottom:1px solid rgba(64,207,224,.5);border-left:1px solid rgba(64,207,224,.5)}
.p-tl{top:46px;left:8px}
.p-tr{top:46px;right:8px}
.p-bl{bottom:110px;left:8px}
.p-br{bottom:110px;right:8px}

/* Panel contents */
.ph{font-family:'Orbitron',monospace;font-size:7px;font-weight:700;letter-spacing:.22em;color:rgba(13,143,160,.6);text-transform:uppercase;margin-bottom:9px;padding-bottom:6px;border-bottom:1px solid rgba(13,143,160,.12);display:flex;align-items:center;justify-content:space-between}
.ptag{font-size:6.5px;padding:1px 5px;border-radius:1px}
.ptag.ok{background:rgba(64,207,224,.1);color:#40cfe0;border:1px solid rgba(64,207,224,.25)}
.ptag.warn{background:rgba(255,187,0,.08);color:#ffbb00;border:1px solid rgba(255,187,0,.2)}
.ptag.off{background:rgba(255,68,68,.08);color:#ff4444;border:1px solid rgba(255,68,68,.18)}
.mrow{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:7px;gap:8px}
.mrow:last-child{margin-bottom:0}
.ml{font-size:8.5px;color:rgba(13,143,160,.5);letter-spacing:.06em;white-space:nowrap}
.mv{font-family:'Orbitron',monospace;font-size:19px;font-weight:700;line-height:1;text-align:right;color:#a8e8f0}
.mv.cy{color:#40cfe0}.mv.gn{color:#00ff88}.mv.yl{color:#ffbb00}
.arow{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px}
.arow:last-child{margin-bottom:0}
.an{font-size:8.5px;color:rgba(100,170,200,.55);letter-spacing:.06em}
.ab{font-size:7px;padding:1px 6px;font-family:'Orbitron',monospace;letter-spacing:.08em;display:flex;align-items:center;gap:3px}
.ab.live{background:rgba(64,207,224,.08);color:#40cfe0;border:1px solid rgba(64,207,224,.2)}
.ab.off{background:rgba(255,68,68,.08);color:#ff4444;border:1px solid rgba(255,68,68,.18)}
.ab.pend{background:rgba(255,187,0,.07);color:#ffbb00;border:1px solid rgba(255,187,0,.15)}
.adot{width:3px;height:3px;background:currentColor;border-radius:50%;animation:bl 1.5s ease-in-out infinite}
.divl{height:1px;background:rgba(13,143,160,.1);margin:7px 0}

/* Bottom bar */
.bbar{position:fixed;bottom:0;left:0;right:0;height:108px;z-index:9;display:flex;background:rgba(2,6,16,.92);border-top:1px solid rgba(13,143,160,.18)}
.blog{flex:1;padding:7px 12px;font-size:9.5px;line-height:1.65;color:rgba(13,143,160,.6);overflow-y:auto;border-right:1px solid rgba(13,143,160,.1)}
.blog::-webkit-scrollbar{width:2px}
.blog::-webkit-scrollbar-thumb{background:rgba(13,143,160,.15)}
.ll{white-space:pre-wrap;word-break:break-all}
.ll.ok{color:rgba(64,207,224,.8)}.ll.er{color:#ff4444}.ll.hi{color:rgba(13,143,160,.8)}
.bchat{width:300px;flex-shrink:0;display:flex;flex-direction:column;padding:7px 10px;gap:5px}
.cout{flex:1;overflow-y:auto;font-size:10.5px;line-height:1.5;color:#a8e8f0}
.cout::-webkit-scrollbar{display:none}
.jl{font-size:8px;letter-spacing:.07em}.jl.j{color:#40cfe0}.jl.u{color:rgba(13,143,160,.45)}
.chat-bar{display:flex;gap:5px}
.ci{flex:1;background:rgba(0,18,30,.6);border:1px solid rgba(13,143,160,.18);border-bottom:1px solid rgba(64,207,224,.25);padding:6px 9px;color:#a8e8f0;font-family:'JetBrains Mono',monospace;font-size:10.5px;outline:none;transition:border-color .2s}
.ci:focus{border-color:rgba(64,207,224,.4)}
.ci::placeholder{color:rgba(13,143,160,.3)}
.cb{background:rgba(13,143,160,.12);border:1px solid rgba(64,207,224,.25);padding:6px 10px;color:#40cfe0;font-family:'Orbitron',monospace;font-size:8px;font-weight:700;letter-spacing:.1em;cursor:pointer;transition:background .2s;white-space:nowrap;clip-path:polygon(5px 0%,100% 0%,100% calc(100% - 5px),calc(100% - 5px) 100%,0% 100%,0% 5px)}
.cb:hover{background:rgba(13,143,160,.25)}
.cb:disabled{opacity:.3;cursor:not-allowed}
/* scanlines */
body::after{content:'';position:fixed;inset:0;pointer-events:none;z-index:2;background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,.04)2px,rgba(0,0,0,.04)4px)}
</style></head>
<body>
<canvas id="cv"></canvas>

<!-- Topbar -->
<div class="tb">
  <div class="tb-logo"><div class="tb-dot"></div>JARVIS</div>
  <div class="tb-chip"><div class="live-dot"></div>SYSTEM ONLINE &nbsp;&mdash;&nbsp; LU2COHOUSE &nbsp;&mdash;&nbsp; <span id="tb-d"></span></div>
  <div class="tb-r"><span id="tb-c"></span><a href="/logout" class="logout">LOGOUT</a></div>
</div>

<!-- TL: Analytics -->
<div class="panel p-tl">
  <div class="ph">7-Day Analytics<span class="ptag ok" id="an-tag">LIVE</span></div>
  <div class="mrow"><span class="ml">IMPRESSIONS</span><span class="mv cy" id="a-imp">—</span></div>
  <div class="mrow"><span class="ml">SAVES</span><span class="mv gn" id="a-sav">—</span></div>
  <div class="mrow"><span class="ml">PIN CLICKS</span><span class="mv" id="a-clk">—</span></div>
  <div class="mrow"><span class="ml">ETSY CLICKS</span><span class="mv yl" id="a-out">—</span></div>
</div>

<!-- TR: Agents -->
<div class="panel p-tr">
  <div class="ph">Agent Status<span class="ptag ok" id="sys-tag">LIVE</span></div>
  <div class="arow"><span class="an">A2 PUBLISHER</span><span class="ab live" id="b2"><div class="adot"></div>LIVE</span></div>
  <div class="arow"><span class="an">A3 ANALYST</span><span class="ab live" id="b3"><div class="adot"></div>LIVE</span></div>
  <div class="arow"><span class="an">A4 REPINNER</span><span class="ab live" id="b4"><div class="adot"></div>LIVE</span></div>
  <div class="divl"></div>
  <div class="arow"><span class="an">SCHEDULER</span><span class="ab live" id="sched"><div class="adot"></div>ONLINE</span></div>
  <div class="arow"><span class="an">ORGANIC PINS</span><span class="ab live"><div class="adot"></div>RUNNING</span></div>
  <div class="arow"><span class="an">PAID ADS</span><span class="ab pend">OCT 2026</span></div>
</div>

<!-- BL: Queue -->
<div class="panel p-bl">
  <div class="ph">Queue Status<span class="ptag ok">LIVE</span></div>
  <div class="mrow"><span class="ml">PINS REMAINING</span><span class="mv cy" id="q-count">—</span></div>
  <div class="mrow"><span class="ml">DAYS CONTENT</span><span class="mv" id="q-days">—</span></div>
  <div class="mrow"><span class="ml">TOTAL POSTED</span><span class="mv gn" id="s-posted">—</span></div>
  <div class="divl"></div>
  <div style="font-size:8.5px;color:#40cfe0;font-family:'Orbitron',monospace;letter-spacing:.04em;line-height:1.6" id="q-next">—</div>
</div>

<!-- BR: Optimization -->
<div class="panel p-br">
  <div class="ph">Optimization<span class="ptag ok">A3</span></div>
  <div class="mrow"><span class="ml">VARIATIONS</span><span class="mv gn" id="s-vars">0</span></div>
  <div class="mrow"><span class="ml">REPIN POOL</span><span class="mv" id="s-pool">—</span></div>
  <div class="divl"></div>
  <div style="font-size:8px;color:rgba(13,143,160,.38);line-height:1.75;letter-spacing:.04em">
    TARGET $1,200/MO SEP 2026<br>TARGET $5,000/MO DEC 2026<br>39 SEWING PATTERNS
  </div>
</div>

<!-- Bottom -->
<div class="bbar">
  <div class="blog" id="blog">Initializing…</div>
  <div class="bchat">
    <div class="cout" id="cout"><div><span class="jl j">JARVIS › </span>All systems operational.</div></div>
    <div class="chat-bar">
      <input class="ci" id="ci" type="text" placeholder="ask jarvis anything…"/>
      <button class="cb" id="cb" onclick="sendChat()">SEND</button>
    </div>
  </div>
</div>

<script>
// Utils
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function fmt(n){n=parseInt(n)||0;return n>=10000?(n/1000).toFixed(1)+'k':n.toLocaleString()}

// Clock
(function tick(){
  const n=new Date(),D=['SUN','MON','TUE','WED','THU','FRI','SAT'];
  document.getElementById('tb-c').textContent=String(n.getHours()).padStart(2,'0')+':'+String(n.getMinutes()).padStart(2,'0')+':'+String(n.getSeconds()).padStart(2,'0');
  document.getElementById('tb-d').textContent=String(n.getDate()).padStart(2,'0')+'/'+String(n.getMonth()+1).padStart(2,'0')+'  '+D[n.getDay()];
  setTimeout(tick,1000);
})();

async function fetchStatus(){
  try{
    const d=await(await fetch('/api/status')).json();
    document.getElementById('q-count').textContent=fmt(d.queue_count);
    document.getElementById('q-days').textContent='~'+d.days_remaining+'d';
    document.getElementById('s-posted').textContent=fmt(d.posted_count);
    document.getElementById('s-vars').textContent=d.variations_made||'0';
    document.getElementById('s-pool').textContent=fmt(d.repin_pool);
    document.getElementById('q-next').textContent=d.next_event||'—';
    const on=d.scheduler;
    document.getElementById('sys-tag').className='ptag '+(on?'ok':'off');
    document.getElementById('sys-tag').textContent=on?'LIVE':'OFFLINE';
    ['b2','b3','b4'].forEach(id=>{
      const el=document.getElementById(id);
      el.className='ab '+(on?'live':'off');
      el.innerHTML='<div class="adot"></div>'+(on?'LIVE':'OFF');
    });
    const sc=document.getElementById('sched');
    sc.className='ab '+(on?'live':'off');
    sc.innerHTML='<div class="adot"></div>'+(on?'ONLINE':'OFFLINE');
  }catch(e){}
}

async function fetchAnalytics(){
  try{
    const d=await(await fetch('/api/analytics')).json();
    const ok=d.status==='ok';
    document.getElementById('a-imp').textContent=ok?fmt(d.impressions):'ERR';
    document.getElementById('a-sav').textContent=ok?fmt(d.saves):'—';
    document.getElementById('a-clk').textContent=ok?fmt(d.pin_clicks):'—';
    document.getElementById('a-out').textContent=ok?fmt(d.outbound_clicks):'—';
    if(!ok){const t=document.getElementById('an-tag');t.className='ptag off';t.textContent='ERR';}
  }catch(e){}
}

async function fetchLog(){
  try{
    const d=await(await fetch('/api/log')).json();
    const lines=(d.poster||[]).slice(-12);
    const el=document.getElementById('blog');
    if(!lines.length){el.innerHTML='<div class="ll hi">Waiting for first pin post at 09:00…</div>';return}
    el.innerHTML=lines.map(l=>{
      let c='ll';
      if(l.includes('SUCCESS')||l.includes('started'))c+=' ok';
      else if(l.includes('FAIL')||l.includes('ERROR')||l.includes('expired'))c+=' er';
      else if(l.includes('[')||l.includes('Posting'))c+=' hi';
      return'<div class="'+c+'">'+esc(l)+'</div>';
    }).join('');
    el.scrollTop=el.scrollHeight;
  }catch(e){}
}

async function sendChat(){
  const inp=document.getElementById('ci'),btn=document.getElementById('cb');
  const out=document.getElementById('cout');
  const msg=inp.value.trim();if(!msg)return;
  inp.value='';btn.disabled=true;
  out.innerHTML+='<div><span class="jl u">YOU › </span>'+esc(msg)+'</div>';
  out.innerHTML+='<div id="jt"><span class="jl j">JARVIS › </span><span style="opacity:.3">…</span></div>';
  out.scrollTop=out.scrollHeight;
  try{
    const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg})});
    const data=await r.json();
    const t=document.getElementById('jt');if(t)t.innerHTML='<span class="jl j">JARVIS › </span>'+esc(data.response||'...');
  }catch(e){const t=document.getElementById('jt');if(t)t.innerHTML='<span class="jl j">JARVIS › </span>Error.';}
  finally{btn.disabled=false;inp.focus();out.scrollTop=out.scrollHeight}
}
document.addEventListener('DOMContentLoaded',()=>{
  document.getElementById('ci').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendChat()}});
});

// ═══════════════════════════════════════════════════════════
//  ARC REACTOR + CIRCUIT BOARD CANVAS
// ═══════════════════════════════════════════════════════════
class ArcReactor {
  constructor(cv){
    this.cv=cv; this.ctx=cv.getContext('2d');
    this.t=0; this.circuits=[]; this.ptcls=[];
    this.resize(); this.buildCircuits();
    window.addEventListener('resize',()=>{this.resize();this.buildCircuits()});
    requestAnimationFrame(()=>this.frame());
  }

  resize(){
    this.cv.width=window.innerWidth;
    this.cv.height=window.innerHeight;
    this.cx=this.cv.width/2;
    this.cy=this.cv.height/2;
    this.R=Math.min(this.cx,this.cy)*0.40; // reactor radius
  }

  buildCircuits(){
    const cx=this.cx,cy=this.cy,W=this.cv.width,H=this.cv.height;
    const r=this.R*1.55; // start circuits from outside reactor

    // Helper: build path starting at angle from reactor edge
    const path=(angle,steps)=>{
      const sx=cx+Math.cos(angle)*r, sy=cy+Math.sin(angle)*r;
      const pts=[{x:sx,y:sy}];
      let x=sx,y=sy;
      steps.forEach(([dx,dy])=>{x+=dx;y+=dy;pts.push({x,y})});
      return {pts, p:0, spd:0.0018+Math.random()*0.001};
    };

    const u=W*0.01, v=H*0.01; // units

    this.circuits=[
      // UP
      path(-Math.PI/2,    [[0,-v*12],[u*-12,-v*0],[u*-12,-v*8],[u*-25,-v*0],[u*-25,-v*5]]),
      path(-Math.PI/2+0.3,[[u*5,-v*10],[u*0,-v*8],[u*12,-v*0],[u*12,-v*6],[u*30,-v*0]]),
      path(-Math.PI/2-0.3,[[-u*5,-v*10],[0,-v*6],[-u*18,-v*0],[-u*18,-v*4],[-u*35,-v*0]]),
      // DOWN
      path(Math.PI/2,     [[0,v*12],[u*12,0],[u*12,v*8],[u*28,0]]),
      path(Math.PI/2+0.3, [[-u*5,v*10],[0,v*6],[-u*20,0],[-u*20,v*5],[-u*38,0]]),
      path(Math.PI/2-0.25,[[u*6,v*9],[u*0,v*5],[u*16,0],[u*16,v*4],[u*36,0]]),
      // RIGHT
      path(0,             [[u*12,0],[0,-v*10],[u*16,0],[u*16,-v*6],[u*14,0]]),
      path(0+0.35,        [[u*10,v*4],[u*8,0],[0,v*10],[u*14,0],[u*14,v*4]]),
      path(0-0.3,         [[u*11,-v*4],[u*6,0],[0,-v*8],[u*18,0]]),
      // LEFT
      path(Math.PI,       [[-u*12,0],[0,v*10],[-u*16,0],[-u*16,v*5],[-u*12,0]]),
      path(Math.PI+0.3,   [[-u*10,-v*4],[-u*8,0],[0,-v*10],[-u*14,0],[-u*14,-v*4]]),
      path(Math.PI-0.3,   [[-u*11,v*4],[-u*6,0],[0,v*8],[-u*18,0]]),
      // DIAGONALS
      path(-Math.PI*0.75, [[-u*8,-v*8],[-u*12,-v*0],[-u*0,-v*10],[-u*10,-v*0],[-u*10,-v*4],[-u*20,-v*0]]),
      path(-Math.PI*0.25, [[u*8,-v*8],[u*16,-v*0],[u*0,-v*8],[u*12,-v*0]]),
      path(Math.PI*0.75,  [[-u*8,v*8],[-u*14,0],[0,v*8],[-u*16,0],[-u*16,v*4]]),
      path(Math.PI*0.25,  [[u*8,v*8],[u*10,0],[0,v*10],[u*14,0],[u*14,v*3],[u*20,0]]),
    ];
  }

  posAlongPath(pts,p){
    let total=0; const lens=[];
    for(let i=1;i<pts.length;i++){const d=Math.hypot(pts[i].x-pts[i-1].x,pts[i].y-pts[i-1].y);lens.push(d);total+=d}
    const target=p*total; let acc=0;
    for(let i=0;i<lens.length;i++){
      if(acc+lens[i]>=target){
        const t=(target-acc)/lens[i];
        return{x:pts[i].x+(pts[i+1].x-pts[i].x)*t,y:pts[i].y+(pts[i+1].y-pts[i].y)*t};
      }
      acc+=lens[i];
    }
    return pts[pts.length-1];
  }

  drawCircuits(){
    const ctx=this.ctx,t=this.t;
    this.circuits.forEach((c,ci)=>{
      const pts=c.pts;
      const alpha=0.28+0.07*Math.sin(t*0.012+ci*0.5);
      // Main line
      ctx.beginPath();ctx.moveTo(pts[0].x,pts[0].y);
      for(let i=1;i<pts.length;i++)ctx.lineTo(pts[i].x,pts[i].y);
      ctx.strokeStyle='rgba(13,143,160,'+alpha+')';ctx.lineWidth=0.7;ctx.stroke();
      // Components at waypoints
      pts.slice(1,-1).forEach((p,pi)=>{
        if(pi%2===0){
          const w=7,h=3.5;
          ctx.strokeStyle='rgba(13,143,160,'+(alpha*0.9)+')';ctx.lineWidth=0.6;
          ctx.strokeRect(p.x-w/2,p.y-h/2,w,h);
          // pins
          ctx.beginPath();ctx.moveTo(p.x-w/2-2,p.y);ctx.lineTo(p.x-w/2,p.y);
          ctx.moveTo(p.x+w/2,p.y);ctx.lineTo(p.x+w/2+2,p.y);
          ctx.stroke();
        } else {
          ctx.beginPath();ctx.arc(p.x,p.y,1.5,0,Math.PI*2);
          ctx.fillStyle='rgba(64,207,224,'+(alpha*1.2)+')';ctx.fill();
        }
      });
      // End cap
      const last=pts[pts.length-1];
      ctx.beginPath();ctx.arc(last.x,last.y,3,0,Math.PI*2);
      ctx.strokeStyle='rgba(64,207,224,'+(alpha*0.8)+')';ctx.lineWidth=0.8;ctx.stroke();
      // Moving particle
      c.p=(c.p+c.spd)%1;
      const pos=this.posAlongPath(pts,c.p);
      ctx.beginPath();ctx.arc(pos.x,pos.y,1.8,0,Math.PI*2);
      ctx.fillStyle='rgba(100,230,245,0.85)';
      ctx.shadowColor='#40cfe0';ctx.shadowBlur=10;ctx.fill();ctx.shadowBlur=0;
    });
  }

  drawReactor(){
    const ctx=this.ctx,cx=this.cx,cy=this.cy,t=this.t,R=this.R;

    // ── Far ambient pulse glow ──
    const pa=0.10+0.05*Math.sin(t*0.04);
    const fog=ctx.createRadialGradient(cx,cy,R*0.7,cx,cy,R*3.8);
    fog.addColorStop(0,'rgba(0,200,220,'+pa+')');
    fog.addColorStop(0.45,'rgba(0,80,100,0.04)');
    fog.addColorStop(1,'transparent');
    ctx.fillStyle=fog;ctx.beginPath();ctx.arc(cx,cy,R*3.8,0,Math.PI*2);ctx.fill();

    // ── 3D drop shadow below reactor ──
    const shg=ctx.createRadialGradient(cx,cy+R*0.92,0,cx,cy+R*0.92,R*1.3);
    shg.addColorStop(0,'rgba(0,180,220,0.22)');
    shg.addColorStop(1,'transparent');
    ctx.fillStyle=shg;ctx.beginPath();ctx.ellipse(cx,cy+R*0.92,R*1.15,R*0.2,0,0,Math.PI*2);ctx.fill();

    // ── Main sphere body (3D lit top-left) ──
    const sg=ctx.createRadialGradient(cx-R*0.3,cy-R*0.3,R*0.04,cx,cy,R*1.05);
    sg.addColorStop(0,'rgba(22,85,95,0.99)');
    sg.addColorStop(0.35,'rgba(5,26,36,0.99)');
    sg.addColorStop(0.75,'rgba(2,9,15,0.99)');
    sg.addColorStop(1,'rgba(0,3,8,0.98)');
    ctx.fillStyle=sg;ctx.beginPath();ctx.arc(cx,cy,R,0,Math.PI*2);ctx.fill();

    // ── Segmented armour panels outer ring (12 panels, slow CW) ──
    const nP=12,rotP=t*0.006;
    for(let i=0;i<nP;i++){
      const aS=(i/nP)*Math.PI*2+rotP, aE=((i+0.82)/nP)*Math.PI*2+rotP;
      const mA=(aS+aE)/2;
      const br=0.4+0.6*Math.pow(Math.max(0,Math.cos(mA+Math.PI*0.75)),1.5);
      ctx.beginPath();ctx.arc(cx,cy,R,aS,aE);ctx.arc(cx,cy,R*0.87,aE,aS,true);ctx.closePath();
      const rv=Math.floor(5+65*br),gv=Math.floor(135+100*br),bv=Math.floor(148+107*br);
      ctx.fillStyle='rgba('+rv+','+gv+','+bv+','+(0.5+0.38*br)+')';ctx.fill();
      ctx.strokeStyle='rgba(64,207,224,'+(0.45+0.5*br)+')';ctx.lineWidth=0.9;ctx.stroke();
    }

    // ── Outer ring glow ──
    ctx.beginPath();ctx.arc(cx,cy,R,0,Math.PI*2);
    ctx.strokeStyle='rgba(64,207,224,0.92)';ctx.lineWidth=3;
    ctx.shadowColor='#00d4ff';ctx.shadowBlur=32;ctx.stroke();ctx.shadowBlur=0;

    // ── Tick marks (60) ──
    for(let i=0;i<60;i++){
      const a=(i/60)*Math.PI*2,big=i%5===0;
      ctx.beginPath();
      ctx.moveTo(cx+Math.cos(a)*R,cy+Math.sin(a)*R);
      ctx.lineTo(cx+Math.cos(a)*(R-R*(big?0.065:0.028)),cy+Math.sin(a)*(R-R*(big?0.065:0.028)));
      ctx.strokeStyle='rgba(64,207,224,'+(big?0.9:0.3)+')';ctx.lineWidth=big?1.6:0.6;ctx.stroke();
    }

    // ── Inner fill behind middle rings ──
    const bg2=ctx.createRadialGradient(cx-R*0.18,cy-R*0.18,0,cx,cy,R*0.86);
    bg2.addColorStop(0,'rgba(14,52,62,0.97)');bg2.addColorStop(1,'rgba(1,6,12,0.98)');
    ctx.fillStyle=bg2;ctx.beginPath();ctx.arc(cx,cy,R*0.86,0,Math.PI*2);ctx.fill();

    // ── Inner segment ring (8 pieces, CCW) ──
    const nI=8,rotI=-t*0.013;
    for(let i=0;i<nI;i++){
      const aS=(i/nI)*Math.PI*2+rotI, aE=((i+0.72)/nI)*Math.PI*2+rotI;
      const mA=(aS+aE)/2,br=0.3+0.7*Math.pow(Math.max(0,Math.cos(mA+Math.PI*0.75)),1.2);
      ctx.beginPath();ctx.arc(cx,cy,R*0.77,aS,aE);ctx.arc(cx,cy,R*0.67,aE,aS,true);ctx.closePath();
      ctx.fillStyle='rgba(0,'+(Math.floor(155+65*br))+','+(Math.floor(170+70*br))+','+(0.28+0.42*br)+')';
      ctx.fill();ctx.strokeStyle='rgba(64,207,224,'+(0.3+0.5*br)+')';ctx.lineWidth=0.7;ctx.stroke();
      // Capacitor dot at each gap
      const dotA=((i+0.86)/nI)*Math.PI*2+rotI, dr=R*0.72;
      ctx.beginPath();ctx.arc(cx+Math.cos(dotA)*dr,cy+Math.sin(dotA)*dr,R*0.016,0,Math.PI*2);
      ctx.fillStyle='rgba(64,207,224,0.9)';
      ctx.shadowColor='#40cfe0';ctx.shadowBlur=10;ctx.fill();ctx.shadowBlur=0;
    }

    // ── 6 rotating spokes ──
    const rotSk=t*0.019;
    for(let i=0;i<6;i++){
      const a=(i/6)*Math.PI*2+rotSk;
      const br=0.4+0.6*Math.max(0,Math.cos(a+Math.PI*0.75));
      ctx.beginPath();ctx.moveTo(cx+Math.cos(a)*R*0.59,cy+Math.sin(a)*R*0.59);
      ctx.lineTo(cx+Math.cos(a)*R*0.66,cy+Math.sin(a)*R*0.66);
      ctx.strokeStyle='rgba(64,207,224,'+(0.4+0.55*br)+')';ctx.lineWidth=2.5;
      ctx.shadowColor='#40cfe0';ctx.shadowBlur=8;ctx.stroke();ctx.shadowBlur=0;
    }

    // ── Inner core sphere (3D) ──
    const R3=R*0.57;
    const ig=ctx.createRadialGradient(cx-R3*0.22,cy-R3*0.22,0,cx,cy,R3);
    ig.addColorStop(0,'rgba(20,78,88,0.98)');ig.addColorStop(0.5,'rgba(4,20,28,0.99)');ig.addColorStop(1,'rgba(0,4,8,0.98)');
    ctx.fillStyle=ig;ctx.beginPath();ctx.arc(cx,cy,R3,0,Math.PI*2);ctx.fill();
    ctx.beginPath();ctx.arc(cx,cy,R3,0,Math.PI*2);
    ctx.strokeStyle='rgba(64,207,224,0.6)';ctx.lineWidth=1.8;
    ctx.shadowColor='#40cfe0';ctx.shadowBlur=16;ctx.stroke();ctx.shadowBlur=0;

    // ── 24 inner ticks ──
    for(let i=0;i<24;i++){
      const a=(i/24)*Math.PI*2,big=i%6===0;
      ctx.beginPath();
      ctx.moveTo(cx+Math.cos(a)*R3,cy+Math.sin(a)*R3);
      ctx.lineTo(cx+Math.cos(a)*(R3-R*0.038),cy+Math.sin(a)*(R3-R*0.038));
      ctx.strokeStyle='rgba(64,207,224,'+(big?0.85:0.28)+')';ctx.lineWidth=big?1.3:0.5;ctx.stroke();
    }

    // ── Iron Man triangular core (IM2 style) CW ──
    const triR=R*0.32, rotTri=t*0.007;
    ctx.save();ctx.translate(cx,cy);ctx.rotate(rotTri);
    ctx.beginPath();
    for(let i=0;i<3;i++){const a=(i/3)*Math.PI*2-Math.PI/2;i?ctx.lineTo(Math.cos(a)*triR,Math.sin(a)*triR):ctx.moveTo(Math.cos(a)*triR,Math.sin(a)*triR);}
    ctx.closePath();
    const tg=ctx.createLinearGradient(-triR,-triR,triR,triR);
    tg.addColorStop(0,'rgba(0,220,240,0.14)');tg.addColorStop(1,'rgba(0,120,150,0.04)');
    ctx.fillStyle=tg;ctx.fill();
    ctx.strokeStyle='rgba(0,220,245,0.98)';ctx.lineWidth=3.5;
    ctx.shadowColor='#00d4ff';ctx.shadowBlur=30;ctx.stroke();ctx.shadowBlur=0;
    ctx.restore();

    // ── Counter-rotating outer triangle ──
    ctx.save();ctx.translate(cx,cy);ctx.rotate(-rotTri*0.55+Math.PI/3);
    ctx.beginPath();
    for(let i=0;i<3;i++){const a=(i/3)*Math.PI*2-Math.PI/2;i?ctx.lineTo(Math.cos(a)*triR*0.7,Math.sin(a)*triR*0.7):ctx.moveTo(Math.cos(a)*triR*0.7,Math.sin(a)*triR*0.7);}
    ctx.closePath();
    ctx.strokeStyle='rgba(0,200,230,0.38)';ctx.lineWidth=1.5;ctx.stroke();
    ctx.restore();

    // ── Energy field inside triangles ──
    const efR=triR*0.52,efA=0.28+0.12*Math.sin(t*0.08);
    const efg=ctx.createRadialGradient(cx,cy,0,cx,cy,efR);
    efg.addColorStop(0,'rgba(80,235,255,'+efA+')');
    efg.addColorStop(0.55,'rgba(0,160,200,0.07)');
    efg.addColorStop(1,'transparent');
    ctx.fillStyle=efg;ctx.beginPath();ctx.arc(cx,cy,efR,0,Math.PI*2);ctx.fill();

    // ── Center core pulse (white-hot) ──
    const pR=R*0.065+R*0.022*Math.sin(t*0.12);
    const pg=ctx.createRadialGradient(cx,cy,0,cx,cy,pR*4);
    pg.addColorStop(0,'rgba(240,255,255,1)');
    pg.addColorStop(0.1,'rgba(150,245,255,0.92)');
    pg.addColorStop(0.4,'rgba(64,207,224,0.4)');
    pg.addColorStop(1,'transparent');
    ctx.fillStyle=pg;ctx.beginPath();ctx.arc(cx,cy,pR*4,0,Math.PI*2);ctx.fill();

    // ── 3D top-left specular highlight ──
    const hlg=ctx.createRadialGradient(cx-R*0.44,cy-R*0.44,0,cx-R*0.18,cy-R*0.18,R*0.78);
    hlg.addColorStop(0,'rgba(210,250,255,0.11)');
    hlg.addColorStop(0.5,'rgba(100,220,240,0.04)');
    hlg.addColorStop(1,'transparent');
    ctx.fillStyle=hlg;ctx.beginPath();ctx.arc(cx,cy,R,0,Math.PI*2);ctx.fill();

    // ── 3 fast energy sweep arcs ──
    for(let i=0;i<3;i++){
      const bA=t*(0.027+i*0.009)+i*(Math.PI*0.65);
      const aLen=Math.PI*(0.16+0.07*Math.sin(t*0.035+i));
      ctx.beginPath();ctx.arc(cx,cy,R*(0.944-i*0.003),bA,bA+aLen);
      ctx.strokeStyle='rgba('+(125+i*35)+','+(222-i*8)+',252,'+(0.88-i*0.22)+')';
      ctx.lineWidth=4-i;
      ctx.shadowColor='#00d4ff';ctx.shadowBlur=22;ctx.stroke();ctx.shadowBlur=0;
    }

    // ── Subtle crosshair ──
    ctx.strokeStyle='rgba(13,143,160,0.1)';ctx.lineWidth=0.5;
    ctx.beginPath();ctx.moveTo(cx-R*1.45,cy);ctx.lineTo(cx+R*1.45,cy);ctx.stroke();
    ctx.beginPath();ctx.moveTo(cx,cy-R*1.45);ctx.lineTo(cx,cy+R*1.45);ctx.stroke();
  }

  frame(){
    const ctx=this.ctx,w=this.cv.width,h=this.cv.height;
    this.t++;

    // Dark background
    ctx.fillStyle='#020c14';ctx.fillRect(0,0,w,h);

    // Subtle radial bg glow
    const bg=ctx.createRadialGradient(this.cx,this.cy,0,this.cx,this.cy,Math.min(this.cx,this.cy)*0.9);
    bg.addColorStop(0,'rgba(0,30,45,0.4)');
    bg.addColorStop(1,'transparent');
    ctx.fillStyle=bg;ctx.fillRect(0,0,w,h);

    // Circuit lines with particles
    this.drawCircuits();

    // Arc reactor (on top)
    this.drawReactor();

    requestAnimationFrame(()=>this.frame());
  }
}

document.addEventListener('DOMContentLoaded',()=>{
  new ArcReactor(document.getElementById('cv'));
  fetchStatus();fetchAnalytics();fetchLog();
  setInterval(fetchStatus,30000);setInterval(fetchLog,15000);
});
</script>
</body></html>"""


if __name__ == "__main__":
    print(f"\n  ◎  JARVIS\n     http://146.190.31.63:{PORT}\n     Password: {JARVIS_PASSWORD}\n")
    app.run(host="0.0.0.0", port=PORT, debug=False)

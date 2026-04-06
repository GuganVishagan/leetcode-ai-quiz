#!/usr/bin/env python3
"""
LeetCode Daily Quiz Server
Run: python3 leetcode_server.py
Open: http://localhost:8765
"""

import json
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8765
LEETCODE_GQL = "https://leetcode.com/graphql/"
CLAUDE_API   = "https://api.anthropic.com/v1/messages"

QUIZ_SYSTEM = """You are a strict but encouraging LeetCode mock interviewer.
You ask ONE question at a time. Wait for the user's answer before asking the next one.
Be specific — reference actual variable names and code from the submission.
Keep questions concise. When the user answers, give brief feedback (1-2 lines) then ask the next question.
Never give away the answer unless the user is completely stuck (they say 'hint' or 'I don't know')."""

QUIZ_STARTERS = {
    "tc_sc": lambda title, diff, tags, lang, code: f"""Problem: "{title}" ({diff}, topics: {tags})
Code ({lang}):
```
{code}
```
Start the TC/SC quiz. Ask ONLY about time complexity first — one specific question referencing the actual loops/structures in the code. Do not ask about space yet.""",

    "code_block": lambda title, diff, tags, lang, code: f"""Problem: "{title}" ({diff}, topics: {tags})
Code ({lang}):
```
{code}
```
Pick the SINGLE most interesting or non-obvious block/snippet from this code (2-5 lines). Quote it exactly, then ask ONE question: why did the author write it this specific way? What would break if it were removed or changed?""",

    "concept": lambda title, diff, tags, lang, code: f"""Problem: "{title}" ({diff}, topics: {tags})
Code ({lang}):
```
{code}
```
Identify the core DSA concept/pattern used (e.g. Kadane's, sliding window, two pointers, etc.). In 2 sentences, name the pattern and what makes it applicable here. Then ask ONE question to test if the user truly understands WHY this pattern fits this problem.""",

    "bug_hunt": lambda title, diff, tags, lang, code: f"""Problem: "{title}" ({diff}, topics: {tags})
Original working code ({lang}):
```
{code}
```
Introduce ONE subtle bug into the code (off-by-one, wrong comparison, missing edge case, etc.). Show the buggy version and ask the user to find the bug. Do NOT reveal what the bug is yet.""",

    "blind_code": lambda title, diff, tags, lang, code: f"""Problem: "{title}" ({diff}, topics: {tags}, language: {lang})
The user previously solved this. Now test if they truly understand it.
Do NOT show any code. Ask them to describe their approach from scratch in plain English first — what data structure, what algorithm, what's the main insight? One question only.""",

    "pattern_match": lambda title, diff, tags, lang, code: f"""Problem: "{title}" ({diff}, topics: {tags})
Code ({lang}):
```
{code}
```
Give a NEW problem (different from this one) that uses the same core pattern. Describe it in 2-3 sentences. Ask: which pattern does this new problem use, and how would you adapt your current solution to solve it?""",

    "interview_sim": lambda title, diff, tags, lang, code: f"""Problem: "{title}" ({diff}, topics: {tags})
Code ({lang}):
```
{code}
```
You are a FAANG interviewer. Start a realistic mock interview. Begin with a warm-up question about this problem as if you just watched the user code it live. Be conversational. One question only to start.""",

    "complexity_compare": lambda title, diff, tags, lang, code: f"""Problem: "{title}" ({diff}, topics: {tags})
Code ({lang}):
```
{code}
```
Propose ONE alternative approach to solve this problem (different algorithm or data structure). Describe it briefly (2 sentences). Then ask: compare your submitted solution vs this alternative — which is better and why?""",
}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.cors()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200); self.cors(); self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/index.html"): self.serve_html()
        else: self.send_response(404); self.end_headers()

    def do_POST(self):
        if   self.path == "/graphql": self.proxy_lc()
        elif self.path == "/chat":    self.handle_chat()
        else: self.send_response(404); self.end_headers()

    def read_body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n))

    def proxy_lc(self):
        try:
            d = self.read_body()
            payload = json.dumps({"query": d["query"], "variables": d.get("variables", {})}).encode()
            req = urllib.request.Request(LEETCODE_GQL, data=payload, method="POST", headers={
                "Content-Type": "application/json",
                "Cookie": f"LEETCODE_SESSION={d['session']}; csrftoken={d['csrf']}",
                "x-csrftoken": d["csrf"], "Referer": "https://leetcode.com", "User-Agent": "Mozilla/5.0",
            })
            with urllib.request.urlopen(req, timeout=20) as r:
                self.send_json(json.loads(r.read()))
        except urllib.error.HTTPError as e:
            self.send_json({"error": f"LeetCode HTTP {e.code}: {e.read().decode()}"}, 500)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def handle_chat(self):
        try:
            d = self.read_body()
            api_key  = d.get("api_key", "").strip()
            messages = d.get("messages", [])
            qtype    = d.get("qtype", "tc_sc")
            prob     = d.get("prob", {})

            if not api_key:
                self.send_json({"error": "No API key."}, 400); return

            # If this is the first message (start of quiz), build the starter prompt
            if not messages:
                starter_fn = QUIZ_STARTERS.get(qtype, QUIZ_STARTERS["tc_sc"])
                starter = starter_fn(
                    prob.get("title",""), prob.get("diff",""), prob.get("tags",""),
                    prob.get("lang",""), prob.get("code","")
                )
                messages = [{"role": "user", "content": starter}]

            payload = json.dumps({
                "model": "claude-opus-4-5",
                "max_tokens": 512,
                "system": QUIZ_SYSTEM,
                "messages": messages
            }).encode()

            req = urllib.request.Request(CLAUDE_API, data=payload, method="POST", headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            })
            with urllib.request.urlopen(req, timeout=30) as r:
                result = json.loads(r.read())
                text = next((b["text"] for b in result.get("content", []) if b["type"] == "text"), "")
                self.send_json({"text": text})

        except urllib.error.HTTPError as e:
            self.send_json({"error": f"Claude HTTP {e.code}: {e.read().decode()}"}, 500)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def serve_html(self):
        html = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>LeetCode Daily Quiz</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#fff;--bg2:#f7f7f7;--bg3:#eee;--text:#111;--text2:#555;--text3:#999;--border:#e2e2e2;--accent:#f89f1b;--r:10px}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg2);color:var(--text);min-height:100vh}
header{background:var(--bg);border-bottom:1px solid var(--border);padding:14px 24px;display:flex;align-items:center;justify-content:space-between}
header h1{font-size:17px;font-weight:600;display:flex;align-items:center;gap:8px}
.wrap{max-width:860px;margin:0 auto;padding:24px 16px}
/* login */
#login{max-width:520px;margin:40px auto;background:var(--bg);border:1px solid var(--border);border-radius:var(--r);padding:32px}
#login h2{font-size:19px;font-weight:600;margin-bottom:6px}
#login p{font-size:13px;color:var(--text2);margin-bottom:16px;line-height:1.6}
.tip{background:#fffbf0;border:1px solid #fde9a2;border-radius:8px;padding:11px 14px;margin-bottom:16px;font-size:12.5px;color:#7a5c00;line-height:1.8}
.field{margin-bottom:12px}
.field label{display:block;font-size:13px;font-weight:500;margin-bottom:5px;color:var(--text2)}
.field input{width:100%;padding:9px 12px;border:1px solid var(--border);border-radius:8px;font-size:13.5px;background:var(--bg);color:var(--text)}
.field input:focus{outline:2px solid var(--accent);border-color:transparent}
.sep{border:none;border-top:1px solid var(--border);margin:16px 0}
.go{display:flex;align-items:center;justify-content:center;width:100%;padding:11px;border-radius:8px;border:none;font-size:14px;font-weight:600;cursor:pointer;background:var(--accent);color:#fff;margin-top:4px}
.go:disabled{opacity:.5;cursor:not-allowed}
.errmsg{background:#fff0f0;border:1px solid #fca5a5;color:#b91c1c;border-radius:8px;padding:10px 14px;font-size:13px;margin-top:10px;display:none}
.foot{font-size:12px;color:var(--text3);margin-top:14px;padding-top:14px;border-top:1px solid var(--border);line-height:1.6}
/* app layout */
#app{display:none}
.topbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;flex-wrap:wrap;gap:10px}
.uinfo{display:flex;align-items:center;gap:10px}
.av{width:34px;height:34px;border-radius:50%;background:var(--accent);color:#fff;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700}
.uname{font-size:15px;font-weight:600}
.ctrls{display:flex;gap:8px}
select{padding:7px 12px;border:1px solid var(--border);border-radius:8px;font-size:13.5px;background:var(--bg);color:var(--text);cursor:pointer}
.sm{padding:7px 14px;font-size:13px;background:var(--bg3);color:var(--text);border:1px solid var(--border);border-radius:7px;cursor:pointer}
.sm:hover{background:var(--border)}
.slabel{font-size:12px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px}
/* problem cards */
.pcard{background:var(--bg);border:1px solid var(--border);border-radius:var(--r);padding:13px 16px;margin-bottom:8px;cursor:pointer;display:flex;align-items:center;justify-content:space-between;gap:12px;transition:border-color .12s}
.pcard:hover{border-color:var(--accent)}
.pcard.on{border-color:var(--accent);background:#fffcf5}
.pname{font-size:14px;font-weight:500}
.psub{font-size:12px;color:var(--text3);margin-top:3px}
.badge{font-size:11px;padding:2px 9px;border-radius:99px;font-weight:600;white-space:nowrap;background:var(--bg3);color:var(--text3)}
.Easy{background:#dcfce7;color:#166534}
.Medium{background:#fef3c7;color:#92400e}
.Hard{background:#fee2e2;color:#991b1b}
.empty{text-align:center;padding:40px;color:var(--text3);font-size:14px;line-height:1.9}
.ls{text-align:center;padding:40px;color:var(--text3);font-size:14px}
/* quiz panel */
#qpanel{background:var(--bg);border:1px solid var(--border);border-radius:var(--r);padding:20px;margin-top:16px;display:none}
.qheader{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:12px}
.qtitle{font-size:16px;font-weight:600}
.qmeta{font-size:12px;color:var(--text3);margin-top:2px}
/* quiz type selector */
.qtype-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:7px;margin-bottom:16px}
.qtype-btn{padding:8px 10px;border-radius:8px;border:1px solid var(--border);background:var(--bg2);font-size:12.5px;cursor:pointer;color:var(--text2);text-align:center;line-height:1.3;transition:all .12s}
.qtype-btn:hover{border-color:var(--accent);color:var(--text)}
.qtype-btn.on{background:var(--accent);color:#fff;border-color:var(--accent);font-weight:500}
.qtype-name{font-weight:500;font-size:12px}
.qtype-desc{font-size:10.5px;opacity:.8;margin-top:2px}
/* code preview */
.code-toggle{font-size:12px;color:var(--accent);cursor:pointer;margin-bottom:10px;display:inline-block}
.codebox{background:#1a1b26;color:#c0caf5;border-radius:8px;padding:14px;font-family:monospace;font-size:12.5px;line-height:1.65;overflow:auto;max-height:200px;margin-bottom:14px;display:none;white-space:pre}
/* chat */
.chat-area{display:none;flex-direction:column;gap:12px;margin-bottom:14px;max-height:420px;overflow-y:auto;padding:4px 2px}
.bubble{padding:12px 14px;border-radius:10px;font-size:13.5px;line-height:1.75;max-width:100%;white-space:pre-wrap}
.bubble.ai{background:#f0f4ff;color:#1a1a3e;border-bottom-left-radius:3px}
.bubble.user{background:var(--accent);color:#fff;border-bottom-right-radius:3px;align-self:flex-end;max-width:85%}
.bubble.ai code{background:#d8dfff;padding:1px 5px;border-radius:4px;font-family:monospace;font-size:12px}
/* answer input */
.answer-row{display:flex;gap:8px;align-items:flex-end;margin-bottom:8px}
.answer-box{flex:1;padding:10px 12px;border:1px solid var(--border);border-radius:8px;font-size:13.5px;font-family:inherit;resize:none;min-height:42px;max-height:120px;background:var(--bg);color:var(--text);line-height:1.5}
.answer-box:focus{outline:2px solid var(--accent);border-color:transparent}
.send-btn{padding:10px 16px;border-radius:8px;border:none;background:var(--accent);color:#fff;font-size:14px;font-weight:600;cursor:pointer;white-space:nowrap;height:42px}
.send-btn:disabled{opacity:.5;cursor:not-allowed}
.voice-btn{width:42px;height:42px;border-radius:8px;border:1px solid var(--border);background:var(--bg3);cursor:pointer;font-size:18px;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.voice-btn.recording{background:#fee2e2;border-color:#fca5a5;animation:pulse 1s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.6}}
.quiz-footer{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.start-btn{padding:9px 20px;border-radius:8px;border:none;font-size:14px;font-weight:600;cursor:pointer;background:var(--accent);color:#fff}
.start-btn:disabled{opacity:.5;cursor:not-allowed}
/* speak toggle */
.speak-toggle{display:flex;align-items:center;gap:6px;font-size:12.5px;color:var(--text2);cursor:pointer;user-select:none}
.speak-toggle input{cursor:pointer}
/* spinner */
.spin{width:13px;height:13px;border:2px solid rgba(0,0,0,.15);border-top-color:var(--text2);border-radius:50%;animation:sp .7s linear infinite;display:inline-block;vertical-align:middle}
@keyframes sp{to{transform:rotate(360deg)}}
</style>
</head>
<body>
<header>
  <h1>⚡ LeetCode Daily Quiz</h1>
</header>
<div class="wrap">

<!-- LOGIN -->
<div id="login">
  <h2>Connect LeetCode</h2>
  <p>Enter your credentials to fetch real submissions and get quizzed on your actual code.</p>
  <div class="tip">
    <strong>Get cookies (30 sec):</strong><br>
    1. Open leetcode.com while logged in &nbsp;2. F12 → Application → Cookies → leetcode.com<br>
    3. Copy <strong>LEETCODE_SESSION</strong> and <strong>csrftoken</strong>
  </div>
  <div class="field"><label>LeetCode Username</label><input id="i-user" placeholder="e.g. GuganVishagan"/></div>
  <div class="field"><label>LEETCODE_SESSION</label><input id="i-sess" type="password" placeholder="eyJhbGci..."/></div>
  <div class="field"><label>csrftoken</label><input id="i-csrf" placeholder="62KYe4c..."/></div>
  <hr class="sep"/>
  <div class="field">
    <label>Anthropic API Key <span style="font-weight:400;color:var(--text3)">(for quiz generation — sk-ant-...)</span></label>
    <input id="i-key" type="password" placeholder="sk-ant-api03-..."/>
  </div>
  <button class="go" onclick="login()">Fetch my submissions →</button>
  <div class="errmsg" id="errmsg"></div>
  <div class="foot">🔒 Everything runs locally. Credentials never leave your machine.</div>
</div>

<!-- APP -->
<div id="app">
  <div class="topbar">
    <div class="uinfo"><div class="av" id="av"></div><span class="uname" id="uname"></span></div>
    <div class="ctrls">
      <select id="period" onchange="loadSubs()">
        <option value="1">Today</option>
        <option value="3" selected>Last 3 days</option>
        <option value="7">Last 7 days</option>
        <option value="30">Last 30 days</option>
      </select>
      <button class="sm" onclick="logout()">Log out</button>
    </div>
  </div>
  <div class="slabel" id="slabel">Submissions</div>
  <div id="plist"><div class="ls">Loading...</div></div>

  <!-- QUIZ PANEL -->
  <div id="qpanel">
    <div class="qheader">
      <div>
        <div class="qtitle" id="qtitle"></div>
        <div class="qmeta" id="qmeta"></div>
      </div>
      <label class="speak-toggle" title="Read Claude's responses aloud">
        <input type="checkbox" id="speak-toggle" checked/> 🔊 Voice
      </label>
    </div>

    <span class="code-toggle" onclick="toggleCode()" id="codetoggle">▶ Show my submitted code</span>
    <div class="codebox" id="codebox"></div>

    <!-- Quiz type grid -->
    <div class="qtype-grid" id="qtype-grid">
      <div class="qtype-btn on" data-t="tc_sc" onclick="pickType(this)">
        <div class="qtype-name">⏱ TC / SC</div>
        <div class="qtype-desc">Time & space complexity</div>
      </div>
      <div class="qtype-btn" data-t="code_block" onclick="pickType(this)">
        <div class="qtype-name">🔍 Code Block</div>
        <div class="qtype-desc">Why this specific snippet?</div>
      </div>
      <div class="qtype-btn" data-t="concept" onclick="pickType(this)">
        <div class="qtype-name">💡 Core Concept</div>
        <div class="qtype-desc">Pattern & theory deep dive</div>
      </div>
      <div class="qtype-btn" data-t="bug_hunt" onclick="pickType(this)">
        <div class="qtype-name">🐛 Bug Hunt</div>
        <div class="qtype-desc">Find the introduced bug</div>
      </div>
      <div class="qtype-btn" data-t="blind_code" onclick="pickType(this)">
        <div class="qtype-name">🙈 Blind Recall</div>
        <div class="qtype-desc">Explain from scratch</div>
      </div>
      <div class="qtype-btn" data-t="pattern_match" onclick="pickType(this)">
        <div class="qtype-name">🧩 Pattern Match</div>
        <div class="qtype-desc">Apply pattern to new problem</div>
      </div>
      <div class="qtype-btn" data-t="interview_sim" onclick="pickType(this)">
        <div class="qtype-name">🎤 Mock Interview</div>
        <div class="qtype-desc">FAANG-style simulation</div>
      </div>
      <div class="qtype-btn" data-t="complexity_compare" onclick="pickType(this)">
        <div class="qtype-name">⚖️ Compare Approaches</div>
        <div class="qtype-desc">Your solution vs alternative</div>
      </div>
    </div>

    <!-- Chat -->
    <div class="chat-area" id="chat-area"></div>

    <!-- Answer input (hidden until quiz starts) -->
    <div id="answer-row" class="answer-row" style="display:none">
      <textarea class="answer-box" id="answer-box" placeholder="Type your answer... (Enter to send, Shift+Enter for newline)" rows="1"
        oninput="autoResize(this)" onkeydown="handleKey(event)"></textarea>
      <button class="voice-btn" id="voice-btn" onclick="toggleVoice()" title="Speak your answer">🎤</button>
      <button class="send-btn" id="send-btn" onclick="sendAnswer()">Send →</button>
    </div>

    <div class="quiz-footer">
      <button class="start-btn" id="start-btn" onclick="startQuiz()">Start quiz →</button>
      <button class="sm" id="reset-btn" onclick="resetQuiz()" style="display:none">↺ New quiz</button>
    </div>
  </div>
</div>

</div><!-- /wrap -->
<script>
const $ = id => document.getElementById(id);
const API = 'http://localhost:8765';
let S = {user:'',sess:'',csrf:'',key:'',subs:[],sel:null,qtype:'tc_sc',messages:[],speaking:false};
let recognition = null;
let synth = window.speechSynthesis;

// ── Auth ─────────────────────────────────────────────────────────────────────
function login(){
  const user=$('i-user').value.trim(),sess=$('i-sess').value.trim(),
        csrf=$('i-csrf').value.trim(),key=$('i-key').value.trim();
  if(!user||!sess||!csrf||!key){showErr('Please fill in all four fields.');return;}
  S.user=user;S.sess=sess;S.csrf=csrf;S.key=key;
  $('av').textContent=user[0].toUpperCase();$('uname').textContent=user;
  $('login').style.display='none';$('app').style.display='block';
  loadSubs();
}
function logout(){
  S={user:'',sess:'',csrf:'',key:'',subs:[],sel:null,qtype:'tc_sc',messages:[],speaking:false};
  $('login').style.display='block';$('app').style.display='none';
  $('qpanel').style.display='none';$('i-sess').value='';$('i-csrf').value='';$('i-key').value='';
}
function showErr(m){const e=$('errmsg');e.textContent=m;e.style.display='block';}

// ── LeetCode API ──────────────────────────────────────────────────────────────
async function lcGql(query,variables){
  const r=await fetch(API+'/graphql',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({query,variables,session:S.sess,csrf:S.csrf})});
  const j=await r.json();
  if(j.error)throw new Error(j.error);
  if(j.errors)throw new Error(j.errors[0]?.message);
  return j;
}

async function loadSubs(){
  const days=parseInt($('period').value);
  const lbl={1:'Today',3:'Last 3 days',7:'Last 7 days',30:'Last 30 days'};
  $('slabel').textContent=lbl[days];
  $('plist').innerHTML='<div class="ls">Fetching submissions...</div>';
  $('qpanel').style.display='none';
  try{
    const data=await lcGql(`query recentAcSubmissions($username:String!,$limit:Int!){
      recentAcSubmissionList(username:$username,limit:$limit){id titleSlug title timestamp lang}
    }`,{username:S.user,limit:50});
    const all=data?.data?.recentAcSubmissionList||[];
    const cut=Math.floor(Date.now()/1000)-days*86400;
    const seen=new Set();
    S.subs=all.filter(s=>parseInt(s.timestamp)>=cut&&!seen.has(s.titleSlug)&&seen.add(s.titleSlug));
    renderList();
  }catch(e){
    $('plist').innerHTML=`<div class="empty">❌ ${e.message}<br><small>Check cookies and make sure the server is running.</small></div>`;
  }
}

function renderList(){
  if(!S.subs.length){$('plist').innerHTML='<div class="empty">No accepted submissions in this period.</div>';return;}
  $('plist').innerHTML=S.subs.map((s,i)=>`
    <div class="pcard" id="pc${i}" onclick="selProb(${i})">
      <div><div class="pname">${s.title}</div>
      <div class="psub">${new Date(parseInt(s.timestamp)*1000).toLocaleDateString('en-IN',{day:'numeric',month:'short'})} · ${s.lang}</div></div>
      <span class="badge" id="b${i}">–</span>
    </div>`).join('');
}

async function selProb(i){
  document.querySelectorAll('.pcard').forEach(c=>c.classList.remove('on'));
  $('pc'+i).classList.add('on');
  S.sel={...S.subs[i]};
  resetQuiz();
  $('qpanel').style.display='block';
  $('qtitle').textContent=S.sel.title;
  $('qmeta').textContent='Fetching your code...';
  $('codebox').style.display='none';$('codetoggle').textContent='▶ Show my submitted code';
  $('qpanel').scrollIntoView({behavior:'smooth',block:'nearest'});
  try{
    const data=await lcGql(`query submissionDetails($submissionId:Int!){
      submissionDetails(submissionId:$submissionId){
        code runtimeDisplay memoryDisplay question{difficulty topicTags{name}}
      }
    }`,{submissionId:parseInt(S.sel.id)});
    const d=data?.data?.submissionDetails;
    if(d){
      S.sel.code=d.code||'';S.sel.diff=d.question?.difficulty||'';
      S.sel.tags=d.question?.topicTags?.map(t=>t.name).join(', ')||'';
      S.sel.rt=d.runtimeDisplay||'';S.sel.mem=d.memoryDisplay||'';
      $('codebox').textContent=d.code||'';
      $('qmeta').textContent=[S.sel.diff,S.sel.tags,S.sel.rt&&`Runtime: ${S.sel.rt}`,S.sel.mem&&`Memory: ${S.sel.mem}`].filter(Boolean).join(' · ');
      const b=$('b'+i);if(b){b.textContent=S.sel.diff||S.sel.lang;b.className='badge '+S.sel.diff;}
    }
  }catch(e){$('qmeta').textContent=`${S.sel.lang} · (code fetch failed — quiz still works)`;}
}

function toggleCode(){
  const box=$('codebox'),tog=$('codetoggle');
  const vis=box.style.display==='block';
  box.style.display=vis?'none':'block';
  tog.textContent=vis?'▶ Show my submitted code':'▼ Hide submitted code';
}

function pickType(el){
  document.querySelectorAll('.qtype-btn').forEach(b=>b.classList.remove('on'));
  el.classList.add('on');S.qtype=el.dataset.t;
  resetQuiz();
}

function resetQuiz(){
  S.messages=[];
  $('chat-area').innerHTML='';$('chat-area').style.display='none';
  $('answer-row').style.display='none';$('answer-box').value='';
  $('start-btn').style.display='inline-flex';$('reset-btn').style.display='none';
  $('start-btn').disabled=false;$('start-btn').textContent='Start quiz →';
  if(synth)synth.cancel();
}

// ── Quiz / Chat ───────────────────────────────────────────────────────────────
async function startQuiz(){
  if(!S.sel)return;
  $('start-btn').disabled=true;$('start-btn').innerHTML='<span class="spin"></span> Starting...';
  $('chat-area').style.display='flex';$('chat-area').innerHTML='';
  S.messages=[];
  await sendToClaude(null); // null = trigger starter prompt
  $('start-btn').style.display='none';$('reset-btn').style.display='inline-block';
  $('answer-row').style.display='flex';$('answer-box').focus();
}

async function sendAnswer(){
  const text=$('answer-box').value.trim();
  if(!text)return;
  $('answer-box').value='';autoResize($('answer-box'));
  appendBubble(text,'user');
  S.messages.push({role:'user',content:text});
  await sendToCloud();
}

async function sendToCloud(){
  $('send-btn').disabled=true;
  const typing=appendBubble('…','ai');
  try{
    const r=await fetch(API+'/chat',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        api_key:S.key,qtype:S.qtype,messages:S.messages,
        prob:{title:S.sel.title,diff:S.sel.diff||'',tags:S.sel.tags||'',
              lang:S.sel.lang,code:S.sel.code||'',rt:S.sel.rt||'',mem:S.sel.mem||''}
      })
    });
    const j=await r.json();
    if(j.error)throw new Error(j.error);
    typing.remove();
    const aiText=j.text;
    appendBubble(aiText,'ai');
    S.messages.push({role:'assistant',content:aiText});
    if($('speak-toggle').checked)speak(aiText);
  }catch(e){
    typing.textContent='Error: '+e.message;
  }
  $('send-btn').disabled=false;
}

async function sendToCloud_starter(){
  const typing=appendBubble('…','ai');
  $('start-btn').disabled=true;
  try{
    const r=await fetch(API+'/chat',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        api_key:S.key,qtype:S.qtype,messages:[],
        prob:{title:S.sel.title,diff:S.sel.diff||'',tags:S.sel.tags||'',
              lang:S.sel.lang,code:S.sel.code||'',rt:S.sel.rt||'',mem:S.sel.mem||''}
      })
    });
    const j=await r.json();
    if(j.error)throw new Error(j.error);
    typing.remove();
    appendBubble(j.text,'ai');
    S.messages.push({role:'assistant',content:j.text});
    if($('speak-toggle').checked)speak(j.text);
  }catch(e){
    typing.textContent='Error: '+e.message;
  }
}

// unified starter
async function sendToClaudeUnified(userText){
  if(userText){
    // continuation
    await sendToCloud();
  } else {
    // first message
    await sendToCloud_starter();
  }
}

// fix startQuiz to use right fn
async function startQuiz(){
  if(!S.sel)return;
  $('start-btn').disabled=true;$('start-btn').innerHTML='<span class="spin"></span> Starting...';
  $('chat-area').style.display='flex';$('chat-area').innerHTML='';
  S.messages=[];
  await sendToCloud_starter();
  $('start-btn').style.display='none';$('reset-btn').style.display='inline-block';
  $('answer-row').style.display='flex';$('answer-box').focus();
}

function appendBubble(text,who){
  const div=document.createElement('div');
  div.className='bubble '+who;
  div.textContent=text;
  $('chat-area').appendChild(div);
  $('chat-area').scrollTop=$('chat-area').scrollHeight;
  return div;
}

// ── Voice ─────────────────────────────────────────────────────────────────────
function speak(text){
  if(!synth)return;
  synth.cancel();
  const clean=text.replace(/```[\s\S]*?```/g,'[code block]').replace(/`[^`]+`/g,'').replace(/[*_#]/g,'');
  const utt=new SpeechSynthesisUtterance(clean);
  utt.rate=1.05;utt.pitch=1;
  synth.speak(utt);
}

function toggleVoice(){
  const btn=$('voice-btn');
  if(!recognition){
    const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
    if(!SpeechRecognition){alert('Speech recognition not supported in this browser. Use Chrome.');return;}
    recognition=new SpeechRecognition();
    recognition.continuous=false;recognition.interimResults=false;recognition.lang='en-US';
    recognition.onresult=e=>{
      const t=e.results[0][0].transcript;
      $('answer-box').value=($('answer-box').value+' '+t).trim();
      autoResize($('answer-box'));
      btn.classList.remove('recording');btn.textContent='🎤';
    };
    recognition.onerror=()=>{btn.classList.remove('recording');btn.textContent='🎤';};
    recognition.onend=()=>{btn.classList.remove('recording');btn.textContent='🎤';};
  }
  if(btn.classList.contains('recording')){
    recognition.stop();btn.classList.remove('recording');btn.textContent='🎤';
  }else{
    recognition.start();btn.classList.add('recording');btn.textContent='🔴';
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function handleKey(e){
  if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendAnswer();}
}
function autoResize(el){el.style.height='auto';el.style.height=Math.min(el.scrollHeight,120)+'px';}
</script>
</body>
</html>"""
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.cors()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = HTTPServer(("localhost", PORT), Handler)
    print(f"\n  ⚡  LeetCode Daily Quiz is running!")
    print(f"  👉  Open in Chrome: http://localhost:{PORT}\n")
    print("  Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("  Stopped.")

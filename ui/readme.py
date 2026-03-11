"""
Knowledge Guide – Saddle AdPulse
Confluence/Jira-style knowledge base rendered as a custom HTML component.
"""

import streamlit as st
import streamlit.components.v1 as components


# ─────────────────────────────────────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────────────────────────────────────

_TUTORIALS = [
    {
        "id": "connect-seller",
        "title": "How to Connect Your Seller Account to Saddl AdPulse",
        "subtitle": "Set up Seller Central access and pull 90-day historical data",
        "badge": "Setup",
        "loom_id": "9758ae484df94157a05ee7de5551e4c2",
        "duration": "4:23",
        "steps": [
            {
                "num": 1, "heading": "Log In to Your Account", "t": 2,
                "img": "https://loom.com/i/37594834a86c43bcb468261ec1ee6cb4?workflows_screenshot=true",
                "notes": ["Go to the login screen.", "Enter your credentials to access your account."],
            },
            {
                "num": 2, "heading": "Overview of the Home Screen", "t": 21,
                "img": "https://loom.com/i/06f8bf3187e147e1a74dfb60c8313e33?workflows_screenshot=true",
                "notes": [
                    "After logging in, you will see the home screen.",
                    "This screen shows your account health score (good, bad, or needs improvement) and key features: Analytics, Optimizer, Impact Results.",
                ],
            },
            {
                "num": 3, "heading": "Access Data Setup", "t": 65,
                "img": "https://loom.com/i/dc5b512f5ae8477fa45b49a953b2773b?workflows_screenshot=true",
                "notes": ["Click on the 'Data Setup' tab.", "You will see two options: Connect your ad account, Connect your Seller Central account."],
            },
            {
                "num": 4, "heading": "Connect Your Seller Central Account", "t": 77,
                "img": "https://loom.com/i/a0584d534f1a4008bff7a01c738a3d87?workflows_screenshot=true",
                "notes": [
                    "Connecting your Seller Central account is crucial for understanding how ads and PPC influence your business metrics.",
                    "First-time users: click 'Connect'. Already connected: click 'Reconnect'.",
                ],
            },
            {
                "num": 5, "heading": "Authorize Connection", "t": 107,
                "img": "https://loom.com/i/5549a3b0905c4614bd5b8c1041822a3e?workflows_screenshot=true",
                "notes": ["After clicking 'Connect', a new screen will load.", "Log in using your Seller Central credentials.", "Select the specific account or marketplace you want to connect."],
            },
            {
                "num": 6, "heading": "Confirm Authorization", "t": 183,
                "img": "https://loom.com/i/0c2d1dadc1b447d5bce3faa49bc93a60?workflows_screenshot=true",
                "notes": ["After selecting your account, you will be prompted to authorize the connection.", "Click 'Confirm' to authorize and redirect back to the main page."],
            },
            {
                "num": 7, "heading": "Verify Connection Status", "t": 192,
                "img": "https://loom.com/i/2a1bc522d41c4d6d871664db29f0560c?workflows_screenshot=true",
                "notes": ["Check that the connection status shows as 'Active'.", "The system will automatically pull historical data from the past 90 days."],
            },
            {
                "num": 8, "heading": "Prepare for Ad Account Connection", "t": 220,
                "img": "https://loom.com/i/cd17265bd4f34ab4aeff85ef85a0f592?workflows_screenshot=true",
                "notes": ["The API for ads is currently being applied for.", "Once available, connecting your ad account works the same way as Seller Central."],
            },
            {
                "num": 9, "heading": "Upload Necessary Reports", "t": 249,
                "img": "https://loom.com/i/4c75ba71f8784577bb4343faff1fda6b?workflows_screenshot=true",
                "notes": ["You will need to add: Search term report, Bulk ID map for your ads, Advertised product report for creating new campaigns, Any internal mapping for your product catalog."],
            },
            {
                "num": 10, "heading": "Focus on Key Reports", "t": 267,
                "img": None,
                "notes": ["The two most important reports are: Search term report, Bulk ID map."],
            },
        ],
    },
    # ── Add more tutorials below ─────────────────────────────────────────────
    # {
    #     "id": "run-optimizer",
    #     "title": "How to Run the Optimizer",
    #     "subtitle": "Upload data, review bids, and export",
    #     "badge": "Optimizer",
    #     "loom_id": "REPLACE_ME",
    #     "duration": "",
    #     "steps": [],
    # },
]

_GUIDES = [
    {
        "id": "guide-getting-started",
        "title": "Getting Started",
        "badge": "Guide",
        "body": """
<p>Follow these three steps to get up and running:</p>
<h3>Step 1: Upload Your Data</h3>
<ul>
  <li>Go to <strong>Data Hub</strong> → Upload your Search Term Report</li>
  <li>Optional: Add Bulk File for campaign IDs, Advertised Products for SKU mapping</li>
</ul>
<h3>Step 2: Run the Optimizer</h3>
<ul>
  <li>Click <strong>Run Optimizer</strong> → Review the recommendations</li>
  <li>Approve bids, harvests, and negatives</li>
</ul>
<h3>Step 3: Export &amp; Apply</h3>
<ul>
  <li>Download the bulk file → Upload to Amazon/Noon Ads Console</li>
</ul>
""",
    },
    {
        "id": "guide-bleeders",
        "title": "Finding Wasted Spend (Bleeders)",
        "badge": "Guide",
        "body": """
<p>Bleeders are search terms consuming your budget with zero returns.</p>
<h3>Where to Find Them</h3>
<ul>
  <li><strong>Optimizer → Negatives Tab</strong> — shows all zero-order terms</li>
  <li><strong>AI Strategist</strong> — ask "Where am I losing money?"</li>
</ul>
<h3>What to Do</h3>
<ol>
  <li>Review the negative recommendations</li>
  <li>Add them as Negative Exact in your campaigns</li>
  <li>Re-run monthly to catch new bleeders</li>
</ol>
""",
    },
    {
        "id": "guide-harvesting",
        "title": "Harvesting Winning Keywords",
        "badge": "Guide",
        "body": """
<p>Harvesting moves winning search terms to Exact Match campaigns for tighter control.</p>
<h3>Why Harvest?</h3>
<ul>
  <li>Lock in high-performing terms</li>
  <li>Set specific bids instead of Auto/Broad defaults</li>
  <li>Improve tracking and attribution</li>
</ul>
<h3>Process</h3>
<ol>
  <li><strong>Optimizer → Harvest Tab</strong> — see qualified terms</li>
  <li>Click <strong>Open Campaign Creator</strong></li>
  <li>Generate bulk file with new Exact campaigns</li>
  <li>Upload to Ads Console</li>
</ol>
""",
    },
    {
        "id": "guide-bids",
        "title": "Understanding Bid Recommendations",
        "badge": "Guide",
        "body": """
<p>The optimizer calculates bids based on performance vs your account baseline.</p>
<h3>Bid Goes UP when:</h3>
<ul>
  <li>Term ROAS &gt; Account Median ROAS</li>
  <li>High conversion rate</li>
  <li>Strong sales velocity</li>
</ul>
<h3>Bid Goes DOWN when:</h3>
<ul>
  <li>Term ROAS &lt; Account Median ROAS</li>
  <li>Low or no conversions</li>
  <li>Spending without returns</li>
</ul>
<p><strong>Tip:</strong> Use the Simulation tab to preview impact before applying.</p>
""",
    },
    {
        "id": "guide-ai",
        "title": "Working with the AI Strategist",
        "badge": "Guide",
        "body": """
<p>The AI knows your data. Ask strategic questions — not just data lookups.</p>
<h3>Access</h3>
<p>Click the 💬 <strong>Chat Bubble</strong> in the bottom-right corner, or use <strong>"Ask Zenny"</strong> in the sidebar.</p>
<h3>Good Questions to Ask</h3>
<ul>
  <li>"Why is my ACOS increasing this month?"</li>
  <li>"What are my biggest opportunities right now?"</li>
  <li>"Which campaigns should I pause?"</li>
  <li>"Help me build a Q1 strategy"</li>
</ul>
<h3>It Already Knows</h3>
<ul>
  <li>Your bleeders and winners</li>
  <li>Campaign performance trends</li>
  <li>Optimization opportunities</li>
  <li>Historical patterns</li>
</ul>
""",
    },
]

_MATH: list = []
_FAQ: list = []


# ─────────────────────────────────────────────────────────────────────────────
# HTML BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def _steps_html(steps, loom_id):
    share_url = f"https://loom.com/share/{loom_id}"
    parts = []
    for s in steps:
        mins, secs = divmod(s["t"], 60)
        ts_label = f"{mins}:{secs:02d}"
        ts_link = f"{share_url}?t={s['t']}"
        img_tag = (
            f'<img src="{s["img"]}" alt="Step {s["num"]}" '
            f'onerror="this.style.display=\'none\'">'
            if s.get("img") else ""
        )
        notes = "".join(f"<li>{n}</li>" for n in s["notes"])
        parts.append(f"""
        <div class="step-card">
          <div class="step-header">
            <div class="step-num">{s["num"]}</div>
            <div class="step-heading">{s["heading"]}</div>
            <a href="{ts_link}" target="_blank" class="step-ts">▶ {ts_label}</a>
          </div>
          <div class="step-body">
            {img_tag}
            <ul class="step-notes">{notes}</ul>
          </div>
        </div>""")
    return "\n".join(parts)


def _article_html(article_id, title, badge, body_html, extra_header=""):
    return f"""
    <div class="article" id="art-{article_id}" style="display:none">
      <div class="breadcrumb">Knowledge Base &rsaquo; {title}</div>
      <div class="art-header">
        <h1 class="art-title">{title}</h1>
        {extra_header}
        <div class="art-meta">
          <span class="badge badge-{badge.lower()}">{badge}</span>
        </div>
      </div>
      <div class="art-body">{body_html}</div>
    </div>"""


def _tutorial_html(t):
    loom_id = t["loom_id"]
    extra = f"""
      <div class="art-meta-row">
        <span class="badge badge-setup">{t['badge']}</span>
        <span class="meta-pill">⏱ {t['duration']}</span>
        <span class="meta-pill">📋 {len(t['steps'])} steps</span>
        <a href="https://loom.com/share/{loom_id}" target="_blank" class="meta-pill meta-link">↗ Watch on Loom</a>
      </div>"""
    body = f"""
      <div class="video-wrap">
        <iframe src="https://www.loom.com/embed/{loom_id}"
          frameborder="0" webkitallowfullscreen mozallowfullscreen allowfullscreen
          style="position:absolute;top:0;left:0;width:100%;height:100%;"></iframe>
      </div>
      <div class="section-label">STEP-BY-STEP GUIDE</div>
      <div class="steps-list">
        {_steps_html(t['steps'], loom_id)}
      </div>"""
    return f"""
    <div class="article" id="art-{t['id']}" style="display:none">
      <div class="breadcrumb">Knowledge Base &rsaquo; Video Tutorials &rsaquo; {t['title']}</div>
      <h1 class="art-title">{t['title']}</h1>
      {extra}
      <div class="art-body">{body}</div>
    </div>"""


def _nav_item(article_id, icon, label):
    return (
        f'<div class="nav-item" id="nav-{article_id}" '
        f'onclick="show(\'{article_id}\')">'
        f'<span class="nav-icon">{icon}</span>'
        f'<span class="nav-label">{label}</span>'
        f'</div>'
    )


@st.cache_data(show_spinner=False)
def _build_html():
    # ── Sidebar nav ──────────────────────────────────────────────────────────
    nav_parts = ['<div class="nav-group-label">VIDEO TUTORIALS</div>']
    for t in _TUTORIALS:
        nav_parts.append(_nav_item(t["id"], "▶", t["title"]))

    nav_parts.append('<div class="nav-group-label">HOW-TO GUIDES</div>')
    icons = {"guide-getting-started": "🚀", "guide-bleeders": "🔍", "guide-harvesting": "🌾", "guide-bids": "📊", "guide-ai": "🤖"}
    for g in _GUIDES:
        nav_parts.append(_nav_item(g["id"], icons.get(g["id"], "📄"), g["title"]))

    sidebar = "\n".join(nav_parts)

    # ── Articles ─────────────────────────────────────────────────────────────
    articles = ""
    for t in _TUTORIALS:
        articles += _tutorial_html(t)
    for g in _GUIDES:
        articles += _article_html(g["id"], g["title"], g["badge"], g["body"])
    for m in _MATH:
        articles += _article_html(m["id"], m["title"], m["badge"], m["body"])
    for fi in _FAQ:
        articles += _article_html(fi["id"], fi["title"], fi["badge"], fi["body"])

    first_id = _TUTORIALS[0]["id"]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {{
  --bg:      #0d1117;
  --sidebar: #161b22;
  --card:    #21262d;
  --border:  #30363d;
  --t1:      #e6edf3;
  --t2:      #8b949e;
  --t3:      #6e7681;
  --accent:  #58a6ff;
  --green:   #3fb950;
  --purple:  #bc8cff;
  --orange:  #ffa657;
  --red:     #f85149;
}}
*{{margin:0;padding:0;box-sizing:border-box;}}
html,body{{height:100%;background:var(--bg);color:var(--t1);font-family:'Inter',sans-serif;font-size:14px;line-height:1.6;}}

/* ── Layout ── */
.kb{{display:flex;height:100vh;overflow:hidden;}}
.sidebar{{width:248px;min-width:248px;background:var(--sidebar);border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden;}}
.sidebar-top{{padding:16px 12px 10px;border-bottom:1px solid var(--border);}}
.sidebar-logo{{font-size:13px;font-weight:700;color:var(--t1);letter-spacing:0.02em;display:flex;align-items:center;gap:8px;margin-bottom:12px;}}
.sidebar-logo-dot{{width:8px;height:8px;border-radius:50%;background:var(--accent);}}
.search-box{{position:relative;}}
.search-box input{{width:100%;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:7px 10px 7px 30px;color:var(--t1);font-size:13px;font-family:'Inter',sans-serif;outline:none;transition:border-color .15s;}}
.search-box input:focus{{border-color:var(--accent);}}
.search-box input::placeholder{{color:var(--t3);}}
.search-icon{{position:absolute;left:9px;top:50%;transform:translateY(-50%);color:var(--t3);font-size:13px;pointer-events:none;}}
.sidebar-nav{{flex:1;overflow-y:auto;padding:8px 0 16px;}}
.sidebar-nav::-webkit-scrollbar{{width:4px;}}
.sidebar-nav::-webkit-scrollbar-track{{background:transparent;}}
.sidebar-nav::-webkit-scrollbar-thumb{{background:var(--border);border-radius:4px;}}
.nav-group-label{{font-size:10px;font-weight:700;letter-spacing:.1em;color:var(--t3);text-transform:uppercase;padding:14px 16px 5px;}}
.nav-item{{display:flex;align-items:flex-start;gap:8px;padding:6px 12px 6px 16px;cursor:pointer;border-left:2px solid transparent;transition:all .12s;color:var(--t2);}}
.nav-item:hover{{color:var(--t1);background:rgba(255,255,255,0.04);}}
.nav-item.active{{color:var(--accent);background:rgba(88,166,255,0.08);border-left-color:var(--accent);}}
.nav-icon{{font-size:11px;margin-top:2px;flex-shrink:0;opacity:.7;}}
.nav-label{{font-size:12.5px;line-height:1.4;}}

/* ── Main area ── */
.main{{flex:1;overflow-y:auto;padding:40px 56px;max-width:860px;}}
.main::-webkit-scrollbar{{width:6px;}}
.main::-webkit-scrollbar-track{{background:transparent;}}
.main::-webkit-scrollbar-thumb{{background:var(--border);border-radius:4px;}}

/* ── Article ── */
.article{{display:none;animation:fadein .2s ease;}}
@keyframes fadein{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:translateY(0)}}}}
.breadcrumb{{font-size:11.5px;color:var(--t3);margin-bottom:14px;}}
.art-title{{font-size:26px;font-weight:700;color:var(--t1);line-height:1.25;margin-bottom:14px;}}
.art-meta-row{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:24px;padding-bottom:22px;border-bottom:1px solid var(--border);}}
.art-meta{{margin-bottom:24px;padding-bottom:20px;border-bottom:1px solid var(--border);}}
.badge{{display:inline-flex;align-items:center;font-size:11px;font-weight:600;padding:2px 9px;border-radius:100px;letter-spacing:.03em;}}
.badge-setup,.badge-video{{background:rgba(88,166,255,.14);color:#58a6ff;}}
.badge-guide{{background:rgba(63,185,80,.14);color:#3fb950;}}
.badge-math{{background:rgba(188,140,255,.14);color:#bc8cff;}}
.badge-faq{{background:rgba(255,166,87,.14);color:#ffa657;}}
.meta-pill{{font-size:12px;color:var(--t2);background:rgba(255,255,255,.05);border:1px solid var(--border);border-radius:100px;padding:2px 10px;}}
.meta-link{{text-decoration:none;transition:background .12s;}}
.meta-link:hover{{background:rgba(88,166,255,.12);color:var(--accent);border-color:rgba(88,166,255,.3);}}

/* ── Article body typography ── */
.art-body h3{{font-size:14px;font-weight:600;color:var(--t1);margin:18px 0 6px;}}
.art-body p{{color:var(--t2);margin:0 0 10px;}}
.art-body ul,.art-body ol{{padding-left:20px;color:var(--t2);margin:6px 0 12px;}}
.art-body li{{margin-bottom:4px;}}
.art-body strong{{color:var(--t1);}}
.code-block{{background:var(--card);border:1px solid var(--border);border-radius:6px;padding:14px 18px;font-family:monospace;font-size:13px;color:#d2a679;margin:12px 0 16px;white-space:pre-wrap;}}

/* ── Video ── */
.video-wrap{{position:relative;padding-bottom:56.25%;height:0;overflow:hidden;border-radius:10px;border:1px solid var(--border);background:#000;margin-bottom:30px;box-shadow:0 8px 32px rgba(0,0,0,.5);}}

/* ── Steps ── */
.section-label{{font-size:10px;font-weight:700;letter-spacing:.12em;color:var(--t3);text-transform:uppercase;margin-bottom:16px;}}
.steps-list{{display:flex;flex-direction:column;gap:12px;}}
.step-card{{background:var(--card);border:1px solid var(--border);border-radius:8px;overflow:hidden;transition:border-color .15s;}}
.step-card:hover{{border-color:rgba(88,166,255,.3);}}
.step-header{{display:flex;align-items:center;gap:10px;padding:14px 16px;}}
.step-num{{width:26px;height:26px;min-width:26px;border-radius:50%;background:rgba(88,166,255,.12);color:var(--accent);display:flex;align-items:center;justify-content:center;font-size:11.5px;font-weight:700;}}
.step-heading{{flex:1;font-size:14px;font-weight:600;color:var(--t1);}}
.step-ts{{text-decoration:none;font-size:11.5px;color:var(--accent);background:rgba(88,166,255,.1);border:1px solid rgba(88,166,255,.2);border-radius:5px;padding:3px 9px;white-space:nowrap;transition:all .12s;}}
.step-ts:hover{{background:rgba(88,166,255,.2);}}
.step-body{{padding:0 16px 14px 52px;}}
.step-body img{{display:block;width:100%;border-radius:6px;border:1px solid var(--border);margin:4px 0 12px;}}
.step-notes{{list-style:none;padding:0;}}
.step-notes li{{font-size:13px;color:var(--t2);padding:2px 0 2px 14px;position:relative;}}
.step-notes li::before{{content:'–';position:absolute;left:0;color:var(--t3);}}

/* ── Search filter ── */
.nav-item.hidden{{display:none;}}
</style>
</head>
<body>
<div class="kb">

  <!-- Sidebar -->
  <div class="sidebar">
    <div class="sidebar-top">
      <div class="sidebar-logo">
        <div class="sidebar-logo-dot"></div>
        Saddl Knowledge Base
      </div>
      <div class="search-box">
        <span class="search-icon">⌕</span>
        <input type="text" id="search-input" placeholder="Search articles..." oninput="filterNav(this.value)">
      </div>
    </div>
    <div class="sidebar-nav">
      {sidebar}
    </div>
  </div>

  <!-- Main content -->
  <div class="main" id="main">
    {articles}
  </div>

</div>

<script>
  var current = null;

  function show(id) {{
    // ── hide previous ──
    if (current) {{
      var prev = document.getElementById('art-' + current);
      if (prev) prev.style.display = 'none';
      var prevNav = document.getElementById('nav-' + current);
      if (prevNav) prevNav.classList.remove('active');
    }}
    // ── show new ──
    var el = document.getElementById('art-' + id);
    if (el) {{ el.style.display = 'block'; }}
    var nav = document.getElementById('nav-' + id);
    if (nav) nav.classList.add('active');
    current = id;
    document.getElementById('main').scrollTop = 0;
  }}

  function filterNav(q) {{
    var query = q.toLowerCase().trim();
    document.querySelectorAll('.nav-item').forEach(function(item) {{
      var label = item.querySelector('.nav-label');
      if (!label) return;
      item.classList.toggle('hidden', query !== '' && !label.textContent.toLowerCase().includes(query));
    }});
  }}

  // init
  show('{first_id}');
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def render_readme():
    """Render the Saddl Knowledge Base."""
    # Minimal top padding to push the iframe flush with the page
    st.markdown(
        "<style>.block-container{padding-top:1rem!important;}</style>",
        unsafe_allow_html=True,
    )
    html = _build_html()
    components.html(html, height=820, scrolling=False)

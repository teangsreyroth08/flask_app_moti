from flask import Flask, request, redirect, send_from_directory, jsonify
import random
import json
import os
from datetime import datetime

app = Flask(__name__)

# Environment detection
IS_SERVERLESS = os.environ.get('VERCEL') == '1'
POSTGRES_URL = os.environ.get('POSTGRES_URL')

DEFAULT_QUOTES = [
    ("Believe you can and you're halfway there.", "Theodore Roosevelt"),
    ("Small steps every day become big results.", "Unknown"),
    ("Discipline beats motivation when motivation is low.", "Unknown"),
    ("Your future is created by what you do today, not tomorrow.", "Robert Kiyosaki"),
    ("Don't watch the clock; do what it does. Keep going.", "Sam Levenson"),
    ("You don't have to be perfect to be proud.", "Unknown"),
    ("Progress, not perfection.", "Unknown"),
    ("It always seems impossible until it's done.", "Nelson Mandela"),
    ("Start where you are. Use what you have. Do what you can.", "Arthur Ashe"),
    ("Dream big. Start small. Act now.", "Robin Sharma"),
]

# ============================================================
# DATABASE SETUP - Works both locally and on Vercel
# ============================================================

if POSTGRES_URL:
    # Use Vercel Postgres (production)
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from contextlib import contextmanager
    
    @contextmanager
    def get_db():
        conn = psycopg2.connect(POSTGRES_URL)
        try:
            yield conn
        finally:
            conn.close()
    
    def init_db():
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quotes (
                    id SERIAL PRIMARY KEY,
                    quote TEXT NOT NULL UNIQUE,
                    author TEXT NOT NULL DEFAULT 'Unknown',
                    is_default BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("SELECT COUNT(*) FROM quotes")
            count = cursor.fetchone()[0]
            
            if count == 0:
                for quote, author in DEFAULT_QUOTES:
                    cursor.execute(
                        "INSERT INTO quotes (quote, author, is_default) VALUES (%s, %s, TRUE) ON CONFLICT (quote) DO NOTHING",
                        (quote, author)
                    )
            
            conn.commit()
            cursor.execute("SELECT COUNT(*) FROM quotes")
            print(f"✅ Postgres initialized with {cursor.fetchone()[0]} quotes")
    
    def load_quotes():
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT quote, author FROM quotes ORDER BY created_at ASC")
            return [(row[0], row[1]) for row in cursor.fetchall()]
    
    def save_quote(quote, author):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO quotes (quote, author, is_default) VALUES (%s, %s, FALSE) RETURNING id",
                (quote, author)
            )
            conn.commit()
            return cursor.fetchone()[0]
    
    def quote_exists(quote):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM quotes WHERE LOWER(quote) = LOWER(%s)", (quote,))
            return cursor.fetchone()[0] > 0

else:
    # Use SQLite (local development)
    import sqlite3
    from contextlib import contextmanager
    
    DB_FILE = os.path.join(app.root_path, "quotes.db")
    
    @contextmanager
    def get_db():
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def init_db():
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quotes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    quote TEXT NOT NULL UNIQUE,
                    author TEXT NOT NULL DEFAULT 'Unknown',
                    is_default BOOLEAN NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("SELECT COUNT(*) as count FROM quotes")
            count = cursor.fetchone()['count']
            
            if count == 0:
                for quote, author in DEFAULT_QUOTES:
                    cursor.execute(
                        "INSERT OR IGNORE INTO quotes (quote, author, is_default) VALUES (?, ?, 1)",
                        (quote, author)
                    )
            
            conn.commit()
            cursor.execute('SELECT COUNT(*) FROM quotes')
            print(f"✅ SQLite initialized with {cursor.fetchone()[0]} quotes")
    
    def load_quotes():
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT quote, author FROM quotes ORDER BY created_at ASC")
            return [(row['quote'], row['author']) for row in cursor.fetchall()]
    
    def save_quote(quote, author):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO quotes (quote, author, is_default) VALUES (?, ?, 0)",
                (quote, author)
            )
            conn.commit()
            return cursor.lastrowid
    
    def quote_exists(quote):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM quotes WHERE LOWER(quote) = LOWER(?)", (quote,))
            return cursor.fetchone()['count'] > 0

# Initialize database on startup
init_db()

# ============================================================
# ROUTES
# ============================================================

@app.route("/images/<path:filename>")
def images(filename):
    images_dir = os.path.join(app.root_path, "images")
    return send_from_directory(images_dir, filename)

@app.route("/api/quotes", methods=["GET"])
def api_quotes():
    quotes = load_quotes()
    return jsonify({
        "ok": True,
        "count": len(quotes),
        "quotes": [{"quote": q, "author": a} for q, a in quotes]
    })

@app.route("/api/quote/random", methods=["GET"])
def api_random_quote():
    quotes = load_quotes()
    if not quotes:
        return jsonify({"ok": False, "message": "No quotes available"}), 404
    
    quote, author = random.choice(quotes)
    return jsonify({
        "ok": True,
        "quote": quote,
        "author": author
    })

@app.route("/add", methods=["POST"])
def add():
    quote = (request.form.get("quote") or "").strip()
    author = (request.form.get("author") or "").strip() or "Unknown"

    if not quote:
        return redirect("/?msg=Quote%20cannot%20be%20empty%20%F0%9F%98%BF")

    if quote_exists(quote):
        return redirect("/?msg=Quote%20already%20exists%20%E2%9C%A8")

    try:
        save_quote(quote, author)
        return redirect("/?msg=Saved%20%F0%9F%8C%B8")
    except Exception as e:
        return redirect(f"/?msg=Error:%20{str(e)}")

@app.route("/add-json", methods=["POST"])
def add_json():
    quote = (request.form.get("quote") or "").strip()
    author = (request.form.get("author") or "").strip() or "Unknown"

    if not quote:
        return jsonify({"ok": False, "message": "Quote cannot be empty 😿"}), 400

    if quote_exists(quote):
        return jsonify({"ok": False, "message": "That quote already exists ✨"}), 409

    try:
        quote_id = save_quote(quote, author)
        return jsonify({
            "ok": True,
            "id": quote_id,
            "quote": quote,
            "author": author,
            "message": "Saved! 🌸"
        })
    except Exception as e:
        return jsonify({"ok": False, "message": f"Database error: {str(e)}"}), 500

@app.route("/")
def home():
    quotes = load_quotes()
    if not quotes:
        quote, author = "Stay positive! ✨", "Unknown"
    else:
        quote, author = random.choice(quotes)
    
    msg = (request.args.get("msg") or "").strip()

    html = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Motivation 💖</title>

<script>
  (function () {
    try {
      const theme = localStorage.getItem("theme");
      if (theme === "dark") document.documentElement.setAttribute("data-theme", "dark");
    } catch (e) {}
  })();
</script>

<style>
  :root{
    --bg1:#ffd6e8; --bg2:#e0f7fa;
    --card:#ffffff;
    --text:#2b2b2b; --muted:#5a5a5a;
    --shadow: rgba(0,0,0,.18);
    --glass: rgba(255,255,255,.72);
    --glassBorder: rgba(255,255,255,.45);
    --ring: rgba(255,111,145,.35);
    --pink1:#ffb3c7; --pink2:#ffd6e8;
    --blue1:#b9f3ff; --blue2:#e0f7fa;
    --nightA:#0b1022; --nightB:#1a1140; --nightC:#022b3a;
    --stars: rgba(255,255,255,.12);
  }

  [data-theme="dark"]{
    --bg1: var(--nightA); --bg2: var(--nightB);
    --card:#0b1222; --text:#f8fafc; --muted:#cbd5f5;
    --shadow: rgba(0,0,0,.62);
    --glass: rgba(11,18,34,.78);
    --glassBorder: rgba(255,255,255,.10);
    --ring: rgba(85,214,255,.28);
  }

  *{box-sizing:border-box}

  html, body, .card, .nav, .quoteCard, .mascot, textarea, input, .btn, .footer, .msg, .toggle {
    transition: background-color .35s ease, color .35s ease, border-color .35s ease,
                box-shadow .35s ease, filter .35s ease, transform .20s ease;
  }

  body{
    margin:0; min-height:100vh; display:flex; justify-content:center; align-items:center;
    font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial;
    color: var(--text); padding: 18px; overflow:hidden;
    background:
      radial-gradient(1200px 800px at 20% 20%, var(--bg1), transparent 60%),
      radial-gradient(1200px 800px at 80% 80%, var(--bg2), transparent 60%),
      linear-gradient(135deg,var(--bg1),var(--bg2));
  }

  [data-theme="dark"] body{
    background:
      radial-gradient(900px 600px at 20% 15%, rgba(120, 90, 255, .25), transparent 60%),
      radial-gradient(900px 600px at 80% 85%, rgba(0, 200, 255, .15), transparent 60%),
      radial-gradient(1200px 800px at 50% 50%, rgba(255,255,255,.06), transparent 65%),
      linear-gradient(135deg, var(--nightA), var(--nightB) 45%, var(--nightC));
  }

  .stars{
    position:fixed; inset:0; pointer-events:none;
    background:
      radial-gradient(circle at 12% 20%, var(--stars) 0 1px, transparent 2px),
      radial-gradient(circle at 25% 70%, var(--stars) 0 1px, transparent 2px),
      radial-gradient(circle at 44% 35%, var(--stars) 0 1px, transparent 2px),
      radial-gradient(circle at 58% 18%, var(--stars) 0 1px, transparent 2px),
      radial-gradient(circle at 77% 58%, var(--stars) 0 1px, transparent 2px),
      radial-gradient(circle at 88% 28%, var(--stars) 0 1px, transparent 2px),
      radial-gradient(circle at 10% 88%, var(--stars) 0 1px, transparent 2px),
      radial-gradient(circle at 92% 86%, var(--stars) 0 1px, transparent 2px);
    opacity: 0; transition: opacity .35s ease;
  }
  [data-theme="dark"] .stars{ opacity: 1; }

  .petal{ position:absolute; top:-12%; font-size:22px; opacity:.88;
    animation: fall linear infinite; user-select:none; pointer-events:none; }
  @keyframes fall{ 0%{transform:translateY(-10vh) rotate(0deg)}
    100%{transform:translateY(110vh) rotate(360deg)} }

  .card{
    width:min(940px, 96%);
    background: color-mix(in srgb, var(--card) 92%, transparent);
    backdrop-filter: blur(10px);
    border-radius:24px; padding:22px 18px 18px;
    border: 1px solid color-mix(in srgb, var(--card) 70%, transparent);
    box-shadow:0 20px 50px var(--shadow);
    animation: enter .75s ease;
  }
  @keyframes enter{ 0%{transform:translateY(10px) scale(.98);opacity:0}
    100%{transform:translateY(0) scale(1);opacity:1} }

  .nav{
    display:flex; align-items:center; justify-content:space-between; gap:14px;
    padding:10px 12px; border-radius:18px;
    background: var(--glass); border:1px solid var(--glassBorder);
    box-shadow: 0 10px 22px var(--shadow); margin-bottom:16px;
    flex-wrap: wrap;
  }
  .brand{ display:flex; align-items:center; gap:10px; font-weight:950; }
  .logo{ width:34px; height:34px; border-radius:12px; display:grid; place-items:center;
    background: linear-gradient(135deg, var(--pink1), var(--blue1));
    box-shadow:0 10px 18px var(--shadow); animation: wiggle 2.8s ease-in-out infinite; }
  @keyframes wiggle{ 0%,100%{transform:rotate(-2deg)} 50%{transform:rotate(2deg)} }

  .toggle{
    display:inline-flex; align-items:center; gap:10px; padding:9px 10px;
    border-radius:14px; background: color-mix(in srgb, var(--glass) 85%, transparent);
    border: 1px solid var(--glassBorder); cursor:pointer; user-select:none; outline:none;
  }
  .toggle:hover{ transform: translateY(-1px); }
  .toggle:active{ transform: scale(.98); }

  .switch{ width:46px; height:26px; border-radius:999px; position:relative;
    background: color-mix(in srgb, var(--text) 15%, transparent);
    box-shadow: inset 0 0 0 2px color-mix(in srgb, var(--text) 12%, transparent); }
  .knob{ width:22px; height:22px; border-radius:999px; position:absolute; top:2px; left:2px;
    background: var(--card); transition:left .18s ease; box-shadow:0 8px 16px var(--shadow); }
  [data-theme="dark"] .knob{ left:22px; }

  .hero{ display:grid; grid-template-columns: 1.15fr .85fr; gap:16px; align-items:stretch; }
  @media (max-width: 760px){ .hero{ grid-template-columns: 1fr; } }

  h1{ margin:10px 0 6px; font-size: clamp(26px, 4vw, 42px); letter-spacing:-0.02em; }
  p{ margin:0 0 14px; color: var(--muted); line-height:1.5; }

  .quoteCard{
    padding:18px 16px; border-radius:20px;
    background: var(--glass); border:1px solid var(--glassBorder);
    box-shadow: 0 16px 28px var(--shadow);
  }
  .quote{ font-size: clamp(18px, 2.6vw, 24px); font-weight:900; line-height:1.35; }
  .author{ margin-top:10px; font-weight:850; color: var(--muted); }

  .btnRow{ display:flex; flex-wrap:wrap; gap:10px; margin-top:12px; }
  .btn{
    border:0; padding:12px 14px; border-radius:16px; font-weight:950;
    cursor:pointer; box-shadow: 0 10px 22px var(--shadow);
    transition: transform .12s ease, box-shadow .12s ease; outline:none;
    background: linear-gradient(135deg, var(--pink1), var(--pink2));
  }
  .btn:hover{ transform: translateY(-3px); }
  .btn:active{ transform: scale(.98); }
  .btn:focus{ box-shadow: 0 0 0 4px var(--ring), 0 10px 22px var(--shadow); }
  .btn.secondary{ background: linear-gradient(135deg, var(--blue1), var(--blue2)); }

  .mascot{
    border-radius:22px;
    background: linear-gradient(135deg,
      color-mix(in srgb, var(--blue1) 55%, transparent),
      color-mix(in srgb, var(--pink1) 55%, transparent)
    );
    border: 1px solid color-mix(in srgb, var(--card) 55%, transparent);
    box-shadow: 0 16px 28px var(--shadow);
    padding:14px;
    display:flex; flex-direction:column; justify-content:center; align-items:center; gap:10px;
    min-height:240px;
  }
  img{ width:min(320px, 100%); height:auto; border-radius:20px;
    box-shadow: 0 18px 30px var(--shadow); }
  .tip{ font-weight:900; color: var(--muted); text-align:center; }

  .form{ width: 100%; display: grid; gap: 10px; margin-top: 8px; }
  textarea, input{
    width:100%; padding:12px 12px; border-radius:16px;
    border:1px solid color-mix(in srgb, var(--text) 18%, transparent);
    background: color-mix(in srgb, var(--card) 82%, transparent);
    color: var(--text); font: inherit; outline:none;
  }
  textarea{ min-height: 90px; resize: vertical; }

  .msg{
    margin-bottom: 14px; padding: 10px 12px; border-radius: 16px;
    background: var(--glass); border: 1px solid var(--glassBorder);
    font-weight: 900; color: var(--text);
  }

  .footer{
    margin-top:14px; display:flex; flex-wrap:wrap; justify-content:space-between; gap:10px;
    color: color-mix(in srgb, var(--muted) 85%, transparent); font-size:13px;
  }
  code{ background: color-mix(in srgb, var(--text) 10%, transparent);
    padding: 3px 8px; border-radius:10px; font-family: ui-monospace, Menlo, Consolas, monospace; }
  
  .badge{
    display: inline-block; padding: 4px 10px; border-radius: 12px;
    font-size: 11px; font-weight: 900;
    background: linear-gradient(135deg, var(--pink1), var(--pink2));
    color: var(--text);
  }
</style>
</head>

<body>
  <div class="stars"></div>

  <span class="petal" style="left:12%;animation-duration:9s">🌸</span>
  <span class="petal" style="left:28%;animation-duration:12s">🌸</span>
  <span class="petal" style="left:46%;animation-duration:10s">🌸</span>
  <span class="petal" style="left:64%;animation-duration:13s">🌸</span>
  <span class="petal" style="left:82%;animation-duration:11s">🌸</span>

  <div class="card">
    <div class="nav">
      <div class="brand">
        <div class="logo">🎀</div>
        <div>Motivation <span class="badge"></span></div>
      </div>

      <div class="toggle" id="themeToggle" title="Toggle dark mode" role="button" tabindex="0" aria-pressed="false">
        <span id="themeIcon">☀️</span>
        <div class="switch"><div class="knob"></div></div>
      </div>
    </div>

    __MSG_BLOCK__

    <div class="hero">
      <div>
        <h1>Today's Cute Motivation 💖</h1>
        <p>One quote can change your mood. Take a deep breath… you got this ✨</p>

        <div class="quoteCard">
          <div class="quote" id="quoteText">"__QUOTE__"</div>
          <div class="author" id="quoteAuthor">— __AUTHOR__</div>

          <div class="btnRow">
            <button class="btn" id="btnNew" type="button">✨ New quote</button>
            <button class="btn secondary" id="btnCopy" type="button">📋 Copy</button>
          </div>
        </div>
      </div>

      <div class="mascot">
        <img src="/images/meow.jpg" alt="Cute cat"/>
        <div class="tip">🐱 Add your own quote below ✨</div>

        <form class="form" id="addForm" method="POST" action="/add-json">
          <textarea id="quoteInput" name="quote" placeholder="Write a new motivational quote..." required></textarea>
          <input id="authorInput" name="author" placeholder="Author (optional)"/>
          <button class="btn" type="submit">🌸 Save quote</button>
        </form>
      </div>
    </div>
  </div>

<script>
  const root = document.documentElement;
  const toggle = document.getElementById("themeToggle");
  const icon = document.getElementById("themeIcon");

  function applyTheme(theme) {
    const isDark = theme === "dark";
    if (isDark) root.setAttribute("data-theme", "dark");
    else root.removeAttribute("data-theme");
    icon.textContent = isDark ? "🌙" : "☀️";
    try { localStorage.setItem("theme", isDark ? "dark" : "light"); } catch (e) {}
    toggle.setAttribute("aria-pressed", String(isDark));
  }

  const saved = (() => {
    try { return localStorage.getItem("theme"); } catch(e) { return null; }
  })();
  applyTheme(saved === "dark" ? "dark" : "light");

  toggle.addEventListener("click", () => {
    const isDarkNow = root.getAttribute("data-theme") === "dark";
    applyTheme(isDarkNow ? "light" : "dark");
  });

  toggle.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      toggle.click();
    }
  });

  let QUOTES = __QUOTES_JSON__;
  const quoteText = document.getElementById("quoteText");
  const quoteAuthor = document.getElementById("quoteAuthor");

  document.getElementById("btnNew").addEventListener("click", () => {
    const [q, a] = QUOTES[Math.floor(Math.random() * QUOTES.length)];
    quoteText.textContent = `"${q}"`;
    quoteAuthor.textContent = `— ${a}`;
  });

  document.getElementById("btnCopy").addEventListener("click", async () => {
    const text = `${quoteText.textContent} ${quoteAuthor.textContent}`;
    try{
      await navigator.clipboard.writeText(text);
      alert("Copied! 💖");
    }catch(e){
      alert("Copy failed 😿 (browser permission)");
    }
  });

  const addForm = document.getElementById("addForm");
  const quoteInput = document.getElementById("quoteInput");
  const authorInput = document.getElementById("authorInput");

  addForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = new FormData(addForm);

    try {
      const res = await fetch("/add-json", { method: "POST", body: formData });
      const data = await res.json();

      if (!res.ok || !data.ok) {
        alert(data.message || "Failed 😿");
        return;
      }

      QUOTES.push([data.quote, data.author]);
      quoteText.textContent = `"${data.quote}"`;
      quoteAuthor.textContent = `— ${data.author}`;
      document.getElementById("quoteCount").textContent = `${QUOTES.length}`;

      quoteInput.value = "";
      authorInput.value = "";
      alert(data.message || "Saved! 🌸");
    } catch (err) {
      alert("Network error 😿");
    }
  });
</script>
</body>
</html>
    """

    msg_block = f'<div class="msg">✨ {msg}</div>' if msg else ""
    html = html.replace("__MSG_BLOCK__", msg_block)
    html = html.replace("__QUOTE__", quote).replace("__AUTHOR__", author)
    html = html.replace("__COUNT__", str(len(quotes)))
    
    db_type = "PG" if POSTGRES_URL else "SQLite"
    html = html.replace("__DB_TYPE__", db_type)

    quotes_json = json.dumps(quotes, ensure_ascii=False)
    html = html.replace("__QUOTES_JSON__", quotes_json)

    return html

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
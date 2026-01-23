from flask import Flask, request, redirect, send_from_directory, jsonify, session
import random
import json
import os
from functools import wraps

app = Flask(__name__)

# IMPORTANT: set SECRET_KEY in env for production
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# Admin credentials (set these in Vercel/hosting env)
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# ============================================================
# ENV + PATHS
# ============================================================

# Vercel sets VERCEL in serverless env; treat any truthy value as serverless
IS_SERVERLESS = bool(os.environ.get("VERCEL"))

# Prefer NON_POOLING for direct connections if you use Vercel Postgres
POSTGRES_URL = os.environ.get("POSTGRES_URL_NON_POOLING") or os.environ.get("POSTGRES_URL")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# If you have: project/images/...
LOCAL_IMAGES_DIR = os.path.join(os.path.dirname(BASE_DIR), "images")

# If you deploy to Vercel and use: project/public/images/...
PUBLIC_IMAGES_DIR = os.path.join(os.path.dirname(BASE_DIR), "public", "images")

# Choose images directory automatically:
# - If /public/images exists -> use it (Vercel-friendly)
# - else -> use /images (your local structure)
IMAGES_DIR = PUBLIC_IMAGES_DIR if os.path.isdir(PUBLIC_IMAGES_DIR) else LOCAL_IMAGES_DIR

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
    ("The only way to do great work is to love what you do.", "Steve Jobs"),
]

# ============================================================
# ADMIN AUTH HELPERS
# ============================================================

def is_admin():
    return bool(session.get("is_admin"))

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_admin():
            return redirect("/admin/login?msg=Please%20login%20as%20admin%20%E2%9C%A8")
        return fn(*args, **kwargs)
    return wrapper

# ============================================================
# DATABASE SETUP
# ============================================================

HAS_DATABASE = False

if POSTGRES_URL:
    # Use Postgres (e.g., Vercel Postgres)
    try:
        import psycopg2
        from contextlib import contextmanager

        @contextmanager
        def get_db():
            conn = psycopg2.connect(POSTGRES_URL)
            try:
                yield conn
            finally:
                conn.close()

        def init_db():
            try:
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
                                "INSERT INTO quotes (quote, author, is_default) VALUES (%s, %s, TRUE) "
                                "ON CONFLICT (quote) DO NOTHING",
                                (quote, author),
                            )
                    conn.commit()
            except Exception as e:
                print(f"⚠️ DB init error (Postgres): {e}")

        def load_quotes():
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT quote, author FROM quotes ORDER BY created_at ASC")
                    return [(row[0], row[1]) for row in cursor.fetchall()]
            except Exception as e:
                print(f"⚠️ Load error (Postgres): {e}")
                return list(DEFAULT_QUOTES)

        def load_quotes_detailed():
            # For admin list page
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, quote, author, created_at FROM quotes ORDER BY created_at DESC")
                rows = cursor.fetchall()
                return [{"id": r[0], "quote": r[1], "author": r[2], "created_at": str(r[3])} for r in rows]

        def save_quote(quote, author):
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO quotes (quote, author, is_default) VALUES (%s, %s, FALSE) RETURNING id",
                    (quote, author),
                )
                quote_id = cursor.fetchone()[0]
                conn.commit()
                return quote_id

        def quote_exists(quote):
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM quotes WHERE LOWER(quote) = LOWER(%s)", (quote,))
                return cursor.fetchone()[0] > 0

        HAS_DATABASE = True

    except Exception as e:
        print(f"⚠️ Postgres setup error: {e}")
        HAS_DATABASE = False

else:
    # Use SQLite fallback
    try:
        import sqlite3
        from contextlib import contextmanager

        # IMPORTANT: on serverless, write only to /tmp
        DB_FILE = "/tmp/quotes.db" if IS_SERVERLESS else os.path.join(os.path.dirname(BASE_DIR), "quotes.db")

        @contextmanager
        def get_db():
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
            finally:
                conn.close()

        def init_db():
            try:
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
                    count = cursor.fetchone()["count"]

                    if count == 0:
                        for quote, author in DEFAULT_QUOTES:
                            cursor.execute(
                                "INSERT OR IGNORE INTO quotes (quote, author, is_default) VALUES (?, ?, 1)",
                                (quote, author),
                            )
                    conn.commit()
            except Exception as e:
                print(f"⚠️ DB init error (SQLite): {e}")

        def load_quotes():
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT quote, author FROM quotes ORDER BY created_at ASC")
                    return [(row["quote"], row["author"]) for row in cursor.fetchall()]
            except Exception as e:
                print(f"⚠️ Load error (SQLite): {e}")
                return list(DEFAULT_QUOTES)

        def load_quotes_detailed():
            with get_db() as conn:
                rows = conn.execute(
                    "SELECT id, quote, author, created_at FROM quotes ORDER BY created_at DESC"
                ).fetchall()
                return [{"id": r["id"], "quote": r["quote"], "author": r["author"], "created_at": str(r["created_at"])} for r in rows]

        def save_quote(quote, author):
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO quotes (quote, author, is_default) VALUES (?, ?, 0)",
                    (quote, author),
                )
                conn.commit()
                return cursor.lastrowid

        def quote_exists(quote):
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as count FROM quotes WHERE LOWER(quote) = LOWER(?)", (quote,))
                return cursor.fetchone()["count"] > 0

        HAS_DATABASE = True

    except Exception as e:
        print(f"⚠️ SQLite setup error: {e}")
        HAS_DATABASE = False


# In-memory fallback (if everything fails)
if not HAS_DATABASE:
    print("⚠️ Using in-memory storage")

    QUOTES_STORE = []
    _qid = 1
    for q, a in DEFAULT_QUOTES:
        QUOTES_STORE.append({"id": _qid, "quote": q, "author": a, "created_at": "n/a"})
        _qid += 1

    def init_db():
        pass

    def load_quotes():
        return [(it["quote"], it["author"]) for it in QUOTES_STORE]

    def load_quotes_detailed():
        return list(reversed(QUOTES_STORE))

    def save_quote(quote, author):
        global _qid
        QUOTES_STORE.append({"id": _qid, "quote": quote, "author": author, "created_at": "n/a"})
        _qid += 1
        return _qid - 1

    def quote_exists(quote):
        return any(it["quote"].lower() == quote.lower() for it in QUOTES_STORE)


# Initialize once on cold start
try:
    init_db()
except Exception as e:
    print(f"⚠️ Init failed: {e}")

# ============================================================
# ROUTES
# ============================================================

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "ok": True,
        "is_serverless": IS_SERVERLESS,
        "has_postgres_url": bool(POSTGRES_URL),
        "images_dir": IMAGES_DIR,
        "has_database": HAS_DATABASE,
        "admin_logged_in": is_admin(),
    })


@app.route("/images/<path:filename>")
def images(filename):
    try:
        return send_from_directory(IMAGES_DIR, filename)
    except Exception:
        return "Image not found", 404


@app.route("/api/quotes", methods=["GET"])
def api_quotes():
    try:
        quotes = load_quotes()
        return jsonify({
            "ok": True,
            "count": len(quotes),
            "quotes": [{"quote": q, "author": a} for q, a in quotes],
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/quote/random", methods=["GET"])
def api_random_quote():
    try:
        quotes = load_quotes()
        if not quotes:
            return jsonify({"ok": False, "message": "No quotes available"}), 404

        quote, author = random.choice(quotes)
        return jsonify({"ok": True, "quote": quote, "author": author})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/add", methods=["POST"])
def add():
    try:
        quote = (request.form.get("quote") or "").strip()
        author = (request.form.get("author") or "").strip() or "Unknown"

        if not quote:
            return redirect("/?msg=Quote%20cannot%20be%20empty%20%F0%9F%98%BF")

        if quote_exists(quote):
            return redirect("/?msg=Quote%20already%20exists%20%E2%9C%A8")

        save_quote(quote, author)
        return redirect("/?msg=Saved%20%F0%9F%8C%B8")
    except Exception:
        return redirect("/?msg=Error")


@app.route("/add-json", methods=["POST"])
def add_json():
    try:
        quote = (request.form.get("quote") or "").strip()
        author = (request.form.get("author") or "").strip() or "Unknown"

        if not quote:
            return jsonify({"ok": False, "message": "Quote cannot be empty 😿"}), 400

        if quote_exists(quote):
            return jsonify({"ok": False, "message": "That quote already exists ✨"}), 409

        quote_id = save_quote(quote, author)
        return jsonify({
            "ok": True,
            "id": quote_id,
            "quote": quote,
            "author": author,
            "message": "Saved! 🌸",
        })
    except Exception as e:
        return jsonify({"ok": False, "message": f"Error: {str(e)}"}), 500


# ============================================================
# ADMIN PAGES
# ============================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    msg = (request.args.get("msg") or "").strip()

    if request.method == "POST":
        u = (request.form.get("username") or "").strip()
        p = (request.form.get("password") or "").strip()
        if u == ADMIN_USERNAME and p == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect("/admin/quotes?msg=Welcome%20admin%20%F0%9F%8C%B8")
        return redirect("/admin/login?msg=Wrong%20username%20or%20password%20%F0%9F%98%BF")

    msg_block = f'<div class="msg">✨ {msg}</div>' if msg else ""

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes"/>
<title>Admin Login 💖</title>
<script>
(function(){{
  try{{
    const t=localStorage.getItem("theme");
    if(t==="dark") document.documentElement.setAttribute("data-theme","dark");
  }}catch(e){{}}
}})();
</script>
<style>
:root{{--bg1:#ffd6e8;--bg2:#e0f7fa;--card:#fff;--text:#2b2b2b;--muted:#5a5a5a;--shadow:rgba(0,0,0,.18);--glass:rgba(255,255,255,.72);--glassBorder:rgba(255,255,255,.45);--ring:rgba(255,111,145,.35);--pink1:#ffb3c7;--pink2:#ffd6e8;--blue1:#b9f3ff;--blue2:#e0f7fa;--nightA:#0b1022;--nightB:#1a1140;--nightC:#022b3a;--stars:rgba(255,255,255,.12)}}
[data-theme="dark"]{{--bg1:var(--nightA);--bg2:var(--nightB);--card:#0b1222;--text:#f8fafc;--muted:#cbd5f5;--shadow:rgba(0,0,0,.62);--glass:rgba(11,18,34,.78);--glassBorder:rgba(255,255,255,.1);--ring:rgba(85,214,255,.28)}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{min-height:100vh;display:flex;justify-content:center;align-items:center;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial;color:var(--text);
padding:16px;background:radial-gradient(1200px 800px at 20% 20%,var(--bg1),transparent 60%),
radial-gradient(1200px 800px at 80% 80%,var(--bg2),transparent 60%),linear-gradient(135deg,var(--bg1),var(--bg2));
background-attachment:fixed}}
.card{{width:100%;max-width:560px;background:color-mix(in srgb,var(--card) 92%,transparent);backdrop-filter:blur(10px);
border-radius:20px;padding:18px;border:1px solid color-mix(in srgb,var(--card) 70%,transparent);box-shadow:0 20px 50px var(--shadow)}}
.nav{{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:10px;border-radius:16px;background:var(--glass);border:1px solid var(--glassBorder);
box-shadow:0 10px 22px var(--shadow);margin-bottom:14px;flex-wrap:wrap}}
.brand{{display:flex;align-items:center;gap:10px;font-weight:950}}
.logo{{width:34px;height:34px;border-radius:12px;display:grid;place-items:center;background:linear-gradient(135deg,var(--pink1),var(--blue1));
box-shadow:0 10px 18px var(--shadow)}}
.toggle{{display:inline-flex;align-items:center;gap:10px;padding:8px 10px;border-radius:14px;background:color-mix(in srgb,var(--glass) 85%,transparent);
border:1px solid var(--glassBorder);cursor:pointer;user-select:none;outline:none}}
.switch{{width:46px;height:26px;border-radius:999px;position:relative;background:color-mix(in srgb,var(--text) 15%,transparent);box-shadow:inset 0 0 0 2px color-mix(in srgb,var(--text) 12%,transparent)}}
.knob{{width:22px;height:22px;border-radius:999px;position:absolute;top:2px;left:2px;background:var(--card);transition:left .18s ease;box-shadow:0 8px 16px var(--shadow)}}
[data-theme="dark"] .knob{{left:calc(100% - 22px - 2px)}}
h1{{margin:10px 0 6px;font-size:28px;letter-spacing:-.02em}}
p{{margin:0 0 14px;color:var(--muted);line-height:1.6}}
.msg{{margin-bottom:14px;padding:12px 14px;border-radius:16px;background:var(--glass);border:1px solid var(--glassBorder);font-weight:900}}
input{{width:100%;padding:12px 14px;border-radius:16px;border:1px solid color-mix(in srgb,var(--text) 18%,transparent);
background:color-mix(in srgb,var(--card) 82%,transparent);color:var(--text);font:inherit;outline:none;margin:8px 0}}
.btn{{border:0;width:100%;padding:12px 14px;border-radius:16px;font-weight:950;cursor:pointer;box-shadow:0 10px 22px var(--shadow);
background:linear-gradient(135deg,var(--pink1),var(--pink2));font-size:14px}}
.link{{display:block;margin-top:10px;text-align:center;color:var(--muted);text-decoration:none;font-weight:800}}
</style>
</head>
<body>
  <div class="card">
    <div class="nav">
      <div class="brand"><div class="logo">🔐</div><div>Admin</div></div>
      <div class="toggle" id="themeToggle" title="Toggle dark mode" role="button" tabindex="0" aria-pressed="false">
        <span id="themeIcon">☀️</span><div class="switch"><div class="knob"></div></div>
      </div>
    </div>

    {msg_block}

    <h1>Cute Admin Login 💖</h1>
    <p>Only admin can see the quote list ✨</p>

    <form method="POST" action="/admin/login">
      <input name="username" placeholder="Username" required />
      <input name="password" type="password" placeholder="Password" required />
      <button class="btn" type="submit">🌸 Login</button>
    </form>

    <a class="link" href="/">← Back home</a>
  </div>

<script>
const root=document.documentElement,toggle=document.getElementById("themeToggle"),icon=document.getElementById("themeIcon");
function applyTheme(t){{
  const e=t==="dark";
  e?root.setAttribute("data-theme","dark"):root.removeAttribute("data-theme");
  icon.textContent=e?"🌙":"☀️";
  try{{localStorage.setItem("theme",e?"dark":"light")}}catch(_{{}}){{}}
  toggle.setAttribute("aria-pressed",String(e));
}}
const saved=(()=>{{try{{return localStorage.getItem("theme")}}catch(e){{return null}}}})();
applyTheme(saved==="dark"?"dark":"light");
toggle.addEventListener("click",()=>{{const t=root.getAttribute("data-theme")==="dark";applyTheme(t?"light":"dark")}});
toggle.addEventListener("keydown",e=>{{if(e.key==="Enter"||e.key===" "){{e.preventDefault();toggle.click()}}}});
</script>
</body>
</html>
"""

@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect("/admin/login?msg=Logged%20out%20%F0%9F%8C%B8")

@app.route("/admin/quotes")
@admin_required
def admin_quotes():
    msg = (request.args.get("msg") or "").strip()
    msg_block = f'<div class="msg">✨ {msg}</div>' if msg else ""

    data = load_quotes_detailed()
    rows_html = ""
    for it in data:
        q = (it.get("quote") or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        a = (it.get("author") or "Unknown").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        ca = (it.get("created_at") or "")
        rows_html += f"""
          <tr>
            <td style="padding:10px 12px;border-bottom:1px solid rgba(0,0,0,.08);font-weight:900">“{q}”</td>
            <td style="padding:10px 12px;border-bottom:1px solid rgba(0,0,0,.08);white-space:nowrap">— {a}</td>
            <td style="padding:10px 12px;border-bottom:1px solid rgba(0,0,0,.08);white-space:nowrap;color:var(--muted)">{ca}</td>
          </tr>
        """

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes"/>
<title>Admin Quotes 💖</title>
<script>
(function(){{
  try{{
    const t=localStorage.getItem("theme");
    if(t==="dark") document.documentElement.setAttribute("data-theme","dark");
  }}catch(e){{}}
}})();
</script>
<style>
:root{{--bg1:#ffd6e8;--bg2:#e0f7fa;--card:#fff;--text:#2b2b2b;--muted:#5a5a5a;--shadow:rgba(0,0,0,.18);--glass:rgba(255,255,255,.72);--glassBorder:rgba(255,255,255,.45);--ring:rgba(255,111,145,.35);--pink1:#ffb3c7;--pink2:#ffd6e8;--blue1:#b9f3ff;--blue2:#e0f7fa;--nightA:#0b1022;--nightB:#1a1140;--nightC:#022b3a;--stars:rgba(255,255,255,.12)}}
[data-theme="dark"]{{--bg1:var(--nightA);--bg2:var(--nightB);--card:#0b1222;--text:#f8fafc;--muted:#cbd5f5;--shadow:rgba(0,0,0,.62);--glass:rgba(11,18,34,.78);--glassBorder:rgba(255,255,255,.1);--ring:rgba(85,214,255,.28)}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{min-height:100vh;display:flex;justify-content:center;align-items:flex-start;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial;color:var(--text);
padding:16px;background:radial-gradient(1200px 800px at 20% 20%,var(--bg1),transparent 60%),
radial-gradient(1200px 800px at 80% 80%,var(--bg2),transparent 60%),linear-gradient(135deg,var(--bg1),var(--bg2));
background-attachment:fixed}}
.card{{width:100%;max-width:980px;background:color-mix(in srgb,var(--card) 92%,transparent);backdrop-filter:blur(10px);
border-radius:20px;padding:18px;border:1px solid color-mix(in srgb,var(--card) 70%,transparent);box-shadow:0 20px 50px var(--shadow);margin-top:10px}}
.nav{{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:10px;border-radius:16px;background:var(--glass);border:1px solid var(--glassBorder);
box-shadow:0 10px 22px var(--shadow);margin-bottom:14px;flex-wrap:wrap}}
.brand{{display:flex;align-items:center;gap:10px;font-weight:950}}
.logo{{width:34px;height:34px;border-radius:12px;display:grid;place-items:center;background:linear-gradient(135deg,var(--pink1),var(--blue1));
box-shadow:0 10px 18px var(--shadow)}}
.badge{{display:inline-block;padding:6px 12px;border-radius:14px;font-size:12px;font-weight:900;background:linear-gradient(135deg,var(--pink1),var(--pink2));
color:var(--text);text-decoration:none}}
.right{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
.toggle{{display:inline-flex;align-items:center;gap:10px;padding:8px 10px;border-radius:14px;background:color-mix(in srgb,var(--glass) 85%,transparent);
border:1px solid var(--glassBorder);cursor:pointer;user-select:none;outline:none}}
.switch{{width:46px;height:26px;border-radius:999px;position:relative;background:color-mix(in srgb,var(--text) 15%,transparent);box-shadow:inset 0 0 0 2px color-mix(in srgb,var(--text) 12%,transparent)}}
.knob{{width:22px;height:22px;border-radius:999px;position:absolute;top:2px;left:2px;background:var(--card);transition:left .18s ease;box-shadow:0 8px 16px var(--shadow)}}
[data-theme="dark"] .knob{{left:calc(100% - 22px - 2px)}}
h1{{margin:10px 0 6px;font-size:28px;letter-spacing:-.02em}}
p{{margin:0 0 14px;color:var(--muted);line-height:1.6}}
.msg{{margin-bottom:14px;padding:12px 14px;border-radius:16px;background:var(--glass);border:1px solid var(--glassBorder);font-weight:900}}
.tableWrap{{overflow:auto;border-radius:16px;border:1px solid color-mix(in srgb,var(--text) 12%,transparent);background:color-mix(in srgb,var(--card) 86%,transparent)}}
table{{width:100%;border-collapse:collapse;min-width:720px}}
th{{text-align:left;padding:10px 12px;border-bottom:1px solid rgba(0,0,0,.12);font-size:12px;letter-spacing:.02em;text-transform:uppercase;color:var(--muted)}}
</style>
</head>
<body>
  <div class="card">
    <div class="nav">
      <div class="brand"><div class="logo">📚</div><div>Admin Quotes</div></div>
      <div class="right">
        <a class="badge" href="/">🏠 Home</a>
        <a class="badge" href="/admin/logout">🚪 Logout</a>
        <div class="toggle" id="themeToggle" title="Toggle dark mode" role="button" tabindex="0" aria-pressed="false">
          <span id="themeIcon">☀️</span><div class="switch"><div class="knob"></div></div>
        </div>
      </div>
    </div>

    {msg_block}

    <h1>All Quotes 💖</h1>
    <p>Total: <b>{len(data)}</b> quotes</p>

    <div class="tableWrap">
      <table>
        <thead>
          <tr>
            <th>Quote</th>
            <th>Author</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>
  </div>

<script>
const root=document.documentElement,toggle=document.getElementById("themeToggle"),icon=document.getElementById("themeIcon");
function applyTheme(t){{
  const e=t==="dark";
  e?root.setAttribute("data-theme","dark"):root.removeAttribute("data-theme");
  icon.textContent=e?"🌙":"☀️";
  try{{localStorage.setItem("theme",e?"dark":"light")}}catch(_{{}}){{}}
  toggle.setAttribute("aria-pressed",String(e));
}}
const saved=(()=>{{try{{return localStorage.getItem("theme")}}catch(e){{return null}}}})();
applyTheme(saved==="dark"?"dark":"light");
toggle.addEventListener("click",()=>{{const t=root.getAttribute("data-theme")==="dark";applyTheme(t?"light":"dark")}});
toggle.addEventListener("keydown",e=>{{if(e.key==="Enter"||e.key===" "){{e.preventDefault();toggle.click()}}}});
</script>
</body>
</html>
"""

# ============================================================
# HOME (Original UI)
# ============================================================

@app.route("/")
def home():
    try:
        quotes = load_quotes()
        if not quotes:
            quote, author = "Stay positive! ✨", "Unknown"
        else:
            quote, author = random.choice(quotes)

        msg = (request.args.get("msg") or "").strip()

        mascot_path = os.path.join(IMAGES_DIR, "meow.jpg")
        mascot_img_tag = (
            '<img src="/images/meow.jpg" alt="cat"/>'
            if os.path.isfile(mascot_path)
            else '<div style="font-size:clamp(60px,12vw,80px)"></div>'
        )

        html = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes"/>
<title> Motiall</title>
<script>
(function(){
  try{
    const t=localStorage.getItem("theme");
    if(t==="dark") document.documentElement.setAttribute("data-theme","dark");
  }catch(e){}
})();
</script>
<style>
:root{--bg1:#ffd6e8;--bg2:#e0f7fa;--card:#fff;--text:#2b2b2b;--muted:#5a5a5a;--shadow:rgba(0,0,0,.18);--glass:rgba(255,255,255,.72);--glassBorder:rgba(255,255,255,.45);--ring:rgba(255,111,145,.35);--pink1:#ffb3c7;--pink2:#ffd6e8;--blue1:#b9f3ff;--blue2:#e0f7fa;--nightA:#0b1022;--nightB:#1a1140;--nightC:#022b3a;--stars:rgba(255,255,255,.12)}
[data-theme="dark"]{--bg1:var(--nightA);--bg2:var(--nightB);--card:#0b1222;--text:#f8fafc;--muted:#cbd5f5;--shadow:rgba(0,0,0,.62);--glass:rgba(11,18,34,.78);--glassBorder:rgba(255,255,255,.1);--ring:rgba(85,214,255,.28)}
*{box-sizing:border-box;margin:0;padding:0}
html{overflow-x:hidden;overflow-y:auto;min-height:100vh}
html,body,.card,.nav,.quoteCard,.mascot,textarea,input,.btn,.footer,.msg,.toggle{transition:background-color .35s ease,color .35s ease,border-color .35s ease,box-shadow .35s ease,filter .35s ease,transform .2s ease}
body{min-height:100vh;display:flex;flex-direction:column;justify-content:flex-start;align-items:center;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial;color:var(--text);padding:clamp(12px,3vw,20px) clamp(12px,2.5vw,18px);background:radial-gradient(1200px 800px at 20% 20%,var(--bg1),transparent 60%),radial-gradient(1200px 800px at 80% 80%,var(--bg2),transparent 60%),linear-gradient(135deg,var(--bg1),var(--bg2));background-attachment:fixed}
[data-theme="dark"] body{background:radial-gradient(900px 600px at 20% 15%,rgba(120,90,255,.25),transparent 60%),radial-gradient(900px 600px at 80% 85%,rgba(0,200,255,.15),transparent 60%),radial-gradient(1200px 800px at 50% 50%,rgba(255,255,255,.06),transparent 65%),linear-gradient(135deg,var(--nightA),var(--nightB) 45%,var(--nightC));background-attachment:fixed}
.stars{position:fixed;inset:0;pointer-events:none;z-index:0;background:
radial-gradient(circle at 12% 20%,var(--stars) 0 1px,transparent 2px),
radial-gradient(circle at 25% 70%,var(--stars) 0 1px,transparent 2px),
radial-gradient(circle at 44% 35%,var(--stars) 0 1px,transparent 2px),
radial-gradient(circle at 58% 18%,var(--stars) 0 1px,transparent 2px),
radial-gradient(circle at 77% 58%,var(--stars) 0 1px,transparent 2px),
radial-gradient(circle at 88% 28%,var(--stars) 0 1px,transparent 2px),
radial-gradient(circle at 10% 88%,var(--stars) 0 1px,transparent 2px),
radial-gradient(circle at 92% 86%,var(--stars) 0 1px,transparent 2px);
opacity:0;transition:opacity .35s ease}
[data-theme="dark"] .stars{opacity:1}
.petal{position:fixed;font-size:clamp(16px,3vw,22px);opacity:.88;animation:fall linear infinite;user-select:none;pointer-events:none;z-index:1}
@keyframes fall{0%{top:-5%;transform:translateX(0) rotate(0deg)}100%{top:110%;transform:translateX(10px) rotate(360deg)}}
.card{width:100%;max-width:940px;background:color-mix(in srgb,var(--card) 92%,transparent);backdrop-filter:blur(10px);border-radius:clamp(16px,3vw,24px);padding:clamp(16px,3vw,22px) clamp(14px,2.5vw,18px) clamp(14px,2.5vw,18px);border:1px solid color-mix(in srgb,var(--card) 70%,transparent);box-shadow:0 20px 50px var(--shadow);animation:enter .75s ease;position:relative;z-index:10}
@keyframes enter{0%{transform:translateY(10px) scale(.98);opacity:0}100%{transform:translateY(0) scale(1);opacity:1}}
.nav{display:flex;align-items:center;justify-content:space-between;gap:clamp(10px,2vw,14px);padding:clamp(8px,1.5vw,10px) clamp(10px,2vw,12px);border-radius:clamp(14px,2.5vw,18px);background:var(--glass);border:1px solid var(--glassBorder);box-shadow:0 10px 22px var(--shadow);margin-bottom:clamp(12px,2vw,16px);flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:clamp(8px,1.5vw,10px);font-weight:950;font-size:clamp(14px,2vw,16px);flex:1;min-width:0}
.brand>div:last-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.logo{width:clamp(28px,5vw,34px);height:clamp(28px,5vw,34px);flex-shrink:0;border-radius:clamp(10px,2vw,12px);display:grid;place-items:center;background:linear-gradient(135deg,var(--pink1),var(--blue1));box-shadow:0 10px 18px var(--shadow);animation:wiggle 2.8s ease-in-out infinite;font-size:clamp(16px,3vw,20px)}
@keyframes wiggle{0%,100%{transform:rotate(-2deg)}50%{transform:rotate(2deg)}}
.toggle{display:inline-flex;align-items:center;gap:clamp(8px,1.5vw,10px);padding:clamp(7px,1.5vw,9px) clamp(8px,1.5vw,10px);border-radius:clamp(12px,2vw,14px);background:color-mix(in srgb,var(--glass) 85%,transparent);border:1px solid var(--glassBorder);cursor:pointer;user-select:none;outline:none;font-size:clamp(14px,2vw,16px);flex-shrink:0}
@media(hover:hover){.toggle:hover{transform:translateY(-1px)}}
.toggle:active{transform:scale(.98)}
.switch{width:clamp(40px,8vw,46px);height:clamp(22px,4.5vw,26px);border-radius:999px;position:relative;background:color-mix(in srgb,var(--text) 15%,transparent);box-shadow:inset 0 0 0 2px color-mix(in srgb,var(--text) 12%,transparent)}
.knob{width:clamp(18px,4vw,22px);height:clamp(18px,4vw,22px);border-radius:999px;position:absolute;top:2px;left:2px;background:var(--card);transition:left .18s ease;box-shadow:0 8px 16px var(--shadow)}
[data-theme="dark"] .knob{left:calc(100% - clamp(18px,4vw,22px) - 2px)}
.hero{display:grid;grid-template-columns:1fr;gap:clamp(14px,2.5vw,18px);width:100%}
@media (min-width:761px){.hero{grid-template-columns:1.2fr .8fr}}
h1{margin:clamp(8px,1.5vw,10px) 0 clamp(4px,1vw,6px);font-size:clamp(24px,5.5vw,42px);letter-spacing:-.02em;line-height:1.2}
p{margin:0 0 clamp(10px,2vw,14px);color:var(--muted);line-height:1.6;font-size:clamp(14px,2vw,16px)}
.quoteCard{padding:clamp(16px,3vw,20px) clamp(14px,2.5vw,18px);border-radius:clamp(16px,3vw,20px);background:var(--glass);border:1px solid var(--glassBorder);box-shadow:0 16px 28px var(--shadow)}
.quote{font-size:clamp(17px,4vw,24px);font-weight:900;line-height:1.4;overflow-wrap:anywhere;word-break:break-word;hyphens:auto}
.author{margin-top:clamp(10px,2vw,12px);font-weight:850;color:var(--muted);font-size:clamp(13px,2vw,15px)}
.btnRow{display:flex;flex-wrap:wrap;gap:clamp(8px,1.5vw,10px);margin-top:clamp(12px,2.5vw,14px)}
.btn{border:0;padding:clamp(11px,2.2vw,13px) clamp(14px,3vw,18px);border-radius:clamp(12px,2.5vw,16px);font-weight:950;cursor:pointer;box-shadow:0 10px 22px var(--shadow);transition:transform .12s ease,box-shadow .12s ease;outline:none;background:linear-gradient(135deg,var(--pink1),var(--pink2));font-size:clamp(13px,2vw,15px);white-space:nowrap;flex:1;min-width:120px}
@media(hover:hover){.btn:hover{transform:translateY(-3px)}}
.btn:active{transform:scale(.98)}
.btn:focus{box-shadow:0 0 0 4px var(--ring),0 10px 22px var(--shadow)}
.btn.secondary{background:linear-gradient(135deg,var(--blue1),var(--blue2))}
.mascot{border-radius:clamp(16px,3vw,22px);background:linear-gradient(135deg,color-mix(in srgb,var(--blue1) 55%,transparent),color-mix(in srgb,var(--pink1) 55%,transparent));border:1px solid color-mix(in srgb,var(--card) 55%,transparent);box-shadow:0 16px 28px var(--shadow);padding:clamp(14px,3vw,18px);display:flex;flex-direction:column;justify-content:center;align-items:center;gap:clamp(10px,2vw,12px);min-height:auto}
.mascot img{width:100%;max-width:280px;height:auto;border-radius:clamp(14px,2.5vw,18px);box-shadow:0 18px 30px var(--shadow)}
.tip{font-weight:900;color:var(--muted);text-align:center;font-size:clamp(13px,2vw,15px);line-height:1.4}
.form{width:100%;display:grid;gap:clamp(10px,2vw,12px);margin-top:clamp(8px,1.5vw,10px)}
textarea,input{width:100%;padding:clamp(11px,2.2vw,13px);border-radius:clamp(12px,2.5vw,16px);border:1px solid color-mix(in srgb,var(--text) 18%,transparent);background:color-mix(in srgb,var(--card) 82%,transparent);color:var(--text);font:inherit;outline:none;font-size:clamp(14px,2vw,16px)}
textarea{min-height:clamp(80px,16vw,100px);resize:vertical}
.msg{margin-bottom:clamp(12px,2.5vw,16px);padding:clamp(10px,2vw,12px) clamp(12px,2.5vw,14px);border-radius:clamp(12px,2.5vw,16px);background:var(--glass);border:1px solid var(--glassBorder);font-weight:900;color:var(--text);font-size:clamp(13px,2vw,15px)}
.footer{margin-top:clamp(12px,2.5vw,16px);padding-top:clamp(10px,2vw,12px);border-top:1px solid color-mix(in srgb,var(--text) 8%,transparent);display:flex;flex-wrap:wrap;justify-content:center;gap:clamp(8px,1.5vw,10px);color:color-mix(in srgb,var(--muted) 85%,transparent);font-size:clamp(12px,1.8vw,14px);text-align:center}
@media (max-width:480px){.btnRow{flex-direction:column}.btn{min-width:0;width:100%}}
@media (prefers-reduced-motion: reduce){*,*::before,*::after{animation-duration:.01ms !important;animation-iteration-count:1 !important;transition-duration:.01ms !important}}
</style>
</head>
<body>
<div class="stars"></div>
<div class="petal" style="left:12%;animation-duration:9s">🌸</div>
<div class="petal" style="left:28%;animation-duration:12s">🌸</div>
<div class="petal" style="left:46%;animation-duration:10s">🌸</div>
<div class="petal" style="left:64%;animation-duration:13s">🌸</div>
<div class="petal" style="left:82%;animation-duration:11s">🌸</div>

<div class="card">
  <div class="nav">
    <div class="brand"><div class="logo">🎀</div><div>Motivation</div></div>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
      <div class="toggle" id="themeToggle" title="Toggle dark mode" role="button" tabindex="0" aria-pressed="false">
        <span id="themeIcon">☀️</span><div class="switch"><div class="knob"></div></div>
      </div>
      <a href="/admin/login" style="text-decoration:none;font-weight:900;font-size:12px;color:var(--muted)">Admin</a>
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
      __MASCOT__
      <div class="tip">Add your own quote below ✨</div>
      <form class="form" id="addForm" method="POST" action="/add-json">
        <textarea id="quoteInput" name="quote" placeholder="Write a new motivational quote..." required></textarea>
        <input id="authorInput" name="author" placeholder="Author (optional)"/>
        <button class="btn" type="submit">🌸 Save quote</button>
      </form>
    </div>
  </div>

  <div class="footer">
    <div>💌 <span id="quoteCount">__COUNT__</span> quotes stored</div>
  </div>
</div>

<script>
const root=document.documentElement,toggle=document.getElementById("themeToggle"),icon=document.getElementById("themeIcon");
function applyTheme(t){
  const e=t==="dark";
  e?root.setAttribute("data-theme","dark"):root.removeAttribute("data-theme");
  icon.textContent=e?"🌙":"☀️";
  try{localStorage.setItem("theme",e?"dark":"light")}catch(_){}
  toggle.setAttribute("aria-pressed",String(e));
}
const saved=(()=>{try{return localStorage.getItem("theme")}catch(e){return null}})();
applyTheme(saved==="dark"?"dark":"light");
toggle.addEventListener("click",()=>{const t=root.getAttribute("data-theme")==="dark";applyTheme(t?"light":"dark")});
toggle.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();toggle.click()}});

let QUOTES=__QUOTES_JSON__;
const quoteText=document.getElementById("quoteText"),quoteAuthor=document.getElementById("quoteAuthor");
document.getElementById("btnNew").addEventListener("click",()=>{
  const [t,a]=QUOTES[Math.floor(Math.random()*QUOTES.length)];
  quoteText.textContent=`"${t}"`;quoteAuthor.textContent=`— ${a}`;
});
document.getElementById("btnCopy").addEventListener("click",async()=>{
  const t=`${quoteText.textContent} ${quoteAuthor.textContent}`;
  try{await navigator.clipboard.writeText(t);alert("Copied! 💖")}catch(e){alert("Copy failed 😿")}
});

const addForm=document.getElementById("addForm"),quoteInput=document.getElementById("quoteInput"),authorInput=document.getElementById("authorInput");
addForm.addEventListener("submit",async e=>{
  e.preventDefault();
  const fd=new FormData(addForm);
  try{
    const r=await fetch("/add-json",{method:"POST",body:fd});
    const o=await r.json();
    if(!r.ok||!o.ok){alert(o.message||"Failed 😿");return}
    QUOTES.push([o.quote,o.author]);
    quoteText.textContent=`"${o.quote}"`;
    quoteAuthor.textContent=`— ${o.author}`;
    document.getElementById("quoteCount").textContent=`${QUOTES.length}`;
    quoteInput.value="";authorInput.value="";
    alert(o.message||"Saved! 🌸");
  }catch(err){alert("Network error 😿")}
});
</script>
</body>
</html>
        """

        msg_block = f'<div class="msg">✨ {msg}</div>' if msg else ""
        html = html.replace("__MSG_BLOCK__", msg_block)
        html = html.replace("__QUOTE__", quote).replace("__AUTHOR__", author)
        html = html.replace("__COUNT__", str(len(quotes)))
        html = html.replace("__MASCOT__", mascot_img_tag)

        quotes_json = json.dumps(quotes, ensure_ascii=False)
        html = html.replace("__QUOTES_JSON__", quotes_json)

        return html

    except Exception as e:
        return f"Error: {str(e)}", 500


# Local run (NOT used on Vercel)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

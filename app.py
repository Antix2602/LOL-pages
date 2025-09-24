from flask import Flask, request, redirect, url_for, session, render_template_string, abort, send_file
import sqlite3, os, io, csv, html
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("LOL_PAGE_SECRET") or "zmien_to_na_coś_bezpiecznego"
DB = os.environ.get("DB_PATH") or "/var/data/app.db"

BAD_WORDS = {"kurwa","chuj","pierdole","jebany","debil","suka","idiota"}

def get_conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    first = not os.path.exists(DB)
    con = get_conn()
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS schools (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      student_limit INTEGER DEFAULT 0,
      created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      password TEXT NOT NULL,
      role TEXT NOT NULL,
      school_id INTEGER,
      created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS threads (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      content TEXT NOT NULL,
      user_id INTEGER,
      school_id INTEGER,
      created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS posts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      thread_id INTEGER NOT NULL,
      content TEXT NOT NULL,
      user_id INTEGER,
      created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    con.commit()
    con.close()

init_db()

def fetch(sql, params=(), one=False):
    c = get_conn()
    cur = c.execute(sql, params)
    rows = cur.fetchall()
    c.close()
    return (rows[0] if rows else None) if one else rows

def run(sql, params=()):
    c = get_conn()
    cur = c.execute(sql, params)
    last = cur.lastrowid
    c.commit()
    c.close()
    return last

def esc_filter(text):
    if text is None:
        return "", False
    s = str(text)
    low = s.lower()
    for w in BAD_WORDS:
        if w in low:
            return "Treść nie jest ładna 🚫", True
    return html.escape(s).replace("\n","<br>"), False

def layout(content, title="LOL page"):
    css = """
    <style>
    :root{--bg:#05060a;--card:#0d1117;--muted:#9aa4b2;--accent:#ffd166}
    *{box-sizing:border-box}
    body{margin:0;background:var(--bg);color:#fff;font-family:Inter,system-ui,Segoe UI,Arial;}
    .topbar{background:linear-gradient(90deg,#08101a,#05111a);padding:14px 18px;border-bottom:1px solid rgba(255,255,255,0.03)}
    .container{max-width:1100px;margin:22px auto;padding:0 16px}
    .brand{font-weight:800;color:var(--accent);font-size:1.15rem}
    .navlinks a{color:#fff;text-decoration:none;margin-right:14px;font-weight:600}
    .card{background:linear-gradient(180deg,rgba(255,255,255,0.02),rgba(255,255,255,0.01));padding:20px;border-radius:12px;border:1px solid rgba(255,255,255,0.03);box-shadow:0 8px 20px rgba(0,0,0,0.6)}
    .row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
    input,textarea,select{background:#02040a;border:1px solid rgba(255,255,255,0.03);color:#fff;padding:10px;border-radius:10px;width:100%;outline:none}
    textarea{min-height:110px;resize:vertical}
    .btn{display:inline-block;padding:10px 14px;border-radius:10px;border:none;cursor:pointer;font-weight:700}
    .btn-eq{width:140px;text-align:center}
    .btn-primary{background:#06b6d4;color:#021124}
    .btn-success{background:#34d399;color:#042014}
    .btn-warning{background:#f59e0b;color:#161100}
    .btn-danger{background:#fb7185;color:#2a0210}
    .muted{color:var(--muted)}
    .thread,.post,.spot{background:var(--card);padding:14px;border-radius:10px;margin-bottom:12px;border:1px solid rgba(255,255,255,0.02)}
    .title-link{color:var(--accent);text-decoration:none;font-weight:700}
    .flex-between{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
    h1,h2,h3{text-align:center;margin:8px 0}
    @media(max-width:720px){ .row{flex-direction:column} .btn-eq{width:100%} }
    </style>
    """
    header = f"""
    <!doctype html><html lang='pl'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
    <title>{html.escape(title)}</title>{css}</head><body>
    <div class='topbar'><div class='container'><div class='flex-between'><div class='brand'>😂 LOL page</div><div class='navlinks'><a href='/'>Forum</a><a href='/schools'>Schools</a><a href='/search'>Szukaj</a></div><div>{('<span class=\"muted\">Zalogowany: <b>' + html.escape(session.get('username')) + '</b></span> <a class=\"btn btn-warning btn-eq\" href=\"/logout\">Wyloguj</a>') if session.get('user_id') else ('<a class=\"btn btn-primary btn-eq\" href=\"/login\">Zaloguj</a> <a class=\"btn btn-success btn-eq\" href=\"/register\">Rejestracja</a>')}</div></div></div></div>
    <div class='container'><div class='card'>
    """
    footer = "</div></div></body></html>"
    return header + content + footer

@app.route("/")
def index():
    q = (request.args.get("q") or "").strip()
    sql = "SELECT th.*, u.username FROM threads th LEFT JOIN users u ON th.user_id=u.id WHERE th.school_id IS NULL"
    params = ()
    if q:
        sql += " AND (th.title LIKE ? OR th.content LIKE ?)"
        params = (f"%{q}%", f"%{q}%")
    sql += " ORDER BY th.created DESC"
    rows = fetch(sql, params)
    out = "<h2>Forum publiczne</h2>"
    out += "<div class='flex-between' style='margin:12px 0'>"
    out += ("<a class='btn btn-success btn-eq' href='/thread/new'>➕ Nowy wątek</a>" if session.get("user_id") else "<span class='muted'>Zaloguj, aby dodawać</span>")
    out += "<div><a class='btn btn-warning btn-eq' href='/schools'>Spotted szkół</a></div></div>"
    out += "<div style='margin:12px 0'><form method='get' action='/' class='row'><input name='q' placeholder='Szukaj w wątkach...' value='" + html.escape(q) + "'><button class='btn btn-primary btn-eq' type='submit'>Szukaj</button></form></div>"
    for r in rows:
        disp, bad = esc_filter(r["content"])
        out += "<div class='thread'><div class='flex-between'><a class='title-link' href='/thread/" + str(r["id"]) + "'>" + html.escape(r["title"]) + "</a><span class='muted'>" + str(r["created"]) + "</span></div>"
        out += "<p>" + disp + "</p>"
        out += "<div class='muted'>Autor: " + html.escape(r["username"] or "Anon") + "</div>"
        if session.get("user_id") and session.get("user_id")==r["user_id"]:
            out += "<div style='margin-top:8px'><a class='btn btn-warning btn-eq' href='/thread/" + str(r["id"]) + "/edit'>Edytuj</a> <a class='btn btn-danger btn-eq' href='/thread/" + str(r["id"]) + "/delete'>Usuń</a></div>"
        out += "</div>"
    return layout(out, title="Forum")

@app.route("/thread/new", methods=["GET","POST"])
def thread_new():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        if not title:
            return layout("<div class='muted'>Tytuł wymagany</div>")
        run("INSERT INTO threads (title, content, user_id, school_id) VALUES (?,?,?,NULL)", (title, content, session["user_id"]))
        return redirect("/")
    form = "<h2>Nowy wątek</h2><form method='post'><input name='title' placeholder='Tytuł' required><textarea name='content' placeholder='Treść'></textarea><div style='margin-top:8px'><button class='btn btn-success btn-eq'>Dodaj</button></div></form>"
    return layout(form, title="Nowy wątek")

@app.route("/thread/<int:tid>", methods=["GET","POST"])
def thread_view(tid):
    th = fetch("SELECT th.*, u.username FROM threads th LEFT JOIN users u ON th.user_id=u.id WHERE th.id=?", (tid,), one=True)
    if not th:
        return layout("<div class='muted'>Wątek nie znaleziony</div>")
    if th["school_id"] is not None:
        return redirect(f"/schools/thread/{tid}")
    if request.method == "POST":
        if "user_id" not in session:
            return redirect(url_for("login"))
        content = (request.form.get("content") or "").strip()
        if content:
            run("INSERT INTO posts (thread_id, content, user_id) VALUES (?,?,?)", (tid, content, session["user_id"]))
            return redirect(f"/thread/{tid}")
    posts = fetch("SELECT p.*, u.username FROM posts p LEFT JOIN users u ON p.user_id=u.id WHERE p.thread_id=? ORDER BY p.created", (tid,))
    disp_main, bad_main = esc_filter(th["content"])
    out = f"<h2>{html.escape(th['title'])}</h2><p>{disp_main}</p><div class='muted'>Autor: {html.escape(th['username'] or 'Anon')} • {th['created']}</div><hr>"
    out += "<h3>Odpowiedzi</h3>"
    for p in posts:
        pd, _ = esc_filter(p["content"])
        out += "<div class='post'><p>" + pd + "</p><div class='muted'>Autor: " + html.escape(p["username"] or "Anon") + " • " + str(p["created"]) + "</div>"
        if session.get("user_id") and session.get("user_id")==p["user_id"]:
            out += "<div style='margin-top:8px'><a class='btn btn-warning btn-eq' href='/post/" + str(p["id"]) + "/edit'>Edytuj</a> <a class='btn btn-danger btn-eq' href='/post/" + str(p["id"]) + "/delete'>Usuń</a></div>"
        out += "</div>"
    if session.get("user_id"):
        out += "<form method='post'><textarea name='content' placeholder='Twoja odpowiedź'></textarea><div style='margin-top:8px'><button class='btn btn-primary btn-eq'>Odpowiedz</button></div></form>"
    else:
        out += "<div class='muted'>Zaloguj się, aby odpowiadać</div>"
    return layout(out, title=th["title"])

@app.route("/thread/<int:tid>/edit", methods=["GET","POST"])
def thread_edit(tid):
    th = fetch("SELECT * FROM threads WHERE id=?", (tid,), one=True)
    if not th or session.get("user_id") != th["user_id"]:
        abort(403)
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        if title:
            run("UPDATE threads SET title=?, content=? WHERE id=?", (title, content, tid))
            return redirect(f"/thread/{tid}")
    form = f"<h2>Edycja wątku</h2><form method='post'><input name='title' value=\"{html.escape(th['title'])}\"><textarea name='content'>{html.escape(th['content'])}</textarea><div style='margin-top:8px'><button class='btn btn-warning btn-eq'>Zapisz</button></div></form>"
    return layout(form, title="Edycja wątku")

@app.route("/thread/<int:tid>/delete")
def thread_delete(tid):
    th = fetch("SELECT * FROM threads WHERE id=?", (tid,), one=True)
    if not th or session.get("user_id") != th["user_id"]:
        abort(403)
    run("DELETE FROM posts WHERE thread_id=?", (tid,))
    run("DELETE FROM threads WHERE id=?", (tid,))
    return redirect("/")

@app.route("/post/<int:pid>/edit", methods=["GET","POST"])
def post_edit(pid):
    p = fetch("SELECT * FROM posts WHERE id=?", (pid,), one=True)
    if not p or session.get("user_id") != p["user_id"]:
        abort(403)
    if request.method == "POST":
        content = (request.form.get("content") or "").strip()
        if content:
            run("UPDATE posts SET content=? WHERE id=?", (content, pid))
            return redirect(f"/thread/{p['thread_id']}")
    form = f"<h2>Edycja posta</h2><form method='post'><textarea name='content'>{html.escape(p['content'])}</textarea><div style='margin-top:8px'><button class='btn btn-warning btn-eq'>Zapisz</button></div></form>"
    return layout(form, title="Edycja posta")

@app.route("/post/<int:pid>/delete")
def post_delete(pid):
    p = fetch("SELECT * FROM posts WHERE id=?", (pid,), one=True)
    if not p or session.get("user_id") != p["user_id"]:
        abort(403)
    run("DELETE FROM posts WHERE id=?", (pid,))
    return redirect(f"/thread/{p['thread_id']}")

@app.route("/register", methods=["GET","POST"])
def register():
    msg = ""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "")
        if not username or not password:
            msg = "Wypełnij pola"
        else:
            try:
                run("INSERT INTO users (username,password,role,school_id) VALUES (?,?,?,NULL)", (username, generate_password_hash(password), "user"))
                return redirect("/login")
            except Exception:
                msg = "Nazwa zajęta"
    form = f"<h2>Rejestracja</h2><form method='post'><input name='username' placeholder='Login'><div class='row'><input id='rpass' type='password' name='password' placeholder='Hasło'><button type='button' class='btn btn-eq btn-primary' onclick=\"document.getElementById('rpass').type=(document.getElementById('rpass').type==='password'?'text':'password')\">👁</button></div><div style='margin-top:8px'><button class='btn btn-success btn-eq'>Zarejestruj</button></div></form><div class='muted'>" + html.escape(msg) + "</div>"
    return layout(form, title="Rejestracja")

@app.route("/login", methods=["GET","POST"])
def login():
    msg = ""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "")
        u = fetch("SELECT * FROM users WHERE username=?", (username,), one=True)
        if u and check_password_hash(u["password"], password):
            session["user_id"] = u["id"]
            session["username"] = u["username"]
            session["role"] = u["role"]
            session["school_id"] = u["school_id"]
            if u["role"] == "teacher":
                return redirect("/teacher/dashboard")
            if u["role"] == "student":
                return redirect("/student/dashboard")
            return redirect("/")
        msg = "Błędny login lub hasło"
    form = f"<h2>Logowanie</h2><form method='post'><input name='username' placeholder='Login'><div class='row'><input id='lpass' type='password' name='password' placeholder='Hasło'><button type='button' class='btn btn-eq btn-primary' onclick=\"document.getElementById('lpass').type=(document.getElementById('lpass').type==='password'?'text':'password')\">👁</button></div><div style='margin-top:8px'><button class='btn btn-success btn-eq'>Zaloguj</button></div></form><div class='muted'>" + html.escape(msg) + "</div>"
    return layout(form, title="Logowanie")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/profile", methods=["GET","POST"])
def profile():
    if "user_id" not in session:
        return redirect("/login")
    msg = ""
    if request.method == "POST":
        if request.form.get("action") == "change_password":
            old = (request.form.get("old") or "")
            new = (request.form.get("new") or "")
            u = fetch("SELECT * FROM users WHERE id=?", (session["user_id"],), one=True)
            if not u or not check_password_hash(u["password"], old):
                msg = "Błędne stare hasło"
            else:
                run("UPDATE users SET password=? WHERE id=?", (generate_password_hash(new), session["user_id"]))
                msg = "Zmieniono hasło"
    u = fetch("SELECT * FROM users WHERE id=?", (session["user_id"],), one=True)
    out = f"<h2>Profil: {html.escape(u['username'])}</h2><p class='muted'>Rola: {html.escape(u['role'])} • Szkoła: {html.escape(str(u['school_id'])) if u['school_id'] else 'Brak'}</p>"
    out += "<hr><h3>Zmiana hasła</h3><form method='post'><input type='hidden' name='action' value='change_password'><input name='old' type='password' placeholder='Stare hasło'><input name='new' type='password' placeholder='Nowe hasło'><div style='margin-top:8px'><button class='btn btn-warning btn-eq'>Zmień</button></div></form>"
    out += "<div class='muted'>" + html.escape(msg) + "</div>"
    return layout(out, title="Profil")

@app.route("/schools")
def schools_index():
    rows = fetch("SELECT * FROM schools ORDER BY created DESC")
    out = "<h2>LOL page for schools</h2><div style='margin:12px 0'><a class='btn btn-success btn-eq' href='/schools/register'>➕ Rejestracja szkoły</a> <a class='btn btn-primary btn-eq' href='/schools/login'>Logowanie szkoła</a></div>"
    for r in rows:
        out += f"<div class='thread'><div class='flex-between'><div><a class='title-link' href='/schools/spotted/{r['id']}'>{html.escape(r['name'])}</a><div class='muted'>Limit: {r['student_limit']}</div></div><div><a class='btn btn-eq' href='/schools/spotted/{r['id']}'>Spotted</a></div></div></div>"
    if not rows:
        out += "<div class='muted'>Brak szkół</div>"
    return layout(out, title="Schools")

@app.route("/schools/register", methods=["GET","POST"])
def schools_register():
    msg = ""
    if request.method == "POST":
        name = (request.form.get("school_name") or "").strip()
        student_limit_raw = (request.form.get("student_limit") or "0").strip()
        teacher_login = (request.form.get("teacher_login") or "").strip()
        teacher_pass = (request.form.get("teacher_pass") or "")
        try:
            student_limit = int(student_limit_raw)
        except Exception:
            student_limit = 0
        if not name or not teacher_login or not teacher_pass:
            msg = "Wypełnij pola"
        else:
            try:
                sid = run("INSERT INTO schools (name, student_limit) VALUES (?,?)", (name, student_limit))
                run("INSERT INTO users (username,password,role,school_id) VALUES (?,?,?,?)", (teacher_login, generate_password_hash(teacher_pass), "teacher", sid))
                return redirect("/schools")
            except Exception:
                msg = "Błąd: login nauczyciela zajęty lub inny problem"
    form = f"<h2>Rejestracja szkoły</h2><form method='post'><input name='school_name' placeholder='Nazwa szkoły'><input name='student_limit' placeholder='Ilu uczniów (liczba)'><input name='teacher_login' placeholder='Login nauczyciela'><div class='row'><input id='tpass' type='password' name='teacher_pass' placeholder='Hasło nauczyciela'><button type='button' class='btn btn-eq btn-primary' onclick=\"document.getElementById('tpass').type=(document.getElementById('tpass').type==='password'?'text':'password')\">👁</button></div><div style='margin-top:8px'><button class='btn btn-success btn-eq'>Zarejestruj szkołę</button></div></form><div class='muted'>" + html.escape(msg) + "</div>"
    return layout(form, title="Rejestracja szkoły")

@app.route("/schools/login", methods=["GET","POST"])
def schools_login():
    msg = ""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "")
        u = fetch("SELECT * FROM users WHERE username=? AND role IN ('teacher','student')", (username,), one=True)
        if u and check_password_hash(u["password"], password):
            session["user_id"] = u["id"]
            session["username"] = u["username"]
            session["role"] = u["role"]
            session["school_id"] = u["school_id"]
            if u["role"] == "teacher":
                return redirect("/teacher/dashboard")
            return redirect("/student/dashboard")
        msg = "Błędny login lub hasło"
    form = f"<h2>Logowanie szkoła</h2><form method='post'><input name='username' placeholder='Login'><div class='row'><input id='slpass' type='password' name='password' placeholder='Hasło'><button type='button' class='btn btn-eq btn-primary' onclick=\"document.getElementById('slpass').type=(document.getElementById('slpass').type==='password'?'text':'password')\">👁</button></div><div style='margin-top:8px'><button class='btn btn-success btn-eq'>Zaloguj</button></div></form><div class='muted'>" + html.escape(msg) + "</div>"
    return layout(form, title="Logowanie szkoła")

@app.route("/teacher/dashboard")
def teacher_dashboard():
    if session.get("role") != "teacher":
        abort(403)
    sid = session.get("school_id")
    school = fetch("SELECT * FROM schools WHERE id=?", (sid,), one=True)
    students = fetch("SELECT * FROM users WHERE school_id=? AND role='student'", (sid,))
    threads = fetch("SELECT th.*, u.username FROM threads th LEFT JOIN users u ON th.user_id=u.id WHERE th.school_id=? ORDER BY th.created DESC", (sid,))
    out = f"<h2>Panel nauczyciela — {html.escape(school['name'])}</h2>"
    out += "<h3>Dodaj ucznia</h3><form method='post' action='/teacher/add_student'><input name='login' placeholder='Login ucznia'><div class='row'><input id='spass' type='password' name='password' placeholder='Hasło'><button type='button' class='btn btn-eq btn-primary' onclick=\"document.getElementById('spass').type=(document.getElementById('spass').type==='password'?'text':'password')\">👁</button></div><div style='margin-top:8px'><button class='btn btn-success btn-eq'>Dodaj</button></div></form>"
    out += "<h3>Uczniowie</h3>"
    for s in students:
        out += f"<div class='thread'>{html.escape(s['username'])} <a class='btn btn-danger btn-eq' href='/teacher/remove_student/{s['id']}'>Usuń</a> <a class='btn btn-warning btn-eq' href='/teacher/reset_password/{s['id']}'>Resetuj hasło</a></div>"
    out += "<hr><h3>Spotted szkoły (zarządzanie)</h3>"
    for th in threads:
        disp, bad = esc_filter(th["content"])
        out += "<div class='thread'><h4>" + html.escape(th['title']) + "</h4><p>" + disp + "</p><div class='muted'>Autor: " + html.escape(th['username'] or "Anon") + " • " + str(th['created']) + "</div>"
        out += "<div style='margin-top:8px'><a class='btn btn-warning btn-eq' href='/teacher/edit_thread/" + str(th['id']) + "'>Edytuj</a> <a class='btn btn-danger btn-eq' href='/teacher/delete_thread/" + str(th['id']) + "'>Usuń</a></div>"
        posts = fetch("SELECT p.*, u.username FROM posts p LEFT JOIN users u ON p.user_id=u.id WHERE p.thread_id=? ORDER BY p.created", (th['id'],))
        for p in posts:
            pd, badp = esc_filter(p["content"])
            out += "<div class='post'>" + pd + "<div class='muted'>Autor: " + html.escape(p['username'] or "Anon") + "</div><div style='margin-top:6px'><a class='btn btn-warning btn-eq' href='/teacher/edit_post/" + str(p['id']) + "'>Edytuj</a> <a class='btn btn-danger btn-eq' href='/teacher/delete_post/" + str(p['id']) + "'>Usuń</a></div></div>"
        out += "</div><hr>"
    out += f"<div style='margin-top:12px'><a class='btn btn-primary btn-eq' href='/schools/spotted/{sid}'>Otwórz spotted</a> <a class='btn btn-eq' href='/schools/export/{sid}'>Eksport CSV</a></div>"
    return layout(out, title="Panel nauczyciela")

@app.route("/teacher/add_student", methods=["POST"])
def teacher_add_student():
    if session.get("role") != "teacher":
        abort(403)
    login = (request.form.get("login") or "").strip()
    password = (request.form.get("password") or "")
    if login and password:
        try:
            run("INSERT INTO users (username,password,role,school_id) VALUES (?,?,?,?)", (login, generate_password_hash(password), "student", session.get("school_id")))
        except Exception:
            pass
    return redirect("/teacher/dashboard")

@app.route("/teacher/remove_student/<int:uid>")
def teacher_remove_student(uid):
    if session.get("role") != "teacher":
        abort(403)
    st = fetch("SELECT * FROM users WHERE id=? AND role='student' AND school_id=?", (uid, session.get("school_id")), one=True)
    if st:
        run("DELETE FROM users WHERE id=?", (uid,))
    return redirect("/teacher/dashboard")

@app.route("/teacher/reset_password/<int:uid>", methods=["GET","POST"])
def teacher_reset_password(uid):
    if session.get("role") != "teacher":
        abort(403)
    st = fetch("SELECT * FROM users WHERE id=? AND role='student' AND school_id=?", (uid, session.get("school_id")), one=True)
    if not st:
        abort(403)
    if request.method == "POST":
        new = (request.form.get("password") or "")
        if new:
            run("UPDATE users SET password=? WHERE id=?", (generate_password_hash(new), uid))
            return redirect("/teacher/dashboard")
    form = f"<h2>Reset hasła - {html.escape(st['username'])}</h2><form method='post'><div class='row'><input id='np' type='password' name='password' placeholder='Nowe hasło'><button type='button' class='btn btn-eq btn-primary' onclick=\"document.getElementById('np').type=(document.getElementById('np').type==='password'?'text':'password')\">👁</button></div><div style='margin-top:8px'><button class='btn btn-warning btn-eq'>Zresetuj</button></div></form>"
    return layout(form, title="Reset hasła")

@app.route("/teacher/edit_thread/<int:tid>", methods=["GET","POST"])
def teacher_edit_thread(tid):
    if session.get("role") != "teacher":
        abort(403)
    th = fetch("SELECT * FROM threads WHERE id=? AND school_id=?", (tid, session.get("school_id")), one=True)
    if not th:
        abort(404)
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        if title:
            run("UPDATE threads SET title=?, content=? WHERE id=?", (title, content, tid))
            return redirect("/teacher/dashboard")
    form = f"<h2>Edytuj wpis</h2><form method='post'><input name='title' value=\"{html.escape(th['title'])}\"><textarea name='content'>{html.escape(th['content'])}</textarea><div style='margin-top:8px'><button class='btn btn-warning btn-eq'>Zapisz</button></div></form>"
    return layout(form, title="Edytuj wpis")

@app.route("/teacher/delete_thread/<int:tid>")
def teacher_delete_thread(tid):
    if session.get("role") != "teacher":
        abort(403)
    th = fetch("SELECT * FROM threads WHERE id=? AND school_id=?", (tid, session.get("school_id")), one=True)
    if th:
        run("DELETE FROM posts WHERE thread_id=?", (tid,))
        run("DELETE FROM threads WHERE id=?", (tid,))
    return redirect("/teacher/dashboard")

@app.route("/teacher/edit_post/<int:pid>", methods=["GET","POST"])
def teacher_edit_post(pid):
    if session.get("role") != "teacher":
        abort(403)
    p = fetch("SELECT p.*, th.school_id FROM posts p LEFT JOIN threads th ON p.thread_id=th.id WHERE p.id=?", (pid,), one=True)
    if not p or p["school_id"] != session.get("school_id"):
        abort(404)
    if request.method == "POST":
        content = (request.form.get("content") or "").strip()
        if content:
            run("UPDATE posts SET content=? WHERE id=?", (content, pid))
            return redirect("/teacher/dashboard")
    form = f"<h2>Edytuj komentarz</h2><form method='post'><textarea name='content'>{html.escape(p['content'])}</textarea><div style='margin-top:8px'><button class='btn btn-warning btn-eq'>Zapisz</button></div></form>"
    return layout(form, title="Edytuj komentarz")

@app.route("/teacher/delete_post/<int:pid>")
def teacher_delete_post(pid):
    if session.get("role") != "teacher":
        abort(403)
    p = fetch("SELECT p.*, th.school_id FROM posts p LEFT JOIN threads th ON p.thread_id=th.id WHERE p.id=?", (pid,), one=True)
    if p and p["school_id"] == session.get("school_id"):
        run("DELETE FROM posts WHERE id=?", (pid,))
    return redirect("/teacher/dashboard")

@app.route("/schools/spotted/<int:school_id>", methods=["GET","POST"])
def schools_spotted(school_id):
    school = fetch("SELECT * FROM schools WHERE id=?", (school_id,), one=True)
    if not school:
        return layout("<div class='muted'>Szkoła nie istnieje</div>")
    if "user_id" not in session or session.get("role") not in ("teacher","student") or session.get("school_id") != school_id:
        return layout("<h2>Spotted</h2><div class='muted'>Dostęp mają tylko uczniowie i nauczyciele tej szkoły.</div>")
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        if title and content:
            run("INSERT INTO threads (title, content, user_id, school_id) VALUES (?,?,?,?)", (title, content, session["user_id"], school_id))
            return redirect(f"/schools/spotted/{school_id}")
    rows = fetch("SELECT th.*, u.username FROM threads th LEFT JOIN users u ON th.user_id=u.id WHERE th.school_id=? ORDER BY th.created DESC", (school_id,))
    out = f"<h2>Spotted — {html.escape(school['name'])}</h2>"
    out += "<h3>Dodaj wpis</h3><form method='post'><input name='title' placeholder='Tytuł'><textarea name='content' placeholder='Treść'></textarea><div style='margin-top:8px'><button class='btn btn-success btn-eq'>Dodaj</button></div></form>"
    for r in rows:
        disp, bad = esc_filter(r["content"])
        out += "<div class='thread'><h4><a class='title-link' href='/schools/thread/" + str(r['id']) + "'>" + html.escape(r["title"]) + "</a></h4><p>" + disp + "</p><div class='muted'>Autor: " + html.escape(r["username"] or "Anon") + " • " + str(r["created"]) + "</div></div>"
    return layout(out, title=f"Spotted {school['name']}")

@app.route("/schools/thread/<int:tid>", methods=["GET","POST"])
def schools_thread(tid):
    th = fetch("SELECT th.*, u.username FROM threads th LEFT JOIN users u ON th.user_id=u.id WHERE th.id=?", (tid,), one=True)
    if not th or th["school_id"] is None:
        return layout("<div class='muted'>Wątek nie znaleziony</div>")
    if "user_id" not in session or session.get("role") not in ("teacher","student") or session.get("school_id") != th["school_id"]:
        return layout("<div class='muted'>Dostęp mają tylko uczniowie i nauczyciele tej szkoły.</div>")
    if request.method == "POST":
        content = (request.form.get("content") or "").strip()
        if content:
            run("INSERT INTO posts (thread_id, content, user_id) VALUES (?,?,?)", (tid, content, session["user_id"]))
            return redirect(f"/schools/thread/{tid}")
    posts = fetch("SELECT p.*, u.username FROM posts p LEFT JOIN users u ON p.user_id=u.id WHERE p.thread_id=? ORDER BY p.created", (tid,))
    disp, bad = esc_filter(th["content"])
    out = f"<h2>{html.escape(th['title'])}</h2><p>{disp}</p><div class='muted'>Autor: {html.escape(th['username'] or 'Anon')} • {th['created']}</div><hr>"
    for p in posts:
        pd, badp = esc_filter(p["content"])
        out += "<div class='post'><p>" + pd + "</p><div class='muted'>Autor: " + html.escape(p["username"] or "Anon") + " • " + str(p["created"]) + "</div></div>"
    out += "<form method='post'><textarea name='content' placeholder='Odpowiedz'></textarea><div style='margin-top:8px'><button class='btn btn-primary btn-eq'>Odpowiedz</button></div></form>"
    out += f"<div style='margin-top:12px'><a class='btn btn-eq' href='/schools/spotted/{th['school_id']}'>⬅ Powrót</a></div>"
    return layout(out, title=th["title"])

@app.route("/schools/export/<int:school_id>")
def schools_export(school_id):
    if session.get("role") != "teacher" or session.get("school_id") != school_id:
        abort(403)
    school = fetch("SELECT * FROM schools WHERE id=?", (school_id,), one=True)
    threads = fetch("SELECT th.*, u.username FROM threads th LEFT JOIN users u ON th.user_id=u.id WHERE th.school_id=?", (school_id,))
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["thread_id","title","content","author","created"])
    for t in threads:
        cw.writerow([t["id"], t["title"], t["content"], t["username"], t["created"]])
    output = io.BytesIO()
    output.write(si.getvalue().encode("utf-8"))
    output.seek(0)
    fname = f"{school['name'].replace(' ','_')}_export_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.csv"
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name=fname)

@app.route("/search", methods=["GET","POST"])
def search():
    q = (request.args.get("q") or request.form.get("q") or "").strip()
    if not q:
        form = "<h2>Szukaj</h2><form method='get'><input name='q' placeholder='Szukaj...'><div style='margin-top:8px'><button class='btn btn-primary btn-eq'>Szukaj</button></div></form>"
        return layout(form, title="Szukaj")
    rows = fetch("SELECT th.*, u.username FROM threads th LEFT JOIN users u ON th.user_id=u.id WHERE (th.title LIKE ? OR th.content LIKE ?) ORDER BY th.created DESC", (f"%{q}%", f"%{q}%"))
    out = f"<h2>Wyniki: {html.escape(q)}</h2>"
    for r in rows:
        disp, bad = esc_filter(r["content"])
        out += f"<div class='thread'><h4><a class='title-link' href='/thread/{r['id']}'>{html.escape(r['title'])}</a></h4><p>{disp}</p><div class='muted'>Autor: {html.escape(r['username'] or 'Anon')}</div></div>"
    if not rows:
        out += "<div class='muted'>Brak wyników</div>"
    return layout(out, title=f"Szukaj: {q}")

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)

















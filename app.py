import os
import sqlite3
from flask import Flask, render_template_string, request, redirect, session, url_for

app = Flask(__name__)
app.secret_key = "supersecret"

# Baza danych w Render
DB_DIR = os.path.join(os.getcwd(), "data")
os.makedirs(DB_DIR, exist_ok=True)
DB = os.path.join(DB_DIR, "app.db")


# ---- DB helpers ----
def get_conn():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    con = get_conn()
    cur = con.cursor()

    # Użytkownicy (wszyscy: normalni, nauczyciele, uczniowie)
    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT, -- admin, teacher, student, user
        school_id INTEGER
    )""")

    # Szkoły
    cur.execute("""CREATE TABLE IF NOT EXISTS schools(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        student_limit INTEGER
    )""")

    # Forum publiczne
    cur.execute("""CREATE TABLE IF NOT EXISTS threads(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        author_id INTEGER
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS posts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        thread_id INTEGER,
        content TEXT,
        author_id INTEGER
    )""")

    # Spotted (szkoły)
    cur.execute("""CREATE TABLE IF NOT EXISTS spotteds(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        school_id INTEGER,
        content TEXT,
        author_id INTEGER
    )""")

    con.commit()
    con.close()

init_db()

# ---- Filtr brzydkich słów ----
BAD_WORDS = ["brzydkie", "kurde", "głupi"]

def filter_content(text):
    for w in BAD_WORDS:
        if w in text.lower():
            return "Treść nie jest ładna"
    return text

# ---- Szablon HTML ----
TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>LOL Page</title>
    <style>
        body { background:#121212; color:white; font-family:sans-serif; margin:0; }
        .navbar { background:#222; padding:15px; text-align:center; }
        .navbar a { color:white; margin:0 10px; text-decoration:none; }
        h1, h2, h3 { text-align:center; }
        .container { width:80%%; margin:auto; padding:20px; }
        input, textarea, select { width:100%%; padding:10px; margin:5px 0; background:#333; color:white; border:none; }
        button { padding:10px 20px; background:#444; color:white; border:none; cursor:pointer; }
        .post, .thread, .spotted { background:#1e1e1e; padding:10px; margin:10px 0; border-radius:8px; }
    </style>
</head>
<body>
    <div class="navbar">
        <a href="/">LOL Page</a>
        <a href="/schools">LOL Page for Schools</a>
        {% if not session.get('user') %}
            <a href="/login">Login</a>
            <a href="/register">Register</a>
        {% else %}
            <span>👤 {{session['user']['username']}} ({{session['user']['role']}})</span>
            <a href="/logout">Logout</a>
        {% endif %}
    </div>
    <div class="container">
        {% block content %}{% endblock %}
    </div>
</body>
</html>
"""

# ---- Routing ----

@app.route("/")
def index():
    con = get_conn()
    cur = con.cursor()
    cur.execute("SELECT t.id, t.title, u.username FROM threads t LEFT JOIN users u ON u.id=t.author_id")
    threads = cur.fetchall()
    con.close()
    return render_template_string(TEMPLATE + """
    {% block content %}
    <h1>LOL Page (Forum Publiczne)</h1>
    <form method="post" action="/thread">
        <input name="title" placeholder="Nowy wątek" required>
        <button type="submit">Dodaj</button>
    </form>
    {% for t in threads %}
        <div class="thread">
            <a href="/thread/{{t[0]}}"><b>{{t[1]}}</b></a><br>
            <small>Author: {{t[2]}}</small>
        </div>
    {% endfor %}
    {% endblock %}
    """, threads=threads)

@app.route("/thread", methods=["POST"])
def new_thread():
    if not session.get("user"): return redirect("/login")
    title = request.form["title"]
    con = get_conn(); cur = con.cursor()
    cur.execute("INSERT INTO threads(title,author_id) VALUES(?,?)", (title, session["user"]["id"]))
    con.commit(); con.close()
    return redirect("/")

@app.route("/thread/<int:tid>", methods=["GET","POST"])
def view_thread(tid):
    if request.method=="POST":
        if not session.get("user"): return redirect("/login")
        content = filter_content(request.form["content"])
        con = get_conn(); cur = con.cursor()
        cur.execute("INSERT INTO posts(thread_id,content,author_id) VALUES(?,?,?)",
                    (tid, content, session["user"]["id"]))
        con.commit(); con.close()
    con = get_conn(); cur = con.cursor()
    cur.execute("SELECT title FROM threads WHERE id=?", (tid,))
    t = cur.fetchone()
    cur.execute("SELECT p.content,u.username FROM posts p LEFT JOIN users u ON u.id=p.author_id WHERE thread_id=?", (tid,))
    posts = cur.fetchall()
    con.close()
    return render_template_string(TEMPLATE + """
    {% block content %}
    <h2>{{t[0]}}</h2>
    <form method="post">
        <textarea name="content" placeholder="Napisz coś"></textarea>
        <button type="submit">Dodaj</button>
    </form>
    {% for p in posts %}
        <div class="post">{{p[0]}}<br><small>Author: {{p[1]}}</small></div>
    {% endfor %}
    {% endblock %}
    """, t=t, posts=posts)

# ---- Schools / Spotted ----
@app.route("/schools")
def schools():
    if not session.get("user"): return redirect("/login")
    if session["user"]["role"] not in ("teacher","student"): return "Brak dostępu"
    con = get_conn(); cur = con.cursor()
    cur.execute("SELECT s.id,s.name FROM schools s JOIN users u ON u.school_id=s.id WHERE u.id=?",(session["user"]["id"],))
    school = cur.fetchone()
    cur.execute("SELECT sp.content,u.username FROM spotteds sp LEFT JOIN users u ON u.id=sp.author_id WHERE sp.school_id=?",(school[0],))
    spotteds = cur.fetchall()
    con.close()
    return render_template_string(TEMPLATE + """
    {% block content %}
    <h1>LOL Page for Schools - {{school[1]}}</h1>
    <form method="post" action="/spotted">
        <textarea name="content" placeholder="Nowy spotted"></textarea>
        <button type="submit">Dodaj</button>
    </form>
    {% for s in spotteds %}
        <div class="spotted">{{s[0]}}<br><small>Author: {{s[1]}}</small></div>
    {% endfor %}
    {% endblock %}
    """, school=school, spotteds=spotteds)

@app.route("/spotted", methods=["POST"])
def add_spotted():
    if not session.get("user"): return redirect("/login")
    if session["user"]["role"] not in ("teacher","student"): return "Brak dostępu"
    content = filter_content(request.form["content"])
    con = get_conn(); cur = con.cursor()
    cur.execute("INSERT INTO spotteds(school_id,content,author_id) VALUES(?,?,?)",
                (session["user"]["school_id"], content, session["user"]["id"]))
    con.commit(); con.close()
    return redirect("/schools")

# ---- Register/Login ----
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        u,p = request.form["username"], request.form["password"]
        con = get_conn(); cur = con.cursor()
        cur.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)",(u,p,"user"))
        con.commit(); con.close()
        return redirect("/login")
    return render_template_string(TEMPLATE + """
    {% block content %}
    <h1>Register</h1>
    <form method="post">
        <input name="username" placeholder="Username">
        <input type="password" name="password" placeholder="Password">
        <button>Register</button>
    </form>
    {% endblock %}
    """)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u,p = request.form["username"], request.form["password"]
        con = get_conn(); cur = con.cursor()
        cur.execute("SELECT id,username,password,role,school_id FROM users WHERE username=?",(u,))
        row = cur.fetchone(); con.close()
        if row and row[2]==p:
            session["user"]={"id":row[0],"username":row[1],"role":row[3],"school_id":row[4]}
            return redirect("/")
        return "Błędny login lub hasło"
    return render_template_string(TEMPLATE + """
    {% block content %}
    <h1>Login</h1>
    <form method="post">
        <input name="username" placeholder="Username">
        <input type="password" name="password" placeholder="Password">
        <button>Login</button>
    </form>
    {% endblock %}
    """)

@app.route("/logout")
def logout():
    session.pop("user",None)
    return redirect("/")

if __name__=="__main__":
    app.run(host="0.0.0.0", port=5000)





















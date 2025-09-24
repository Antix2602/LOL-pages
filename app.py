import os
import sqlite3
from flask import Flask, request, session, redirect, url_for, render_template_string, g

app = Flask(__name__)
app.secret_key = "supersekret"

DB_PATH = os.getenv("DB_PATH", "/data/app.db")

# ===================== Baza =====================
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT CHECK(role IN ('student','teacher','guest')) NOT NULL
        );

        CREATE TABLE IF NOT EXISTS spotted (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            user_id INTEGER,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS threads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id INTEGER,
            content TEXT,
            user_id INTEGER,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(thread_id) REFERENCES threads(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
    )
    db.commit()

@app.before_request
def before_request():
    init_db()

# ===================== Widoki =====================

TEMPLATE = """
<!doctype html>
<html>
<head>
  <title>LOL Page</title>
  <style>
    body { font-family: Arial; background: #f2f2f2; margin:0; }
    .navbar { background:#222; color:white; padding:10px; text-align:center; }
    .container { width:80%%; margin:20px auto; background:white; padding:20px; border-radius:10px; }
    .post { border-bottom:1px solid #ccc; padding:5px; }
    .admin { color:red; font-weight:bold; }
  </style>
</head>
<body>
  <div class="navbar">
    <a href="{{ url_for('index') }}" style="color:white; margin:10px;">Home</a>
    <a href="{{ url_for('forum') }}" style="color:white; margin:10px;">Forum</a>
    {% if session.get('role') in ['student','teacher'] %}
      <a href="{{ url_for('spotted_page') }}" style="color:white; margin:10px;">Spotted</a>
    {% endif %}
    {% if session.get('user_id') %}
      <span style="margin-left:20px;">Zalogowany jako: {{ session.get('username') }} ({{ session.get('role') }})</span>
      <a href="{{ url_for('logout') }}" style="color:white; margin-left:20px;">Wyloguj</a>
    {% else %}
      <a href="{{ url_for('login') }}" style="color:white; margin:10px;">Logowanie</a>
    {% endif %}
  </div>
  <div class="container">
    {% block content %}{% endblock %}
  </div>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(
        TEMPLATE + """
        {% block content %}
        <h2>Witaj na LOL Page 🚀</h2>
        <p>To forum i spotted dla uczniów i nauczycieli.</p>
        {% endblock %}
        """
    )

# -------- Logowanie --------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (request.form["username"], request.form["password"]),
        ).fetchone()
        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("index"))
        return "Błędne dane!"
    return render_template_string(
        TEMPLATE + """
        {% block content %}
        <h2>Logowanie</h2>
        <form method="post">
          <input name="username" placeholder="Login"><br>
          <input name="password" placeholder="Hasło" type="password"><br>
          <button>Zaloguj</button>
        </form>
        {% endblock %}
        """
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# -------- Spotted --------
@app.route("/spotted", methods=["GET", "POST"])
def spotted_page():
    if session.get("role") not in ["student", "teacher"]:
        return "Dostęp tylko dla uczniów i nauczycieli!", 403

    db = get_db()
    if request.method == "POST":
        db.execute(
            "INSERT INTO spotted (content, user_id) VALUES (?, ?)",
            (request.form["content"], session["user_id"]),
        )
        db.commit()
        return redirect(url_for("spotted_page"))

    spotteds = db.execute(
        "SELECT s.*, u.username FROM spotted s LEFT JOIN users u ON s.user_id=u.id ORDER BY s.created DESC"
    ).fetchall()
    return render_template_string(
        TEMPLATE + """
        {% block content %}
        <h2>Spotted</h2>
        <form method="post">
          <textarea name="content" placeholder="Twoje spotted"></textarea><br>
          <button>Dodaj</button>
        </form>
        <hr>
        {% for s in spotteds %}
          <div class="post">
            <b>{{ s['username'] }}</b>: {{ s['content'] }}
            {% if session.get('role') == 'teacher' %}
              <a href="{{ url_for('delete_spotted', spotted_id=s['id']) }}">[usuń]</a>
            {% endif %}
          </div>
        {% endfor %}
        {% endblock %}
        """,
        spotteds=spotteds,
    )

@app.route("/spotted/delete/<int:spotted_id>")
def delete_spotted(spotted_id):
    if session.get("role") != "teacher":
        return "Tylko nauczyciel może usuwać!", 403
    db = get_db()
    db.execute("DELETE FROM spotted WHERE id=?", (spotted_id,))
    db.commit()
    return redirect(url_for("spotted_page"))

# -------- Forum --------
@app.route("/forum", methods=["GET", "POST"])
def forum():
    db = get_db()
    if request.method == "POST":
        db.execute("INSERT INTO threads (title) VALUES (?)", (request.form["title"],))
        db.commit()
        return redirect(url_for("forum"))

    threads = db.execute("SELECT * FROM threads ORDER BY created DESC").fetchall()
    return render_template_string(
        TEMPLATE + """
        {% block content %}
        <h2>Forum</h2>
        <form method="post">
          <input name="title" placeholder="Tytuł wątku">
          <button>Dodaj wątek</button>
        </form>
        <hr>
        {% for t in threads %}
          <div><a href="{{ url_for('thread', thread_id=t['id']) }}">{{ t['title'] }}</a></div>
        {% endfor %}
        {% endblock %}
        """,
        threads=threads,
    )

@app.route("/forum/<int:thread_id>", methods=["GET", "POST"])
def thread(thread_id):
    db = get_db()
    if request.method == "POST":
        db.execute(
            "INSERT INTO posts (thread_id, content, user_id) VALUES (?, ?, ?)",
            (thread_id, request.form["content"], session.get("user_id")),
        )
        db.commit()
        return redirect(url_for("thread", thread_id=thread_id))

    thread = db.execute("SELECT * FROM threads WHERE id=?", (thread_id,)).fetchone()
    posts = db.execute(
        "SELECT p.*, u.username FROM posts p LEFT JOIN users u ON p.user_id=u.id WHERE thread_id=? ORDER BY created",
        (thread_id,),
    ).fetchall()
    return render_template_string(
        TEMPLATE + """
        {% block content %}
        <h2>{{ thread['title'] }}</h2>
        <form method="post">
          <textarea name="content" placeholder="Treść posta"></textarea><br>
          <button>Dodaj post</button>
        </form>
        <hr>
        {% for p in posts %}
          <div class="post"><b>{{ p['username'] }}</b>: {{ p['content'] }}</div>
        {% endfor %}
        {% endblock %}
        """,
        thread=thread,
        posts=posts,
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)























import os
from flask import Flask, render_template_string, request, redirect, url_for, session, abort, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import urlparse

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "zmien_to_w_prod")

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL or "sqlite:///dev.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

BAD_WORDS = ["kurwa", "chuj", "pierdole", "idiota", "głupi", "brzydkie"]

def clean_text(txt):
    if not txt:
        return txt
    lower = txt.lower()
    for w in BAD_WORDS:
        if w in lower:
            return "Treść nie jest ładna"
    return txt

class School(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    users = db.relationship("User", backref="school", lazy=True)
    spotteds = db.relationship("Spotted", backref="school", lazy=True)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # "nauczyciel" / "uczen"
    school_id = db.Column(db.Integer, db.ForeignKey("school.id"), nullable=True)
    posts = db.relationship("Post", backref="author", lazy=True)

class Thread(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    posts = db.relationship("Post", backref="thread", lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    thread_id = db.Column(db.Integer, db.ForeignKey("thread.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

class Spotted(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey("school.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

with app.app_context():
    db.create_all()

BASE = """
<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LOL page</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body { background:#0b0b0d; color:#fff; }
.navbar, .card, .form-control, .btn { background:#111; color:#fff; border-color:#222; }
a { color:#9ad1ff; }
.container { max-width:960px; }
.card { border-radius:12px; }
.form-control, textarea { background:#0f0f10; color:#fff; }
.small-muted { color:#cfcfcf; }
.header-title { text-align:center; margin:18px 0; font-weight:700; }
@media (max-width:576px) {
  .container { padding:10px; }
  .header-title { font-size:1.4rem; }
}
</style>
</head>
<body>
<nav class="navbar navbar-expand-lg mb-3">
  <div class="container">
    <a class="navbar-brand text-white" href="{{ url_for('index') }}">😂 LOL page</a>
    <div class="d-flex">
      <a class="nav-link" href="{{ url_for('threads') }}">Forum</a>
      <a class="nav-link" href="{{ url_for('schools_list') }}">Schools</a>
      {% if session.get('user_id') and session.get('role') in ['nauczyciel','uczen'] %}
        <a class="nav-link" href="{{ url_for('spotted') }}">Spotted</a>
      {% endif %}
      {% if session.get('user_id') %}
        <span class="nav-link">👤 {{ session.get('username') }} ({{ session.get('role') }})</span>
        <a class="nav-link" href="{{ url_for('logout') }}">Logout</a>
      {% else %}
        <a class="nav-link" href="{{ url_for('login') }}">Login</a>
      {% endif %}
    </div>
  </div>
</nav>
<div class="container mb-5">
  {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
      {% for cat, msg in messages %}
        <div class="alert alert-{{ 'warning' if cat=='warning' else 'info' }}" role="alert">{{ msg }}</div>
      {% endfor %}
    {% endif %}
  {% endwith %}
  {{ content|safe }}
</div>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(BASE, content="""
    <div class="header-title">LOL page</div>
    <div class="card p-3">
      <h4>Witamy na LOL page — forum i spotted dla szkół</h4>
      <p class="small-muted">Zaloguj się lub zarejestruj szkołę aby zacząć.</p>
    </div>
    """)

# ---- AUTH / SCHOOLS ----
@app.route("/register_school", methods=["GET","POST"])
def register_school():
    if request.method == "POST":
        name = request.form.get("school_name", "").strip()
        teacher_login = request.form.get("teacher_login", "").strip()
        teacher_pass = request.form.get("teacher_password", "").strip()
        if not name or not teacher_login or not teacher_pass:
            flash("Wypełnij wszystkie pola", "warning"); return redirect(url_for("register_school"))
        if School.query.filter_by(name=name).first():
            flash("Taka szkoła już istnieje", "warning"); return redirect(url_for("register_school"))
        school = School(name=name)
        db.session.add(school); db.session.commit()
        hashed = generate_password_hash(teacher_pass)
        t = User(username=teacher_login, password=hashed, role="nauczyciel", school_id=school.id)
        db.session.add(t); db.session.commit()
        flash("Szkoła i konto nauczyciela utworzone. Zaloguj się.", "info")
        return redirect(url_for("login"))
    return render_template_string(BASE, content="""
    <div class="card p-3">
      <h3>Rejestracja szkoły — LOL page for schools</h3>
      <form method="post">
        <input class="form-control mb-2" name="school_name" placeholder="Nazwa szkoły">
        <input class="form-control mb-2" name="teacher_login" placeholder="Login pierwszego nauczyciela">
        <input class="form-control mb-2" name="teacher_password" placeholder="Hasło" type="password">
        <button class="btn btn-primary">Utwórz szkołę i konto nauczyciela</button>
      </form>
    </div>
    """)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "")
        user = User.query.filter_by(username=u).first()
        if user and check_password_hash(user.password, p):
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            session["school_id"] = user.school_id
            session["school_name"] = user.school.name if user.school else None
            flash("Zalogowano", "info")
            return redirect(url_for("index"))
        flash("Błędny login lub hasło", "warning")
    return render_template_string(BASE, content="""
    <div class="card p-3">
      <h3>Logowanie</h3>
      <form method="post">
        <input class="form-control mb-2" name="username" placeholder="Login">
        <input class="form-control mb-2" name="password" placeholder="Hasło" type="password">
        <button class="btn btn-primary">Zaloguj</button>
      </form>
    </div>
    """)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# ---- SCHOOLS LIST ----
@app.route("/schools")
def schools_list():
    schools = School.query.order_by(School.name).all()
    html = '<div class="card p-3"><h3>Szkoły</h3>'
    html += '<a class="btn btn-success mb-2" href="%s">Zarejestruj szkołę</a>' % url_for("register_school")
    for s in schools:
        html += '<div class="p-2 mb-2" style="border:1px solid #222;border-radius:8px;"><a href="%s">%s</a></div>' % (url_for("school_view", school_id=s.id), s.name)
    html += "</div>"
    return render_template_string(BASE, content=html)

@app.route("/schools/<int:school_id>")
def school_view(school_id):
    s = School.query.get_or_404(school_id)
    teachers = User.query.filter_by(school_id=s.id, role="nauczyciel").all()
    students = User.query.filter_by(school_id=s.id, role="uczen").all()
    html = f'<div class="card p-3"><h3>{s.name}</h3><h5>Nauczyciele</h5>'
    for t in teachers:
        html += f'<div>{t.username}</div>'
    html += "<h5>Uczniowie</h5>"
    for st in students:
        html += f'<div>{st.username}</div>'
    html += "</div>"
    return render_template_string(BASE, content=html)

# ---- SPOTTED (tylko dla uczniów i nauczycieli) ----
@app.route("/spotted", methods=["GET","POST"])
def spotted():
    if "user_id" not in session or session.get("role") not in ("nauczyciel", "uczen"):
        abort(403)
    if not session.get("school_id"):
        flash("Nie jesteś przypisany do szkoły", "warning"); return redirect(url_for("index"))
    if request.method == "POST":
        txt = clean_text(request.form.get("content", "").strip())
        spot = Spotted(content=txt, school_id=session["school_id"], user_id=session["user_id"])
        db.session.add(spot); db.session.commit()
        return redirect(url_for("spotted"))
    spots = Spotted.query.filter_by(school_id=session["school_id"]).order_by(Spotted.id.desc()).all()
    html = f'<div class="card p-3"><h3>Spotted — {session.get("school_name")}</h3>'
    html += '<form method="post"><textarea class="form-control mb-2" name="content" placeholder="Napisz spotted..."></textarea><button class="btn btn-primary">Dodaj</button></form><hr>'
    for s in spots:
        usr = User.query.get(s.user_id)
        author = usr.username if usr else "Anon"
        remove_btn = ""
        if session.get("role") == "nauczyciel":
            remove_btn = f' <a class="text-danger" href="{url_for("teacher_delete_spotted", spotted_id=s.id)}">[Usuń]</a>'
        html += f'<div class="mb-2"><b>{author}</b>: {s.content}{remove_btn}</div>'
    html += "</div>"
    return render_template_string(BASE, content=html)

@app.route("/teacher/delete_spotted/<int:spotted_id>")
def teacher_delete_spotted(spotted_id):
    if session.get("role") != "nauczyciel":
        abort(403)
    sp = Spotted.query.get_or_404(spotted_id)
    if sp.school_id != session.get("school_id"):
        abort(403)
    db.session.delete(sp); db.session.commit()
    flash("Wpis usunięty", "info")
    return redirect(url_for("spotted"))

# ---- TEACHER PANEL: manage users in same school ----
@app.route("/teacher/panel", methods=["GET","POST"])
def teacher_panel():
    if session.get("role") != "nauczyciel":
        abort(403)
    school_id = session.get("school_id")
    users = User.query.filter_by(school_id=school_id).all()
    html = '<div class="card p-3"><h3>Panel nauczyciela</h3>'
    html += '<h5>Dodaj ucznia</h5><form method="post" action="%s"><input class="form-control mb-2" name="stu_login" placeholder="login"><input class="form-control mb-2" name="stu_pass" placeholder="hasło"><button class="btn btn-success">Dodaj ucznia</button></form>' % url_for("teacher_add_student")
    html += '<h5 class="mt-3">Dodaj nauczyciela</h5><form method="post" action="%s"><input class="form-control mb-2" name="t_login" placeholder="login"><input class="form-control mb-2" name="t_pass" placeholder="hasło"><button class="btn btn-success">Dodaj nauczyciela</button></form>' % url_for("teacher_add_teacher")
    html += "<hr><h5>Użytkownicy szkoły</h5>"
    for u in users:
        html += f'<div class="mb-2">{u.username} — {u.role} '
        if u.role == "uczen":
            html += f'| <a href="{url_for("teacher_reset_password", user_id=u.id)}">Resetuj hasło</a> | <a class="text-danger" href="{url_for("teacher_delete_user", user_id=u.id)}">Usuń</a>'
        elif u.role == "nauczyciel":
            # don't allow deleting yourself via link; allow deleting other teachers
            if u.id != session.get("user_id"):
                html += f'| <a class="text-danger" href="{url_for("teacher_delete_user", user_id=u.id)}">Usuń nauczyciela</a>'
        html += "</div>"
    html += "</div>"
    return render_template_string(BASE, content=html)

@app.route("/teacher/add_student", methods=["POST"])
def teacher_add_student():
    if session.get("role") != "nauczyciel":
        abort(403)
    login = request.form.get("stu_login", "").strip()
    pw = request.form.get("stu_pass", "")
    if not login or not pw:
        flash("Wypełnij wszystkie pola", "warning"); return redirect(url_for("teacher_panel"))
    if User.query.filter_by(username=login).first():
        flash("Login już istnieje", "warning"); return redirect(url_for("teacher_panel"))
    hashed = generate_password_hash(pw)
    u = User(username=login, password=hashed, role="uczen", school_id=session.get("school_id"))
    db.session.add(u); db.session.commit()
    flash("Uczeń dodany", "info")
    return redirect(url_for("teacher_panel"))

@app.route("/teacher/add_teacher", methods=["POST"])
def teacher_add_teacher():
    if session.get("role") != "nauczyciel":
        abort(403)
    login = request.form.get("t_login", "").strip()
    pw = request.form.get("t_pass", "")
    if not login or not pw:
        flash("Wypełnij wszystkie pola", "warning"); return redirect(url_for("teacher_panel"))
    if User.query.filter_by(username=login).first():
        flash("Login już istnieje", "warning"); return redirect(url_for("teacher_panel"))
    hashed = generate_password_hash(pw)
    u = User(username=login, password=hashed, role="nauczyciel", school_id=session.get("school_id"))
    db.session.add(u); db.session.commit()
    flash("Nauczyciel dodany", "info")
    return redirect(url_for("teacher_panel"))

@app.route("/teacher/reset/<int:user_id>", methods=["GET","POST"])
def teacher_reset_password(user_id):
    if session.get("role") != "nauczyciel":
        abort(403)
    user = User.query.get_or_404(user_id)
    if user.school_id != session.get("school_id"):
        abort(403)
    if request.method == "POST":
        newpw = request.form.get("password", "")
        if not newpw:
            flash("Wpisz hasło", "warning"); return redirect(url_for("teacher_reset_password", user_id=user_id))
        user.password = generate_password_hash(newpw)
        db.session.commit()
        flash("Hasło zresetowane", "info")
        return redirect(url_for("teacher_panel"))
    return render_template_string(BASE, content=f"""
    <div class="card p-3"><h4>Reset hasła dla {user.username}</h4>
    <form method="post"><input class="form-control mb-2" name="password" placeholder="Nowe hasło"><button class="btn btn-primary">Zapisz</button></form>
    </div>
    """)

@app.route("/teacher/delete_user/<int:user_id>")
def teacher_delete_user(user_id):
    if session.get("role") != "nauczyciel":
        abort(403)
    user = User.query.get_or_404(user_id)
    if user.school_id != session.get("school_id"):
        abort(403)
    if user.id == session.get("user_id"):
        flash("Nie możesz usunąć siebie", "warning"); return redirect(url_for("teacher_panel"))
    db.session.delete(user); db.session.commit()
    flash("Użytkownik usunięty", "info")
    return redirect(url_for("teacher_panel"))

# ---- FORUM: threads, posts, search ----
@app.route("/threads")
def threads():
    q = request.args.get("q", "").strip()
    if q:
        threads = Thread.query.filter(Thread.title.ilike(f"%{q}%")).all()
    else:
        threads = Thread.query.order_by(Thread.id.desc()).all()
    html = '<div class="card p-3"><h3>Forum</h3><form class="d-flex mb-2" method="get" action="%s"><input class="form-control me-2" name="q" placeholder="Szukaj wątków"><button class="btn btn-outline-light">Szukaj</button></form>' % url_for("threads")
    html += '<a class="btn btn-success mb-2" href="%s">Nowy wątek</a>' % url_for("thread_new")
    for t in threads:
        html += f'<div class="mb-2"><a href="{url_for("thread_view", thread_id=t.id)}">{t.title}</a></div>'
    html += "</div>"
    return render_template_string(BASE, content=html)

@app.route("/threads/new", methods=["GET","POST"])
def thread_new():
    if request.method == "POST":
        title = clean_text(request.form.get("title", "").strip())
        if not title:
            flash("Podaj tytuł", "warning"); return redirect(url_for("thread_new"))
        th = Thread(title=title); db.session.add(th); db.session.commit()
        return redirect(url_for("threads"))
    return render_template_string(BASE, content="""
    <div class="card p-3"><h4>Nowy wątek</h4>
    <form method="post"><input class="form-control mb-2" name="title" placeholder="Tytuł"><button class="btn btn-primary">Utwórz</button></form></div>
    """)

@app.route("/threads/<int:thread_id>", methods=["GET","POST"])
def thread_view(thread_id):
    th = Thread.query.get_or_404(thread_id)
    if request.method == "POST":
        if "user_id" not in session:
            flash("Zaloguj się by pisać", "warning"); return redirect(url_for("login"))
        content = clean_text(request.form.get("content", "").strip())
        p = Post(content=content, thread_id=th.id, user_id=session.get("user_id"))
        db.session.add(p); db.session.commit()
        return redirect(url_for("thread_view", thread_id=thread_id))
    posts = Post.query.filter_by(thread_id=thread_id).all()
    html = f'<div class="card p-3"><h4>{th.title}</h4>'
    for p in posts:
        user = User.query.get(p.user_id)
        author = user.username if user else "Anon"
        controls = ""
        if session.get("user_id") == p.user_id:
            controls = f' | <a href="{url_for("post_delete", post_id=p.id)}" class="text-danger">Usuń</a>'
        html += f'<div class="mb-2"><b>{author}</b>: {p.content}{controls}</div>'
    html += '<form method="post"><textarea class="form-control mb-2" name="content" placeholder="Napisz odpowiedź"></textarea><button class="btn btn-primary">Odpowiedz</button></form></div>'
    return render_template_string(BASE, content=html)

@app.route("/post/delete/<int:post_id>")
def post_delete(post_id):
    p = Post.query.get_or_404(post_id)
    if session.get("user_id") != p.user_id and session.get("role") != "nauczyciel":
        abort(403)
    db.session.delete(p); db.session.commit()
    flash("Post usunięty", "info")
    return redirect(request.referrer or url_for("threads"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

























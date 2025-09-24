import os
from flask import Flask, render_template_string, request, redirect, url_for, session, flash, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask("lol_page")
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
    low = txt.lower()
    for w in BAD_WORDS:
        if w in low:
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
    role = db.Column(db.String(20), nullable=False)  # "nauczyciel" / "uczen" / "user"
    school_id = db.Column(db.Integer, db.ForeignKey("school.id"), nullable=True)
    lol_posts = db.relationship("LOLPost", backref="author", lazy=True)
    posts = db.relationship("Post", backref="author", lazy=True)

class LOLPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created = db.Column(db.DateTime, server_default=db.func.now())
    replies = db.relationship("LOLReply", backref="post", lazy=True, cascade="all,delete")

class LOLReply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("LOLPost.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created = db.Column(db.DateTime, server_default=db.func.now())

class Thread(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    created = db.Column(db.DateTime, server_default=db.func.now())
    posts = db.relationship("Post", backref="thread", lazy=True, cascade="all,delete")

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    thread_id = db.Column(db.Integer, db.ForeignKey("thread.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created = db.Column(db.DateTime, server_default=db.func.now())

class Spotted(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey("school.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created = db.Column(db.DateTime, server_default=db.func.now())
    replies = db.relationship("SpottedReply", backref="spotted", lazy=True, cascade="all,delete")

class SpottedReply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    spotted_id = db.Column(db.Integer, db.ForeignKey("spotted.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created = db.Column(db.DateTime, server_default=db.func.now())

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
.container { max-width:1000px; }
.card { border-radius:12px; }
.form-control, textarea { background:#0f0f10; color:#fff; border:1px solid #222; }
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
      <a class="nav-link" href="{{ url_for('lol_page') }}">LOL page</a>
      <a class="nav-link" href="{{ url_for('schools_list') }}">Schools</a>
      {% if session.get('user_id') and session.get('role') in ['nauczyciel','uczen'] %}
        <a class="nav-link" href="{{ url_for('spotted') }}">Spotted</a>
      {% endif %}
      {% if session.get('user_id') %}
        <span class="nav-link">👤 {{ session.get('username') }} ({{ session.get('role') }})</span>
        {% if session.get('role') == 'nauczyciel' %}
          <a class="nav-link" href="{{ url_for('teacher_panel') }}">Panel nauczyciela</a>
        {% endif %}
        <a class="nav-link" href="{{ url_for('logout') }}">Wyloguj</a>
      {% else %}
        <a class="nav-link" href="{{ url_for('login') }}">Login</a>
        <a class="nav-link" href="{{ url_for('register') }}">Register</a>
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
      <h4>Witamy — zaloguj się aby korzystać z LOL page i szkół</h4>
      <p class="small-muted">Forum, LOL page i Spotted — wszystko w jednym.</p>
    </div>
    """)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        uname = request.form.get("username","").strip()
        pw = request.form.get("password","")
        if not uname or not pw:
            flash("Wypełnij pola", "warning"); return redirect(url_for("register"))
        if User.query.filter_by(username=uname).first():
            flash("Login zajęty", "warning"); return redirect(url_for("register"))
        hashed = generate_password_hash(pw)
        u = User(username=uname, password=hashed, role="user")
        db.session.add(u); db.session.commit()
        flash("Konto utworzone. Zaloguj się.", "info"); return redirect(url_for("login"))
    return render_template_string(BASE, content="""
    <div class="card p-3"><h3>Rejestracja</h3>
    <form method="post">
      <input class="form-control mb-2" name="username" placeholder="Login">
      <input class="form-control mb-2" name="password" placeholder="Hasło" type="password">
      <button class="btn btn-primary">Zarejestruj</button>
    </form></div>
    """)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u = request.form.get("username","").strip()
        p = request.form.get("password","")
        user = User.query.filter_by(username=u).first()
        if user and check_password_hash(user.password, p):
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            session["school_id"] = user.school_id
            session["school_name"] = user.school.name if user.school else None
            flash("Zalogowano", "info"); return redirect(url_for("index"))
        flash("Błędny login lub hasło", "warning")
    return render_template_string(BASE, content="""
    <div class="card p-3"><h3>Logowanie</h3>
    <form method="post">
      <input class="form-control mb-2" name="username" placeholder="Login">
      <input class="form-control mb-2" name="password" placeholder="Hasło" type="password">
      <button class="btn btn-primary">Zaloguj</button>
    </form></div>
    """)

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("index"))

@app.route("/schools")
def schools_list():
    schools = School.query.order_by(School.name).all()
    html = '<div class="card p-3"><h3>Szkoły</h3>'
    html += '<a class="btn btn-success mb-2" href="%s">Zarejestruj szkołę</a>' % url_for("register_school")
    for s in schools:
        html += '<div class="p-2 mb-2" style="border:1px solid #222;border-radius:8px;"><a href="%s">%s</a></div>' % (url_for("school_view", school_id=s.id), s.name)
    html += "</div>"
    return render_template_string(BASE, content=html)

@app.route("/register_school", methods=["GET","POST"])
def register_school():
    if request.method=="POST":
        name = request.form.get("school_name","").strip()
        t_login = request.form.get("teacher_login","").strip()
        t_pass = request.form.get("teacher_password","")
        if not name or not t_login or not t_pass:
            flash("Wypełnij pola", "warning"); return redirect(url_for("register_school"))
        if School.query.filter_by(name=name).first():
            flash("Szkoła istnieje", "warning"); return redirect(url_for("register_school"))
        school = School(name=name); db.session.add(school); db.session.commit()
        hashed = generate_password_hash(t_pass)
        nt = User(username=t_login, password=hashed, role="nauczyciel", school_id=school.id)
        db.session.add(nt); db.session.commit()
        flash("Szkoła i konto nauczyciela utworzone", "info"); return redirect(url_for("login"))
    return render_template_string(BASE, content="""
    <div class="card p-3"><h3>Rejestracja szkoły</h3>
    <form method="post">
      <input class="form-control mb-2" name="school_name" placeholder="Nazwa szkoły">
      <input class="form-control mb-2" name="teacher_login" placeholder="Login nauczyciela">
      <input class="form-control mb-2" name="teacher_password" placeholder="Hasło" type="password">
      <button class="btn btn-primary">Utwórz</button>
    </form></div>
    """)

@app.route("/schools/<int:school_id>")
def school_view(school_id):
    s = School.query.get_or_404(school_id)
    teachers = User.query.filter_by(school_id=s.id, role="nauczyciel").all()
    students = User.query.filter_by(school_id=s.id, role="uczen").all()
    html = f'<div class="card p-3"><h3>{s.name}</h3><h5>Nauczyciele</h5>'
    for t in teachers: html += f'<div>{t.username}</div>'
    html += "<h5>Uczniowie</h5>"
    for st in students: html += f'<div>{st.username}</div>'
    html += "</div>"
    return render_template_string(BASE, content=html)

@app.route("/spotted", methods=["GET","POST"])
def spotted():
    if "user_id" not in session or session.get("role") not in ("nauczyciel","uczen"):
        abort(403)
    if not session.get("school_id"):
        flash("Nie jesteś przypisany do szkoły", "warning"); return redirect(url_for("index"))
    if request.method=="POST":
        txt = clean_text(request.form.get("content","").strip())
        sp = Spotted(content=txt, school_id=session["school_id"], user_id=session["user_id"])
        db.session.add(sp); db.session.commit(); return redirect(url_for("spotted"))
    spots = Spotted.query.filter_by(school_id=session["school_id"]).order_by(Spotted.created.desc()).all()
    html = f'<div class="card p-3"><h3>Spotted — {session.get("school_name")}</h3>'
    html += '<form method="post"><textarea class="form-control mb-2" name="content" placeholder="Napisz spotted..."></textarea><button class="btn btn-primary">Dodaj</button></form><hr>'
    for s in spots:
        usr = User.query.get(s.user_id); author = usr.username if usr else "Anon"
        rem = ''
        if session.get("role")=="nauczyciel":
            rem = f' <a class="text-danger" href="{url_for("teacher_delete_spotted", spotted_id=s.id)}">[Usuń]</a>'
        html += f'<div class="mb-2"><b>{author}</b>: {s.content}{rem} <a href="{url_for("spotted_view", spotted_id=s.id)}">[odpowiedzi]</a></div>'
    html += "</div>"
    return render_template_string(BASE, content=html)

@app.route("/spotted/<int:spotted_id>", methods=["GET","POST"])
def spotted_view(spotted_id):
    if "user_id" not in session or session.get("role") not in ("nauczyciel","uczen"):
        abort(403)
    sp = Spotted.query.get_or_404(spotted_id)
    if sp.school_id != session.get("school_id"):
        abort(403)
    if request.method == "POST":
        txt = clean_text(request.form.get("reply","").strip())
        if txt:
            r = SpottedReply(content=txt, spotted_id=sp.id, user_id=session["user_id"])
            db.session.add(r); db.session.commit(); return redirect(url_for("spotted_view", spotted_id=sp.id))
    replies = SpottedReply.query.filter_by(spotted_id=sp.id).order_by(SpottedReply.created).all()
    author = User.query.get(sp.user_id); an = author.username if author else "Anon"
    html = f'<div class="card p-3"><h4>{an}: {sp.content}</h4>'
    for r in replies:
        u = User.query.get(r.user_id); name = u.username if u else "Anon"
        html += f'<div class="mb-2"><b>{name}</b>: {r.content}</div>'
    html += f'<form method="post"><input class="form-control mb-2" name="reply" placeholder="Twoja odpowiedź"><button class="btn btn-primary">Odpowiedz</button></form></div>'
    return render_template_string(BASE, content=html)

@app.route("/teacher/delete_spotted/<int:spotted_id>")
def teacher_delete_spotted(spotted_id):
    if session.get("role")!="nauczyciel": abort(403)
    sp = Spotted.query.get_or_404(spotted_id)
    if sp.school_id != session.get("school_id"): abort(403)
    db.session.delete(sp); db.session.commit(); flash("Wpis usunięty", "info"); return redirect(url_for("spotted"))

@app.route("/teacher/panel")
def teacher_panel():
    if session.get("role")!="nauczyciel": abort(403)
    users = User.query.filter_by(school_id=session.get("school_id")).all()
    return render_template_string(BASE, content="""
    <div class="card p-3"><h3>Panel nauczyciela</h3>
    <h5>Dodaj ucznia</h5>
    <form method="post" action="{{ url_for('teacher_add_student') }}">
      <input class="form-control mb-2" name="stu_login" placeholder="login">
      <input class="form-control mb-2" name="stu_pass" placeholder="hasło" type="password">
      <button class="btn btn-success">Dodaj ucznia</button>
    </form>
    <h5 class="mt-3">Dodaj nauczyciela</h5>
    <form method="post" action="{{ url_for('teacher_add_teacher') }}">
      <input class="form-control mb-2" name="t_login" placeholder="login">
      <input class="form-control mb-2" name="t_pass" placeholder="hasło" type="password">
      <button class="btn btn-success">Dodaj nauczyciela</button>
    </form>
    <hr><h5>Użytkownicy szkoły</h5>
    {% for u in users %}
      <div class="mb-2">{{ u.username }} — {{ u.role }}
        {% if u.role == 'uczen' %}
          | <a href="{{ url_for('teacher_reset_password', user_id=u.id) }}">Resetuj hasło</a>
          | <a class="text-danger" href="{{ url_for('teacher_delete_user', user_id=u.id) }}">Usuń</a>
        {% elif u.role == 'nauczyciel' %}
          {% if u.id != session.get('user_id') %}
            | <a class="text-danger" href="{{ url_for('teacher_delete_user', user_id=u.id) }}">Usuń nauczyciela</a>
          {% endif %}
        {% endif %}
      </div>
    {% endfor %}
    </div>
    """, users=users)

@app.route("/teacher/add_student", methods=["POST"])
def teacher_add_student():
    if session.get("role")!="nauczyciel": abort(403)
    login = request.form.get("stu_login","").strip(); pw = request.form.get("stu_pass","")
    if not login or not pw: flash("Wypełnij pola", "warning"); return redirect(url_for("teacher_panel"))
    if User.query.filter_by(username=login).first(): flash("Login istnieje", "warning"); return redirect(url_for("teacher_panel"))
    hashed = generate_password_hash(pw); u = User(username=login, password=hashed, role="uczen", school_id=session.get("school_id"))
    db.session.add(u); db.session.commit(); flash("Uczeń dodany", "info"); return redirect(url_for("teacher_panel"))

@app.route("/teacher/add_teacher", methods=["POST"])
def teacher_add_teacher():
    if session.get("role")!="nauczyciel": abort(403)
    login = request.form.get("t_login","").strip(); pw = request.form.get("t_pass","")
    if not login or not pw: flash("Wypełnij pola", "warning"); return redirect(url_for("teacher_panel"))
    if User.query.filter_by(username=login).first(): flash("Login istnieje", "warning"); return redirect(url_for("teacher_panel"))
    hashed = generate_password_hash(pw); u = User(username=login, password=hashed, role="nauczyciel", school_id=session.get("school_id"))
    db.session.add(u); db.session.commit(); flash("Nauczyciel dodany", "info"); return redirect(url_for("teacher_panel"))

@app.route("/teacher/reset/<int:user_id>", methods=["GET","POST"])
def teacher_reset_password(user_id):
    if session.get("role")!="nauczyciel": abort(403)
    user = User.query.get_or_404(user_id)
    if user.school_id != session.get("school_id"): abort(403)
    if request.method=="POST":
        newpw = request.form.get("password","")
        if not newpw: flash("Wpisz hasło", "warning"); return redirect(url_for("teacher_reset_password", user_id=user_id))
        user.password = generate_password_hash(newpw); db.session.commit(); flash("Hasło zresetowane", "info"); return redirect(url_for("teacher_panel"))
    return render_template_string(BASE, content=f"""
    <div class="card p-3"><h4>Reset hasła dla {user.username}</h4>
    <form method="post"><input class="form-control mb-2" name="password" placeholder="Nowe hasło" type="password"><button class="btn btn-primary">Zapisz</button></form>
    </div>
    """)

@app.route("/teacher/delete_user/<int:user_id>")
def teacher_delete_user(user_id):
    if session.get("role")!="nauczyciel": abort(403)
    user = User.query.get_or_404(user_id)
    if user.school_id != session.get("school_id"): abort(403)
    if user.id == session.get("user_id"): flash("Nie możesz usunąć siebie", "warning"); return redirect(url_for("teacher_panel"))
    db.session.delete(user); db.session.commit(); flash("Użytkownik usunięty", "info"); return redirect(url_for("teacher_panel"))

@app.route("/lol", methods=["GET","POST"])
def lol_page():
    if "user_id" not in session:
        flash("Zaloguj się aby zobaczyć LOL page", "warning"); return redirect(url_for("login"))
    if request.method=="POST":
        txt = clean_text(request.form.get("content","").strip())
        if txt:
            lp = LOLPost(content=txt, user_id=session.get("user_id"))
            db.session.add(lp); db.session.commit()
        return redirect(url_for("lol_page"))
    posts = LOLPost.query.order_by(LOLPost.created.desc()).all()
    html = '<div class="card p-3"><h3>LOL page</h3><form method="post"><textarea class="form-control mb-2" name="content" placeholder="Dodaj wpis..."></textarea><button class="btn btn-primary">Dodaj</button></form><hr>'
    for p in posts:
        author = User.query.get(p.user_id)
        author_name = author.username if author else "Anon"
        delete_btn = ''
        if session.get("role")=="nauczyciel" or session.get("user_id")==p.user_id:
            delete_btn = f' <a class="text-danger" href="{url_for("lol_delete", post_id=p.id)}">[Usuń]</a>'
        html += f'<div class="mb-2"><b>{author_name}</b>: {p.content}{delete_btn} <a href="{url_for("lol_view", post_id=p.id)}">[odpowiedzi]</a></div>'
    html += "</div>"
    return render_template_string(BASE, content=html)

@app.route("/lol/<int:post_id>", methods=["GET","POST"])
def lol_view(post_id):
    if "user_id" not in session: abort(403)
    post = LOLPost.query.get_or_404(post_id)
    if request.method=="POST":
        txt = clean_text(request.form.get("reply","").strip())
        if txt:
            rep = LOLReply(content=txt, post_id=post.id, user_id=session.get("user_id"))
            db.session.add(rep); db.session.commit()
        return redirect(url_for("lol_view", post_id=post_id))
    replies = LOLReply.query.filter_by(post_id=post.id).order_by(LOLReply.created).all()
    author = User.query.get(post.user_id)
    auth = author.username if author else "Anon"
    html = f'<div class="card p-3"><h4>{auth}: {post.content}</h4>'
    for r in replies:
        u = User.query.get(r.user_id); name = u.username if u else "Anon"
        html += f'<div class="mb-2"><b>{name}</b>: {r.content}</div>'
    html += f'<form method="post"><input class="form-control mb-2" name="reply" placeholder="Twoja odpowiedź"><button class="btn btn-primary">Odpowiedz</button></form></div>'
    return render_template_string(BASE, content=html)

@app.route("/lol/delete/<int:post_id>")
def lol_delete(post_id):
    p = LOLPost.query.get_or_404(post_id)
    if session.get("role")!="nauczyciel" and session.get("user_id")!=p.user_id: abort(403)
    db.session.delete(p); db.session.commit(); flash("Wpis usunięty", "info"); return redirect(url_for("lol_page"))

@app.route("/threads")
def threads():
    q = request.args.get("q","").strip()
    if q:
        threads = Thread.query.filter(Thread.title.ilike(f"%{q}%")).order_by(Thread.created.desc()).all()
    else:
        threads = Thread.query.order_by(Thread.created.desc()).all()
    html = '<div class="card p-3"><h3>Forum</h3><form class="d-flex mb-2" method="get" action="%s"><input class="form-control me-2" name="q" placeholder="Szukaj wątków"><button class="btn btn-outline-light">Szukaj</button></form>' % url_for("threads")
    html += '<a class="btn btn-success mb-2" href="%s">Nowy wątek</a>' % url_for("thread_new")
    for t in threads:
        html += f'<div class="mb-2"><a href="{url_for("thread_view", thread_id=t.id)}">{t.title}</a></div>'
    html += "</div>"
    return render_template_string(BASE, content=html)

@app.route("/threads/new", methods=["GET","POST"])
def thread_new():
    if request.method=="POST":
        title = clean_text(request.form.get("title","").strip())
        if not title: flash("Podaj tytuł", "warning"); return redirect(url_for("thread_new"))
        db.session.add(Thread(title=title)); db.session.commit(); return redirect(url_for("threads"))
    return render_template_string(BASE, content="""
    <div class="card p-3"><h4>Nowy wątek</h4>
    <form method="post"><input class="form-control mb-2" name="title" placeholder="Tytuł"><button class="btn btn-primary">Utwórz</button></form></div>
    """)

@app.route("/threads/<int:thread_id>", methods=["GET","POST"])
def thread_view(thread_id):
    th = Thread.query.get_or_404(thread_id)
    if request.method=="POST":
        if "user_id" not in session: flash("Zaloguj się by pisać", "warning"); return redirect(url_for("login"))
        content = clean_text(request.form.get("content","").strip())
        if content:
            db.session.add(Post(content=content, thread_id=th.id, user_id=session.get("user_id"))); db.session.commit()
        return redirect(url_for("thread_view", thread_id=thread_id))
    posts = Post.query.filter_by(thread_id=thread_id).order_by(Post.created).all()
    html = f'<div class="card p-3"><h4>{th.title}</h4>'
    for p in posts:
        u = User.query.get(p.user_id); author = u.username if u else "Anon"
        controls = ""
        if session.get("user_id")==p.user_id or session.get("role")=="nauczyciel":
            controls = f' | <a class="text-danger" href="{url_for("post_delete", post_id=p.id)}">Usuń</a>'
        html += f'<div class="mb-2"><b>{author}</b>: {p.content}{controls}</div>'
    html += f"""
      <form method="post">
        <textarea class="form-control mb-2" name="content" placeholder="Dodaj odpowiedź..."></textarea>
        <button class="btn btn-primary">Dodaj</button>
      </form>
    </div>
    """
    return render_template_string(BASE, content=html)

@app.route("/posts/delete/<int:post_id>")
def post_delete(post_id):
    post = Post.query.get_or_404(post_id)
    if session.get("role")!="nauczyciel" and session.get("user_id")!=post.user_id:
        abort(403)
    tid = post.thread_id
    db.session.delete(post)
    db.session.commit()
    flash("Post usunięty", "info")
    return redirect(url_for("thread_view", thread_id=tid))

@app.route("/threads/delete/<int:thread_id>")
def thread_delete(thread_id):
    th = Thread.query.get_or_404(thread_id)
    if session.get("role")!="nauczyciel":
        abort(403)
    db.session.delete(th)
    db.session.commit()
    flash("Wątek usunięty", "info")
    return redirect(url_for("threads"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))




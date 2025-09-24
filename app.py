import os
from flask import Flask, request, redirect, url_for, session, render_template_string
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# Flask setup
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret")

# Database setup (PostgreSQL on Render)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///local.db").replace("postgres://", "postgresql://")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# =======================
# MODELS
# =======================

class School(db.Model):
    __tablename__ = "school"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    teachers = db.relationship("User", backref="school", lazy=True)


class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")  # "student", "teacher", "normal"
    school_id = db.Column(db.Integer, db.ForeignKey("school.id"), nullable=True)

    posts = db.relationship("LOLPost", backref="author", lazy=True)
    replies = db.relationship("LOLReply", backref="author", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class LOLPost(db.Model):
    __tablename__ = "lol_post"
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(20), nullable=False, default="normal")  # "normal" or "school"
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    replies = db.relationship("LOLReply", backref="post", lazy=True)


class LOLReply(db.Model):
    __tablename__ = "lol_reply"
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("lol_post.id"), nullable=False)


# =======================
# HELPERS
# =======================

def current_user():
    if "user_id" in session:
        return User.query.get(session["user_id"])
    return None

# =======================
# ROUTES
# =======================

@app.route("/")
def home():
    return render_template_string("""
    <h1>LOL Page</h1>
    {% if user %}
        <p>Zalogowany jako {{ user.username }} ({{ user.role }})</p>
        <a href="{{ url_for('logout') }}">Wyloguj</a> | 
        <a href="{{ url_for('normal_page') }}">Normal LOL Page</a> | 
        <a href="{{ url_for('school_page') }}">LOL Page for Schools</a>
    {% else %}
        <a href="{{ url_for('login') }}">Zaloguj</a> | 
        <a href="{{ url_for('register') }}">Zarejestruj</a>
    {% endif %}
    """, user=current_user())


# -----------------------
# AUTH
# -----------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        role = request.form.get("role", "normal")
        school_name = request.form.get("school")

        if User.query.filter_by(username=username).first():
            return "Użytkownik już istnieje!"

        school = None
        if school_name:
            school = School.query.filter_by(name=school_name).first()
            if not school:
                school = School(name=school_name)
                db.session.add(school)

        user = User(username=username, role=role, school=school)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for("login"))

    return render_template_string("""
        <h2>Rejestracja</h2>
        <form method="post">
            Nazwa użytkownika: <input name="username"><br>
            Hasło: <input type="password" name="password"><br>
            Rola: 
            <select name="role">
                <option value="normal">Normal</option>
                <option value="student">Student</option>
                <option value="teacher">Teacher</option>
            </select><br>
            Szkoła (opcjonalnie): <input name="school"><br>
            <button type="submit">Zarejestruj</button>
        </form>
    """)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            return redirect(url_for("home"))
        return "Nieprawidłowe dane logowania!"
    return render_template_string("""
        <h2>Logowanie</h2>
        <form method="post">
            Nazwa użytkownika: <input name="username"><br>
            Hasło: <input type="password" name="password"><br>
            <button type="submit">Zaloguj</button>
        </form>
    """)


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("home"))


# -----------------------
# NORMAL LOL PAGE
# -----------------------

@app.route("/normal", methods=["GET", "POST"])
def normal_page():
    user = current_user()
    if not user:
        return "Musisz się zalogować!"

    if request.method == "POST":
        content = request.form["content"]
        post = LOLPost(content=content, category="normal", author=user)
        db.session.add(post)
        db.session.commit()
        return redirect(url_for("normal_page"))

    posts = LOLPost.query.filter_by(category="normal").all()
    return render_template_string("""
        <h2>Normal LOL Page</h2>
        <form method="post">
            <textarea name="content"></textarea><br>
            <button type="submit">Dodaj post</button>
        </form>
        <ul>
            {% for p in posts %}
                <li>{{ p.content }} - {{ p.author.username }}
                    <ul>
                        {% for r in p.replies %}
                            <li>{{ r.content }} ({{ r.author.username }})</li>
                        {% endfor %}
                    </ul>
                    <form method="post" action="{{ url_for('reply', post_id=p.id) }}">
                        <input name="content" placeholder="Odpowiedź">
                        <button type="submit">Dodaj</button>
                    </form>
                </li>
            {% endfor %}
        </ul>
    """, posts=posts)


# -----------------------
# SCHOOL LOL PAGE
# -----------------------

@app.route("/school", methods=["GET", "POST"])
def school_page():
    user = current_user()
    if not user or user.role not in ["student", "teacher"]:
        return "Tylko uczniowie i nauczyciele mają dostęp!"

    if request.method == "POST":
        content = request.form["content"]
        post = LOLPost(content=content, category="school", author=user)
        db.session.add(post)
        db.session.commit()
        return redirect(url_for("school_page"))

    posts = LOLPost.query.filter_by(category="school").all()
    return render_template_string("""
        <h2>LOL Page for Schools</h2>
        <form method="post">
            <textarea name="content"></textarea><br>
            <button type="submit">Dodaj post</button>
        </form>
        <ul>
            {% for p in posts %}
                <li>{{ p.content }} - {{ p.author.username }}
                    <ul>
                        {% for r in p.replies %}
                            <li>{{ r.content }} ({{ r.author.username }})</li>
                        {% endfor %}
                    </ul>
                    <form method="post" action="{{ url_for('reply', post_id=p.id) }}">
                        <input name="content" placeholder="Odpowiedź">
                        <button type="submit">Dodaj</button>
                    </form>
                </li>
            {% endfor %}
        </ul>
    """, posts=posts)


# -----------------------
# REPLY
# -----------------------

@app.route("/reply/<int:post_id>", methods=["POST"])
def reply(post_id):
    user = current_user()
    if not user:
        return "Musisz się zalogować!"

    content = request.form["content"]
    reply = LOLReply(content=content, author=user, post_id=post_id)
    db.session.add(reply)
    db.session.commit()
    post = LOLPost.query.get(post_id)
    if post.category == "normal":
        return redirect(url_for("normal_page"))
    return redirect(url_for("school_page"))


# =======================
# INIT
# =======================
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)





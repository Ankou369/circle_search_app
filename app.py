import os
import sqlite3

from flask import (Flask, flash, g, redirect, render_template, request,
                   send_from_directory, url_for)
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

# データベースのファイル名（初回起動時に自動作成される）
DATABASE = "campus_hub.db"

app = Flask(__name__)
# セッション署名用の秘密鍵（環境変数があればそれを使い、無ければ開発用）
app.secret_key = os.environ.get("SECRET_KEY", "campus-hub-dev-secret")

# ログイン管理（Flask-Login）
login_manager = LoginManager()
login_manager.init_app(app)

os.makedirs("uploads", exist_ok=True)


class User(UserMixin):
    def __init__(self, userid):
        self.id = userid


### データベース ############################

def connect_db():
    rv = sqlite3.connect(DATABASE)
    rv.row_factory = sqlite3.Row
    return rv


def get_db():
    if not hasattr(g, "sqlite_db"):
        g.sqlite_db = connect_db()
    return g.sqlite_db


def init_db():
    db = connect_db()
    # 学生（個人ユーザー）
    db.execute("""
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            userid TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT,
            faculty TEXT
        )
    """)
    # サークルアカウント
    db.execute("""
        CREATE TABLE IF NOT EXISTS circle_account (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            circle_id TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    # 投稿
    db.execute("""
        CREATE TABLE IF NOT EXISTS post (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            userid TEXT NOT NULL,
            name TEXT,
            title TEXT,
            comment TEXT,
            image_path TEXT
        )
    """)
    # フォロー関係
    db.execute("""
        CREATE TABLE IF NOT EXISTS follow_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            follow_id TEXT NOT NULL
        )
    """)
    # サークル情報
    db.execute("""
        CREATE TABLE IF NOT EXISTS circle_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            circle_id TEXT NOT NULL,
            circle_name TEXT,
            circle_time TEXT,
            circle_place TEXT,
            activity_details TEXT
        )
    """)
    # サークルの学部別人数
    db.execute("""
        CREATE TABLE IF NOT EXISTS circle_number_of_students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            circle_id TEXT NOT NULL,
            information_and_data_science INTEGER DEFAULT 0,
            multicultural_society INTEGER DEFAULT 0,
            education INTEGER DEFAULT 0,
            economics INTEGER DEFAULT 0,
            medicine INTEGER DEFAULT 0,
            dentistry INTEGER DEFAULT 0,
            pharmacy INTEGER DEFAULT 0,
            engineering INTEGER DEFAULT 0,
            environmental_science INTEGER DEFAULT 0,
            fisheries INTEGER DEFAULT 0
        )
    """)
    db.commit()
    db.close()


init_db()


### ログイン共通 ############################

@login_manager.user_loader
def load_user(userid):
    return User(userid)


@login_manager.unauthorized_handler
def unauthorized():
    return redirect("/login")


def get_user_type(user_id):
    """user テーブルにあれば学生、circle_account にあればサークル幹部。"""
    db = get_db()
    if db.execute("SELECT id FROM user WHERE userid = ?", (user_id,)).fetchone():
        return "normal_user"
    if db.execute("SELECT id FROM circle_account WHERE circle_id = ?", (user_id,)).fetchone():
        return "circle_user"
    return None


def current_type():
    """ログイン中のアカウント種別（未ログインなら None）。"""
    if not current_user.is_authenticated:
        return None
    return get_user_type(current_user.id)


def circle_display_name(db, circle_id):
    row = db.execute(
        "SELECT circle_name FROM circle_info WHERE circle_id = ?", (circle_id,)
    ).fetchone()
    if row and row["circle_name"]:
        return row["circle_name"]
    return circle_id


def get_posts(db):
    return db.execute("""
        SELECT post.*,
               (SELECT circle_name FROM circle_info
                 WHERE circle_info.circle_id = post.userid) AS display_name
          FROM post ORDER BY post.id DESC
    """).fetchall()


def get_follow_list(db, user_id):
    rows = db.execute(
        "SELECT follow_id FROM follow_table WHERE user_id = ?", (user_id,)
    ).fetchall()
    return [row[0] for row in rows]


def get_circles(db):
    return db.execute("""
        SELECT circle_account.circle_id AS circle_id,
               (SELECT circle_name FROM circle_info
                 WHERE circle_info.circle_id = circle_account.circle_id) AS circle_name
          FROM circle_account ORDER BY circle_account.id
    """).fetchall()


### 認証ページ（学生） #########################
# 役割タブとログイン/登録の切り替えも、リンクで別URLに分けてサーバー側で管理する。

def render_auth(role, mode, error_message="", id_value=""):
    return render_template(
        "campus_hub/auth.html",
        role=role,
        mode=mode,
        error_message=error_message,
        id_value=id_value,
    )


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect("/")
    if request.method == "GET":
        return render_auth("student", "register")
    userid = request.form.get("userid")
    password = request.form.get("password")
    name = request.form.get("name")
    faculty = request.form.get("faculty")
    if not userid or not password:
        return render_auth("student", "register", "メールアドレスとパスワードを入力してください。", userid or "")
    password_hash = generate_password_hash(password)
    db = get_db()
    if db.execute("SELECT id FROM user WHERE userid = ?", (userid,)).fetchone():
        return render_auth("student", "register", "このIDはすでに使われています。", userid)
    db.execute(
        "INSERT INTO user (userid, password, name, faculty) VALUES (?, ?, ?, ?)",
        (userid, password_hash, name, faculty),
    )
    db.commit()
    flash("登録が完了しました。ログインしてください。")
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect("/")
    if request.method == "GET":
        return render_auth("student", "login")
    userid = request.form.get("userid")
    password = request.form.get("password")
    db = get_db()
    user = db.execute("SELECT * FROM user WHERE userid = ?", (userid,)).fetchone()
    if user and check_password_hash(user["password"], password):
        login_user(User(userid))
        return redirect("/")
    return render_auth("student", "login", "IDかパスワードが誤っています。", userid or "")


### 認証ページ（サークル幹部） ###################

@app.route("/circle_signup", methods=["GET", "POST"])
def circle_signup():
    if current_user.is_authenticated:
        return redirect("/")
    if request.method == "GET":
        return render_auth("leader", "register")
    circle_name = request.form.get("circle_name")
    circle_id = request.form.get("userid")
    password = request.form.get("password")
    if not circle_id or not password:
        return render_auth("leader", "register", "サークルIDとパスワードを入力してください。", circle_id or "")
    password_hash = generate_password_hash(password)
    db = get_db()
    if db.execute("SELECT id FROM circle_account WHERE circle_id = ?", (circle_id,)).fetchone():
        return render_auth("leader", "register", "このサークルIDはすでに使われています。", circle_id)
    db.execute(
        "INSERT INTO circle_account (circle_id, password) VALUES (?, ?)",
        (circle_id, password_hash),
    )
    db.execute(
        "INSERT INTO circle_info (circle_id, circle_name) VALUES (?, ?)",
        (circle_id, circle_name),
    )
    db.commit()
    flash("サークル登録が完了しました。ログインしてください。")
    return redirect("/circle_login")


@app.route("/circle_login", methods=["GET", "POST"])
def circle_login():
    if current_user.is_authenticated:
        return redirect("/")
    if request.method == "GET":
        return render_auth("leader", "login")
    circle_id = request.form.get("userid")
    password = request.form.get("password")
    db = get_db()
    circle = db.execute(
        "SELECT * FROM circle_account WHERE circle_id = ?", (circle_id,)
    ).fetchone()
    if circle and check_password_hash(circle["password"], password):
        login_user(User(circle_id))
        return redirect("/leader")
    return render_auth("leader", "login", "IDかパスワードが誤っています。", circle_id or "")


@app.route("/logout", methods=["GET"])
@login_required
def logout():
    logout_user()
    return redirect("/login")


### 学生の画面 ################################

@app.route("/")
def index():
    if not current_user.is_authenticated:
        return redirect("/login")
    if current_type() == "circle_user":
        return redirect("/leader")
    db = get_db()
    return render_template(
        "campus_hub/student/home.html",
        nav="student",
        active="home",
        posts=get_posts(db),
        follow_list=get_follow_list(db, current_user.id),
    )


@app.route("/campus-hub")
def campus_hub():
    return redirect("/")


@app.route("/discover")
@login_required
def discover():
    if current_type() == "circle_user":
        return redirect("/leader")
    return render_template(
        "campus_hub/student/discover.html", nav="student", active="discover"
    )


@app.route("/list")
@login_required
def circle_list_page():
    if current_type() == "circle_user":
        return redirect("/leader")
    db = get_db()
    return render_template(
        "campus_hub/student/list.html",
        nav="student",
        active="list",
        circles=get_circles(db),
    )


@app.route("/dm")
@login_required
def student_dm():
    if current_type() == "circle_user":
        return redirect("/leader")
    return render_template(
        "campus_hub/student/dm.html", nav="student", active="dm"
    )


@app.route("/profile")
@login_required
def profile():
    if current_type() == "circle_user":
        return redirect("/leader")
    db = get_db()
    student_info = db.execute(
        "SELECT name, faculty FROM user WHERE userid = ?", (current_user.id,)
    ).fetchone()
    return render_template(
        "campus_hub/student/profile.html",
        nav="student",
        active="profile",
        student_info=student_info,
    )


@app.route("/diagnostic")
@login_required
def diagnostic():
    if current_type() == "circle_user":
        return redirect("/leader")
    return render_template("campus_hub/diagnostic.html")


### 幹部の画面 ################################

@app.route("/leader")
@login_required
def leader_home():
    if current_type() != "circle_user":
        return redirect("/")
    db = get_db()
    return render_template(
        "campus_hub/leader/home.html",
        nav="leader",
        active="leader-home",
        leader_circle_name=circle_display_name(db, current_user.id),
    )


@app.route("/leader/dm")
@login_required
def leader_dm():
    if current_type() != "circle_user":
        return redirect("/")
    return render_template(
        "campus_hub/leader/dm.html", nav="leader", active="leader-dm"
    )


@app.route("/leader/settings")
@login_required
def leader_settings():
    if current_type() != "circle_user":
        return redirect("/")
    db = get_db()
    return render_template(
        "campus_hub/leader/settings.html",
        nav="leader",
        active="leader-settings",
        leader_circle_name=circle_display_name(db, current_user.id),
    )


### 投稿 ####################################

@app.route("/post", methods=["POST"])
@login_required
def post():
    if get_user_type(current_user.id) != "circle_user":
        return redirect("/")
    name = request.form["name"]
    title = request.form["title"]
    comment = request.form["comment"]
    image = request.files.get("image")
    image_path = None
    if image and image.filename:
        filename = secure_filename(image.filename)
        image.save(os.path.join("uploads", filename))
        image_path = filename
    db = get_db()
    db.execute(
        "INSERT INTO post (userid, name, title, comment, image_path) VALUES (?, ?, ?, ?, ?)",
        (current_user.id, name, title, comment, image_path),
    )
    db.commit()
    return redirect("/leader")


@app.route("/reset", methods=["POST"])
@login_required
def reset():
    post_id = request.form["post_id"]
    db = get_db()
    db.execute(
        "DELETE FROM post WHERE id = ? AND userid = ?", (post_id, current_user.id)
    )
    db.commit()
    return redirect(request.referrer or "/")


@app.route("/uploads/<filename>")
@login_required
def uploaded_file(filename):
    return send_from_directory("uploads", filename)


### フォロー ################################

@app.route("/follow", methods=["POST"])
@login_required
def follow():
    follow_id = request.form["follow_id"]
    if follow_id == current_user.id:
        return redirect(request.referrer or "/")
    db = get_db()
    result = db.execute(
        """
        SELECT EXISTS(
            SELECT 1 FROM follow_table WHERE user_id = ? AND follow_id = ?
        )
        """,
        (current_user.id, follow_id),
    ).fetchone()
    if result[0] == 0:
        db.execute(
            "INSERT INTO follow_table (user_id, follow_id) VALUES (?, ?)",
            (current_user.id, follow_id),
        )
    else:
        db.execute(
            "DELETE FROM follow_table WHERE user_id = ? AND follow_id = ?",
            (current_user.id, follow_id),
        )
    db.commit()
    return redirect(request.referrer or "/")


### サークル詳細ページ #######################

@app.route("/circle/<string:circle_id>")
@login_required
def circle_account(circle_id):
    db = get_db()
    circle = db.execute(
        "SELECT * FROM circle_account WHERE circle_id = ?", (circle_id,)
    ).fetchone()
    if circle is None:
        return redirect("/")
    posts = db.execute(
        "SELECT * FROM post WHERE userid = ? ORDER BY id DESC", (circle_id,)
    ).fetchall()
    follower = db.execute(
        "SELECT COUNT(*) FROM follow_table WHERE follow_id = ?", (circle_id,)
    ).fetchone()[0]
    following = db.execute(
        "SELECT COUNT(*) FROM follow_table WHERE user_id = ?", (circle_id,)
    ).fetchone()[0]
    circle_info = db.execute(
        "SELECT * FROM circle_info WHERE circle_id = ?", (circle_id,)
    ).fetchone()
    row = db.execute(
        "SELECT 1 FROM follow_table WHERE user_id = ? AND follow_id = ?",
        (current_user.id, circle_id),
    ).fetchone()
    return render_template(
        "campus_hub/circle_detail.html",
        circle=circle,
        circle_name=circle_display_name(db, circle_id),
        posts=posts,
        follower=follower,
        following=following,
        circle_info=circle_info,
        is_following=row is not None,
        now_user_type=get_user_type(current_user.id),
    )


### サークル情報の登録 #######################

@app.route("/regist_circle_info/<string:circle_id>", methods=["GET", "POST"])
@login_required
def regist_circle_info(circle_id):
    if current_user.id != circle_id:
        return redirect("/")
    db = get_db()
    if request.method == "POST":
        circle_name = request.form.get("circle_name")
        circle_time = request.form.get("circle_time")
        circle_place = request.form.get("circle_place")
        activity_details = request.form.get("activity_details")
        existing = db.execute(
            "SELECT id FROM circle_info WHERE circle_id = ?", (circle_id,)
        ).fetchone()
        if existing:
            db.execute(
                """
                UPDATE circle_info
                   SET circle_name = ?, circle_time = ?, circle_place = ?,
                       activity_details = ?
                 WHERE circle_id = ?
                """,
                (circle_name, circle_time, circle_place, activity_details, circle_id),
            )
        else:
            db.execute(
                """
                INSERT INTO circle_info
                    (circle_id, circle_name, circle_time, circle_place, activity_details)
                VALUES (?, ?, ?, ?, ?)
                """,
                (circle_id, circle_name, circle_time, circle_place, activity_details),
            )
        db.commit()
        return redirect(url_for("circle_account", circle_id=circle_id))
    circle_info = db.execute(
        "SELECT * FROM circle_info WHERE circle_id = ?", (circle_id,)
    ).fetchone()
    return render_template(
        "campus_hub/regist_circle_info.html",
        circle_id=circle_id,
        circle_info=circle_info,
    )


if __name__ == "__main__":
    app.run(debug=True)

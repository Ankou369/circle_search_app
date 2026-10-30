import os
import sqlite3

from flask import Flask, flash, g, redirect, render_template, request, send_from_directory
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.security import check_password_hash, generate_password_hash

DATABASE = "campus_hub.db"
UPLOAD_FOLDER = "uploads"

app = Flask(__name__)
# NOTE: 掲示板アプリでは os.urandom(24) で起動ごとに変わり、再起動で全員ログアウトしていた。
# 合体版では環境変数 SECRET_KEY があればそれを使い、無ければ開発用の固定値にする。
app.secret_key = os.environ.get("SECRET_KEY", "campus-hub-dev-secret")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

login_manager = LoginManager()
login_manager.init_app(app)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


class User(UserMixin):
    def __init__(self, userid):
        self.id = userid


### データベース ############################
# NOTE: 掲示板アプリでは get_db() が app.run() より後ろに定義されていて
# `python app.py` 起動時に NameError になったため、合体版では前に置いている。

def connect_db():
    rv = sqlite3.connect(DATABASE)
    rv.row_factory = sqlite3.Row
    return rv


def get_db():
    if not hasattr(g, "sqlite_db"):
        g.sqlite_db = connect_db()
    return g.sqlite_db


def init_db():
    db = sqlite3.connect(DATABASE)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS user (
            userid TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            user_type TEXT,
            name TEXT,
            faculty TEXT
        );
        CREATE TABLE IF NOT EXISTS circle_account (
            circle_id TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            user_type TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS post (
            id INTEGER PRIMARY KEY,
            title TEXT,
            comment TEXT,
            image TEXT,
            userid TEXT
        );
        CREATE TABLE IF NOT EXISTS follow_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            follower_id TEXT NOT NULL,
            following_id TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS circle_info (
            circle_id TEXT,
            name TEXT,
            time TEXT,
            place TEXT,
            activity_details TEXT
        );
        CREATE TABLE IF NOT EXISTS circle_number_of_students (
            circle_id TEXT,
            circle_name TEXT,
            multicultural_count INTEGER DEFAULT 0,
            education_count INTEGER DEFAULT 0,
            economics_count INTEGER DEFAULT 0,
            medicine_count INTEGER DEFAULT 0,
            health_count INTEGER DEFAULT 0,
            dentistry_count INTEGER DEFAULT 0,
            pharmacy_count INTEGER DEFAULT 0,
            data_science_count INTEGER DEFAULT 0,
            engineering_count INTEGER DEFAULT 0,
            environment_count INTEGER DEFAULT 0,
            fisheries_count INTEGER DEFAULT 0
        );
        """
    )
    db.commit()
    db.close()


init_db()


### ログイン共通 ############################

@login_manager.user_loader
def load_user(userid):
    return User(userid)


@login_manager.unauthorized_handler
def unauthorized():
    return redirect("/")


def get_user_type(user_id):
    """掲示板アプリと同じ方式: user → circle_account の順に探して user_type を返す。"""
    if user_id is None:
        return None
    db = get_db()
    row = db.execute("SELECT user_type FROM user WHERE userid = ?", (user_id,)).fetchone()
    if row is None:
        row = db.execute(
            "SELECT user_type FROM circle_account WHERE circle_id = ?", (user_id,)
        ).fetchone()
    return row[0] if row is not None else None


def circle_display_name(db, circle_id):
    row = db.execute(
        "SELECT name FROM circle_info WHERE circle_id = ? LIMIT 1", (circle_id,)
    ).fetchone()
    if row is not None and row["name"]:
        return row["name"]
    return circle_id


### ホーム（CampusHub の1ページ） ############

def render_home(error_message="", auth_role="student", auth_mode="login", initial_screen=None):
    posts = []
    follow_list = []
    circles = []
    student_info = None
    leader_info = None
    leader_circle_name = None

    if current_user.is_authenticated:
        db = get_db()
        posts = db.execute(
            """
            SELECT post.*,
                   (SELECT name FROM circle_info
                     WHERE circle_id = post.userid LIMIT 1) AS display_name
            FROM post
            ORDER BY id DESC
            """
        ).fetchall()

        rows = db.execute(
            "SELECT following_id FROM follow_table WHERE follower_id = ?",
            (current_user.id,),
        ).fetchall()
        follow_list = [row["following_id"] for row in rows]

        circles = db.execute(
            """
            SELECT circle_account.circle_id,
                   (SELECT name FROM circle_info
                     WHERE circle_id = circle_account.circle_id LIMIT 1) AS name
            FROM circle_account
            ORDER BY circle_account.circle_id
            """
        ).fetchall()

        user_type = get_user_type(current_user.id)
        if user_type == "circle_user":
            leader_info = db.execute(
                "SELECT * FROM circle_account WHERE circle_id = ?", (current_user.id,)
            ).fetchone()
            leader_circle_name = circle_display_name(db, current_user.id)
            if initial_screen is None:
                initial_screen = "leader-home"
        else:
            student_info = db.execute(
                "SELECT * FROM user WHERE userid = ?", (current_user.id,)
            ).fetchone()
            if initial_screen is None:
                initial_screen = "student-home"
    else:
        user_type = None
        if initial_screen is None:
            initial_screen = "auth"

    return render_template(
        "campus_hub/index.html",
        posts=posts,
        follow_list=follow_list,
        circles=circles,
        student_info=student_info,
        leader_info=leader_info,
        leader_circle_name=leader_circle_name,
        now_user_type=user_type,
        error_message=error_message,
        auth_role=auth_role,
        auth_mode=auth_mode,
        initial_screen=initial_screen,
    )


@app.route("/")
def index():
    return render_home()


@app.route("/campus-hub")
def campus_hub():
    return render_home()


### 新規登録・ログイン（学生） ###############

@app.route("/signup", methods=["POST"])
def signup():
    userid = request.form.get("userid")
    password = request.form.get("password")
    name = request.form.get("name")
    faculty = request.form.get("faculty")
    pass_hash = generate_password_hash(password)

    db = get_db()
    user_check = db.execute(
        "SELECT userid FROM user WHERE userid = ?", (userid,)
    ).fetchall()
    if not user_check:
        db.execute(
            "INSERT INTO user (userid, password, user_type, name, faculty)"
            " VALUES (?, ?, 'normal_user', ?, ?)",
            (userid, pass_hash, name, faculty),
        )
        db.commit()
        flash("登録が完了しました。ログインしてください。")
        return redirect("/")
    return render_home(
        error_message="入力されたユーザIDはすでに利用されています",
        auth_role="student",
        auth_mode="register",
        initial_screen="auth",
    )


@app.route("/login", methods=["POST"])
def login():
    userid = request.form.get("userid")
    password = request.form.get("password")

    user_data = get_db().execute(
        "SELECT password FROM user WHERE userid = ?", (userid,)
    ).fetchone()

    if user_data is not None and check_password_hash(user_data[0], password):
        login_user(User(userid))
        return redirect("/")

    return render_home(
        error_message="入力されたIDもしくはパスワードが誤っています",
        auth_role="student",
        auth_mode="login",
        initial_screen="auth",
    )


### 新規登録・ログイン（サークル幹部） ########

@app.route("/circle_signup", methods=["POST"])
def circle_signup():
    circle_id = request.form.get("circle_id")
    password = request.form.get("password")
    circle_name = request.form.get("circle_name")
    pass_hash = generate_password_hash(password)

    db = get_db()
    # NOTE: 掲示板アプリでは重複チェックが user テーブルを見ていた誤りを修正し、
    # circle_account テーブルを見るようにした。
    circle_check = db.execute(
        "SELECT circle_id FROM circle_account WHERE circle_id = ?", (circle_id,)
    ).fetchall()
    if not circle_check:
        db.execute(
            "INSERT INTO circle_account (circle_id, password, user_type)"
            " VALUES (?, ?, 'circle_user')",
            (circle_id, pass_hash),
        )
        if circle_name:
            db.execute(
                "INSERT INTO circle_info (circle_id, name) VALUES (?, ?)",
                (circle_id, circle_name),
            )
        db.commit()
        flash("サークル登録が完了しました。ログインしてください。")
        return redirect("/")
    return render_home(
        error_message="入力されたサークルIDはすでに利用されています",
        auth_role="leader",
        auth_mode="register",
        initial_screen="auth",
    )


@app.route("/circle_login", methods=["POST"])
def circle_login():
    circle_id = request.form.get("circle_id")
    password = request.form.get("password")

    user_data = get_db().execute(
        "SELECT password FROM circle_account WHERE circle_id = ?", (circle_id,)
    ).fetchone()

    if user_data is not None and check_password_hash(user_data[0], password):
        login_user(User(circle_id))
        return redirect("/")

    return render_home(
        error_message="入力されたIDもしくはパスワードが誤っています",
        auth_role="leader",
        auth_mode="login",
        initial_screen="auth",
    )


@app.route("/logout", methods=["GET"])
@login_required
def logout():
    logout_user()
    return redirect("/")


### 投稿 ####################################

@app.route("/post", methods=["POST"])
@login_required
def post():
    # 掲示板アプリと同じく、投稿できるのはサークルアカウントだけ
    if get_user_type(current_user.id) != "circle_user":
        return redirect("/")

    title = request.form.get("title")
    comment = request.form.get("comment")
    image = request.files.get("image")

    filename = None
    if image and image.filename != "":
        filename = image.filename
        image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    db = get_db()
    db.execute(
        "INSERT INTO post (title, comment, image, userid) VALUES (?, ?, ?, ?)",
        (title, comment, filename, current_user.id),
    )
    db.commit()
    return redirect("/")


@app.route("/reset", methods=["POST"])
@login_required
def reset():
    db = get_db()
    post_id = request.form.get("id")
    db.execute(
        "DELETE FROM post WHERE id = ? AND userid = ?", (post_id, current_user.id)
    )
    db.commit()
    return redirect(request.referrer or "/")


@app.route("/uploads/<filename>")
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


### フォロー ################################

@app.route("/follow", methods=["POST"])
@login_required
def follow():
    follow_userid = request.form.get("follow_userid")

    db = get_db()
    result = db.execute(
        """
        SELECT EXISTS(
            SELECT 1 FROM follow_table
            WHERE follower_id = ? AND following_id = ?
        )
        """,
        (current_user.id, follow_userid),
    ).fetchone()

    if result[0]:
        db.execute(
            "DELETE FROM follow_table WHERE follower_id = ? AND following_id = ?",
            (current_user.id, follow_userid),
        )
    else:
        db.execute(
            "INSERT INTO follow_table (follower_id, following_id) VALUES (?, ?)",
            (current_user.id, follow_userid),
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

    follower_count = db.execute(
        "SELECT COUNT(*) FROM follow_table WHERE following_id = ?", (circle_id,)
    ).fetchone()[0]
    following_count = db.execute(
        "SELECT COUNT(*) FROM follow_table WHERE follower_id = ?", (circle_id,)
    ).fetchone()[0]

    circle_info = db.execute(
        "SELECT * FROM circle_info WHERE circle_id = ?", (circle_id,)
    ).fetchone()

    is_following = (
        db.execute(
            "SELECT 1 FROM follow_table WHERE follower_id = ? AND following_id = ?",
            (current_user.id, circle_id),
        ).fetchone()
        is not None
    )

    return render_template(
        "campus_hub/circle_detail.html",
        circle=circle,
        circle_name=circle_display_name(db, circle_id),
        posts=posts,
        follower_count=follower_count,
        following_count=following_count,
        circle_info=circle_info,
        is_following=is_following,
        now_user_type=get_user_type(current_user.id),
    )


### サークル情報の登録 #######################

@app.route("/regist_circle_info/<string:circle_id>", methods=["GET", "POST"])
@login_required
def regist_circle_info(circle_id):
    # 自分のサークルの情報だけ編集できる
    if current_user.id != circle_id:
        return redirect("/")

    db = get_db()
    circle = db.execute(
        "SELECT * FROM circle_account WHERE circle_id = ?", (circle_id,)
    ).fetchone()
    if circle is None:
        return redirect("/")

    if request.method == "POST":
        circle_name = request.form.get("circle_name")
        activity_time = request.form.get("activity_time")
        activity_place = request.form.get("activity_place")
        activity_details = request.form.get("activity_details")

        existing = db.execute(
            "SELECT * FROM circle_info WHERE circle_id = ?", (circle_id,)
        ).fetchone()
        if existing is None:
            db.execute(
                "INSERT INTO circle_info (circle_id, name, time, place, activity_details)"
                " VALUES (?, ?, ?, ?, ?)",
                (circle_id, circle_name, activity_time, activity_place, activity_details),
            )
        else:
            db.execute(
                "UPDATE circle_info SET name = ?, time = ?, place = ?,"
                " activity_details = ? WHERE circle_id = ?",
                (circle_name, activity_time, activity_place, activity_details, circle_id),
            )
        db.commit()
        return redirect(f"/circle/{circle_id}")

    circle_info = db.execute(
        "SELECT * FROM circle_info WHERE circle_id = ?", (circle_id,)
    ).fetchone()
    return render_template(
        "campus_hub/regist_circle_info.html",
        circle=circle,
        circle_info=circle_info,
    )


if __name__ == "__main__":
    app.run(debug=True)

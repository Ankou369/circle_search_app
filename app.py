import os
import sqlite3
from calendar import monthcalendar
from datetime import date

from flask import (Flask, flash, g, redirect, render_template, request,
                   send_from_directory, url_for)
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

# データベースのファイル名（初回起動時に自動作成される）
DATABASE = "campus_hub.db"

# 学部一覧（circle_number_of_students の列名と表示名の対応）
FACULTIES = [
    ("information_and_data_science", "情報データ科学部"),
    ("multicultural_society", "多文化社会学部"),
    ("education", "教育学部"),
    ("economics", "経済学部"),
    ("medicine", "医学部"),
    ("dentistry", "歯学部"),
    ("pharmacy", "薬学部"),
    ("engineering", "工学部"),
    ("environmental_science", "環境科学部"),
    ("fisheries", "水産学部"),
]

# 活動曜日（Python の date.weekday() と同じ番号: 月=0 〜 日=6）
WEEKDAYS = [(0, "月"), (1, "火"), (2, "水"), (3, "木"), (4, "金"), (5, "土"), (6, "日")]

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
            activity_details TEXT,
            activity_weekdays TEXT,
            activity_start TEXT,
            activity_end TEXT
        )
    """)
    # 既存のDB（列追加前に作られたもの）に不足列を足す
    existing_cols = [row[1] for row in db.execute("PRAGMA table_info(circle_info)")]
    for col in ("activity_weekdays", "activity_start", "activity_end"):
        if col not in existing_cols:
            db.execute(f"ALTER TABLE circle_info ADD COLUMN {col} TEXT")
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


def schedule_text(info):
    """circle_info の活動スケジュールを「毎週火・金 18:00〜20:00」の形にする。"""
    if not info or not info["activity_weekdays"]:
        return ""
    labels = dict(WEEKDAYS)
    days = "・".join(
        labels[int(d)] for d in info["activity_weekdays"].split(",") if d.strip().isdigit()
    )
    text = f"毎週{days}"
    if info["activity_start"] and info["activity_end"]:
        text += f" {info['activity_start']}〜{info['activity_end']}"
    elif info["activity_start"]:
        text += f" {info['activity_start']}〜"
    return text


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
                 WHERE circle_info.circle_id = circle_account.circle_id) AS circle_name,
               (SELECT activity_details FROM circle_info
                 WHERE circle_info.circle_id = circle_account.circle_id) AS activity_details
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


@app.route("/calendar")
@login_required
def my_calendar():
    if current_type() == "circle_user":
        return redirect("/leader")
    today = date.today()
    ym = request.args.get("ym", "")
    try:
        year, month = (int(part) for part in ym.split("-"))
        date(year, month, 1)
    except (ValueError, AttributeError):
        year, month = today.year, today.month
    db = get_db()
    followed = db.execute(
        """
        SELECT follow_table.follow_id AS circle_id,
               circle_info.circle_name AS circle_name,
               circle_info.activity_weekdays AS activity_weekdays,
               circle_info.activity_start AS activity_start,
               circle_info.activity_end AS activity_end,
               circle_info.circle_place AS circle_place
          FROM follow_table
          LEFT JOIN circle_info ON circle_info.circle_id = follow_table.follow_id
         WHERE follow_table.user_id = ?
        """,
        (current_user.id,),
    ).fetchall()
    schedules = []
    for row in followed:
        if not row["activity_weekdays"]:
            continue
        days = {int(d) for d in row["activity_weekdays"].split(",") if d.strip().isdigit()}
        if days:
            schedules.append((row, days))
    weeks = []
    month_events = []
    for week in monthcalendar(year, month):
        cells = []
        for day_num in week:
            if day_num == 0:
                cells.append(None)
                continue
            current = date(year, month, day_num)
            events = [
                {
                    "circle_id": row["circle_id"],
                    "name": row["circle_name"] or row["circle_id"],
                    "start": row["activity_start"],
                    "end": row["activity_end"],
                    "place": row["circle_place"],
                }
                for row, days in schedules
                if current.weekday() in days
            ]
            cells.append(
                {"day": day_num, "events": events, "is_today": current == today}
            )
            for event in events:
                month_events.append({"date": current, **event})
        weeks.append(cells)
    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    return render_template(
        "campus_hub/student/calendar.html",
        nav="student",
        active="calendar",
        year=year,
        month=month,
        weeks=weeks,
        month_events=month_events,
        weekday_labels=[label for _num, label in WEEKDAYS],
        prev_ym=f"{prev_year}-{prev_month:02d}",
        next_ym=f"{next_year}-{next_month:02d}",
        has_follows=len(followed) > 0,
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
    follower_count = db.execute(
        "SELECT COUNT(*) FROM follow_table WHERE follow_id = ?", (current_user.id,)
    ).fetchone()[0]
    return render_template(
        "campus_hub/leader/home.html",
        nav="leader",
        active="leader-home",
        leader_circle_name=circle_display_name(db, current_user.id),
        follower_count=follower_count,
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


@app.route("/leader/followers")
@login_required
def leader_followers():
    if current_type() != "circle_user":
        return redirect("/")
    db = get_db()
    followers = db.execute(
        """
        SELECT user.userid AS userid, user.name AS name, user.faculty AS faculty
          FROM follow_table
          JOIN user ON user.userid = follow_table.user_id
         WHERE follow_table.follow_id = ?
         ORDER BY follow_table.id
        """,
        (current_user.id,),
    ).fetchall()
    return render_template(
        "campus_hub/leader/followers.html",
        nav="leader",
        active="leader-home",
        followers=followers,
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
    students_row = db.execute(
        "SELECT * FROM circle_number_of_students WHERE circle_id = ?", (circle_id,)
    ).fetchone()
    faculty_stats = []
    if students_row:
        faculty_stats = [
            (label, students_row[col] or 0) for col, label in FACULTIES
        ]
    return render_template(
        "campus_hub/circle_detail.html",
        schedule_text=schedule_text(circle_info),
        faculty_stats=faculty_stats,
        faculty_total=sum(count for _label, count in faculty_stats),
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
        # 活動スケジュール（曜日は "1,4" のようなカンマ区切りで保存する）
        weekdays = sorted({int(d) for d in request.form.getlist("weekdays") if d.isdigit()})
        activity_weekdays = ",".join(str(d) for d in weekdays)
        activity_start = request.form.get("activity_start") or None
        activity_end = request.form.get("activity_end") or None
        existing = db.execute(
            "SELECT id FROM circle_info WHERE circle_id = ?", (circle_id,)
        ).fetchone()
        if existing:
            db.execute(
                """
                UPDATE circle_info
                   SET circle_name = ?, circle_time = ?, circle_place = ?,
                       activity_details = ?, activity_weekdays = ?,
                       activity_start = ?, activity_end = ?
                 WHERE circle_id = ?
                """,
                (circle_name, circle_time, circle_place, activity_details,
                 activity_weekdays, activity_start, activity_end, circle_id),
            )
        else:
            db.execute(
                """
                INSERT INTO circle_info
                    (circle_id, circle_name, circle_time, circle_place, activity_details,
                     activity_weekdays, activity_start, activity_end)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (circle_id, circle_name, circle_time, circle_place, activity_details,
                 activity_weekdays, activity_start, activity_end),
            )
        # 学部別部員数（circle_number_of_students）も一緒に保存する
        counts = {}
        for col, _label in FACULTIES:
            try:
                counts[col] = max(0, int(request.form.get(col) or 0))
            except ValueError:
                counts[col] = 0
        cols = [col for col, _label in FACULTIES]
        existing_students = db.execute(
            "SELECT id FROM circle_number_of_students WHERE circle_id = ?",
            (circle_id,),
        ).fetchone()
        if existing_students:
            assignments = ", ".join(f"{col} = ?" for col in cols)
            db.execute(
                f"UPDATE circle_number_of_students SET {assignments} WHERE circle_id = ?",
                tuple(counts[col] for col in cols) + (circle_id,),
            )
        else:
            col_names = ", ".join(cols)
            placeholders = ", ".join("?" for _ in cols)
            db.execute(
                f"INSERT INTO circle_number_of_students (circle_id, {col_names}) VALUES (?, {placeholders})",
                (circle_id,) + tuple(counts[col] for col in cols),
            )
        db.commit()
        return redirect(url_for("circle_account", circle_id=circle_id))
    circle_info = db.execute(
        "SELECT * FROM circle_info WHERE circle_id = ?", (circle_id,)
    ).fetchone()
    students_row = db.execute(
        "SELECT * FROM circle_number_of_students WHERE circle_id = ?", (circle_id,)
    ).fetchone()
    selected_weekdays = []
    if circle_info and circle_info["activity_weekdays"]:
        selected_weekdays = [
            int(d) for d in circle_info["activity_weekdays"].split(",") if d.strip().isdigit()
        ]
    return render_template(
        "campus_hub/regist_circle_info.html",
        circle_id=circle_id,
        circle_info=circle_info,
        faculties=FACULTIES,
        students_row=students_row,
        weekdays=WEEKDAYS,
        selected_weekdays=selected_weekdays,
    )


if __name__ == "__main__":
    app.run(debug=True)

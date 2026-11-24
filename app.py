import json
import os
import secrets
import smtplib
import sqlite3
from calendar import monthcalendar
from datetime import date, datetime, timedelta
from email.message import EmailMessage

from flask import (Flask, flash, g, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)
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

# サークルの分類（一覧の絞り込み用。circle_info.category に保存する）
CATEGORIES = [("sports", "運動系"), ("culture", "文化系")]

# 学生の新規登録で使えるメールアドレスのドメイン（大学メールのみ許可し、
# メール確認が取れるまで本登録しないことで荒らしを防ぐ）
UNIVERSITY_EMAIL_DOMAIN = "ms.nagasaki-u.ac.jp"

# メール送信設定（環境変数 CAMPUSHUB_SMTP_* で指定する）
# 未設定のときは開発モードとして、確認リンクをサーバーのコンソールに表示する
SMTP_HOST = os.environ.get("CAMPUSHUB_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("CAMPUSHUB_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("CAMPUSHUB_SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("CAMPUSHUB_SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("CAMPUSHUB_SMTP_FROM", "") or SMTP_USER

# 相性診断の質問項目（キーは circle_diagnostic の列名 q1〜q10 と対応）
# (キー, 観点ラベル, 学生への質問文, サークル側の自己評価文)
# 点数はどちらも 1〜10（10 = とてもあてはまる、1 = 全くあてはまらない）
DIAGNOSTIC_QUESTIONS = [
    ("q1", "運動系", "体を動かす活動は好きですか？", "体を動かす活動が中心だ"),
    ("q2", "サークル内交流", "大人数でワイワイ賑やかに盛り上がるのは好きですか？", "大人数でワイワイ賑やかに盛り上がる雰囲気だ"),
    ("q3", "活動日数", "週に何度も頻繁に活動したいですか？", "週に何度も頻繁に活動している"),
    ("q4", "新規性", "今までにやったことがない新しいことに挑戦したいですか？", "新しいことに挑戦する機会が多い"),
    ("q5", "勝負", "勝ち負けをはっきりさせる環境は好きですか？", "勝ち負けをはっきりさせる活動だ（対戦・大会志向）"),
    ("q6", "部費", "活動の充実のためなら、お金を多く支払ってもいいと思えますか？", "部費・活動費は高めだ"),
    ("q7", "上下関係", "先輩・後輩といった立場や規律を重んじる環境は好きですか？", "先輩・後輩の立場や規律を重んじる雰囲気だ"),
    ("q8", "活動場所（屋外）", "屋内よりも屋外（アウトドア）で活動する方が好きですか？", "屋外（アウトドア）での活動が中心だ"),
    ("q9", "活動場所（学外）", "学内の決まった場所だけでなく、色々な場所へ移動して活動したいですか？", "学内だけでなく、色々な場所へ移動して活動することが多い"),
    ("q10", "人前に立つ", "ステージの上など、人前に立って目立つのは好きですか？", "ステージなど、人前に立って目立つ機会が多い"),
]

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
            activity_end TEXT,
            logo_path TEXT,
            category TEXT
        )
    """)
    # 既存のDB（列追加前に作られたもの）に不足列を足す
    existing_cols = [row[1] for row in db.execute("PRAGMA table_info(circle_info)")]
    for col in ("activity_weekdays", "activity_start", "activity_end", "logo_path", "category"):
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
    # 相性診断用プロフィール（サークル側が自分たちで決める 1〜10 の自己評価）
    diag_cols = ", ".join(
        f"{key} INTEGER" for key, _label, _student_q, _circle_q in DIAGNOSTIC_QUESTIONS
    )
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS circle_diagnostic (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            circle_id TEXT UNIQUE NOT NULL,
            {diag_cols}
        )
    """)
    # 相性診断の履歴（マイページで直近1回分を表示するために保存する）
    db.execute("""
        CREATE TABLE IF NOT EXISTS diagnostic_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            answers TEXT,
            results TEXT,
            created_at TEXT
        )
    """)
    # 投稿へのいいね（1人1投稿につき1回まで）
    db.execute("""
        CREATE TABLE IF NOT EXISTS post_like (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            UNIQUE (post_id, user_id)
        )
    """)
    # 投稿へのコメント
    db.execute("""
        CREATE TABLE IF NOT EXISTS post_comment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT
        )
    """)
    # 学生の仮登録（メール確認が終わるまで本登録しない）
    db.execute("""
        CREATE TABLE IF NOT EXISTS pending_user (
            token TEXT PRIMARY KEY,
            userid TEXT NOT NULL,
            password TEXT NOT NULL,
            name TEXT,
            faculty TEXT,
            expires_at TEXT,
            created_at TEXT
        )
    """)
    # チャットの会話（学生×サークルのペア。開始できるのは学生側だけ）
    db.execute("""
        CREATE TABLE IF NOT EXISTS chat_room (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            circle_id TEXT NOT NULL,
            created_at TEXT,
            UNIQUE (student_id, circle_id)
        )
    """)
    # チャットのメッセージ（本文・画像のどちらか、または両方）
    db.execute("""
        CREATE TABLE IF NOT EXISTS chat_message (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            sender_id TEXT NOT NULL,
            body TEXT,
            image_path TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TEXT
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


def diagnostic_score(user_answers, circle_row):
    """相性スコア: 項目ごとに (学生の回答 − サークルの点数) の二乗を合計する。

    小さいほど相性が良い（全項目一致で 0、最大は 10項目 × 9² = 810）。
    """
    total = 0
    for (key, _label, _student_q, _circle_q), answer in zip(
        DIAGNOSTIC_QUESTIONS, user_answers
    ):
        total += (answer - circle_row[key]) ** 2
    return total


def latest_diagnostic(db, user_id):
    """学生の直近1回の診断結果を返す（無ければ None）。

    results は保存時の順位のまま、サークル名は表示時点のもので解決する。
    """
    row = db.execute(
        "SELECT * FROM diagnostic_history WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    if not row:
        return None
    results = [
        {
            "circle_id": r["circle_id"],
            "name": circle_display_name(db, r["circle_id"]),
            "score": r["score"],
        }
        for r in json.loads(row["results"])
    ]
    return {"created_at": row["created_at"], "results": results}


def get_posts(db, user_id=None, circle_id=None):
    """投稿一覧（表示名・ロゴ・いいね数・コメント数・自分のいいね有無つき）。

    circle_id を渡すとそのサークルの投稿だけを返す。
    """
    sql = """
        SELECT post.*,
               (SELECT circle_name FROM circle_info
                 WHERE circle_info.circle_id = post.userid) AS display_name,
               (SELECT logo_path FROM circle_info
                 WHERE circle_info.circle_id = post.userid) AS logo_path,
               (SELECT COUNT(*) FROM post_like
                 WHERE post_like.post_id = post.id) AS like_count,
               (SELECT COUNT(*) FROM post_comment
                 WHERE post_comment.post_id = post.id) AS comment_count,
               EXISTS(SELECT 1 FROM post_like
                 WHERE post_like.post_id = post.id
                   AND post_like.user_id = ?) AS liked
          FROM post
    """
    params = [user_id or ""]
    if circle_id is not None:
        sql += " WHERE post.userid = ?"
        params.append(circle_id)
    sql += " ORDER BY post.id DESC"
    return db.execute(sql, params).fetchall()


def get_post_comments(db, post_id):
    """投稿へのコメント（投稿者の表示名とロゴつき、古い順）。"""
    return db.execute("""
        SELECT post_comment.*,
               COALESCE(
                   (SELECT name FROM user WHERE user.userid = post_comment.user_id),
                   (SELECT circle_name FROM circle_info
                     WHERE circle_info.circle_id = post_comment.user_id),
                   post_comment.user_id
               ) AS display_name,
               (SELECT logo_path FROM circle_info
                 WHERE circle_info.circle_id = post_comment.user_id) AS logo_path
          FROM post_comment
         WHERE post_comment.post_id = ?
         ORDER BY post_comment.id
    """, (post_id,)).fetchall()


def chat_unread_count(db, user_id):
    """自分宛ての未読チャットメッセージ数。"""
    return db.execute(
        """
        SELECT COUNT(*) FROM chat_message
          JOIN chat_room ON chat_room.id = chat_message.room_id
         WHERE (chat_room.student_id = ? OR chat_room.circle_id = ?)
           AND chat_message.sender_id != ?
           AND chat_message.is_read = 0
        """,
        (user_id, user_id, user_id),
    ).fetchone()[0]


def get_chat_room(db, room_id, user_id):
    """自分が参加者である会話だけを返す（他人の会話は None）。"""
    return db.execute(
        "SELECT * FROM chat_room WHERE id = ? AND (student_id = ? OR circle_id = ?)",
        (room_id, user_id, user_id),
    ).fetchone()


def chat_partner_info(db, room, user_id):
    """会話相手の id・表示名・ロゴを返す。"""
    if room["student_id"] == user_id:
        partner_id = room["circle_id"]
        row = db.execute(
            "SELECT circle_name, logo_path FROM circle_info WHERE circle_id = ?",
            (partner_id,),
        ).fetchone()
        name = row["circle_name"] if row and row["circle_name"] else partner_id
        logo = row["logo_path"] if row else None
        return {"id": partner_id, "name": name, "logo_path": logo}
    partner_id = room["student_id"]
    row = db.execute(
        "SELECT name FROM user WHERE userid = ?", (partner_id,)
    ).fetchone()
    name = row["name"] if row and row["name"] else partner_id
    return {"id": partner_id, "name": name, "logo_path": None}


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
                 WHERE circle_info.circle_id = circle_account.circle_id) AS activity_details,
               (SELECT logo_path FROM circle_info
                 WHERE circle_info.circle_id = circle_account.circle_id) AS logo_path,
               (SELECT category FROM circle_info
                 WHERE circle_info.circle_id = circle_account.circle_id) AS category
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


def send_verification_email(to_email, verify_url):
    """登録確認メールを送る。SMTP 未設定なら開発モードとしてリンクをコンソールに出す。"""
    if not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD):
        print(f"[開発モード] {to_email} 宛の登録確認リンク: {verify_url}", flush=True)
        return False
    msg = EmailMessage()
    msg["Subject"] = "【CampusHub】メールアドレスの確認"
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.set_content(
        "CampusHub へのご登録ありがとうございます。\n"
        "以下のリンクを開くと登録が完了します（リンクは24時間有効です）。\n\n"
        f"{verify_url}\n\n"
        "心当たりがない場合は、このメールを破棄してください。\n"
    )
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(msg)
        return True
    except Exception as exc:  # 送信に失敗しても仮登録は残し、リンクはコンソールに出す
        print(f"[メール送信失敗: {exc}] {to_email} 宛の登録確認リンク: {verify_url}", flush=True)
        return False


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect("/")
    if request.method == "GET":
        return render_auth("student", "register")
    userid = (request.form.get("userid") or "").strip()
    password = request.form.get("password")
    name = request.form.get("name")
    faculty = request.form.get("faculty")
    if not userid or not password:
        return render_auth("student", "register", "メールアドレスとパスワードを入力してください。", userid or "")
    suffix = "@" + UNIVERSITY_EMAIL_DOMAIN
    if not userid.endswith(suffix) or len(userid) <= len(suffix):
        return render_auth(
            "student", "register",
            f"大学のメールアドレス（@{UNIVERSITY_EMAIL_DOMAIN}）を入力してください。",
            userid,
        )
    db = get_db()
    if db.execute("SELECT id FROM user WHERE userid = ?", (userid,)).fetchone():
        return render_auth("student", "register", "このメールアドレスはすでに登録されています。", userid)
    # 以前の仮登録があれば消して作り直す（＝確認メールの再送になる）
    db.execute("DELETE FROM pending_user WHERE userid = ?", (userid,))
    token = secrets.token_urlsafe(32)
    now = datetime.now()
    db.execute(
        "INSERT INTO pending_user (token, userid, password, name, faculty, expires_at, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            token,
            userid,
            generate_password_hash(password),
            name,
            faculty,
            (now + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S"),
            now.strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    db.commit()
    verify_url = request.host_url.rstrip("/") + "/verify/" + token
    send_verification_email(userid, verify_url)
    return render_template("campus_hub/verify_sent.html", email=userid)


@app.route("/verify/<string:token>")
def verify_email(token):
    """確認メールのリンク。開かれたら仮登録を本登録に移す。"""
    db = get_db()
    row = db.execute(
        "SELECT * FROM pending_user WHERE token = ?", (token,)
    ).fetchone()
    if row is None:
        return render_template(
            "campus_hub/verify_result.html",
            message="この確認リンクは無効です。お手数ですが、もう一度新規登録からやり直してください。",
        )
    if row["expires_at"] < datetime.now().strftime("%Y-%m-%d %H:%M:%S"):
        db.execute("DELETE FROM pending_user WHERE token = ?", (token,))
        db.commit()
        return render_template(
            "campus_hub/verify_result.html",
            message="確認リンクの期限（24時間）が切れています。もう一度新規登録からやり直してください。",
        )
    if db.execute("SELECT id FROM user WHERE userid = ?", (row["userid"],)).fetchone():
        db.execute("DELETE FROM pending_user WHERE token = ?", (token,))
        db.commit()
        flash("すでに登録が完了しています。ログインしてください。")
        return redirect("/login")
    db.execute(
        "INSERT INTO user (userid, password, name, faculty) VALUES (?, ?, ?, ?)",
        (row["userid"], row["password"], row["name"], row["faculty"]),
    )
    db.execute("DELETE FROM pending_user WHERE token = ?", (token,))
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

def render_feed(nav, active, can_post=False):
    """ホームのフィード（学生用／サークル用で共用。タブでフォロー中・その他を絞る）。"""
    db = get_db()
    tab = request.args.get("tab", "all")
    if tab not in ("all", "following", "others"):
        tab = "all"
    follow_list = get_follow_list(db, current_user.id)
    posts = get_posts(db, current_user.id)
    if tab == "following":
        posts = [p for p in posts if p["userid"] in follow_list]
    elif tab == "others":
        posts = [p for p in posts if p["userid"] not in follow_list]
    return render_template(
        "campus_hub/student/home.html",
        nav=nav,
        active=active,
        posts=posts,
        follow_list=follow_list,
        tab=tab,
        can_post=can_post,
        feed_base="/" if nav == "student" else "/leader/home",
        leader_circle_name=circle_display_name(db, current_user.id) if can_post else "",
        chat_unread=chat_unread_count(db, current_user.id),
    )


@app.route("/")
def index():
    if not current_user.is_authenticated:
        return redirect("/login")
    if current_type() == "circle_user":
        return redirect("/leader")
    return render_feed("student", "home")


@app.route("/leader/home")
@login_required
def leader_feed():
    """サークル側のホーム（学生と同じフィード＋上部の新歓投稿フォーム）。"""
    if current_type() != "circle_user":
        return redirect("/")
    return render_feed("leader", "leader-feed", can_post=True)


@app.route("/campus-hub")
def campus_hub():
    return redirect("/")


@app.route("/list")
@login_required
def circle_list_page():
    if current_type() == "circle_user":
        return redirect("/leader")
    db = get_db()
    cat = request.args.get("cat", "all")
    if cat not in ("all", "sports", "culture"):
        cat = "all"
    circles = get_circles(db)
    if cat != "all":
        circles = [c for c in circles if c["category"] == cat]
    return render_template(
        "campus_hub/student/list.html",
        nav="student",
        active="list",
        circles=circles,
        cat=cat,
        categories=dict(CATEGORIES),
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
        latest_diag=latest_diagnostic(db, current_user.id),
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
def diagnostic_home():
    """相性診断のホーム（説明＋前回結果）。ここから診断を開始する。"""
    if current_type() == "circle_user":
        return redirect("/leader")
    db = get_db()
    diag_count = db.execute("SELECT COUNT(*) FROM circle_diagnostic").fetchone()[0]
    return render_template(
        "campus_hub/diagnostic_home.html",
        nav="student",
        active="diagnostic",
        latest_diag=latest_diagnostic(db, current_user.id),
        diag_count=diag_count,
    )


@app.route("/diagnostic/questions", methods=["GET", "POST"])
@login_required
def diagnostic():
    """相性診断（1問ずつ表示し、回答はセッションに貯めて最後に結果を出す）。"""
    if current_type() == "circle_user":
        return redirect("/leader")
    total = len(DIAGNOSTIC_QUESTIONS)
    keys = [key for key, _l, _s, _c in DIAGNOSTIC_QUESTIONS]

    def render_step(step, error=None):
        key, label, student_q, _circle_q = DIAGNOSTIC_QUESTIONS[step - 1]
        saved = session.get("diag_answers", {})
        return render_template(
            "campus_hub/diagnostic.html",
            step=step,
            total=total,
            percent=round(step / total * 100),
            key=key,
            label=label,
            student_q=student_q,
            answer=saved.get(key),
            error=error,
        )

    if request.method == "POST":
        try:
            step = int(request.form.get("step", "1"))
        except ValueError:
            step = 1
        if not 1 <= step <= total:
            step = 1
        key = keys[step - 1]
        raw = request.form.get(key)
        try:
            value = int(raw)
            if not 1 <= value <= 10:
                raise ValueError
        except (TypeError, ValueError):
            return render_step(step, error="1〜10 のいずれかを選んでください。")
        saved = dict(session.get("diag_answers", {}))
        saved[key] = value
        session["diag_answers"] = saved
        if step < total:
            return redirect(f"/diagnostic/questions?step={step + 1}")
        # 最終問題: 10問そろっていなければ、最初の未回答へ戻す
        missing = [i + 1 for i, k in enumerate(keys) if k not in saved]
        if missing:
            return redirect(f"/diagnostic/questions?step={missing[0]}")
        answers = [saved[k] for k in keys]
        session.pop("diag_answers", None)
        db = get_db()
        results = []
        for row in db.execute("SELECT * FROM circle_diagnostic").fetchall():
            results.append(
                {
                    "circle_id": row["circle_id"],
                    "name": circle_display_name(db, row["circle_id"]),
                    "score": diagnostic_score(answers, row),
                }
            )
        # スコアが小さい（相性が良い）順、同点は名前順
        results.sort(key=lambda r: (r["score"], r["name"]))
        if results:
            # マイページで直近1回分を表示するため、履歴に保存する
            db.execute(
                "INSERT INTO diagnostic_history (user_id, answers, results, created_at)"
                " VALUES (?, ?, ?, ?)",
                (
                    current_user.id,
                    ",".join(str(a) for a in answers),
                    json.dumps(
                        [
                            {"circle_id": r["circle_id"], "score": r["score"]}
                            for r in results
                        ]
                    ),
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                ),
            )
            db.commit()
        return render_template(
            "campus_hub/diagnostic_result.html",
            results=results,
            answers=answers,
        )

    # GET: step 指定がなければ最初から（前回の途中回答は破棄する）
    step_param = request.args.get("step")
    if step_param is None:
        session.pop("diag_answers", None)
        return redirect("/diagnostic/questions?step=1")
    try:
        step = int(step_param)
    except ValueError:
        step = 1
    if not 1 <= step <= total:
        step = 1
    return render_step(step)


@app.route("/diagnostic/result")
@login_required
def diagnostic_result():
    """直近1回の診断結果をもう一度見る（マイページから）。"""
    if current_type() == "circle_user":
        return redirect("/leader")
    db = get_db()
    latest = latest_diagnostic(db, current_user.id)
    if latest is None:
        return redirect("/diagnostic")
    return render_template(
        "campus_hub/diagnostic_result.html",
        results=latest["results"],
        answers=None,
    )


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
    return redirect(request.referrer or "/leader")


@app.route("/reset", methods=["POST"])
@login_required
def reset():
    post_id = request.form["post_id"]
    db = get_db()
    cur = db.execute(
        "DELETE FROM post WHERE id = ? AND userid = ?", (post_id, current_user.id)
    )
    if cur.rowcount:
        # 投稿を消したら、その投稿へのいいね・コメントも一緒に消す
        db.execute("DELETE FROM post_like WHERE post_id = ?", (post_id,))
        db.execute("DELETE FROM post_comment WHERE post_id = ?", (post_id,))
    db.commit()
    return redirect(request.referrer or "/")


@app.route("/like", methods=["POST"])
@login_required
def like_post():
    """投稿へのいいね（押すたびに付ける／外すを切り替える）。"""
    post_id = request.form.get("post_id")
    db = get_db()
    if db.execute("SELECT id FROM post WHERE id = ?", (post_id,)).fetchone():
        existing = db.execute(
            "SELECT id FROM post_like WHERE post_id = ? AND user_id = ?",
            (post_id, current_user.id),
        ).fetchone()
        if existing:
            db.execute(
                "DELETE FROM post_like WHERE post_id = ? AND user_id = ?",
                (post_id, current_user.id),
            )
        else:
            db.execute(
                "INSERT INTO post_like (post_id, user_id) VALUES (?, ?)",
                (post_id, current_user.id),
            )
        db.commit()
    return redirect(request.referrer or "/")


@app.route("/post/<int:post_id>")
@login_required
def post_detail(post_id):
    """投稿の詳細（コメント一覧とコメント投稿フォーム）。"""
    db = get_db()
    posts = get_posts(db, current_user.id)
    post = next((p for p in posts if p["id"] == post_id), None)
    if post is None:
        return redirect("/")
    if current_type() == "circle_user":
        back_url = f"/circle/{post['userid']}"
    else:
        back_url = "/"
    return render_template(
        "campus_hub/post_detail.html",
        post=post,
        comments=get_post_comments(db, post_id),
        back_url=back_url,
        follow_list=get_follow_list(db, current_user.id),
    )


@app.route("/post/<int:post_id>/comment", methods=["POST"])
@login_required
def add_comment(post_id):
    body = (request.form.get("body") or "").strip()
    db = get_db()
    if body and db.execute("SELECT id FROM post WHERE id = ?", (post_id,)).fetchone():
        db.execute(
            "INSERT INTO post_comment (post_id, user_id, body, created_at)"
            " VALUES (?, ?, ?, ?)",
            (post_id, current_user.id, body, datetime.now().strftime("%Y-%m-%d %H:%M")),
        )
        db.commit()
    return redirect(f"/post/{post_id}")


@app.route("/comment/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_comment(comment_id):
    db = get_db()
    row = db.execute(
        "SELECT post_id FROM post_comment WHERE id = ? AND user_id = ?",
        (comment_id, current_user.id),
    ).fetchone()
    if row:
        db.execute("DELETE FROM post_comment WHERE id = ?", (comment_id,))
        db.commit()
        return redirect(f"/post/{row['post_id']}")
    return redirect("/")


### チャット（学生×サークルの1対1。開始できるのは学生側だけ） ##########

@app.route("/chat")
@login_required
def chat_list():
    db = get_db()
    rooms = db.execute(
        """
        SELECT chat_room.*,
               (SELECT MAX(id) FROM chat_message
                 WHERE chat_message.room_id = chat_room.id) AS last_id
          FROM chat_room
         WHERE chat_room.student_id = ? OR chat_room.circle_id = ?
         ORDER BY COALESCE(last_id, 0) DESC, chat_room.id DESC
        """,
        (current_user.id, current_user.id),
    ).fetchall()
    items = []
    for room in rooms:
        last = db.execute(
            "SELECT * FROM chat_message WHERE room_id = ? ORDER BY id DESC LIMIT 1",
            (room["id"],),
        ).fetchone()
        unread = db.execute(
            "SELECT COUNT(*) FROM chat_message"
            " WHERE room_id = ? AND sender_id != ? AND is_read = 0",
            (room["id"], current_user.id),
        ).fetchone()[0]
        items.append(
            {
                "room": room,
                "partner": chat_partner_info(db, room, current_user.id),
                "last": last,
                "unread": unread,
            }
        )
    is_circle = current_type() == "circle_user"
    return render_template(
        "campus_hub/chat_list.html",
        items=items,
        nav="leader" if is_circle else "student",
        active="leader-chat" if is_circle else "chat",
    )


@app.route("/chat/start/<string:circle_id>")
@login_required
def chat_start(circle_id):
    """学生がサークルとの会話を始める（サークル側からは開始できない）。"""
    if current_type() != "normal_user":
        return redirect("/chat")
    db = get_db()
    if not db.execute(
        "SELECT id FROM circle_account WHERE circle_id = ?", (circle_id,)
    ).fetchone():
        return redirect("/list")
    room = db.execute(
        "SELECT * FROM chat_room WHERE student_id = ? AND circle_id = ?",
        (current_user.id, circle_id),
    ).fetchone()
    if room is None:
        cur = db.execute(
            "INSERT INTO chat_room (student_id, circle_id, created_at) VALUES (?, ?, ?)",
            (current_user.id, circle_id, datetime.now().strftime("%Y-%m-%d %H:%M")),
        )
        db.commit()
        room_id = cur.lastrowid
    else:
        room_id = room["id"]
    return redirect(f"/chat/room/{room_id}")


@app.route("/chat/room/<int:room_id>")
@login_required
def chat_room(room_id):
    db = get_db()
    room = get_chat_room(db, room_id, current_user.id)
    if room is None:
        return redirect("/chat")
    # 開いたら相手からのメッセージを既読にする
    db.execute(
        "UPDATE chat_message SET is_read = 1 WHERE room_id = ? AND sender_id != ?",
        (room_id, current_user.id),
    )
    db.commit()
    messages = db.execute(
        "SELECT * FROM chat_message WHERE room_id = ? ORDER BY id", (room_id,)
    ).fetchall()
    return render_template(
        "campus_hub/chat_room.html",
        room=room,
        partner=chat_partner_info(db, room, current_user.id),
        messages=messages,
    )


@app.route("/chat/room/<int:room_id>/send", methods=["POST"])
@login_required
def chat_send(room_id):
    db = get_db()
    room = get_chat_room(db, room_id, current_user.id)
    if room is None:
        return redirect("/chat")
    body = (request.form.get("body") or "").strip()
    image = request.files.get("image")
    image_path = None
    if image and image.filename:
        image_path = f"chat_{room_id}_{secure_filename(image.filename)}"
        image.save(os.path.join("uploads", image_path))
    if body or image_path:
        db.execute(
            "INSERT INTO chat_message (room_id, sender_id, body, image_path, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (room_id, current_user.id, body or None, image_path,
             datetime.now().strftime("%Y-%m-%d %H:%M")),
        )
        db.commit()
    return redirect(f"/chat/room/{room_id}")


@app.route("/chat/room/<int:room_id>/messages")
@login_required
def chat_messages(room_id):
    """新着メッセージのポーリング用（JSON）。取得ついでに既読も付ける。"""
    db = get_db()
    room = get_chat_room(db, room_id, current_user.id)
    if room is None:
        return jsonify({"messages": []})
    try:
        after = int(request.args.get("after", "0"))
    except ValueError:
        after = 0
    rows = db.execute(
        "SELECT * FROM chat_message WHERE room_id = ? AND id > ? ORDER BY id",
        (room_id, after),
    ).fetchall()
    db.execute(
        "UPDATE chat_message SET is_read = 1 WHERE room_id = ? AND sender_id != ?",
        (room_id, current_user.id),
    )
    db.commit()
    return jsonify(
        {
            "messages": [
                {
                    "id": m["id"],
                    "mine": m["sender_id"] == current_user.id,
                    "body": m["body"],
                    "image_path": m["image_path"],
                    "created_at": m["created_at"],
                }
                for m in rows
            ]
        }
    )


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
    posts = get_posts(db, current_user.id, circle_id=circle_id)
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
        category = request.form.get("category")
        if category not in ("sports", "culture"):
            category = None
        circle_time = request.form.get("circle_time")
        circle_place = request.form.get("circle_place")
        activity_details = request.form.get("activity_details")
        # 活動スケジュール（曜日は "1,4" のようなカンマ区切りで保存する）
        weekdays = sorted({int(d) for d in request.form.getlist("weekdays") if d.isdigit()})
        activity_weekdays = ",".join(str(d) for d in weekdays)
        activity_start = request.form.get("activity_start") or None
        activity_end = request.form.get("activity_end") or None
        # ロゴ画像（新しいファイルが選ばれたときだけ差し替える）
        logo_path = None
        logo = request.files.get("logo")
        if logo and logo.filename:
            logo_filename = f"{circle_id}_logo_{secure_filename(logo.filename)}"
            logo.save(os.path.join("uploads", logo_filename))
            logo_path = logo_filename
        existing = db.execute(
            "SELECT id FROM circle_info WHERE circle_id = ?", (circle_id,)
        ).fetchone()
        if existing:
            db.execute(
                """
                UPDATE circle_info
                   SET circle_name = ?, circle_time = ?, circle_place = ?,
                       activity_details = ?, activity_weekdays = ?,
                       activity_start = ?, activity_end = ?, category = ?
                 WHERE circle_id = ?
                """,
                (circle_name, circle_time, circle_place, activity_details,
                 activity_weekdays, activity_start, activity_end, category, circle_id),
            )
        else:
            db.execute(
                """
                INSERT INTO circle_info
                    (circle_id, circle_name, circle_time, circle_place, activity_details,
                     activity_weekdays, activity_start, activity_end, category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (circle_id, circle_name, circle_time, circle_place, activity_details,
                 activity_weekdays, activity_start, activity_end, category),
            )
        if logo_path:
            db.execute(
                "UPDATE circle_info SET logo_path = ? WHERE circle_id = ?",
                (logo_path, circle_id),
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
        # 相性診断用プロフィール（circle_diagnostic）も一緒に保存する
        # 10項目すべてに 1〜10 が入っているときだけ保存する（未設定・一部だけは対象外）
        diag_values = []
        diag_complete = True
        for key, _label, _student_q, _circle_q in DIAGNOSTIC_QUESTIONS:
            raw = request.form.get(f"diag_{key}")
            try:
                value = int(raw)
                if not 1 <= value <= 10:
                    raise ValueError
                diag_values.append(value)
            except (TypeError, ValueError):
                diag_complete = False
                break
        if diag_complete:
            diag_keys = [key for key, _l, _s, _c in DIAGNOSTIC_QUESTIONS]
            existing_diag = db.execute(
                "SELECT id FROM circle_diagnostic WHERE circle_id = ?", (circle_id,)
            ).fetchone()
            if existing_diag:
                assignments = ", ".join(f"{key} = ?" for key in diag_keys)
                db.execute(
                    f"UPDATE circle_diagnostic SET {assignments} WHERE circle_id = ?",
                    tuple(diag_values) + (circle_id,),
                )
            else:
                col_names = ", ".join(diag_keys)
                placeholders = ", ".join("?" for _ in diag_keys)
                db.execute(
                    f"INSERT INTO circle_diagnostic (circle_id, {col_names}) VALUES (?, {placeholders})",
                    (circle_id,) + tuple(diag_values),
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
    diag_row = db.execute(
        "SELECT * FROM circle_diagnostic WHERE circle_id = ?", (circle_id,)
    ).fetchone()
    return render_template(
        "campus_hub/regist_circle_info.html",
        circle_id=circle_id,
        circle_info=circle_info,
        categories=CATEGORIES,
        faculties=FACULTIES,
        students_row=students_row,
        weekdays=WEEKDAYS,
        selected_weekdays=selected_weekdays,
        diagnostic_questions=DIAGNOSTIC_QUESTIONS,
        diag_row=diag_row,
    )


if __name__ == "__main__":
    app.run(debug=True)

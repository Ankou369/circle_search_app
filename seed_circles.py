# -*- coding: utf-8 -*-
"""サークルの一括作成スクリプト（初期データ投入用）。

使い方: このファイルがあるフォルダで `python seed_circles.py` を実行する。
campus_hub.db に、DATA の各サークルについて
  - circle_account（ログイン用アカウント）
  - circle_info（サークル名と活動日数から作る活動時間テキスト）
  - circle_diagnostic（相性診断の自己評価 q1〜q10）
を作成する。

パスワードは実行のたびにランダム生成し、作成した分だけを最後に一覧表示する
（この画面でしか見られないので、必要な場合はその場で控えること）。
すでに同じユーザー名のアカウントがあるサークルはスキップする（上書きしない）。
"""
import os
import secrets
import string
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from werkzeug.security import generate_password_hash

import app as campus  # import 時に init_db() が走り、テーブルが用意される

# (ユーザー名, サークル名, 活動日数/週（None は未記入）, [q1..q10])
# 活動日数の "?" は表で不明だったもの、そのままでは登録しない。
DATA = [
    ("maybes", "Maybe's", "2", [6, 7, 3, 1, 8, 5, 3, 3, 2, 3]),
    ("nx", "N(X)", "1", [5, 5, 1, 7, 8, 5, 3, 1, 2, 3]),
    ("volvicrew", "VOLVICREW", "2", [5, 5, 3, 3, 8, 5, 3, 1, 2, 3]),
    ("archery", "アーチェリー（部）", "1", [5, 5, 1, 8, 7, 5, 3, 6, 2, 4]),
    ("amefuto", "アメフト（部）", "0", [9, 5, 1, 10, 8, 5, 3, 8, 5, 6]),
    ("bobcats", "BOB CATS（部）", "3", [8, 5, 4, 9, 7, 5, 3, 1, 4, 4]),
    ("karate", "空手（部）", "3", [7, 5, 4, 1, 6, 5, 3, 2, 5, 5]),
    ("gymnastics", "器械体操（部）", "3", [7, 5, 4, 7, 7, 5, 3, 2, 5, 5]),
    ("kyudo", "弓道（部）", "4", [6, 5, 6, 4, 8, 5, 3, 6, 5, 5]),
    ("kyogi_dance", "競技ダンス（部）", "0", [7, 7, 1, 8, 8, 5, 3, 2, 5, 7]),
    ("kendo", "剣道（部）", "5", [8, 5, 8, 1, 8, 5, 3, 2, 5, 5]),
    ("hard_tennis", "硬式テニス（部）", "?", [9, 5, 2, 1, 8, 5, 3, 10, 5, 5]),
    ("shochakai_volley", "小茶会バレー", "2", [9, 8, 3, 1, 6, 5, 3, 2, 2, 2]),
    ("cycling", "サイクリング（部）", "1", [8, 5, 1, 4, 8, 5, 3, 10, 8, 5]),
    ("chosa_heidan", "調査兵団（部）", "3", [7, 5, 4, 9, 3, 5, 3, 7, 6, 9]),
    ("jackpot", "Jackpot", "1", [3, 4, 1, 10, 3, 1, 1, 1, 4, 8]),
    ("judo", "柔道（部）", "1", [9, 5, 1, 8, 8, 5, 3, 2, 5, 6]),
    ("shorinji_kempo", "少林寺拳法（部）", "3", [8, 5, 4, 10, 6, 5, 3, 4, 5, 6]),
    ("w_soccer", "女子サッカー（部）", "4", [10, 5, 1, 1, 8, 5, 3, 10, 5, 5]),
    ("w_basketball", "女子バスケ（部）", "4", [10, 5, 1, 1, 8, 5, 3, 10, 5, 5]),
    ("w_volleyball", "女子バレー（部）", "3", [10, 5, 1, 1, 8, 5, 3, 10, 5, 5]),
    ("swimming", "水泳（部）", "5", [9, 5, 8, 1, 8, 5, 3, 1, 6, 6]),
    ("soft_tennis", "ソフテニ（部）", "7", [9, 5, 10, 1, 6, 5, 3, 7, 5, 5]),
    ("isana", "ISANA", "0/1", [7, 5, 1, 10, 3, 5, 3, 1, 9, 2]),
    ("tanken", "探検（部）", "1", [10, 5, 1, 10, 1, 5, 3, 10, 9, 1]),
    ("m_soccer", "男子サッカー（部）", "?", [10, 5, 3, 1, 8, 5, 3, 10, 4, 5]),
    ("m_basketball", "男子バスケ（部）", "4", [10, 5, 6, 1, 8, 5, 3, 10, 4, 5]),
    ("m_volleyball", "男子バレー（部）", "4", [10, 5, 6, 1, 8, 5, 3, 10, 4, 5]),
    ("m_handball", "男子ハンドボール（部）", "?", [8, 5, 3, 5, 8, 5, 3, 10, 4, 5]),
    ("berries", "BERRIES（部）", "3", [7, 5, 4, 5, 6, 5, 3, 3, 3, 8]),
    ("taekwondo", "テコンドー（部）", "3", [7, 5, 4, 6, 8, 5, 3, 2, 4, 7]),
    ("tennis", "テニス（部）", "2", [10, 5, 3, 1, 8, 5, 3, 10, 4, 4]),
    ("triathlon", "トライアスロン（部）", "3", [10, 5, 4, 7, 8, 5, 3, 10, 6, 5]),
    ("badminton_club", "バドミントン（同好会）", "2", [5, 5, 3, 1, 6, 5, 2, 1, 3, 2]),
    ("badminton", "バドミントン（部）", "4", [8, 5, 6, 1, 8, 5, 3, 1, 3, 5]),
    ("forza", "FORZA（部）", "3", [7, 5, 4, 7, 7, 5, 3, 2, 2, 4]),
    ("bouldering", "ボルダリング（部）", "?", [8, 5, 3, 7, 8, 5, 3, 4, 4, 4]),
    ("toppu", "突風（部）", "2", [6, 5, 3, 7, 3, 5, 3, 8, 7, 8]),
    ("yacht", "ヨット（部）", "1", [7, 5, 1, 9, 8, 5, 3, 9, 7, 6]),
    ("rugby", "ラグビー（部）", "5", [10, 5, 8, 2, 8, 5, 3, 10, 6, 6]),
    ("dance_ishiyaku", "ダンス（医歯薬）（部）", "6", [8, 5, 9, 7, 6, 5, 3, 4, 3, 8]),
    ("shinkyokushin", "新極真空手", None, [7, 5, 3, 8, 7, 5, 3, 2, 3, 6]),
    ("table_tennis", "卓球", None, [8, 5, 3, 1, 8, 5, 3, 2, 3, 4]),
    ("ice_hockey_m", "アイスホッケーm", None, [8, 5, 3, 8, 8, 5, 3, 5, 5, 6]),
    ("zao", "Zao", None, [8, 5, 3, 6, 8, 5, 3, 5, 3, 5]),
    ("pickleball", "ピックルボール", None, [7, 5, 3, 10, 8, 5, 3, 1, 2, 4]),
    ("muscle", "マッスル部", None, [6, 5, 3, 8, 8, 5, 3, 2, 2, 8]),
    ("track_field", "陸上競技", None, [10, 5, 3, 1, 8, 5, 3, 10, 5, 5]),
]


def time_text(days):
    """活動日数/週 を表示用の活動時間テキストにする（不明なら空）。"""
    if days is None or days == "?":
        return ""
    if days == "0/1":
        return "週0〜1回"
    return f"週{days}回"


def gen_password():
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(10))


def main():
    db = campus.connect_db()
    created = []
    skipped = []
    diag_cols = ", ".join(f"q{i}" for i in range(1, 11))
    diag_ph = ", ".join("?" for _ in range(10))
    for username, name, days, scores in DATA:
        exists = db.execute(
            "SELECT id FROM circle_account WHERE circle_id = ?", (username,)
        ).fetchone()
        if exists:
            skipped.append(username)
            continue
        password = gen_password()
        db.execute(
            "INSERT INTO circle_account (circle_id, password) VALUES (?, ?)",
            (username, generate_password_hash(password)),
        )
        db.execute(
            "INSERT INTO circle_info (circle_id, circle_name, circle_time) VALUES (?, ?, ?)",
            (username, name, time_text(days)),
        )
        db.execute(
            f"INSERT INTO circle_diagnostic (circle_id, {diag_cols}) VALUES (?, {diag_ph})",
            (username, *scores),
        )
        created.append((username, name, password))
    db.commit()
    db.close()

    print(f"作成: {len(created)}件 / スキップ（既存）: {len(skipped)}件")
    if skipped:
        print("スキップしたユーザー名:", ", ".join(skipped))
    if created:
        print("\n=== 仮パスワード一覧（この表示でしか確認できません）===")
        for username, name, password in created:
            print(f"{username}\t{password}\t{name}")


if __name__ == "__main__":
    main()

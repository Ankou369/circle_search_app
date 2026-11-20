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
ただし circle_info / circle_diagnostic が未登録なら、データがある分だけ補完する。

DATA が第1弾（運動系48）、DATA2 が第2弾（文科系39）。
DATA2 の P.M.C と エコマジック は表で質問10が空欄だったため q10 が None で、
診断プロフィールは未登録になる（値が分かり次第ここに追記して再実行すれば補完される）。
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

# 第2弾（文科系）: (ユーザー名, サークル名, 活動時間テキスト, 活動内容,
#                    活動曜日CSV（月=0..日=6、無ければ ""）, [q1..q10])
# 表の活動日が「ない」・空欄のものは活動時間テキストを空にした。
# 将棋部は表の名前欄が「将棋部まで見た」となっていたため、名前は「将棋部」とした。
DATA2 = [
    ("dj", "DJ", "", "", "", [1, 3, 3, 8, 6, 7, 3, 4, 1, 7]),
    ("flan", "FLAN", "", "救急医療系サークル、BLS体験、ALS体験", "", [1, 2, 3, 6, 1, 2, 3, 4, 3, 3]),
    ("pmc", "P.M.C", "週1回", "軽音サークル", "", [1, 7, 3, 5, 6, 7, 3, 3, 1, None]),
    ("partners_shoes", "Partner's Shoes", "", "LGBTQ+", "", [1, 2, 3, 4, 5, 2, 3, 1, 5, 1]),
    ("peace_caravan", "Peace Caravan隊", "", "平和講座の出前講座", "", [1, 2, 3, 9, 2, 2, 3, 2, 1, 3]),
    ("ronrock", "RON.Rock（部）", "", "軽音サークル", "", [1, 7, 2, 5, 5, 7, 4, 2, 1, 10]),
    ("stars", "STARs", "", "移民・難民問題", "", [1, 2, 3, 8, 2, 2, 3, 2, 10, 1]),
    ("study_for_two", "STUDY FOR TWO", "", "教科書の寄付を半額で販売し寄付する", "", [1, 1, 3, 8, 1, 2, 3, 1, 1, 1]),
    ("igo", "囲碁", "週2回（水曜・金曜）", "囲碁", "2,4", [1, 3, 3, 2, 9, 2, 3, 1, 1, 3]),
    ("ishikei_keion", "医師系軽音（部）", "週1回", "軽音サークル", "", [1, 7, 3, 5, 6, 7, 3, 2, 3, 10]),
    ("eco_magic", "エコマジック", "", "", "", [1, 8, 3, 8, 1, 1, 3, 6, 7, None]),
    ("iroha_dan", "いろは団（部）", "月・水・土", "劇団（社会人や他校もいる）", "0,2,5", [1, 9, 4, 9, 7, 10, 3, 2, 8, 10]),
    ("ryuseikai", "流生会（部）", "週1回", "茶道部", "", [1, 3, 1, 3, 5, 2, 3, 2, 2, 3]),
    ("ccc", "CCC", "", "お笑いサークル", "", [1, 10, 3, 9, 8, 4, 3, 5, 6, 10]),
    ("boat", "BOAT", "", "発展途上国の貧困支援", "", [1, 2, 3, 4, 1, 2, 3, 4, 2, 1]),
    ("kyogi_karuta", "競技かるた（部）", "", "かるた", "", [1, 4, 3, 2, 10, 3, 3, 1, 2, 3]),
    ("kuragi", "クラギ（部）", "月・水・金", "くらっしくギター", "0,2,4", [1, 8, 4, 6, 2, 5, 3, 4, 2, 9]),
    ("keion", "軽音（部）", "火・金・日", "軽音サークル", "1,4,6", [1, 7, 4, 5, 4, 7, 3, 5, 2, 10]),
    ("eureka", "Eureka!", "木曜", "国際交流サークル", "3", [1, 3, 1, 3, 1, 2, 3, 6, 1, 1]),
    ("shishinoko", "ししのこ", "", "社会課題について考える", "", [1, 3, 3, 7, 1, 2, 3, 5, 1, 1]),
    ("shashin", "写真（部）", "第三土曜日", "", "", [1, 4, 1, 5, 1, 4, 3, 8, 10, 3]),
    ("shodo", "書道（部）", "火・金", "", "1,4", [1, 3, 3, 2, 3, 3, 3, 3, 2, 4]),
    ("suisogaku", "吹奏楽（部）", "月・火・木・土", "", "0,1,3,5", [1, 8, 6, 2, 4, 3, 3, 2, 4, 8]),
    ("chodai_no_yu", "長大の湯", "", "温泉旅行サークル", "", [1, 7, 1, 9, 1, 8, 3, 7, 10, 1]),
    ("kaientai", "海援隊", "", "海の清掃サークル", "", [1, 7, 1, 10, 1, 2, 3, 10, 8, 2]),
    ("hamonepia", "はもねぴあ", "月曜", "アカペラサークル", "0", [1, 7, 1, 9, 4, 2, 3, 5, 3, 9]),
    ("biotope", "ビオトープ", "", "ビオトープ（ため池）の清掃", "", [1, 7, 1, 9, 1, 2, 3, 9, 6, 1]),
    ("bijutsu", "美術（部）", "", "", "", [1, 5, 1, 2, 1, 3, 3, 2, 1, 1]),
    ("bungei", "文芸（部）", "", "マンガ書いたり小説書いたりゲームしたり", "", [1, 6, 1, 3, 3, 3, 3, 2, 1, 1]),
    ("hoso_kenkyukai", "放送研究会", "水・金", "朗読とかNHKコンテスト", "2,4", [1, 6, 3, 5, 8, 2, 3, 2, 3, 9]),
    ("boardgame", "ボードゲーム", "", "", "", [1, 9, 1, 4, 9, 2, 3, 1, 1, 1]),
    ("rakugo", "落語", "", "落語サークル", "", [1, 7, 1, 10, 7, 2, 3, 1, 3, 9]),
    ("waka_sosaku", "和歌創作（部）", "", "和歌の創作", "", [1, 4, 1, 10, 1, 2, 3, 1, 1, 1]),
    ("e_rockers", "e_rockers", "月一、月末か初め", "", "", [1, 7, 1, 5, 4, 6, 3, 3, 2, 10]),
    ("costellar", "costellar", "不定期", "コスプレサークル", "", [1, 7, 3, 8, 3, 7, 3, 3, 6, 7]),
    ("lifelogfactory", "lifelogfactory", "不定期", "ものづくりサークル", "", [1, 6, 3, 8, 8, 6, 3, 2, 5, 6]),
    ("nagasaki_sips", "長崎Sip-S（シップス）", "不定期", "ボランティアサークル", "", [1, 8, 3, 6, 1, 2, 3, 6, 7, 3]),
    ("kado", "華道部", "月三回（木曜）", "", "", [1, 5, 1, 7, 4, 2, 3, 1, 1, 5]),
    ("shogi", "将棋部", "", "", "", [1, 3, 2, 5, 3, 2, 3, 1, 1, 2]),
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
    backfilled = []
    diag_cols = ", ".join(f"q{i}" for i in range(1, 11))
    diag_ph = ", ".join("?" for _ in range(10))

    def register(username, name, time_str, details, weekdays, scores):
        exists = db.execute(
            "SELECT id FROM circle_account WHERE circle_id = ?", (username,)
        ).fetchone()
        if not exists:
            password = gen_password()
            db.execute(
                "INSERT INTO circle_account (circle_id, password) VALUES (?, ?)",
                (username, generate_password_hash(password)),
            )
            created.append((username, name, password))
        else:
            skipped.append(username)
        # circle_info が無ければ作る（既存は上書きしない）
        info = db.execute(
            "SELECT id FROM circle_info WHERE circle_id = ?", (username,)
        ).fetchone()
        if not info:
            db.execute(
                "INSERT INTO circle_info (circle_id, circle_name, circle_time,"
                " circle_place, activity_details, activity_weekdays,"
                " activity_start, activity_end) VALUES (?, ?, ?, '', ?, ?, '', '')",
                (username, name, time_str, details, weekdays),
            )
            if exists:
                backfilled.append(f"{username}(info)")
        # 診断プロフィールが無く、10問そろっていれば作る
        if scores and all(s is not None for s in scores):
            diag = db.execute(
                "SELECT id FROM circle_diagnostic WHERE circle_id = ?", (username,)
            ).fetchone()
            if not diag:
                db.execute(
                    f"INSERT INTO circle_diagnostic (circle_id, {diag_cols})"
                    f" VALUES (?, {diag_ph})",
                    (username, *scores),
                )
                if exists:
                    backfilled.append(f"{username}(診断)")

    for username, name, days, scores in DATA:
        register(username, name, time_text(days), "", "", scores)
    for username, name, time_str, details, weekdays, scores in DATA2:
        register(username, name, time_str, details, weekdays, scores)
    db.commit()
    db.close()

    print(f"作成: {len(created)}件 / スキップ（既存）: {len(skipped)}件")
    if backfilled:
        print("補完したもの:", ", ".join(backfilled))
    if skipped:
        print("スキップしたユーザー名:", ", ".join(skipped))
    if created:
        print("\n=== 仮パスワード一覧（この表示でしか確認できません）===")
        for username, name, password in created:
            print(f"{username}\t{password}\t{name}")


if __name__ == "__main__":
    main()

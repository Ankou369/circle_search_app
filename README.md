# CampusHub (NUCS)

長崎大学のサークル検索アプリ（Flask + SQLite）。

## 状態遷移図

画面遷移はすべて app.py のルートで管理している（1画面 = 1URL）。

```mermaid
flowchart TD
    subgraph auth ["認証（未ログイン）"]
        L["/login 学生ログイン"]
        SU["/signup 学生登録（仮登録）"]
        VER["/verify/ メール確認"]
        CL["/circle_login 幹部ログイン"]
        CS["/circle_signup 幹部登録"]
        L <--> SU
        CL <--> CS
        L <--> CL
    end
    subgraph student ["学生"]
        HOME["/ フィード"]
        LIST["/list サークル一覧"]
        CAL["/calendar マイカレンダー"]
        PROF["/profile マイページ"]
        DIAG["/diagnostic 診断ホーム"]
        QUES["/diagnostic/questions 診断（1問ずつ回答）"]
        RES["/diagnostic/result 診断結果（直近1回）"]
        HOME <--> LIST
        HOME <--> CAL
        HOME <--> PROF
        HOME <--> DIAG
        DIAG -->|診断を開始する| QUES
        QUES -->|診断する| RES
        PROF -->|最近の結果を見る| RES
    end
    subgraph leader ["サークル幹部"]
        DASH["/leader ダッシュボード"]
        LFEED["/leader/home ホーム（フィード＋新歓投稿）"]
        LCAL["/leader/calendar 幹部カレンダー（イベント登録）"]
        FOL["/leader/followers フォロワー一覧"]
        SET["/leader/settings 設定"]
        DASH <--> SET
        DASH <--> LFEED
        DASH <--> LCAL
        DASH --> FOL
        FOL --> DASH
    end
    DET["/circle/サークル詳細"]
    PDET["/post/投稿詳細（コメント）"]
    CHAT["/chat 会話一覧"]
    ROOM["/chat/room トーク"]
    REG["/regist_circle_info 情報登録・編集"]
    L -->|学生ログイン成功| HOME
    SU -->|確認メール送信| VER
    VER -->|登録完了| L
    CL -->|幹部ログイン成功| DASH
    CS -->|登録後| CL
    LIST --> DET
    HOME --> DET
    HOME --> PDET
    DET --> PDET
    LFEED --> DET
    LFEED --> PDET
    HOME --> CHAT
    DASH --> CHAT
    DET -->|連絡する（学生のみ開始可）| ROOM
    CHAT <--> ROOM
    DASH --> REG
    SET --> REG
    DET -->|自分のサークルの場合| REG
    REG -->|保存後| DET
    PROF -->|ログアウト| L
    SET -->|ログアウト| L
```

- 未ログインで各ページを開くと /login へリダイレクトされる
- 幹部が学生のページを開くと /leader へ、学生が幹部のページを開くと / へリダイレクトされる
- 投稿・フォロー・削除などの処理は POST のあと元の画面へリダイレクトされる（PRG パターン）

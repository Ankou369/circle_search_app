# CampusHub (NUCS)

長崎大学のサークル検索アプリ（Flask + SQLite）。

## 状態遷移図

画面遷移はすべて app.py のルートで管理している（1画面 = 1URL）。

```mermaid
flowchart TD
    subgraph auth ["認証（未ログイン）"]
        L["/login 学生ログイン"]
        SU["/signup 学生登録"]
        CL["/circle_login 幹部ログイン"]
        CS["/circle_signup 幹部登録"]
        L <--> SU
        CL <--> CS
        L <--> CL
    end
    subgraph student ["学生"]
        HOME["/ フィード"]
        LIST["/list サークル一覧"]
        PROF["/profile マイページ"]
        DIAG["/diagnostic 相性診断"]
        HOME <--> LIST
        HOME <--> PROF
        PROF --> DIAG
        DIAG --> HOME
    end
    subgraph leader ["サークル幹部"]
        DASH["/leader ダッシュボード"]
        FOL["/leader/followers フォロワー一覧"]
        SET["/leader/settings 設定"]
        DASH <--> SET
        DASH --> FOL
        FOL --> DASH
    end
    DET["/circle/サークル詳細"]
    REG["/regist_circle_info 情報登録・編集"]
    L -->|学生ログイン成功| HOME
    SU -->|登録後| L
    CL -->|幹部ログイン成功| DASH
    CS -->|登録後| CL
    LIST --> DET
    HOME --> DET
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

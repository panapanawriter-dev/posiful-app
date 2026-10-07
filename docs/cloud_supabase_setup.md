# 公開版をSupabase共有版へ切り替える

## 1. GitHubへpush

`app.py` と `posiful/settings.py` をpushします。検証用の `tests/test_settings.py`、この手順書、READMEも共有できます。`.env` と `.streamlit/secrets.toml` はpushしません。

## 2. Streamlit CloudのSecretsを設定

公開アプリの **Manage app → Settings → Secrets** を開きます。既存のデモ設定を次の設定へ変更します。URL・公開キーはローカルの `.env` と同じSupabaseプロジェクトのものを使います。

```toml
POSIFUL_DEMO_SESSION_ONLY = false
SUPABASE_URL = "https://dklpsxmjbhmgertlbnhc.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "ここに既存プロジェクトの公開キーを入力"
```

AIによるレシピ登録も利用する場合は、同じSecretsに追加します。

```toml
OPENAI_API_KEY = "ここにOpenAI APIキーを入力"
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
```

キーはSecretsにだけ入力し、GitHubには含めません。service_role・secretキーは使用しません。設定はルート階層に記載してください。

## 3. 保存・再起動して確認

Secretsを保存し、必要ならReboot appで再起動します。サイドバーに **共有ワークスペース · 全員が編集できます** と表示されれば共有版です。詳細画面の保存先も **Supabaseの共有予定に保存されます** に変わります。

レシピ・在庫・販売実績・予定と保存済みベクトルをDBから読み込みます。検索だけではOpenAI APIを呼びません。レシピ登録・予定差し替えは同じ共有DBに保存され、別ブラウザでも再読み込みすると反映されます。ログインは不要です。

切り替え前のデモセッションで行った変更はDBへ自動移行されません。既にDBに移行済みの10件のベクトルを使用します。

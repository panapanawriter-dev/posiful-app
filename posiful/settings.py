"""ローカル環境変数とCloud Secretsから起動設定を読み込む。"""
import os


CONFIG_KEYS = (
    'SUPABASE_URL', 'SUPABASE_PUBLISHABLE_KEY', 'OPENAI_API_KEY',
    'OPENAI_CHAT_MODEL', 'OPENAI_EMBEDDING_MODEL', 'POSIFUL_DEMO_SESSION_ONLY',
)


def configure(secrets, environ=None):
    """Secretsを優先。値をログに出さず、既存のAPI層へ渡す。"""
    environ = os.environ if environ is None else environ
    for key in CONFIG_KEYS:
        if key in secrets:
            value = secrets[key]
            environ[key] = str(value)
    return str(environ.get('POSIFUL_DEMO_SESSION_ONLY', '')).strip().lower() in ('true', '1')

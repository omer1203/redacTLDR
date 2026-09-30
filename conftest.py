"""Force pytest at a local database so a developer `.env` cannot point tests at a shared project."""

import os

os.environ["ENVIRONMENT"] = "local"
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_REGION", "us-east-1")


def _first_reachable_test_url() -> str:
    explicit = os.environ.get("REDACTLDR_TEST_DATABASE_URL")
    candidates = [
        explicit,
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/redactldr_test",
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5433/redactldr_test",
    ]
    try:
        import psycopg
    except ImportError:
        return candidates[1]
    for url in candidates:
        if not url:
            continue
        admin = url.rsplit("/", 1)[0] + "/postgres"
        admin = admin.replace("postgresql+psycopg://", "postgresql://", 1)
        try:
            with psycopg.connect(admin, connect_timeout=2) as conn:
                conn.execute("SELECT 1")
            return url
        except Exception:
            continue
    return explicit or candidates[1]


os.environ["DATABASE_URL"] = _first_reachable_test_url()

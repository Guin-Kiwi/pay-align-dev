import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault(
    "SESSION_SECRET_KEY", "test-only-session-secret-key-at-least-32-characters"
)

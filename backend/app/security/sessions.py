from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import Settings

COOKIE = "piae_session"
CSRF_COOKIE = "piae_csrf"


def serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt="piae-session")


def dump_session(settings: Settings, user_id: str, csrf: str) -> str:
    return serializer(settings).dumps({"uid": user_id, "csrf": csrf})


def load_session(settings: Settings, token: str) -> dict | None:
    try:
        data = serializer(settings).loads(token, max_age=settings.session_ttl_seconds)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict) or "uid" not in data or "csrf" not in data:
        return None
    return data

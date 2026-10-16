from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import SourceSetting, User
from app.security.passwords import hash_password

SOURCE_ROWS = [
    ("demonstration", True, "Live collection is off. Only the submitted indicator is stored.", False, False),
    ("dns", False, "Public DNS resolution through the worker resolver. Disabled while demonstration mode is on.", False, False),
    ("rdap", False, "Public RDAP registration lookup. Subject to provider limits.", False, False),
    ("ct", False, "Certificate transparency via crt.sh. Free-tier rate limits apply.", False, False),
    ("urlhaus", False, "URLHaus host API. Enable only if you accept the provider terms.", False, False),
    ("ripe", False, "RIPEstat prefix, ASN, and country for current public addresses. No API key.", False, False),
    ("wayback", False, "Wayback Machine capture dates for the host. No API key.", False, False),
    ("page", False, "One public page request for the title, SEO fields, image URLs, server header, and technology hints.", False, False),
    ("profiles", False, "Public page checks for a full name. No API key.", False, False),
    ("openrouter", False, "Optional narrative reports. The API key stays in the environment.", True, False),
]


def _ensure_user(db: Session, email: str, password: str, display_name: str, role: str) -> User:
    user = db.query(User).filter(User.email == email).one_or_none()
    if user is not None:
        return user
    user = User(email=email, display_name=display_name, password_hash=hash_password(password), role=role)
    db.add(user)
    db.flush()
    return user


def _ensure_sources(db: Session) -> None:
    settings = get_settings()
    configured = {
        "openrouter": bool(settings.openrouter_api_key),
    }
    for name, enabled, description, requires_key, _key in SOURCE_ROWS:
        row = db.get(SourceSetting, name)
        key_configured = configured.get(name, False)
        if name == "dns":
            enabled = enabled or settings.dns_enabled
        elif name == "rdap":
            enabled = enabled or settings.rdap_enabled
        elif name == "ct":
            enabled = enabled or settings.ct_enabled
        elif name == "urlhaus":
            enabled = enabled or settings.urlhaus_enabled
        elif name == "ripe":
            enabled = enabled or settings.ripe_enabled
        elif name == "wayback":
            enabled = enabled or settings.wayback_enabled
        elif name == "page":
            enabled = enabled or settings.page_enabled
        elif name == "profiles":
            enabled = (not settings.demo_mode) and settings.profiles_enabled
        elif name == "openrouter":
            enabled = key_configured
        if row is None:
            db.add(
                SourceSetting(
                    name=name,
                    enabled=enabled,
                    description=description,
                    requires_key=requires_key,
                    key_configured=key_configured,
                )
            )
        else:
            row.description = description
            row.requires_key = requires_key
            row.key_configured = key_configured
            row.enabled = enabled


def seed_database(db: Session | None = None) -> None:
    own_session = db is None
    if db is None:
        from app.db import SessionLocal as session_factory
        from app.db import init_db

        if session_factory is None:
            init_db(get_settings())
            from app.db import SessionLocal as session_factory
        if session_factory is None:
            raise RuntimeError("Database is not initialised")
        db = session_factory()
    settings = get_settings()
    try:
        _ensure_user(
            db,
            settings.analyst_email,
            settings.analyst_password,
            settings.analyst_display_name,
            "analyst",
        )
        _ensure_user(db, settings.admin_email, settings.admin_password, settings.admin_display_name, "admin")
        _ensure_sources(db)
        db.commit()
    finally:
        if own_session:
            db.close()

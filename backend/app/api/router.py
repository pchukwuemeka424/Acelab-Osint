import csv
import io
import json
import secrets
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import (
    AnalystFeedback,
    AuditEvent,
    Entity,
    EvidenceSource,
    ExportJob,
    Investigation,
    InvestigationJob,
    Observation,
    Relationship,
    SourceSetting,
    User,
    utcnow,
)
from app.security.passwords import hash_password, verify_password
from app.security.rate_limit import RateLimitExceeded, limiter
from app.security.sessions import COOKIE, CSRF_COOKIE, dump_session, load_session
from app.security.ssrf import UnsafeURL, fetch_recorded_image
from app.services.campaign import ensure_campaign, rank_expansion
from app.services.graph_analysis import shortest_path
from app.services.normalize import InvalidIndicator, classify_indicator
from app.services.pipeline import enqueue
from app.services.reports import build_handoff, build_report

router = APIRouter(prefix="/api")

TYPE_GROUPS = {
    "domain": ["domain"],
    "ip": ["ip"],
    "certificate": ["certificate"],
    "ssh": ["ssh"],
    "contact": ["contact", "name", "account"],
    "file": ["file"],
    "hypothesis": ["hypothesis"],
    "seo": ["seo"],
    "logo": ["logo"],
    "url": ["url"],
    "whois": ["whois"],
    "more": ["nameserver", "hosting", "indicator", "fingerprint"],
}
SORTS = {"domain", "registrar", "reg_date", "exp_date", "ip"}
DEFAULT_GRAPH_TYPES = ["domain", "ip", "certificate", "nameserver", "url", "hosting", "indicator", "fingerprint", "account"]


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=200)


class InvestigationIn(BaseModel):
    indicator: str = Field(min_length=1, max_length=512)


class InvestigationPatch(BaseModel):
    is_saved: bool | None = None
    title: str | None = Field(default=None, max_length=512)


class NoteIn(BaseModel):
    note: str = Field(min_length=1, max_length=4000)
    entity_id: str | None = None


class SettingsIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    current_password: str | None = None
    new_password: str | None = Field(default=None, min_length=8, max_length=200)


class SourcePatch(BaseModel):
    enabled: bool


class PathIn(BaseModel):
    source_id: str
    target_id: str


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _cookie_flags() -> dict:
    settings = get_settings()
    return {
        "secure": settings.environment == "production",
        "samesite": "lax",
        "path": "/",
        "max_age": settings.session_ttl_seconds,
    }


def _audit(db: Session, user_id: str | None, action: str, target: str, details: dict | None = None) -> None:
    db.add(AuditEvent(user_id=user_id, action=action, target=target[:255], details_json=details or {}))


def _local_analyst(db: Session) -> User | None:
    email = get_settings().analyst_email.strip().lower()
    user = db.query(User).filter(User.email == email).one_or_none()
    if user is not None:
        return user
    return db.query(User).order_by(User.created_at.asc()).first()


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE)
    payload = load_session(get_settings(), token) if token else None
    user = db.get(User, payload["uid"]) if payload is not None else None
    if user is None:
        user = _local_analyst(db)
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required.")
        return user
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        header = request.headers.get("x-csrf-token")
        cookie = request.cookies.get(CSRF_COOKIE)
        if not header or header != cookie or header != payload["csrf"]:
            raise HTTPException(status_code=403, detail="CSRF check failed.")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access is required.")
    return user


def _investigation(db: Session, user: User, investigation_id: str) -> Investigation:
    row = db.get(Investigation, investigation_id)
    if row is None or (row.owner_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="Investigation not found.")
    return row


def _counts(entities: list[Entity]) -> dict[str, int]:
    counts = {key: 0 for key in TYPE_GROUPS}
    for entity in entities:
        for name, types in TYPE_GROUPS.items():
            if entity.entity_type in types:
                counts[name] += 1
    return counts


def _latest_observation(db: Session, entity_id: str) -> Observation | None:
    return (
        db.query(Observation)
        .filter(Observation.entity_id == entity_id)
        .order_by(Observation.retrieved_at.desc())
        .first()
    )


def _entity_out(db: Session, entity: Entity) -> dict:
    observation = _latest_observation(db, entity.id)
    source_name = None
    if observation is not None:
        from app.models import EvidenceSource

        source = db.get(EvidenceSource, observation.source_id)
        source_name = source.name if source else None
    return {
        "id": entity.id,
        "entity_type": entity.entity_type,
        "display_value": entity.display_value,
        "normalized_value": entity.normalized_value,
        "risk_state": entity.risk_state,
        "degree": entity.degree,
        "pos_x": entity.pos_x,
        "pos_y": entity.pos_y,
        "metadata": entity.metadata_json or {},
        "first_observed": _iso(entity.first_observed),
        "last_observed": _iso(entity.last_observed),
        "source_name": source_name,
        "retrieved_at": _iso(observation.retrieved_at) if observation else None,
        "observed_at": _iso(observation.observed_at) if observation else None,
        "verification_status": observation.verification_status if observation else None,
        "observation_id": observation.id if observation else None,
    }


def _sort_value(entity: Entity, sort: str) -> str:
    meta = entity.metadata_json or {}
    if sort == "registrar":
        return str(meta.get("registrar") or "")
    if sort == "reg_date":
        return str(meta.get("registered_at") or "")
    if sort == "exp_date":
        return str(meta.get("expires_at") or "")
    if sort == "ip":
        if entity.entity_type == "ip":
            return entity.normalized_value
        return str(meta.get("ip") or "")
    return entity.display_value.lower()


def _investigation_out(row: Investigation) -> dict:
    return {
        "id": row.id,
        "root_indicator": row.root_indicator,
        "indicator_type": row.indicator_type,
        "title": row.title,
        "status": row.status,
        "is_saved": row.is_saved,
        "is_demonstration": row.is_demonstration,
        "entity_count": row.entity_count,
        "relationship_count": row.relationship_count,
        "root_entity_id": row.root_entity_id,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    database = True
    try:
        db.query(User).limit(1).all()
    except Exception:
        database = False
    redis_ok = False
    settings = get_settings()
    if settings.redis_url:
        try:
            import redis

            redis_ok = bool(redis.Redis.from_url(settings.redis_url).ping())
        except Exception:
            redis_ok = False
    return {
        "status": "ok" if database else "degraded",
        "database": database,
        "redis": redis_ok,
        "neo4j_configured": bool(settings.neo4j_uri),
        "demo_mode": settings.demo_mode,
        "openrouter_configured": bool(settings.openrouter_api_key),
        "debug": settings.debug,
    }


@router.post("/auth/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    try:
        limiter.check(f"login:{_client_key(request)}", 10, 60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=exc.public_message) from exc
    email = body.email.strip().lower()
    user = db.query(User).filter(User.email == email).one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Those credentials were not accepted.")
    csrf = secrets.token_urlsafe(24)
    flags = _cookie_flags()
    response.set_cookie(COOKIE, dump_session(get_settings(), user.id, csrf), httponly=True, **flags)
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, **flags)
    _audit(db, user.id, "login", user.email)
    db.commit()
    return {"id": user.id, "email": user.email, "display_name": user.display_name, "role": user.role}


@router.post("/auth/logout")
def logout(response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    response.delete_cookie(COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    _audit(db, user.id, "logout", user.email)
    db.commit()
    return {"ok": True}


@router.get("/auth/me")
def me(user: User = Depends(current_user)) -> dict:
    return {"id": user.id, "email": user.email, "display_name": user.display_name, "role": user.role}


@router.patch("/settings")
def update_settings(body: SettingsIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    if body.display_name:
        user.display_name = body.display_name.strip()
    if body.new_password:
        if not body.current_password or not verify_password(body.current_password, user.password_hash):
            raise HTTPException(status_code=400, detail="The current password was not accepted.")
        user.password_hash = hash_password(body.new_password)
    _audit(db, user.id, "settings_update", user.id)
    db.commit()
    return {"id": user.id, "email": user.email, "display_name": user.display_name, "role": user.role}


@router.get("/investigations")
def list_investigations(
    saved: bool | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(Investigation)
    if user.role != "admin":
        query = query.filter(Investigation.owner_id == user.id)
    if saved is not None:
        query = query.filter(Investigation.is_saved == saved)
    rows = query.order_by(Investigation.created_at.desc()).limit(200).all()
    return {"items": [_investigation_out(row) for row in rows]}


@router.get("/investigations/current")
def current_investigation(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    row = (
        db.query(Investigation)
        .filter(Investigation.owner_id == user.id)
        .order_by(Investigation.created_at.desc())
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="No investigation is available.")
    return _investigation_out(row)


def _missing_public_sources(db: Session, investigation: Investigation) -> bool:
    required = [
        name
        for name in ("ripe", "wayback", "page")
        if (row := db.get(SourceSetting, name)) is not None and row.enabled
    ]
    if not required:
        return False
    found = {
        name
        for (name,) in db.query(EvidenceSource.name)
        .join(Observation, Observation.source_id == EvidenceSource.id)
        .filter(Observation.investigation_id == investigation.id)
        .all()
    }
    if any(name not in found for name in required):
        return True
    domain = (
        db.query(Entity)
        .filter(Entity.investigation_id == investigation.id, Entity.entity_type == "domain")
        .first()
    )
    metadata = domain.metadata_json or {} if domain is not None else {}
    if "page" in required and not metadata.get("subpages"):
        return True
    rdap = db.get(SourceSetting, "rdap")
    if rdap is not None and rdap.enabled and not metadata.get("whois_record"):
        return True
    if "mx" not in metadata:
        return True
    addresses = (
        db.query(Entity)
        .filter(Entity.investigation_id == investigation.id, Entity.entity_type == "ip")
        .all()
    )
    return any(
        (row.metadata_json or {}).get("prefix") and "geoloc" not in (row.metadata_json or {})
        for row in addresses
    )


@router.post("/investigations", status_code=202)
def create_investigation(
    body: InvestigationIn,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        limiter.check(f"investigate:{user.id}", 10, 60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=exc.public_message) from exc
    try:
        indicator_type, normalized = classify_indicator(body.indicator)
    except InvalidIndicator as exc:
        raise HTTPException(status_code=422, detail=exc.public_message) from exc
    existing = (
        db.query(Investigation)
        .filter(
            Investigation.owner_id == user.id,
            Investigation.root_indicator == normalized,
            Investigation.status == "completed",
        )
        .order_by(Investigation.created_at.desc())
        .first()
    )
    if (
        existing is not None
        and (get_settings().demo_mode or not _missing_public_sources(db, existing))
    ):
        return {**_investigation_out(existing), "existing": True, "job_id": None}
    investigation = Investigation(
        owner_id=user.id,
        root_indicator=normalized,
        indicator_type=indicator_type,
        title=normalized,
        status="queued",
        is_demonstration=get_settings().demo_mode,
    )
    db.add(investigation)
    db.flush()
    job = InvestigationJob(investigation_id=investigation.id, status="queued", stage="queued", progress=0)
    db.add(job)
    _audit(db, user.id, "investigation_create", investigation.id, {"indicator_type": indicator_type})
    db.commit()
    enqueue(investigation.id, job.id)
    db.refresh(investigation)
    return {**_investigation_out(investigation), "existing": False, "job_id": job.id}


@router.get("/investigations/{investigation_id}")
def get_investigation(investigation_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return _investigation_out(_investigation(db, user, investigation_id))


@router.patch("/investigations/{investigation_id}")
def patch_investigation(
    investigation_id: str,
    body: InvestigationPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    row = _investigation(db, user, investigation_id)
    if body.is_saved is not None:
        row.is_saved = body.is_saved
    if body.title:
        row.title = body.title.strip()
    row.updated_at = utcnow()
    _audit(db, user.id, "investigation_update", row.id, {"is_saved": row.is_saved})
    db.commit()
    return _investigation_out(row)


@router.get("/investigations/{investigation_id}/jobs/{job_id}")
def get_job(investigation_id: str, job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    _investigation(db, user, investigation_id)
    job = db.get(InvestigationJob, job_id)
    if job is None or job.investigation_id != investigation_id:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "id": job.id,
        "status": job.status,
        "progress": job.progress,
        "stage": job.stage,
        "error": job.error,
    }


@router.get("/investigations/{investigation_id}/entities")
def list_entities(
    investigation_id: str,
    entity_type: str = "domain",
    sort: str = "domain",
    direction: str = "asc",
    q: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=200, ge=1, le=200),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    investigation = _investigation(db, user, investigation_id)
    if entity_type not in TYPE_GROUPS or sort not in SORTS or direction not in {"asc", "desc"}:
        raise HTTPException(status_code=422, detail="That filter is not supported.")
    entities = db.query(Entity).filter(Entity.investigation_id == investigation.id).all()
    counts = _counts(entities)
    typed = [entity for entity in entities if entity.entity_type in TYPE_GROUPS[entity_type]]
    needle = q.strip().lower()[:200]
    if needle:
        def matches(entity: Entity) -> bool:
            meta = entity.metadata_json or {}
            haystack = " ".join(
                [
                    entity.display_value,
                    entity.normalized_value,
                    str(meta.get("registrar") or ""),
                    str(meta.get("organization") or ""),
                    str(meta.get("ip") or ""),
                    str(meta.get("fingerprint") or ""),
                    str(meta.get("title") or ""),
                    str(meta.get("description") or ""),
                    str(meta.get("url") or ""),
                    str(meta.get("kind") or ""),
                    str(meta.get("platform") or ""),
                    str(meta.get("category") or ""),
                    str(meta.get("handle") or ""),
                ]
            ).lower()
            return needle in haystack

        typed = [entity for entity in typed if matches(entity)]
    typed.sort(key=lambda entity: _sort_value(entity, sort), reverse=direction == "desc")
    start = (page - 1) * page_size
    page_items = typed[start : start + page_size]
    return {
        "items": [_entity_out(db, entity) for entity in page_items],
        "total": len(typed),
        "counts": counts,
        "page": page,
        "page_size": page_size,
    }


@router.get("/investigations/{investigation_id}/entities/{entity_id}/image")
def entity_image(investigation_id: str, entity_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    investigation = _investigation(db, user, investigation_id)
    entity = db.get(Entity, entity_id)
    url = (entity.metadata_json or {}).get("url") if entity is not None else None
    if entity is None or entity.investigation_id != investigation.id or entity.entity_type != "logo" or not isinstance(url, str):
        raise HTTPException(status_code=404, detail="Image not found.")
    try:
        content, media_type = fetch_recorded_image(url)
    except UnsafeURL as exc:
        raise HTTPException(status_code=404, detail="The image could not be retrieved.") from exc
    return Response(content=content, media_type=media_type, headers={"Cache-Control": "private, max-age=300"})


@router.get("/investigations/{investigation_id}/entities/{entity_id}")
def get_entity(investigation_id: str, entity_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    investigation = _investigation(db, user, investigation_id)
    entity = db.get(Entity, entity_id)
    if entity is None or entity.investigation_id != investigation.id:
        raise HTTPException(status_code=404, detail="Entity not found.")
    relationships = (
        db.query(Relationship)
        .filter(
            Relationship.investigation_id == investigation.id,
            ((Relationship.source_entity_id == entity.id) | (Relationship.target_entity_id == entity.id)),
        )
        .limit(40)
        .all()
    )
    payload = _entity_out(db, entity)
    payload["relationships"] = [_relationship_out(db, row) for row in relationships]
    return payload


def _relationship_out(db: Session, row: Relationship) -> dict:
    source = db.get(Entity, row.source_entity_id)
    target = db.get(Entity, row.target_entity_id)
    return {
        "id": row.id,
        "source": row.source_entity_id,
        "target": row.target_entity_id,
        "source_label": source.display_value if source else "",
        "target_label": target.display_value if target else "",
        "rel_type": row.rel_type,
        "reason": row.reason,
        "provenance": row.provenance,
        "risk_state": row.risk_state,
        "observation_ids": row.observation_ids or [],
        "observed_at": _iso(row.observed_at),
        "retrieved_at": _iso(row.retrieved_at),
        "is_conflicting": row.is_conflicting,
        "is_stale": row.is_stale,
        "weak_reason": row.weak_reason,
    }


@router.get("/investigations/{investigation_id}/graph")
def get_graph(
    investigation_id: str,
    types: str = "",
    rel_types: str = "",
    risk: str = "",
    observed_after: date | None = None,
    observed_before: date | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    investigation = _investigation(db, user, investigation_id)
    ensure_campaign(db, investigation)
    allowed = {item.strip() for item in types.split(",") if item.strip()} or set(DEFAULT_GRAPH_TYPES)
    allowed_rel = {item.strip() for item in rel_types.split(",") if item.strip()}
    allowed_risk = {item.strip() for item in risk.split(",") if item.strip()}
    entities = db.query(Entity).filter(Entity.investigation_id == investigation.id).all()
    cap = get_settings().graph_node_cap
    selected = []
    for entity in entities:
        if entity.entity_type not in allowed:
            continue
        if allowed_risk and entity.risk_state not in allowed_risk:
            continue
        if not _seen_in_window(entity.last_observed or entity.first_observed, observed_after, observed_before):
            continue
        selected.append(entity)
        if len(selected) >= cap:
            break
    ids = {entity.id for entity in selected}
    relationships = []
    for row in db.query(Relationship).filter(Relationship.investigation_id == investigation.id).all():
        if row.source_entity_id not in ids or row.target_entity_id not in ids:
            continue
        if allowed_rel and row.rel_type not in allowed_rel:
            continue
        if allowed_risk and row.risk_state not in allowed_risk:
            continue
        relationships.append(row)
    return {
        "nodes": [_entity_out(db, entity) for entity in selected],
        "edges": [_relationship_out(db, row) for row in relationships],
        "root_entity_id": investigation.root_entity_id,
        "truncated": len(selected) >= cap,
        "campaign": (investigation.analysis_json or {}).get("campaign") or {},
    }


def _seen_in_window(value: datetime | None, start: date | None, end: date | None) -> bool:
    if start is None and end is None:
        return True
    if value is None:
        return False
    seen = value.date()
    if start and seen < start:
        return False
    if end and seen > end:
        return False
    return True


@router.post("/investigations/{investigation_id}/graph/expand")
def expand_graph(
    investigation_id: str,
    entity_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    investigation = _investigation(db, user, investigation_id)
    entity = db.get(Entity, entity_id)
    if entity is None or entity.investigation_id != investigation.id:
        raise HTTPException(status_code=404, detail="Entity not found.")
    limit = get_settings().graph_expand_limit
    relationships = (
        db.query(Relationship)
        .filter(
            Relationship.investigation_id == investigation.id,
            ((Relationship.source_entity_id == entity.id) | (Relationship.target_entity_id == entity.id)),
        )
        .all()
    )
    neighbor_ids = {entity.id}
    for row in relationships:
        neighbor_ids.add(row.source_entity_id)
        neighbor_ids.add(row.target_entity_id)
    neighbors = db.query(Entity).filter(Entity.id.in_(neighbor_ids)).all() if neighbor_ids else []
    visible_ids_now = {row.id for row in neighbors}
    relationships = [
        row
        for row in relationships
        if row.source_entity_id in visible_ids_now and row.target_entity_id in visible_ids_now
    ]
    by_id = {row.id: row for row in neighbors}
    suggestions = rank_expansion(entity.id, relationships, by_id)
    order = {item["entity_id"]: index for index, item in enumerate(suggestions)}
    relationships = sorted(relationships, key=lambda row: order.get(row.target_entity_id if row.source_entity_id == entity.id else row.source_entity_id, 10_000))
    relationships = relationships[:limit]
    kept = {entity.id}
    for row in relationships:
        kept.add(row.source_entity_id)
        kept.add(row.target_entity_id)
    visible = [row for row in neighbors if row.id in kept]
    visible_ids = {item["entity_id"] for item in suggestions[:limit]}
    return {
        "nodes": [_entity_out(db, row) for row in visible],
        "edges": [_relationship_out(db, row) for row in relationships],
        "suggestions": [item for item in suggestions if item["entity_id"] in visible_ids],
    }


@router.post("/investigations/{investigation_id}/graph/path")
def graph_path(
    investigation_id: str,
    body: PathIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    investigation = _investigation(db, user, investigation_id)
    entities = db.query(Entity).filter(Entity.investigation_id == investigation.id).all()
    relationships = db.query(Relationship).filter(Relationship.investigation_id == investigation.id).all()
    node_ids = shortest_path(
        [row.id for row in entities],
        [(row.source_entity_id, row.target_entity_id) for row in relationships],
        body.source_id,
        body.target_id,
    )
    wanted = set(zip(node_ids, node_ids[1:], strict=False))
    edge_ids = []
    for row in relationships:
        if (row.source_entity_id, row.target_entity_id) in wanted or (row.target_entity_id, row.source_entity_id) in wanted:
            edge_ids.append(row.id)
    return {"node_ids": node_ids, "edge_ids": edge_ids}


@router.get("/investigations/{investigation_id}/report")
def get_report(investigation_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    investigation = _investigation(db, user, investigation_id)
    ensure_campaign(db, investigation)
    report = dict(investigation.report_json or {})
    notes = (
        db.query(AnalystFeedback)
        .filter(AnalystFeedback.investigation_id == investigation.id)
        .order_by(AnalystFeedback.created_at.asc())
        .all()
    )
    report["notes"] = [{"id": row.id, "note": row.note, "created_at": _iso(row.created_at)} for row in notes]
    report["root_indicator"] = investigation.root_indicator
    report["status"] = investigation.status
    report["analysis"] = investigation.analysis_json or report.get("analysis") or {}
    if not report.get("summary"):
        report = build_report(db, investigation)
    return report


@router.post("/investigations/{investigation_id}/notes")
def add_note(
    investigation_id: str,
    body: NoteIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    investigation = _investigation(db, user, investigation_id)
    if body.entity_id:
        entity = db.get(Entity, body.entity_id)
        if entity is None or entity.investigation_id != investigation.id:
            raise HTTPException(status_code=404, detail="Entity not found.")
    note = AnalystFeedback(
        investigation_id=investigation.id,
        user_id=user.id,
        entity_id=body.entity_id,
        note=body.note.strip(),
    )
    db.add(note)
    _audit(db, user.id, "note_create", investigation.id)
    db.commit()
    return {"id": note.id, "note": note.note, "created_at": _iso(note.created_at)}


@router.get("/investigations/{investigation_id}/export")
def export_investigation(
    investigation_id: str,
    format: str = "json",
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    if format not in {"json", "csv", "handoff"}:
        raise HTTPException(status_code=422, detail="Export format must be json, csv, or handoff.")
    investigation = _investigation(db, user, investigation_id)
    entities = db.query(Entity).filter(Entity.investigation_id == investigation.id).all()
    relationships = db.query(Relationship).filter(Relationship.investigation_id == investigation.id).all()
    db.add(ExportJob(investigation_id=investigation.id, user_id=user.id, format=format, status="completed"))
    _audit(db, user.id, "export", investigation.id, {"format": format})
    db.commit()
    filename = f"piae-{investigation.id}.handoff.json" if format == "handoff" else f"piae-{investigation.id}.{format}"
    if format == "handoff":
        content = json.dumps(build_handoff(db, investigation), default=str)
        media = "application/json"
    elif format == "json":
        payload = {
            "investigation": _investigation_out(investigation),
            "report": investigation.report_json,
            "entities": [_entity_out(db, entity) for entity in entities],
            "relationships": [_relationship_out(db, row) for row in relationships],
            "demonstration": investigation.is_demonstration,
        }
        content = json.dumps(payload, default=str)
        media = "application/json"
    else:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["record", "id", "type", "value", "risk_state", "other", "reason", "provenance"])
        for entity in entities:
            writer.writerow(["entity", entity.id, entity.entity_type, entity.display_value, entity.risk_state, "", "", ""])
        for row in relationships:
            writer.writerow(
                ["relationship", row.id, row.rel_type, row.source_entity_id, row.risk_state, row.target_entity_id, row.reason, row.provenance]
            )
        content = buffer.getvalue()
        media = "text/csv"
    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/notifications")
def notifications(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    events = (
        db.query(AuditEvent)
        .filter(AuditEvent.user_id == user.id)
        .order_by(AuditEvent.created_at.desc())
        .limit(20)
        .all()
    )
    seen = user.notifications_seen_at
    items = [
        {
            "id": event.id,
            "action": event.action,
            "target": event.target,
            "created_at": _iso(event.created_at),
            "unread": seen is None or (event.created_at is not None and event.created_at > seen),
        }
        for event in events
    ]
    return {"items": items, "unread": any(item["unread"] for item in items)}


@router.post("/notifications/read")
def read_notifications(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    user.notifications_seen_at = utcnow()
    db.commit()
    return {"ok": True}


@router.get("/sources")
def list_sources(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    rows = db.query(SourceSetting).order_by(SourceSetting.name.asc()).all()
    return {
        "demo_mode": get_settings().demo_mode,
        "items": [
            {
                "name": row.name,
                "enabled": row.enabled,
                "description": row.description,
                "requires_key": row.requires_key,
                "key_configured": row.key_configured,
            }
            for row in rows
        ],
    }


@router.put("/sources/{name}")
def update_source(
    name: str,
    body: SourcePatch,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    row = db.get(SourceSetting, name)
    if row is None or name == "demonstration":
        raise HTTPException(status_code=404, detail="Source not found.")
    row.enabled = body.enabled
    _audit(db, user.id, "source_update", name, {"enabled": body.enabled})
    db.commit()
    return {"name": row.name, "enabled": row.enabled}


@router.get("/audit")
def audit_events(user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    rows = db.query(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(100).all()
    return {
        "items": [
            {
                "id": row.id,
                "user_id": row.user_id,
                "action": row.action,
                "target": row.target,
                "created_at": _iso(row.created_at),
            }
            for row in rows
        ]
    }

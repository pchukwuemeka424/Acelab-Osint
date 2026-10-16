"""Rare artifacts shared with this analyst's saved investigations.

A match is a kit structure, distinctive logo path, uncommon nameserver, or
non-redacted contact. It is not an operator identification and it is not a
claim that any asset is malicious.
"""

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.models import AssociationAssessment, Entity, Investigation, Observation, Relationship, utcnow
from app.services.scoring import WEAK_REASONS, ScoreInput, score_association

GENERIC_FIELDS = frozenset(
    {
        "email",
        "password",
        "pass",
        "submit",
        "search",
        "q",
        "s",
        "csrf",
        "token",
        "_token",
        "utf8",
        "name",
        "message",
        "phone",
        "username",
        "login",
        "user",
        "query",
    }
)
GENERIC_SCRIPTS = frozenset(
    {
        "jquery.js",
        "jquery.min.js",
        "bootstrap.js",
        "bootstrap.min.js",
        "analytics.js",
        "gtag.js",
        "gtm.js",
        "recaptcha.js",
        "api.js",
        "polyfill.js",
        "font-awesome.min.js",
        "wp-embed.min.js",
        "wp-emoji-release.min.js",
    }
)
GENERIC_LOGOS = frozenset(
    {
        "favicon.ico",
        "favicon.png",
        "favicon.svg",
        "logo.png",
        "logo.svg",
        "logo.jpg",
        "logo.jpeg",
        "apple-touch-icon.png",
        "icon.png",
        "icon.svg",
    }
)
_PUBLIC_NS_SUFFIXES = (
    "cloudflare.com",
    "domaincontrol.com",
    "googledomains.com",
    "google.com",
    "registrar-servers.com",
    "dnsowl.com",
    "he.net",
    "nsone.net",
    "worldnic.com",
    "hover.com",
)
_PUBLIC_NS_MARKERS = ("awsdns", "azure-dns", "dnspod.", "cloudns.", "ui-dns.", "namecheap")
_PRIVACY = ("redact", "privacy", "withheld", "not disclosed", "data protected", "whoisguard", "domainsbyproxy")
_SCRIPT_NOISE = ("jquery", "bootstrap", "analytics", "recaptcha", "gtag", "font-awesome", "cloudflare")
_COMMON_LIMIT = 8
_MATCH_LIMIT = 12
NOTE = (
    "Matches are rare artifacts shared with this analyst's saved cases. "
    "They do not assert malice and they do not name an operator."
)


@dataclass
class Artifact:
    key: str
    kind: str
    label: str
    entity_ids: list[str] = field(default_factory=list)


def script_is_generic(name: str) -> bool:
    base = name.rsplit("/", 1)[-1].lower()
    if not base or base in GENERIC_SCRIPTS:
        return True
    return any(token in base for token in _SCRIPT_NOISE)


def is_public_nameserver(value: str) -> bool:
    host = value.lower().rstrip(".")
    if any(host == suffix or host.endswith(f".{suffix}") for suffix in _PUBLIC_NS_SUFFIXES):
        return True
    return any(marker in host for marker in _PUBLIC_NS_MARKERS)


def is_redacted_contact(value: str, metadata: dict | None = None) -> bool:
    if (metadata or {}).get("redacted") is True:
        return True
    text = value.lower()
    return any(marker in text for marker in _PRIVACY)


def _meta(entity: object) -> dict:
    raw = getattr(entity, "metadata_json", None)
    if not isinstance(raw, dict):
        raw = getattr(entity, "metadata", None)
    return raw if isinstance(raw, dict) else {}


def _day(value: object) -> str | None:
    text = str(value or "").strip()
    if re.fullmatch(r"\d{14}", text):
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    if re.match(r"\d{4}-\d{2}-\d{2}", text):
        return text[:10]
    return None


def artifacts_from(entities: list) -> list[Artifact]:
    """Stable rare artifacts. Generic scripts, public DNS, and redacted contacts are omitted."""
    tokens: list[str] = []
    token_ids: list[str] = []
    logos: dict[str, Artifact] = {}
    nameservers: dict[str, Artifact] = {}
    contacts: dict[str, Artifact] = {}
    for entity in entities:
        if getattr(entity, "entity_type", "") == "fingerprint":
            continue
        metadata = _meta(entity)
        entity_id = str(getattr(entity, "id", "") or "")
        if getattr(entity, "entity_type", "") == "domain":
            for field_name in metadata.get("kit_fields") or []:
                token = str(field_name).strip().lower()
                if token and token not in GENERIC_FIELDS and f"field:{token}" not in tokens:
                    tokens.append(f"field:{token}")
                    if entity_id:
                        token_ids.append(entity_id)
            for script_name in metadata.get("kit_scripts") or []:
                script = str(script_name).strip().lower()
                if script and not script_is_generic(script) and f"script:{script}" not in tokens:
                    tokens.append(f"script:{script}")
                    if entity_id:
                        token_ids.append(entity_id)
        if getattr(entity, "entity_type", "") == "file" and metadata.get("kind") == "script":
            script = str(urlsplit(str(metadata.get("url") or getattr(entity, "normalized_value", ""))).path.rsplit("/", 1)[-1]).lower()
            if script and not script_is_generic(script) and f"script:{script}" not in tokens:
                tokens.append(f"script:{script}")
                if entity_id:
                    token_ids.append(entity_id)
        if getattr(entity, "entity_type", "") == "logo":
            path = urlsplit(str(metadata.get("url") or "")).path.lower()
            base = path.rsplit("/", 1)[-1]
            if path and base not in GENERIC_LOGOS:
                key = f"logo:{path[:180]}"
                current = logos.get(key)
                if current is None:
                    logos[key] = Artifact(key=key, kind="logo", label=f"Logo path {base[:80]}", entity_ids=[entity_id] if entity_id else [])
                elif entity_id and entity_id not in current.entity_ids:
                    current.entity_ids.append(entity_id)
        if getattr(entity, "entity_type", "") == "nameserver":
            host = str(getattr(entity, "normalized_value", "")).lower().rstrip(".")
            if host and not is_public_nameserver(host):
                key = f"ns:{host}"
                current = nameservers.get(key)
                if current is None:
                    nameservers[key] = Artifact(key=key, kind="nameserver", label=host, entity_ids=[entity_id] if entity_id else [])
                elif entity_id and entity_id not in current.entity_ids:
                    current.entity_ids.append(entity_id)
        if getattr(entity, "entity_type", "") == "contact":
            value = str(getattr(entity, "normalized_value", ""))
            if value and not is_redacted_contact(value, metadata) and not is_redacted_contact(str(getattr(entity, "display_value", "")), metadata):
                key = f"contact:{value.lower()[:180]}"
                current = contacts.get(key)
                if current is None:
                    contacts[key] = Artifact(
                        key=key,
                        kind="contact",
                        label=str(getattr(entity, "display_value", value))[:120],
                        entity_ids=[entity_id] if entity_id else [],
                    )
                elif entity_id and entity_id not in current.entity_ids:
                    current.entity_ids.append(entity_id)
    found = [*logos.values(), *nameservers.values(), *contacts.values()]
    if len(tokens) >= 2:
        digest = hashlib.sha256("\n".join(sorted(tokens)).encode()).hexdigest()
        found.insert(0, Artifact(key=f"kit:{digest}", kind="kit", label=f"Kit structure {digest[:8]}", entity_ids=list(dict.fromkeys(token_ids))))
    return found


def infrastructure_timeline(entities: list, subject: str) -> list[dict]:
    """Registration, earliest certificate, and Wayback capture dates for one subject."""
    events: list[dict] = []
    registered: str | None = None
    registered_entity = ""
    earliest_cert: str | None = None
    cert_entity = ""
    captures: list[tuple[str, str]] = []
    for entity in entities:
        metadata = _meta(entity)
        entity_id = str(getattr(entity, "id", "") or "")
        if getattr(entity, "entity_type", "") in {"domain", "whois"}:
            day = _day(metadata.get("registered_at"))
            if day and (registered is None or day < registered):
                registered = day
                registered_entity = entity_id
        if getattr(entity, "entity_type", "") == "certificate":
            day = _day(metadata.get("not_before"))
            if day and (earliest_cert is None or day < earliest_cert):
                earliest_cert = day
                cert_entity = entity_id
        for row in metadata.get("wayback") or []:
            if isinstance(row, dict):
                day = _day(row.get("timestamp"))
                if day:
                    captures.append((day, entity_id))
    if registered:
        events.append(
            {
                "kind": "registration",
                "at": registered,
                "label": "Registration date published",
                "subject": subject,
                "entity_id": registered_entity or None,
            }
        )
    if earliest_cert:
        events.append(
            {
                "kind": "certificate",
                "at": earliest_cert,
                "label": "Earliest certificate not-before",
                "subject": subject,
                "entity_id": cert_entity or None,
            }
        )
    if captures:
        captures.sort()
        events.append(
            {
                "kind": "wayback",
                "at": captures[0][0],
                "label": "Earliest Wayback capture",
                "subject": subject,
                "entity_id": captures[0][1] or None,
            }
        )
        if captures[-1][0] != captures[0][0]:
            events.append(
                {
                    "kind": "wayback",
                    "at": captures[-1][0],
                    "label": "Latest stored Wayback capture",
                    "subject": subject,
                    "entity_id": captures[-1][1] or None,
                }
            )
    events.sort(key=lambda item: (item["at"], item["subject"], item["kind"]))
    return events


def _empty(timeline: list[dict] | None = None, artifact_count: int = 0, withheld_common: int = 0) -> dict:
    return {
        "matches": [],
        "case_count": 0,
        "domain_count": 0,
        "artifact_count": artifact_count,
        "withheld_common": withheld_common,
        "timeline": timeline or [],
        "note": NOTE,
        "active": True,
    }


def _root_entity(investigation: Investigation, entities: list[Entity]) -> Entity | None:
    if investigation.root_entity_id:
        for entity in entities:
            if entity.id == investigation.root_entity_id:
                return entity
    wanted = "url" if investigation.indicator_type == "url" else investigation.indicator_type
    for entity in entities:
        if entity.entity_type == wanted and entity.normalized_value == investigation.root_indicator:
            return entity
    for entity in entities:
        if entity.normalized_value == investigation.root_indicator:
            return entity
    return entities[0] if entities else None


def _observation_ids(db: Session, investigation_id: str, entity_ids: list[str]) -> list[str]:
    if not entity_ids:
        return []
    rows = (
        db.query(Observation.id)
        .filter(Observation.investigation_id == investigation_id, Observation.entity_id.in_(entity_ids))
        .limit(12)
        .all()
    )
    return [row[0] for row in rows]


def _ensure_entity(
    db: Session,
    investigation: Investigation,
    entity_map: dict[tuple[str, str], Entity],
    entity_type: str,
    normalized_value: str,
    display_value: str,
    metadata: dict,
) -> Entity:
    key = (entity_type, normalized_value[:512])
    entity = entity_map.get(key)
    if entity is not None:
        entity.metadata_json = {**(entity.metadata_json or {}), **metadata}
        return entity
    entity = Entity(
        investigation_id=investigation.id,
        entity_type=entity_type,
        stable_id=f"{entity_type}:{normalized_value}"[:160],
        display_value=display_value[:512],
        normalized_value=normalized_value[:512],
        risk_state="contextual",
        metadata_json=metadata,
    )
    db.add(entity)
    db.flush()
    entity_map[key] = entity
    return entity


def _ensure_link(
    db: Session,
    investigation: Investigation,
    existing: set[tuple[str, str, str]],
    source: Entity,
    target: Entity,
    reason: str,
    observation_ids: list[str],
    weak_reason: str | None = None,
) -> None:
    key = (source.id, target.id, "matches_kit")
    if source.id == target.id or key in existing:
        return
    existing.add(key)
    scored = score_association(
        ScoreInput(
            rel_type="matches_kit",
            weak_reason=weak_reason,
            source_reliability=0.6,
            rarity=1.0,
            corroboration=1,
        )
    )
    row = Relationship(
        investigation_id=investigation.id,
        source_entity_id=source.id,
        target_entity_id=target.id,
        rel_type="matches_kit",
        reason=reason,
        provenance="campaign",
        observation_ids=observation_ids[:12],
        risk_state="contextual",
        retrieved_at=utcnow(),
        weak_reason=weak_reason,
    )
    db.add(row)
    db.flush()
    db.add(
        AssociationAssessment(
            investigation_id=investigation.id,
            relationship_id=row.id,
            entity_id=source.id,
            related_entity_id=target.id,
            heuristic_score=scored.heuristic_score,
            score_kind=scored.score_kind,
            label=scored.label,
            summary=scored.summary,
            factors_json=scored.factors,
        )
    )


def attach_campaign(db: Session, investigation: Investigation) -> dict:
    """Link rare artifacts in this investigation to the same analyst's saved cases."""
    current = db.query(Entity).filter(Entity.investigation_id == investigation.id).all()
    timeline = infrastructure_timeline(current, investigation.root_indicator)
    if investigation.is_demonstration:
        payload = _empty(timeline)
        payload["active"] = False
        return payload
    current_artifacts = artifacts_from(current)
    if not current_artifacts:
        return _empty(timeline)
    saved = (
        db.query(Investigation)
        .filter(
            Investigation.owner_id == investigation.owner_id,
            Investigation.id != investigation.id,
            Investigation.is_saved.is_(True),
            Investigation.is_demonstration.is_(False),
        )
        .all()
    )
    current_keys = {artifact.key: artifact for artifact in current_artifacts}
    saved_hits: dict[str, list[tuple[Investigation, list]]] = defaultdict(list)
    frequency: dict[str, int] = defaultdict(int)
    saved_entities: dict[str, list] = {}
    for other in saved:
        rows = db.query(Entity).filter(Entity.investigation_id == other.id).all()
        saved_entities[other.id] = rows
        seen: set[str] = set()
        for artifact in artifacts_from(rows):
            if artifact.key in seen:
                continue
            seen.add(artifact.key)
            if artifact.key in current_keys:
                frequency[artifact.key] += 1
                saved_hits[artifact.key].append((other, rows))
    withheld = sum(1 for key, count in frequency.items() if count >= _COMMON_LIMIT)
    root = _root_entity(investigation, current)
    entity_map = {(entity.entity_type, entity.normalized_value): entity for entity in current}
    existing = {
        (row.source_entity_id, row.target_entity_id, row.rel_type)
        for row in db.query(Relationship).filter(Relationship.investigation_id == investigation.id).all()
    }
    matches: list[dict] = []
    seen_domains: set[str] = set()
    for key, artifact in current_keys.items():
        if frequency.get(key, 0) >= _COMMON_LIMIT:
            continue
        hits = saved_hits.get(key) or []
        if not hits or root is None:
            continue
        support = _observation_ids(db, investigation.id, artifact.entity_ids)
        fingerprint = _ensure_entity(
            db,
            investigation,
            entity_map,
            "fingerprint",
            artifact.key,
            artifact.label,
            {"kind": artifact.kind, "campaign": True},
        )
        _ensure_link(
            db,
            investigation,
            existing,
            root,
            fingerprint,
            f"{artifact.label} is rare enough to compare with saved cases.",
            support,
        )
        for other, _rows in hits:
            if len(seen_domains) >= _MATCH_LIMIT and other.root_indicator not in seen_domains:
                continue
            seen_domains.add(other.root_indicator)
            matched = _ensure_entity(
                db,
                investigation,
                entity_map,
                "domain",
                other.root_indicator,
                other.root_indicator,
                {
                    "campaign_match": True,
                    "saved_investigation_id": other.id,
                    "saved_title": other.title,
                },
            )
            reason = (
                f"Saved case {other.title} ({other.root_indicator}) shares {artifact.label}. "
                "This records a shared artifact, not who operates the host."
            )
            _ensure_link(db, investigation, existing, fingerprint, matched, reason, support)
            timeline.extend(infrastructure_timeline(saved_entities.get(other.id, []), other.root_indicator))
            matches.append(
                {
                    "artifact_kind": artifact.kind,
                    "artifact_label": artifact.label,
                    "saved_investigation_id": other.id,
                    "saved_title": other.title,
                    "saved_indicator": other.root_indicator,
                    "entity_id": matched.id,
                    "observation_ids": support,
                }
            )
    deduped: list[dict] = []
    seen_events: set[tuple[str, str, str]] = set()
    for event in timeline:
        marker = (event["kind"], event["at"], event["subject"])
        if marker in seen_events:
            continue
        seen_events.add(marker)
        deduped.append(event)
    deduped.sort(key=lambda item: (item["at"], item["subject"], item["kind"]))
    case_ids = {item["saved_investigation_id"] for item in matches}
    return {
        "matches": matches,
        "case_count": len(case_ids),
        "domain_count": len({item["saved_indicator"] for item in matches}),
        "artifact_count": len(current_artifacts),
        "withheld_common": withheld,
        "timeline": deduped,
        "note": NOTE,
        "active": True,
    }


def ensure_campaign(db: Session, investigation: Investigation) -> dict:
    """Fill in campaign memory for an investigation that was collected before this comparison existed."""
    analysis = dict(investigation.analysis_json or {})
    campaign = analysis.get("campaign")
    if isinstance(campaign, dict) and "active" in campaign:
        return campaign
    campaign = attach_campaign(db, investigation)
    analysis["campaign"] = campaign
    investigation.analysis_json = analysis
    if campaign.get("matches"):
        investigation.entity_count = db.query(Entity).filter(Entity.investigation_id == investigation.id).count()
        investigation.relationship_count = db.query(Relationship).filter(Relationship.investigation_id == investigation.id).count()
    db.commit()
    return campaign


def rank_expansion(entity_id: str, relationships: list, entities: dict) -> list[dict]:
    """Rank neighbors so a rare artifact is the next click and shared hosting is last."""
    suggestions = []
    for rel in relationships:
        other_id = rel.target_entity_id if rel.source_entity_id == entity_id else rel.source_entity_id
        other = entities.get(other_id)
        if other is None or other_id == entity_id:
            continue
        weak, reason, tier = _expansion_tier(rel, other)
        suggestions.append(
            {
                "entity_id": other.id,
                "label": other.display_value,
                "rel_type": rel.rel_type,
                "reason": reason,
                "weak": weak,
                "tier": tier,
                "degree": other.degree or 0,
            }
        )
    suggestions.sort(key=lambda item: (item["tier"], item["degree"], item["label"]))
    for item in suggestions:
        item.pop("tier", None)
        item.pop("degree", None)
    return suggestions


def _expansion_tier(rel: Relationship, other: Entity) -> tuple[bool, str, int]:
    if rel.rel_type == "matches_kit" or other.entity_type == "fingerprint":
        return False, "Rare artifact shared with a saved case.", 0
    if other.entity_type == "nameserver" and is_public_nameserver(other.normalized_value):
        return True, WEAK_REASONS["public_dns"], 2
    if rel.weak_reason:
        return True, WEAK_REASONS.get(rel.weak_reason, "This shared infrastructure characteristic is weak evidence."), 2
    if other.entity_type in {"nameserver", "contact"} and (other.degree or 0) <= 2:
        return False, "Uncommon link. Fewer neighbors makes this a better next step.", 0
    return False, "Contextual link.", 1

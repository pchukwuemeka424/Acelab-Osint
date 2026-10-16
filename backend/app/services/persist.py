import math
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.connectors.base import CollectionResult
from app.models import (
    AssociationAssessment,
    Entity,
    EvidenceSource,
    Investigation,
    Observation,
    Relationship,
    ThreatIndicator,
    utcnow,
)
from app.services.campaign import attach_campaign
from app.services.graph_analysis import communities, connected_components, rank_candidates
from app.services.reports import build_report
from app.services.scoring import ScoreInput, score_association

SOURCE_DEFS = [
    ("demonstration", "demonstration", 0.4, True, "Reserved source. Investigations do not invent infrastructure."),
    ("dns", "dns", 0.7, False, "Resolver answers. Retrieval time is not publication time."),
    ("rdap", "registration", 0.6, False, "Public registration data when a provider returns it."),
    ("certificate_transparency", "certificate", 0.65, False, "Certificate transparency entries."),
    ("urlhaus", "threat_feed", 0.75, False, "URLHaus host lookup when enabled."),
    ("ripe", "network", 0.7, False, "RIPEstat prefix and announcing network. Not passive DNS history."),
    ("wayback", "archive", 0.55, False, "Wayback Machine capture dates. Archived pages are not downloaded."),
    ("page", "http", 0.5, False, "One public page response from the submitted host."),
    ("profiles", "http", 0.45, False, "Public pages that contain a submitted full name."),
    ("submitted", "analyst", 0.5, False, "Indicator submitted by an analyst."),
]


def ensure_sources(db: Session) -> dict[str, EvidenceSource]:
    found = {row.name: row for row in db.query(EvidenceSource).all()}
    for name, kind, reliability, demo, description in SOURCE_DEFS:
        if name in found:
            continue
        row = EvidenceSource(
            name=name,
            kind=kind,
            reliability=reliability,
            is_demonstration=demo,
            description=description,
        )
        db.add(row)
        found[name] = row
    db.flush()
    return found


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _jsonable(metadata: dict) -> dict:
    clean = {}
    for key, value in metadata.items():
        if isinstance(value, datetime):
            clean[key] = value.isoformat()
        else:
            clean[key] = value
    return clean


def persist_collection(db: Session, investigation: Investigation, result: CollectionResult) -> None:
    sources = ensure_sources(db)
    entity_map: dict[tuple[str, str], Entity] = {}
    for entity in db.query(Entity).filter(Entity.investigation_id == investigation.id).all():
        entity_map[(entity.entity_type, entity.normalized_value)] = entity

    observations: dict[tuple[str, str], list[str]] = defaultdict(list)
    for index, item in enumerate(result.entities):
        key = (item.entity_type, item.normalized_value)
        metadata = _jsonable(item.metadata)
        entity = entity_map.get(key)
        if entity is None:
            angle = index * 2.399963
            entity = Entity(
                investigation_id=investigation.id,
                entity_type=item.entity_type,
                stable_id=f"{item.entity_type}:{item.normalized_value}"[:160],
                display_value=item.display_value[:512],
                normalized_value=item.normalized_value[:512],
                risk_state=item.risk_state,
                pos_x=item.x if item.x is not None else math.cos(angle) * (80 + index),
                pos_y=item.y if item.y is not None else math.sin(angle) * (80 + index),
                metadata_json=metadata,
                first_observed=item.observed_at,
                last_observed=item.observed_at,
            )
            db.add(entity)
            db.flush()
            entity_map[key] = entity
        else:
            entity.metadata_json = {**(entity.metadata_json or {}), **metadata}
            observed = _aware(item.observed_at)
            if observed and (_aware(entity.first_observed) is None or observed < _aware(entity.first_observed)):
                entity.first_observed = observed
            if observed and (_aware(entity.last_observed) is None or observed > _aware(entity.last_observed)):
                entity.last_observed = observed
        source = sources.get(item.source_name, sources["demonstration"])
        observation = Observation(
            investigation_id=investigation.id,
            entity_id=entity.id,
            source_id=source.id,
            original_value=item.original_value or item.display_value,
            normalized_value=item.normalized_value,
            confidence=item.confidence,
            verification_status=item.verification_status,
            observed_at=item.observed_at,
            retrieved_at=utcnow(),
            details_json={"demonstration": bool(metadata.get("demonstration", source.is_demonstration))},
        )
        db.add(observation)
        db.flush()
        observations[key].append(observation.id)

    existing_rels = {
        (row.source_entity_id, row.target_entity_id, row.rel_type)
        for row in db.query(Relationship).filter(Relationship.investigation_id == investigation.id).all()
    }
    target_counts: dict[tuple[str, str], int] = defaultdict(int)
    prepared = []
    seen = set(existing_rels)
    for rel in result.relationships:
        source = entity_map.get((rel.source_type, rel.source_value))
        target = entity_map.get((rel.target_type, rel.target_value))
        if source is None or target is None or source.id == target.id:
            continue
        key = (source.id, target.id, rel.rel_type)
        if key in seen:
            continue
        seen.add(key)
        target_counts[(rel.rel_type, target.normalized_value)] += 1
        prepared.append((rel, source, target))

    for rel, source, target in prepared:
        shared = target_counts[(rel.rel_type, target.normalized_value)]
        rarity = 1.0 if shared <= 3 else 0.45 if shared <= 12 else 0.25
        source_name = rel.provenance if rel.provenance in sources else "demonstration"
        reliability = sources[source_name].reliability
        scored = score_association(
            ScoreInput(
                rel_type=rel.rel_type,
                weak_reason=rel.weak_reason,
                source_reliability=reliability,
                rarity=rarity,
                temporal_overlap=rel.temporal_overlap,
                corroboration=rel.corroboration,
                conflicting=rel.conflicting,
                stale=rel.stale,
                threat_match=rel.threat_match,
            )
        )
        support = observations.get((rel.source_type, rel.source_value), []) + observations.get(
            (rel.target_type, rel.target_value), []
        )
        row = Relationship(
            investigation_id=investigation.id,
            source_entity_id=source.id,
            target_entity_id=target.id,
            rel_type=rel.rel_type,
            reason=rel.reason,
            provenance=rel.provenance,
            observation_ids=support[:12],
            risk_state=rel.risk_state,
            observed_at=rel.observed_at,
            retrieved_at=utcnow(),
            is_conflicting=rel.conflicting,
            is_stale=rel.stale,
            weak_reason=rel.weak_reason,
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

    for indicator in result.indicators:
        entity = entity_map.get((indicator.entity_type, indicator.entity_value))
        if entity is None:
            continue
        source = sources.get(indicator.source_name, sources["demonstration"])
        db.add(
            ThreatIndicator(
                investigation_id=investigation.id,
                entity_id=entity.id,
                source_id=source.id,
                indicator_type=indicator.indicator_type,
                value=indicator.value[:512],
                status=indicator.status,
                actor_name=indicator.actor_name,
                details_json=indicator.details,
                observed_at=indicator.observed_at,
                retrieved_at=utcnow(),
            )
        )

    campaign = attach_campaign(db, investigation)
    degree: dict[str, int] = defaultdict(int)
    edges: list[tuple[str, str]] = []
    stored_entities = db.query(Entity).filter(Entity.investigation_id == investigation.id).all()
    nodes = [entity.id for entity in stored_entities]
    for rel in db.query(Relationship).filter(Relationship.investigation_id == investigation.id).all():
        degree[rel.source_entity_id] += 1
        degree[rel.target_entity_id] += 1
        edges.append((rel.source_entity_id, rel.target_entity_id))
    for entity in stored_entities:
        entity.degree = degree[entity.id]

    component_lists = connected_components(nodes, edges)
    community_map = communities(nodes, edges)
    for entity in stored_entities:
        metadata = dict(entity.metadata_json or {})
        metadata["community"] = community_map.get(entity.id, 0)
        entity.metadata_json = metadata

    assessments = [
        {
            "entity_id": row.entity_id,
            "related_entity_id": row.related_entity_id,
            "heuristic_score": row.heuristic_score,
            "label": row.label,
            "summary": row.summary,
        }
        for row in db.query(AssociationAssessment).filter(AssociationAssessment.investigation_id == investigation.id).all()
    ]
    investigation.entity_count = len(stored_entities)
    investigation.relationship_count = len(edges)
    investigation.analysis_json = {
        "component_count": len(component_lists),
        "largest_component": max((len(item) for item in component_lists), default=0),
        "community_count": len(set(community_map.values())) if community_map else 0,
        "ranked": rank_candidates(assessments)[:15],
        "campaign": campaign,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    investigation.updated_at = utcnow()
    root = entity_map.get((investigation.indicator_type if investigation.indicator_type != "url" else "url", investigation.root_indicator))
    if root is None:
        for entity in entity_map.values():
            if entity.normalized_value == investigation.root_indicator:
                root = entity
                break
    if root is not None:
        investigation.root_entity_id = root.id
    db.flush()
    investigation.report_json = build_report(db, investigation, result.limitations)
    db.flush()

from sqlalchemy.orm import Session

from app.models import (
    AnalystFeedback,
    AssociationAssessment,
    Entity,
    EvidenceSource,
    Investigation,
    Observation,
    Relationship,
    ThreatIndicator,
)
from app.services.openrouter import maybe_narrate


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def build_report(db: Session, investigation: Investigation, limitations: list[str] | None = None) -> dict:
    entities = db.query(Entity).filter(Entity.investigation_id == investigation.id).all()
    relationships = db.query(Relationship).filter(Relationship.investigation_id == investigation.id).all()
    observations = db.query(Observation).filter(Observation.investigation_id == investigation.id).all()
    assessments = (
        db.query(AssociationAssessment)
        .filter(AssociationAssessment.investigation_id == investigation.id)
        .order_by(AssociationAssessment.heuristic_score.desc())
        .all()
    )
    indicators = db.query(ThreatIndicator).filter(ThreatIndicator.investigation_id == investigation.id).all()
    notes = (
        db.query(AnalystFeedback)
        .filter(AnalystFeedback.investigation_id == investigation.id)
        .order_by(AnalystFeedback.created_at.asc())
        .all()
    )
    sources = {row.id: row for row in db.query(EvidenceSource).all()}
    entity_by_id = {row.id: row for row in entities}
    conflicts = [row for row in relationships if row.is_conflicting]
    stale = [row for row in relationships if row.is_stale]
    actor_names = sorted({row.actor_name for row in indicators if row.actor_name})
    limitation_list = list(limitations or [])
    if any((entity.metadata_json or {}).get("demonstration") for entity in entities):
        limitation_list.append("Demonstration records are synthetic and did not come from a live investigation.")
    elif investigation.is_demonstration:
        limitation_list.append("Live collection is disabled. No infrastructure was added beyond the submitted indicator.")
    limitation_list.append("Association scores use heuristic baseline v1. They are not probabilities.")
    limitation_list.append("Shared hosting, CDNs, public DNS, and common certificate authorities are weak evidence.")
    if not actor_names:
        limitation_list.append("Stored evidence does not support naming a threat actor.")
    else:
        limitation_list.append("An actor name is present only where a source record explicitly provided it.")
    campaign = (investigation.analysis_json or {}).get("campaign") or {}
    if campaign.get("matches"):
        limitation_list.append("Campaign matches are shared artifacts with this analyst's saved cases. They do not identify an operator.")

    timeline = []
    for observation in observations:
        timeline.append(
            {
                "observation_id": observation.id,
                "entity_id": observation.entity_id,
                "observed_at": _iso(observation.observed_at),
                "retrieved_at": _iso(observation.retrieved_at),
                "source": sources.get(observation.source_id).name if observation.source_id in sources else None,
                "verification_status": observation.verification_status,
                "value": observation.normalized_value,
            }
        )
    timeline.sort(key=lambda item: item["observed_at"] or item["retrieved_at"] or "")

    association_rows = []
    for row in assessments[:40]:
        association_rows.append(
            {
                "id": row.id,
                "entity_id": row.entity_id,
                "related_entity_id": row.related_entity_id,
                "source": entity_by_id[row.entity_id].display_value if row.entity_id in entity_by_id else None,
                "target": entity_by_id[row.related_entity_id].display_value if row.related_entity_id in entity_by_id else None,
                "heuristic_score": row.heuristic_score,
                "score_kind": row.score_kind,
                "label": row.label,
                "summary": row.summary,
                "factors": row.factors_json,
            }
        )
    packet = {
        "investigation_id": investigation.id,
        "root_indicator": investigation.root_indicator,
        "is_demonstration": investigation.is_demonstration,
        "limitations": limitation_list,
        "observation_ids": [row.id for row in observations[:40]],
        "associations": association_rows[:20],
        "conflicts": [row.reason for row in conflicts[:10]],
        "actor_names": actor_names,
    }
    narrative, narrative_status = maybe_narrate(packet)
    return {
        "investigation_id": investigation.id,
        "root_indicator": investigation.root_indicator,
        "indicator_type": investigation.indicator_type,
        "status": investigation.status,
        "is_demonstration": investigation.is_demonstration,
        "summary": (
            f"Investigation of {investigation.root_indicator} stored {len(entities)} entities and "
            f"{len(relationships)} relationships. Scores are heuristic, not probabilities."
        ),
        "counts": _counts(entities),
        "associations": association_rows,
        "timeline": timeline[:80],
        "sources": [
            {
                "name": source.name,
                "kind": source.kind,
                "reliability": source.reliability,
                "is_demonstration": source.is_demonstration,
                "description": source.description,
            }
            for source in sources.values()
        ],
        "indicators": [
            {
                "id": row.id,
                "value": row.value,
                "status": row.status,
                "actor_name": row.actor_name,
                "indicator_type": row.indicator_type,
                "details": row.details_json,
            }
            for row in indicators
        ],
        "conflicts": [{"id": row.id, "reason": row.reason, "observation_ids": row.observation_ids} for row in conflicts],
        "stale": [{"id": row.id, "reason": row.reason} for row in stale],
        "limitations": limitation_list,
        "notes": [{"id": row.id, "note": row.note, "created_at": _iso(row.created_at)} for row in notes],
        "narrative": narrative,
        "narrative_status": narrative_status,
        "analysis": investigation.analysis_json or {},
    }


def build_handoff(db: Session, investigation: Investigation) -> dict:
    """Every claim cites stored observations. The handoff states what is not being claimed."""
    relationships = db.query(Relationship).filter(Relationship.investigation_id == investigation.id).all()
    observations = db.query(Observation).filter(Observation.investigation_id == investigation.id).all()
    sources = {row.id: row for row in db.query(EvidenceSource).all()}
    observation_by_id = {row.id: row for row in observations}
    indicators = db.query(ThreatIndicator).filter(ThreatIndicator.investigation_id == investigation.id).all()
    actor_names = sorted({row.actor_name for row in indicators if row.actor_name})
    claims = []
    for row in relationships:
        cited = []
        for observation_id in row.observation_ids or []:
            observation = observation_by_id.get(observation_id)
            if observation is None:
                continue
            source = sources.get(observation.source_id)
            cited.append(
                {
                    "observation_id": observation.id,
                    "observed_at": _iso(observation.observed_at),
                    "retrieved_at": _iso(observation.retrieved_at),
                    "source": source.name if source else None,
                    "value": observation.normalized_value,
                    "verification_status": observation.verification_status,
                }
            )
        claims.append(
            {
                "statement": row.reason,
                "relationship_id": row.id,
                "rel_type": row.rel_type,
                "weak_reason": row.weak_reason,
                "observation_ids": row.observation_ids or [],
                "observations": cited,
            }
        )
    not_claimed = [
        "This handoff does not assert that an asset is malicious.",
        "This handoff does not name a threat actor unless a stored source record explicitly does.",
        "Association scores are heuristic baseline v1 and are not probabilities.",
        "Shared hosting, CDNs, public DNS, and common certificate authorities are weak evidence.",
    ]
    if not actor_names:
        not_claimed.append("No stored source record names a threat actor.")
    return {
        "kind": "cited_handoff",
        "investigation_id": investigation.id,
        "root_indicator": investigation.root_indicator,
        "is_demonstration": investigation.is_demonstration,
        "claims": claims,
        "actor_names": actor_names,
        "not_claimed": not_claimed,
        "campaign": (investigation.analysis_json or {}).get("campaign") or {},
    }


def _counts(entities: list[Entity]) -> dict[str, int]:
    counts = {key: 0 for key in ["domain", "ip", "certificate", "ssh", "contact", "file", "hypothesis", "seo", "logo", "url", "whois", "more"]}
    more = {"nameserver", "hosting", "indicator", "fingerprint"}
    for entity in entities:
        if entity.entity_type in counts:
            counts[entity.entity_type] += 1
        elif entity.entity_type in more:
            counts["more"] += 1
    return counts

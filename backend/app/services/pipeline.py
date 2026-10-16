import logging

from sqlalchemy.orm import Session

from app.config import get_settings
from app.connectors.base import CollectionResult, EntityIn, ProviderError
from app.connectors.ct import collect_ct
from app.connectors.demo import collect_demo
from app.connectors.dns_connector import collect_dns
from app.connectors.page import collect_page
from app.connectors.profiles import collect_name_websites
from app.connectors.rdap import collect_rdap
from app.connectors.ripe import collect_ripe
from app.connectors.urlhaus import collect_urlhaus
from app.connectors.wayback import collect_wayback
from app.models import Investigation, InvestigationJob, SourceSetting, utcnow
from app.services.neo4j_projection import project_investigation
from app.services.persist import persist_collection
from app.services.reports import build_report

logger = logging.getLogger(__name__)

_CACHE: dict[str, tuple[float, CollectionResult]] = {}


def _merge(target: CollectionResult, extra: CollectionResult) -> None:
    target.entities.extend(extra.entities)
    target.relationships.extend(extra.relationships)
    target.indicators.extend(extra.indicators)
    target.limitations.extend(extra.limitations)


def _enabled(db: Session, name: str, default: bool) -> bool:
    row = db.get(SourceSetting, name)
    if row is None:
        return default
    return bool(row.enabled)


def _collect_domain_sources(db: Session, result: CollectionResult, domain: str, page_url: str | None, settings) -> None:
    if _enabled(db, "dns", settings.dns_enabled):
        _safe(result, "dns", lambda: collect_dns(domain))
    if _enabled(db, "rdap", settings.rdap_enabled):
        _safe(result, "rdap", lambda: collect_rdap(domain))
    if _enabled(db, "ct", settings.ct_enabled):
        _safe(result, "ct", lambda: collect_ct(domain))
    if _enabled(db, "urlhaus", settings.urlhaus_enabled):
        _safe(result, "urlhaus", lambda: collect_urlhaus(domain))
    addresses = [
        entity.normalized_value
        for entity in result.entities
        if entity.entity_type == "ip" and not entity.metadata.get("non_public")
    ]
    if _enabled(db, "ripe", settings.ripe_enabled):
        _safe(result, "ripe", lambda: collect_ripe(domain, addresses))
    if _enabled(db, "wayback", settings.wayback_enabled):
        _safe(result, "wayback", lambda: collect_wayback(domain))
    if page_url and _enabled(db, "page", settings.page_enabled):
        _safe(result, "page", lambda: collect_page(domain, page_url))


def _profiles_active(db: Session, settings) -> bool:
    if settings.demo_mode:
        return True
    return _enabled(db, "profiles", settings.profiles_enabled)


def _collect_identity(db: Session, investigation: Investigation, settings) -> CollectionResult:
    """Full-name investigations keep public pages that contain that text."""
    result = CollectionResult()
    value = investigation.root_indicator
    result.entities.append(
        EntityIn(
            entity_type="name",
            normalized_value=value,
            display_value=value,
            risk_state="contextual",
            source_name="submitted",
            verification_status="submitted",
            metadata={"submitted": True},
        )
    )
    if _profiles_active(db, settings):
        _safe(result, "profiles", lambda: collect_name_websites(value))
    return result


def collect_for(db: Session, investigation: Investigation) -> CollectionResult:
    settings = get_settings()
    if investigation.indicator_type == "name":
        return _collect_identity(db, investigation, settings)
    if settings.demo_mode or not any(
        _enabled(db, name, False) for name in ("dns", "rdap", "ct", "urlhaus", "ripe", "wayback", "page")
    ):
        return collect_demo(investigation.indicator_type, investigation.root_indicator)
    result = CollectionResult()
    domain = investigation.root_indicator if investigation.indicator_type == "domain" else None
    page_url = f"https://{domain}/" if domain else None
    if investigation.indicator_type == "url":
        from urllib.parse import urlsplit

        page_url = investigation.root_indicator
        domain = urlsplit(page_url).hostname
    if domain:
        _collect_domain_sources(db, result, domain, page_url, settings)
    if not result.entities:
        result.entities.append(
            EntityIn(
                entity_type=investigation.indicator_type if investigation.indicator_type != "url" else "url",
                normalized_value=investigation.root_indicator,
                display_value=investigation.root_indicator,
                risk_state="uncertain",
                source_name="submitted",
                verification_status="submitted",
                metadata={"submitted": True, "demonstration": False},
            )
        )
        result.limitations.append("No external observations were retrieved.")
    return result


def _safe(result: CollectionResult, name: str, func) -> None:
    try:
        _merge(result, func())
    except ProviderError:
        logger.warning("provider_failed", extra={"provider": name})
        result.limitations.append(f"{name} could not be queried. Other sources were still recorded.")
    except Exception:
        logger.warning("provider_failed", extra={"provider": name})
        result.limitations.append(f"{name} could not be queried. Other sources were still recorded.")


def enqueue(investigation_id: str, job_id: str) -> None:
    if get_settings().investigation_eager:
        run_pipeline(investigation_id, job_id)
        return
    from app.workers.celery_app import investigate_task

    investigate_task.delay(investigation_id, job_id)


def run_pipeline(investigation_id: str, job_id: str) -> None:
    from app.db import SessionLocal

    if SessionLocal is None:
        raise RuntimeError("Database is not initialised")
    db = SessionLocal()
    try:
        job = db.get(InvestigationJob, job_id)
        investigation = db.get(Investigation, investigation_id)
        if job is None or investigation is None:
            return
        job.status = "running"
        job.started_at = utcnow()
        job.stage = "collect"
        job.progress = 15
        investigation.status = "running"
        db.commit()
        result = collect_for(db, investigation)
        job.stage = "persist"
        job.progress = 55
        db.commit()
        persist_collection(db, investigation, result)
        job.stage = "project"
        job.progress = 80
        db.commit()
        project_investigation(db, investigation.id)
        investigation.status = "completed"
        investigation.report_json = build_report(db, investigation, result.limitations)
        job.status = "completed"
        job.stage = "report"
        job.progress = 100
        job.finished_at = utcnow()
        job.error = None
        db.commit()
    except Exception:
        logger.exception("investigation_failed")
        db.rollback()
        job = db.get(InvestigationJob, job_id)
        investigation = db.get(Investigation, investigation_id)
        if job is not None:
            job.status = "failed"
            job.stage = "failed"
            job.error = "The investigation could not be completed."
            job.finished_at = utcnow()
        if investigation is not None:
            investigation.status = "failed"
        db.commit()
    finally:
        db.close()

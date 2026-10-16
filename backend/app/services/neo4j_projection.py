import logging

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Entity, Relationship

logger = logging.getLogger(__name__)


def project_investigation(db: Session, investigation_id: str) -> bool:
    """Rebuild the Neo4j subgraph from PostgreSQL. Returns False when Neo4j is unset or unavailable."""
    settings = get_settings()
    if not settings.neo4j_uri:
        return False
    try:
        from neo4j import GraphDatabase

        entities = db.query(Entity).filter(Entity.investigation_id == investigation_id).all()
        relationships = db.query(Relationship).filter(Relationship.investigation_id == investigation_id).all()
        driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
        with driver.session() as session:
            session.run("MATCH (n {investigation_id: $id}) DETACH DELETE n", id=investigation_id)
            for entity in entities:
                session.run(
                    """
                    CREATE (n:Infrastructure {
                        id: $id,
                        investigation_id: $investigation_id,
                        entity_type: $entity_type,
                        value: $value,
                        risk_state: $risk_state
                    })
                    """,
                    id=entity.id,
                    investigation_id=investigation_id,
                    entity_type=entity.entity_type,
                    value=entity.display_value,
                    risk_state=entity.risk_state,
                )
            for rel in relationships:
                session.run(
                    """
                    MATCH (a {id: $source_id}), (b {id: $target_id})
                    CREATE (a)-[:RELATED {id: $id, rel_type: $rel_type, investigation_id: $investigation_id}]->(b)
                    """,
                    source_id=rel.source_entity_id,
                    target_id=rel.target_entity_id,
                    id=rel.id,
                    rel_type=rel.rel_type,
                    investigation_id=investigation_id,
                )
        driver.close()
        return True
    except Exception:
        logger.warning("neo4j_projection_failed")
        return False

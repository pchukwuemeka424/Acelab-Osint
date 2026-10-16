from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EntityIn:
    entity_type: str
    normalized_value: str
    display_value: str
    risk_state: str = "contextual"
    metadata: dict = field(default_factory=dict)
    x: float | None = None
    y: float | None = None
    observed_at: datetime | None = None
    verification_status: str = "observed"
    source_name: str = "demonstration"
    original_value: str | None = None
    confidence: str = "reported"


@dataclass
class RelIn:
    source_type: str
    source_value: str
    target_type: str
    target_value: str
    rel_type: str
    reason: str
    risk_state: str = "contextual"
    observed_at: datetime | None = None
    conflicting: bool = False
    stale: bool = False
    weak_reason: str | None = None
    provenance: str = "demonstration"
    threat_match: bool = False
    corroboration: int = 1
    temporal_overlap: bool = False


@dataclass
class IndicatorIn:
    entity_type: str
    entity_value: str
    indicator_type: str
    value: str
    status: str = "unverified"
    actor_name: str | None = None
    details: dict = field(default_factory=dict)
    observed_at: datetime | None = None
    source_name: str = "demonstration"


@dataclass
class CollectionResult:
    entities: list[EntityIn] = field(default_factory=list)
    relationships: list[RelIn] = field(default_factory=list)
    indicators: list[IndicatorIn] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


class ProviderError(Exception):
    def __init__(self, provider: str, message: str) -> None:
        super().__init__(message)
        self.provider = provider
        self.public_message = f"{provider} could not be queried."

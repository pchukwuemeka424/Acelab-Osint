from app.connectors.base import CollectionResult, EntityIn


def collect_demo(indicator_type: str, value: str) -> CollectionResult:
    """Store the submitted indicator only. No infrastructure is invented."""
    result = CollectionResult()
    result.entities.append(
        EntityIn(
            entity_type="url" if indicator_type == "url" else indicator_type,
            normalized_value=value,
            display_value=value,
            risk_state="uncertain",
            source_name="submitted",
            verification_status="submitted",
            metadata={"submitted": True, "demonstration": False},
        )
    )
    result.limitations.append(
        "Live collection is disabled. No external observations were retrieved, and no infrastructure was added."
    )
    return result

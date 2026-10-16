from app.services.scoring import ScoreInput, score_association


def test_shared_public_dns_is_capped_and_explained():
    scored = score_association(
        ScoreInput(rel_type="uses_nameserver", weak_reason="public_dns", source_reliability=0.7, corroboration=2)
    )
    assert scored.heuristic_score <= 15
    assert scored.label == "insufficient"
    assert "public DNS" in scored.summary
    assert scored.score_kind == "heuristic_baseline_v1"
    assert any(factor["name"] == "common_infrastructure_cap" for factor in scored.factors)


def test_direct_resolution_outranks_shared_hosting():
    direct = score_association(ScoreInput(rel_type="resolves_to", source_reliability=0.7, temporal_overlap=True))
    shared = score_association(ScoreInput(rel_type="shares_infrastructure", weak_reason="shared_hosting"))
    assert direct.heuristic_score > shared.heuristic_score
    assert direct.label == "observed"
    assert "probability" not in direct.summary

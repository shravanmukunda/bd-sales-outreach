"""Lead scorer. The scaffold returns the requested fixed score and does not call a model."""

from __future__ import annotations

from webknot_bd.schemas.lead import LeadCard
from webknot_bd.schemas.tool_io import ScoreLeadInput, ScoreLeadOutput


def score_lead(payload: ScoreLeadInput) -> ScoreLeadOutput:
    lead = LeadCard(
        company=payload.company,
        signal=payload.signal,
        evidence_url=payload.evidence_url,
        fit_score=payload.fit_score,
        matched_service=payload.matched_service,
        reasoning=(
            "PLACEHOLDER fit score. The scorer does not call a model yet, "
            "and this number is not a judgment about a real company. "
            f"Signal noted: {payload.snippet or payload.signal.value}."
        ),
    )
    return ScoreLeadOutput(lead=lead, placeholder=True)

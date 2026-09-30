"""Structured match evidence for internal debugging.

Consumer UI must not display raw scores. This module only organizes the
existing MatchAssessment evidence dict.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from mayabu.domain.matching import MatchAssessment


@dataclass(frozen=True, slots=True)
class MatchEvidence:
    relation: str
    merge_allowed: bool
    needs_review: bool
    identity_rule: str | None
    brand_match: bool | None
    model_code_match: bool | None
    family_match: bool | None
    title_similarity: float | None
    hard_conflicts: tuple[str, ...]
    matching_version: str | None
    explanation: str


def explain_match(assessment: MatchAssessment, *, category: str | None = None) -> MatchEvidence:
    evidence = assessment.evidence or {}
    raw_conflicts = evidence.get("reject") or evidence.get("hard_conflict")
    if isinstance(raw_conflicts, (list, tuple, set)):
        conflicts = tuple(str(item) for item in raw_conflicts if item)
    elif evidence.get("hard_conflict") is True:
        conflicts = tuple(str(item) for item in (evidence.get("reject") or []) if item)
        if not conflicts:
            conflicts = (str(evidence.get("deterministic_relation") or assessment.relation),)
    else:
        conflicts = ()
    brand = evidence.get("brand")
    model_match = evidence.get("model_code_match")
    family = evidence.get("family")
    if assessment.relation == "exact" and assessment.merge_allowed:
        explanation = "Exact merge: deterministic identity agreed and no hard conflict."
        if evidence.get("identity_rule") == "fuzzy_fallback":
            explanation = (
                "Exact merge via conservative fallback after structured identity was incomplete, "
                "with no hard conflict."
            )
    elif assessment.relation == "variant":
        explanation = "Same family or model with a hard variant conflict; listings stay separate."
    elif assessment.relation == "conflict":
        explanation = "Hard identity conflict blocked an exact merge."
    elif assessment.needs_review:
        explanation = "Ambiguous evidence; listing stays unmatched / review-needed."
    else:
        explanation = "Related or weak identity; do not exact-merge."

    return MatchEvidence(
        relation=assessment.relation,
        merge_allowed=assessment.merge_allowed,
        needs_review=assessment.needs_review,
        identity_rule=evidence.get("identity_rule"),
        brand_match=bool(brand) if brand is not None else None,
        model_code_match=bool(model_match) if model_match is not None else None,
        family_match=bool(family) if family is not None else None,
        title_similarity=_as_float(evidence.get("title_similarity")),
        hard_conflicts=conflicts,
        matching_version=evidence.get("matching_version"),
        explanation=explanation,
    )


def explain_match_dict(assessment: MatchAssessment, *, category: str | None = None) -> dict[str, Any]:
    payload = asdict(explain_match(assessment, category=category))
    payload["hard_conflicts"] = list(payload["hard_conflicts"])
    return payload


def _as_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None

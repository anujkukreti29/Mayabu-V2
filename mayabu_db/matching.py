from __future__ import annotations

import json
from typing import Any

from mayabu.domain.matching import MATCH_THRESHOLD, REVIEW_THRESHOLD, assess_product_match


def product_row_to_match_dict(row: dict[str, Any]) -> dict[str, Any]:
    specs = row.get("specs") or {}
    if isinstance(specs, str):
        specs = json.loads(specs)
    return {
        "product_id": str(row.get("id")),
        "category": row.get("category"),
        "canonical_title": row.get("canonical_title"),
        "title_norm": row.get("title_norm"),
        "brand": row.get("brand"),
        "specs": specs,
    }


def choose_match(listing: dict[str, Any], candidate_rows: list[dict[str, Any]]) -> tuple[str | None, float, str, dict[str, Any], bool]:
    """Return product_id, confidence, method, evidence and review requirement.

    Every ingestion path now uses the same deterministic identity rules. Explicit
    variants/conflicts are never merged by fuzzy title similarity.
    """
    best_id: str | None = None
    best_score = -1000.0
    best_evidence: dict[str, Any] = {}
    best_needs_review = False

    for row in candidate_rows:
        product = product_row_to_match_dict(row)
        assessment = assess_product_match(listing, product)
        evidence = dict(assessment.evidence)
        candidate_sources = row.get("candidate_sources") or []
        db_similarity = max(float(row.get("title_similarity") or 0), float(row.get("listing_title_similarity") or 0))
        if candidate_sources:
            evidence["candidate_sources"] = candidate_sources
        if db_similarity:
            evidence["db_title_similarity"] = round(db_similarity, 3)

        if assessment.merge_allowed:
            method = "deterministic_identity_exact" if assessment.score >= 1000 else "fuzzy_identity_fallback"
            return str(row["id"]), assessment.score, method, evidence, False

        if assessment.needs_review and assessment.score > best_score:
            best_id = str(row["id"])
            best_score = assessment.score
            best_evidence = evidence
            best_needs_review = True

    if best_id and best_needs_review and best_score >= REVIEW_THRESHOLD:
        return best_id, best_score, "needs_manual_review", best_evidence, True
    return None, 0.0, "new_product", {}, False


__all__ = ["MATCH_THRESHOLD", "REVIEW_THRESHOLD", "choose_match", "product_row_to_match_dict"]

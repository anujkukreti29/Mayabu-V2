"""Unified product matching used by every Mayabu ingestion path.

The deterministic identity engine is authoritative. Fuzzy title scoring is only
used when structured identity is incomplete, never to override an explicit
variant or conflict (for example 512 GB vs 1 TB, or different model codes).

Matching V2 adds:
- marketing-noise stripping for fuzzy titles
- category-agnostic hard conflicts in the fuzzy path (camera body/kit, capacity, etc.)
- explainable evidence including matching_version
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from typing import Any

from mayabu.domain.categories.registry import hard_conflicts as category_hard_conflicts
from mayabu.domain.categories.base import cpu_models_compatible, discrete_gpu_conflict
from mayabu.domain.matching_noise import MATCHING_VERSION, strip_matching_noise
from mayabu.domain.product_identity import (
    ProductIdentity,
    build_identity,
    classify_relation,
)
from mayabu_common import title_tokens

MATCH_THRESHOLD = 82.0
REVIEW_THRESHOLD = 70.0
_MAX_FUZZY_TEXT_LENGTH = 2_048
_MAX_CANDIDATE_SOFT_BOUND = 64


@dataclass(frozen=True, slots=True)
class MatchAssessment:
    relation: str
    score: float
    evidence: dict[str, Any]
    merge_allowed: bool
    needs_review: bool


def _coerce_specs(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _as_set(value: Any) -> set[str]:
    if isinstance(value, (list, tuple, set)):
        return {str(item).strip().lower() for item in value if str(item).strip()}
    if value not in (None, ""):
        return {str(value).strip().lower()}
    return set()


def _bounded_text(value: Any) -> str:
    return str(value or "")[:_MAX_FUZZY_TEXT_LENGTH]


def _token_jaccard(left: str, right: str) -> float:
    left_tokens = title_tokens(_bounded_text(left))
    right_tokens = title_tokens(_bounded_text(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _sequence_ratio(left: str, right: str) -> float:
    return difflib.SequenceMatcher(
        None,
        _bounded_text(left),
        _bounded_text(right),
        autojunk=False,
    ).ratio()


def _number(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _numeric_equal(left: Any, right: Any, *, tolerance: float = 0.0) -> bool:
    if left in (None, "") or right in (None, ""):
        return False
    left_number, right_number = _number(left), _number(right)
    if left_number is not None and right_number is not None:
        return abs(left_number - right_number) <= tolerance
    return str(left).strip().lower() == str(right).strip().lower()


def _numeric_conflict(left: Any, right: Any, *, tolerance: float = 0.0) -> bool:
    if left in (None, "") or right in (None, ""):
        return False
    return not _numeric_equal(left, right, tolerance=tolerance)


def _spec_conflicts(left: dict[str, Any], right: dict[str, Any]) -> list[str]:
    conflicts: list[str] = []
    if left.get("brand") and right.get("brand") and left["brand"] != right["brand"]:
        conflicts.append("brand")
    if (
        left.get("category")
        and right.get("category")
        and left["category"] != right["category"]
    ):
        conflicts.append("category")
    if left.get("family") and right.get("family") and left["family"] != right["family"]:
        conflicts.append("family")

    left_models, right_models = (
        _as_set(left.get("model_codes")),
        _as_set(right.get("model_codes")),
    )
    if left_models and right_models and not (left_models & right_models):
        conflicts.append("model_code")

    left_cpus, right_cpus = (
        _as_set(left.get("cpu_models")),
        _as_set(right.get("cpu_models")),
    )
    if left_cpus and right_cpus and not cpu_models_compatible(left_cpus, right_cpus):
        conflicts.append("cpu_model")
    if (
        left.get("cpu_series")
        and right.get("cpu_series")
        and left["cpu_series"] != right["cpu_series"]
        and not cpu_models_compatible(
            left.get("cpu_models") or [left["cpu_series"]],
            right.get("cpu_models") or [right["cpu_series"]],
        )
    ):
        conflicts.append("cpu_series")

    if _numeric_conflict(left.get("ram_gb"), right.get("ram_gb")):
        conflicts.append("ram")
    if _numeric_conflict(left.get("storage_gb"), right.get("storage_gb"), tolerance=8):
        conflicts.append("storage")
    if _numeric_conflict(
        left.get("screen_inch"), right.get("screen_inch"), tolerance=0.6
    ):
        conflicts.append("screen")
    if _numeric_conflict(
        left.get("screen_size_inch"), right.get("screen_size_inch"), tolerance=0.6
    ):
        conflicts.append("screen_size")
    if _numeric_conflict(left.get("capacity_l"), right.get("capacity_l"), tolerance=5):
        conflicts.append("capacity_l")
    if _numeric_conflict(left.get("capacity_kg"), right.get("capacity_kg"), tolerance=0.2):
        conflicts.append("capacity_kg")
    if (
        left.get("load_type")
        and right.get("load_type")
        and str(left["load_type"]).lower() != str(right["load_type"]).lower()
    ):
        conflicts.append("load_type")
    if (
        left.get("connectivity")
        and right.get("connectivity")
        and str(left["connectivity"]).lower() != str(right["connectivity"]).lower()
    ):
        conflicts.append("connectivity")

    if discrete_gpu_conflict(left.get("gpu"), right.get("gpu")):
        conflicts.append("gpu")

    # Adapter-level hard conflicts (camera body/kit, etc.) — never fuzzy-overridable.
    category = left.get("category") or right.get("category")
    if category:
        for reason in category_hard_conflicts(category, left, right):
            if reason not in conflicts:
                conflicts.append(reason)
    return conflicts


def score_product_similarity(
    listing: dict[str, Any], product: dict[str, Any]
) -> tuple[float, dict[str, Any]]:
    """Conservative fuzzy fallback retained for weak-identity listings."""
    specs = _coerce_specs(listing.get("specs"))
    product_specs = _coerce_specs(product.get("specs"))
    conflicts = _spec_conflicts(specs, product_specs)
    if conflicts:
        return -100.0, {"reject": conflicts, "hard_conflict": conflicts}

    title = strip_matching_noise(listing.get("title_norm") or listing.get("title") or "")
    product_title = strip_matching_noise(
        product.get("title_norm") or product.get("canonical_title") or ""
    )
    score = 0.0
    evidence: dict[str, Any] = {"matching_version": MATCHING_VERSION}

    if specs.get("brand") and specs.get("brand") == product_specs.get("brand"):
        score += 12
        evidence["brand"] = specs["brand"]
    if specs.get("family") and specs.get("family") == product_specs.get("family"):
        score += 32
        evidence["family"] = specs["family"]

    model_overlap = _as_set(specs.get("model_codes")) & _as_set(
        product_specs.get("model_codes")
    )
    if model_overlap:
        score += 58
        evidence["model_code"] = sorted(model_overlap)
        evidence["model_code_match"] = True

    cpu_overlap = _as_set(specs.get("cpu_models")) & _as_set(
        product_specs.get("cpu_models")
    )
    if cpu_overlap:
        score += 32
        evidence["cpu_model"] = sorted(cpu_overlap)
    elif specs.get("cpu_series") and specs.get("cpu_series") == product_specs.get(
        "cpu_series"
    ):
        score += 15
        evidence["cpu_series"] = specs["cpu_series"]

    if _numeric_equal(specs.get("ram_gb"), product_specs.get("ram_gb")):
        score += 14
        evidence["ram_gb"] = specs["ram_gb"]
        evidence["ram_match"] = True
    if _numeric_equal(
        specs.get("storage_gb"), product_specs.get("storage_gb"), tolerance=8
    ):
        score += 12
        evidence["storage_gb"] = specs["storage_gb"]
        evidence["storage_match"] = True
    if _numeric_equal(
        specs.get("screen_inch"), product_specs.get("screen_inch"), tolerance=0.3
    ):
        score += 8
        evidence["screen_inch"] = specs["screen_inch"]
    if specs.get("gpu") and specs.get("gpu") == product_specs.get("gpu"):
        score += 8
        evidence["gpu"] = specs["gpu"]

    jaccard = _token_jaccard(title, product_title)
    sequence = _sequence_ratio(title, product_title)
    score += jaccard * 22
    score += sequence * 12
    evidence["title_jaccard"] = round(jaccard, 3)
    evidence["title_sequence"] = round(sequence, 3)
    evidence["title_similarity"] = round((jaccard + sequence) / 2, 3)

    exact_signals = sum(
        1
        for key in (
            "family",
            "model_code",
            "cpu_model",
            "ram_gb",
            "storage_gb",
            "screen_inch",
        )
        if key in evidence
    )
    if "model_code" not in evidence and exact_signals < 3:
        strong_text = jaccard >= 0.58 and sequence >= 0.67
        if exact_signals >= 2 and strong_text:
            review_score = min(max(score, REVIEW_THRESHOLD + 2), MATCH_THRESHOLD - 0.5)
            return round(review_score, 2), {**evidence, "weak_identity_review": True}
        if score < 92:
            return min(score, REVIEW_THRESHOLD - 1), {**evidence, "weak_identity": True}

    return round(score, 2), evidence


def _identity_evidence(identity: ProductIdentity, prefix: str) -> dict[str, Any]:
    return {
        f"{prefix}_exact_fingerprint": identity.exact_fingerprint,
        f"{prefix}_family_fingerprint": identity.family_fingerprint,
        f"{prefix}_model_codes": list(identity.model_codes),
        f"{prefix}_cpu_models": list(identity.cpu_models),
        f"{prefix}_ram_gb": identity.ram_gb,
        f"{prefix}_storage_gb": identity.storage_gb,
        f"{prefix}_screen_inch": identity.screen_inch,
    }


def assess_product_match(
    listing: dict[str, Any], product: dict[str, Any]
) -> MatchAssessment:
    """Return one authoritative match decision for discovery, URL ingest and maintenance."""
    import time

    from mayabu.domain.product_type import classify_product_type, product_types_compatible
    from mayabu.monitoring import instrumentation as metrics

    started = time.perf_counter()
    listing_title = listing.get("title") or listing.get("title_norm") or ""
    product_title = (
        product.get("canonical_title")
        or product.get("title")
        or product.get("title_norm")
        or ""
    )
    listing_category = listing.get("category") or "laptop"
    product_category = product.get("category") or listing_category

    # Product-type gate: accessory containing a model code must never exact-merge.
    listing_type = classify_product_type(listing_title, category=listing_category)
    product_type = classify_product_type(product_title, category=product_category)
    if not product_types_compatible(listing_type, product_type):
        assessment = MatchAssessment(
            relation="conflict",
            score=0.0,
            evidence={
                "matching_version": MATCHING_VERSION,
                "reject": ["product_type"],
                "listing_product_type": listing_type,
                "product_product_type": product_type,
                "reason_code": "product_type_conflict",
            },
            merge_allowed=False,
            needs_review=False,
        )
        category = (listing_category or product_category or "unknown")[:40]
        metrics.MATCH_DURATION.observe(
            (time.perf_counter() - started) * 1000,
            category=category,
            relation=assessment.relation,
        )
        metrics.MATCH_RESULTS.inc(category=category, relation=assessment.relation)
        return assessment

    listing_identity = build_identity(
        listing_title, _coerce_specs(listing.get("specs")), listing_category
    )
    product_identity = build_identity(
        product_title, _coerce_specs(product.get("specs")), product_category
    )
    relation = classify_relation(listing_identity, product_identity)
    evidence = {
        "matching_version": MATCHING_VERSION,
        "deterministic_relation": relation,
        "listing_product_type": listing_type,
        "product_product_type": product_type,
        **_identity_evidence(listing_identity, "listing"),
        **_identity_evidence(product_identity, "product"),
    }

    def _finish(assessment: MatchAssessment) -> MatchAssessment:
        category = (listing_category or product_category or "unknown")[:40]
        metrics.MATCH_DURATION.observe(
            (time.perf_counter() - started) * 1000,
            category=category,
            relation=assessment.relation,
        )
        metrics.MATCH_RESULTS.inc(category=category, relation=assessment.relation)
        from mayabu.domain.match_evidence import explain_match

        explained = explain_match(assessment, category=None)
        evidence.update(
            {
                "explanation": explained.explanation,
                "merge_allowed": explained.merge_allowed,
                "needs_review": explained.needs_review,
            }
        )
        return assessment

    if relation == "exact":
        shared_models = sorted(
            set(listing_identity.model_codes) & set(product_identity.model_codes)
        )
        evidence["shared_model_codes"] = shared_models
        evidence["model_code_match"] = bool(shared_models)
        evidence["identity_rule"] = "deterministic_exact"
        return _finish(MatchAssessment("exact", 1000.0, evidence, True, False))

    if relation in {"variant", "conflict"}:
        evidence["reject"] = [relation]
        evidence["identity_rule"] = "deterministic_block"
        evidence["hard_conflict"] = True
        return _finish(MatchAssessment(relation, -100.0, evidence, False, False))

    fuzzy_score, fuzzy_evidence = score_product_similarity(listing, product)
    evidence.update(fuzzy_evidence)
    evidence["identity_rule"] = "fuzzy_fallback"

    if fuzzy_evidence.get("reject"):
        return _finish(MatchAssessment("conflict", fuzzy_score, evidence, False, False))
    if fuzzy_score >= MATCH_THRESHOLD and not fuzzy_evidence.get("weak_identity"):
        return _finish(MatchAssessment("exact", fuzzy_score, evidence, True, False))
    if fuzzy_score >= REVIEW_THRESHOLD:
        return _finish(MatchAssessment("related", fuzzy_score, evidence, False, True))
    return _finish(MatchAssessment("related", fuzzy_score, evidence, False, False))

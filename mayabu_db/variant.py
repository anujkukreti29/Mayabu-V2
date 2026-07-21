from __future__ import annotations

from typing import Any


def _first(value: Any) -> str | None:
    if isinstance(value, list) and value:
        return str(value[0]).lower()
    if value:
        return str(value).lower()
    return None


def build_variant_key(specs: dict[str, Any], title_norm: str | None = None) -> str | None:
    """Create a conservative laptop variant key.

    Variant keys should only be produced when enough identity signals exist.
    A duplicate product is better than a wrong merge, so this function returns
    None for weak/ambiguous listings.
    """
    brand = specs.get("brand")
    category = specs.get("category") or "laptop"
    model = _first(specs.get("model_codes"))
    family = specs.get("family")
    cpu = _first(specs.get("cpu_models")) or specs.get("cpu_series")
    ram = specs.get("ram_gb")
    storage = specs.get("storage_gb")
    gpu = specs.get("gpu") or "integrated_or_unknown"
    screen = specs.get("screen_inch")

    strong_count = sum(1 for value in [brand, model or family, cpu, ram, storage] if value)
    if strong_count < 4:
        return None

    identity = model or family or (title_norm or "")[:48]
    parts = [category, brand, identity, cpu, f"{ram}gb" if ram else None, f"{storage}gb" if storage else None, gpu]
    if screen:
        parts.append(str(screen))
    return "|".join(str(p).strip().lower().replace(" ", "_") for p in parts if p)

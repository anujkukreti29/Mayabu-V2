from mayabu.catalog.overlap_queries import missing_retailers, overlap_query


def test_model_code_beats_a_family_query() -> None:
    query = overlap_query(
        "laptop",
        "lenovo",
        "Lenovo LOQ 82XV00F6IN Core i5",
        {"family": "loq", "model_code": "82XV00F6IN"},
    )
    assert query == "82XV00F6IN"


def test_missing_retailers_skip_attached_stores() -> None:
    missing = missing_retailers("television", {"flipkart"}, healthy={"flipkart", "reliancedigital"})
    assert missing == ["reliancedigital"]
    assert missing_retailers(
        "television", set(), healthy={"flipkart", "reliancedigital"}
    ) == ["reliancedigital", "flipkart"]
    assert missing_retailers("laptop", {"flipkart", "reliancedigital", "poorvika"}) == []


def test_phone_query_keeps_storage() -> None:
    query = overlap_query(
        "smartphone",
        "apple",
        "Apple iPhone 16 Pro",
        {"model_code": "MU793HN", "storage_gb": 256, "color": "Desert Titanium"},
    )
    assert query is not None
    assert "256GB" in query
    assert "Desert Titanium" in query


def test_refrigerator_fallback_needs_capacity_and_door() -> None:
    assert overlap_query("refrigerator", "lg", "LG fridge", {"capacity_l": 260}) is None
    query = overlap_query(
        "refrigerator",
        "lg",
        "LG 260 L Frost Free",
        {"capacity_l": 260, "door_type": "double_door"},
    )
    assert query == "lg 260 L double door refrigerator"


def test_weak_family_without_model_is_not_a_tv_search() -> None:
    assert overlap_query("television", "samsung", "Samsung TV", {"family": "crystal"}) is None


def test_laptop_query_prefers_the_sku_over_a_cpu() -> None:
    query = overlap_query(
        "laptop",
        "hp",
        "HP Victus 15 13420H 16GB",
        {"model_codes": ["13420H", "15-FA2701TX"], "cpu_models": ["13420H"], "ram_gb": 16},
    )
    assert query == "15-FA2701TX"
    fallback = overlap_query(
        "laptop",
        "hp",
        "HP Victus 13420H",
        {"family": "victus", "cpu_models": ["13420H"], "ram_gb": 16, "storage_gb": 512, "model_codes": ["13420H"]},
    )
    assert fallback is not None
    assert "13420H" in fallback
    assert "victus" in fallback
    assert "13420H" != fallback
    query = overlap_query(
        "camera",
        "sony",
        "Sony ILCE-7M4 with 28-70MM kit",
        {"kit_lens": True, "model_codes": ["28-70MM", "ILCE7M4"]},
    )
    assert query == "ILCE7M4 kit"
    assert overlap_query("camera", "sony", "Sony 24-70MM lens", {"kit_lens": True}) is None

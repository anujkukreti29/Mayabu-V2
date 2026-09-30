from mayabu.search.intent_rank import intent_adjustment
from mayabu.search.ranker import score_product


def test_gaming_laptop_outranks_a_thin_notebook() -> None:
    specs = {"_query": "gaming laptop", "_category": "laptop"}
    gaming = score_product(
        {
            "category": "laptop",
            "canonical_title": "ASUS ROG Strix G16 RTX 4060",
            "family": "rog",
            "brand": "asus",
            "text_rank": 0.2,
        },
        specs,
    )
    thin = score_product(
        {
            "category": "laptop",
            "canonical_title": "Samsung Galaxy Book5",
            "family": "galaxy book",
            "brand": "samsung",
            "text_rank": 0.9,
            "platform_count": 3,
        },
        specs,
    )
    assert gaming > thin
    assert intent_adjustment(query="gaming laptop", category="laptop", text="asus rog rtx 4060") == 48.0
    assert intent_adjustment(query="gaming laptop", category="laptop", text="samsung galaxy book5") == -36.0
    assert intent_adjustment(query="gaming laptop", category="laptop", text="msi gf63 gaming laptop") == 48.0


def test_other_intents_are_lightweight() -> None:
    assert intent_adjustment(query="oled tv", category="television", text="lg oled c4") == 24.0
    assert intent_adjustment(query="samsung tv", category="television", text="samsung crystal") == 0.0
    assert intent_adjustment(query="front load washing machine", category="washing_machine", text="front load 8 kg") == 20.0
    assert intent_adjustment(query="laptop", category="laptop", text="macbook air") == 0.0


def test_generic_camera_downranks_lens_and_kids_camera() -> None:
    body = intent_adjustment(query="camera", category="camera", text="sony alpha ilce-7m4 mirrorless camera body")
    lens = intent_adjustment(query="camera", category="camera", text="zeiss batis telephoto camera lens")
    kids = intent_adjustment(query="camera", category="camera", text="livora kids camera 13mp")
    assert body > lens
    assert body > kids
    assert intent_adjustment(query="canon", category="camera", text="canon eos r6 camera body") >= 0
    placeholder = intent_adjustment(query="dslr camera", category="camera", text="DSLR/SLR Camera")
    real = intent_adjustment(query="dslr camera", category="camera", text="nikon d7500 dslr camera body")
    accessory = intent_adjustment(
        query="sony camera", category="camera", text="Designed For: Sony Mirror-less DSLR Cameras"
    )
    assert real > placeholder
    assert real > accessory

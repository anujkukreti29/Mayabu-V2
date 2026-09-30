from mayabu.domain.phone_recovery import phone_recovery_verdict


def test_storage_token_alone_is_not_a_smartphone() -> None:
    assert phone_recovery_verdict("8GB RAM") == "fragment"
    assert phone_recovery_verdict("5000mAh battery") == "fragment"
    assert phone_recovery_verdict("JBL PartyBox 128GB speaker") == "ambiguous"


def test_tablets_watches_and_accessories_are_not_phones() -> None:
    assert phone_recovery_verdict("Samsung Galaxy Tab S9 128GB") == "wrong_category"
    assert phone_recovery_verdict("Samsung Galaxy Watch9 (44mm, Bluetooth)") == "wrong_category"
    assert phone_recovery_verdict("Apple iPhone 16 Pro case 256GB") == "wrong_category"
    assert phone_recovery_verdict("JioFi 5G hotspot 128GB") == "wrong_category"


def test_brand_plus_storage_is_a_smartphone() -> None:
    assert phone_recovery_verdict("realme C100x (Golden Coast, 64 GB)") == "correct_smartphone"
    assert phone_recovery_verdict("Apple iPhone 16 Pro 256GB") == "correct_smartphone"

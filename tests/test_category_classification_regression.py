"""Category detection regressions — TV vs speaker, accessories, etc."""

from __future__ import annotations

from mayabu.domain.categories.registry import detect_category_from_evidence, detect_category_result


def test_real_tv_stays_television() -> None:
    assert (
        detect_category_from_evidence(title="Samsung 55 inch 4K UHD Smart LED TV 55U8400F")
        == "television"
    )
    assert detect_category_from_evidence(title="Sony Bravia 65 inch OLED Smart TV") == "television"


def test_soundbar_is_not_television() -> None:
    cat = detect_category_from_evidence(
        title="LG Soundbar for TV, 2.1 Channel, 300W, WOW Interface, AI Sound Pro"
    )
    assert cat != "television"
    assert cat == "headphones"


def test_party_speaker_is_not_television() -> None:
    title = (
        "Sony ULT TOWER9 (SRS-ULT 900) Wireless, Bluetooth Party Speaker "
        "with Massive Bass, TV Sound Booster"
    )
    assert detect_category_from_evidence(title=title) != "television"


def test_structured_tv_breadcrumb_rejected_for_speaker_title() -> None:
    det = detect_category_result(
        title="Sony ULT TOWER9 Wireless Bluetooth Party Speaker",
        structured_category="television",
    )
    assert det.category != "television"


def test_tws_not_camera_accessory() -> None:
    assert detect_category_from_evidence(title="Sony WF-1000XM5 True Wireless Earbuds") == "tws"


def test_camera_body_not_accessory() -> None:
    assert (
        detect_category_from_evidence(title="Canon EOS R10 24.2MP Mirrorless Camera Body Only")
        == "camera"
    )


def test_camera_bag_is_accessory() -> None:
    assert detect_category_from_evidence(title="Canon Camera Bag for EOS R10") == "accessory"


def test_phone_lens_protector_is_accessory_not_smartphone() -> None:
    title = "CloudValley Camera Lens Protector for 18 Pro Max"
    assert detect_category_from_evidence(title=title) == "accessory"
    assert detect_category_from_evidence(title=title) != "smartphone"


def test_tempered_glass_is_accessory() -> None:
    assert (
        detect_category_from_evidence(title="Tempered Glass Screen Protector for iPhone 16")
        == "accessory"
    )


def test_laptop_sleeve_is_accessory() -> None:
    assert detect_category_from_evidence(title="Laptop Sleeve Bag for MacBook 14 inch") == "accessory"

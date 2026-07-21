from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mayabu_refresh.common import (
    calculate_discount_percent,
    clean_price_to_int,
    classify_visible_prices,
    refresh_health_report,
)
from mayabu_refresh.models import RefreshResult
from mayabu_scraper_base import discovery_health_report, structural_cards_to_raw_records


def test_refresh_result_is_price_only():
    result = RefreshResult(current_price=69990, mrp=89689, discount_percent=21.96)
    assert result.as_dict() == {"current_price": 69990, "mrp": 89689, "discount_percent": 21.96}


def test_price_parsing_and_discount():
    assert clean_price_to_int("₹1,02,990.00") == 102990
    assert calculate_discount_percent(69990, 89689) == 21.96


def test_visible_price_classifier_handles_plain_flipkart_mrp():
    candidates = [
        {
            "text": "22% 89,689 ₹69,990",
            "price_text": "₹69,990",
            "context": "22% 89,689 ₹69,990 +₹306 Protect Promise Fee",
            "font_size": 27,
            "font_weight": "700",
            "text_decoration": "none",
            "y": 300,
            "width": 140,
            "height": 36,
        }
    ]
    current, mrp, discount = classify_visible_prices(candidates, page_text="22% 89,689 ₹69,990")
    assert current == 69990
    assert mrp == 89689
    assert discount == 22.0


def test_structural_card_to_raw_record_contract():
    cards = [
        {
            "href": "https://www.flipkart.com/demo-laptop/p/itmabc?pid=COM123",
            "anchor_text": "Demo Laptop Intel Core i5 16 GB 512 GB SSD",
            "text": "Demo Laptop Intel Core i5 16 GB 512 GB SSD\n22%\n89,689\n₹69,990",
            "image_url": "https://img.example/demo.png",
            "price_nodes": [
                {
                    "text": "₹69,990",
                    "price_text": "₹69,990",
                    "context": "22% 89,689 ₹69,990",
                    "font_size": 27,
                    "font_weight": "700",
                    "text_decoration": "none",
                    "y": 330,
                    "width": 130,
                    "height": 35,
                }
            ],
        }
    ]
    records = structural_cards_to_raw_records("flipkart", "laptop", cards)
    assert len(records) == 1
    assert records[0]["title"].startswith("Demo Laptop")
    assert records[0]["currentPrice"] == "₹69990"
    assert records[0]["maxRetailPrice"] == "₹89689"
    assert records[0]["link"].startswith("https://www.flipkart.com")


def test_health_reports():
    discovery = discovery_health_report([
        {"title": "Demo Laptop", "currentPrice": "₹69,990", "link": "https://example.com/p/1", "image": "https://img"}
    ], min_products=1)
    assert discovery["status"] == "healthy"
    refresh = refresh_health_report(RefreshResult(current_price=69990, mrp=89689, discount_percent=21.96))
    assert refresh["status"] == "healthy"


if __name__ == "__main__":
    test_refresh_result_is_price_only()
    test_price_parsing_and_discount()
    test_visible_price_classifier_handles_plain_flipkart_mrp()
    test_structural_card_to_raw_record_contract()
    test_health_reports()
    print("Mayabu v4.3 scraper contract smoke test passed")

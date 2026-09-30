"""Curated matching golden set for Matching V2 regression.

Labels use existing relation semantics:
  exact | variant | related | conflict

Keep small and maintainable. Prefer realistic cross-retailer wording.
"""

from __future__ import annotations

from typing import Any, Literal

Relation = Literal["exact", "variant", "related", "conflict"]

GOLDEN_PAIRS: list[dict[str, Any]] = [
    # --- Smartphone ---
    {
        "id": "phone_exact_cross_title",
        "category": "smartphone",
        "left": {
            "title": "Samsung Galaxy S24 5G 8GB 256GB",
            "specs": {"brand": "samsung", "family": "galaxy_s24", "ram_gb": 8, "storage_gb": 256, "model_codes": ["SM-S921B"]},
        },
        "right": {
            "title": "Samsung Galaxy S24 (8 GB RAM, 256 GB) SM-S921B",
            "specs": {"brand": "samsung", "family": "galaxy_s24", "ram_gb": 8, "storage_gb": 256, "model_codes": ["SM-S921B"]},
        },
        "expected": "exact",
    },
    {
        "id": "phone_storage_variant",
        "category": "smartphone",
        "left": {
            "title": "Samsung Galaxy S24 8GB 128GB",
            "specs": {"brand": "samsung", "family": "galaxy_s24", "ram_gb": 8, "storage_gb": 128, "model_codes": ["SM-S921B"]},
        },
        "right": {
            "title": "Samsung Galaxy S24 8GB 256GB",
            "specs": {"brand": "samsung", "family": "galaxy_s24", "ram_gb": 8, "storage_gb": 256, "model_codes": ["SM-S921B"]},
        },
        "expected": "variant",
    },
    {
        "id": "phone_missing_storage_related",
        "category": "smartphone",
        "left": {
            "title": "Samsung Galaxy S24",
            "specs": {"brand": "samsung", "family": "galaxy_s24", "model_codes": []},
        },
        "right": {
            "title": "Samsung Galaxy S24 256GB",
            "specs": {"brand": "samsung", "family": "galaxy_s24", "storage_gb": 256, "model_codes": []},
        },
        "expected": "related",
    },
    {
        "id": "phone_brand_conflict",
        "category": "smartphone",
        "left": {
            "title": "Samsung Galaxy S24 256GB",
            "specs": {"brand": "samsung", "family": "galaxy_s24", "storage_gb": 256},
        },
        "right": {
            "title": "Sony Xperia 256GB",
            "specs": {"brand": "sony", "family": "xperia", "storage_gb": 256},
        },
        "expected": "conflict",
    },
    # --- Laptop ---
    {
        "id": "laptop_exact_model",
        "category": "laptop",
        "left": {
            "title": "ASUS Vivobook 15 X1504VA 16GB 512GB",
            "specs": {
                "brand": "asus",
                "family": "vivobook_15",
                "model_codes": ["X1504VA"],
                "ram_gb": 16,
                "storage_gb": 512,
                "cpu_series": "intel core i5",
            },
        },
        "right": {
            "title": "ASUS VivoBook 15 X1504VA Intel Core i5 16 GB 512 GB Laptop",
            "specs": {
                "brand": "asus",
                "family": "vivobook_15",
                "model_codes": ["X1504VA"],
                "ram_gb": 16,
                "storage_gb": 512,
                "cpu_series": "intel core i5",
            },
        },
        "expected": "exact",
    },
    {
        "id": "laptop_ram_variant",
        "category": "laptop",
        "left": {
            "title": "ASUS Vivobook 15 X1504VA 8GB 512GB",
            "specs": {"brand": "asus", "family": "vivobook_15", "model_codes": ["X1504VA"], "ram_gb": 8, "storage_gb": 512},
        },
        "right": {
            "title": "ASUS Vivobook 15 X1504VA 16GB 512GB",
            "specs": {"brand": "asus", "family": "vivobook_15", "model_codes": ["X1504VA"], "ram_gb": 16, "storage_gb": 512},
        },
        "expected": "variant",
    },
    # --- TV ---
    {
        "id": "tv_exact_marketing_noise",
        "category": "television",
        "left": {
            "title": "Samsung 55 inch 4K QLED Smart TV Best Seller",
            "specs": {"brand": "samsung", "family": "qled", "screen_size_inch": 55, "model_codes": ["QA55Q60C"]},
        },
        "right": {
            "title": "Samsung QA55Q60C 55\" QLED 4K TV No Cost EMI",
            "specs": {"brand": "samsung", "family": "qled", "screen_size_inch": 55, "model_codes": ["QA55Q60C"]},
        },
        "expected": "exact",
    },
    {
        "id": "tv_size_conflict",
        "category": "television",
        "left": {
            "title": "LG Bravia 43 inch 4K TV",
            "specs": {"brand": "lg", "family": "bravia", "screen_size_inch": 43, "model_codes": ["43UT8050"]},
        },
        "right": {
            "title": "LG Bravia 55 inch 4K TV",
            "specs": {"brand": "lg", "family": "bravia", "screen_size_inch": 55, "model_codes": ["55UT8050"]},
        },
        "expected": "variant",
    },
    # --- Refrigerator ---
    {
        "id": "fridge_exact_wording",
        "category": "refrigerator",
        "left": {
            "title": "LG 260L Frost Free Double Door Refrigerator",
            "specs": {"brand": "lg", "capacity_l": 260, "door_type": "double_door", "model_codes": ["GL-I292RPZL"]},
        },
        "right": {
            "title": "LG GL-I292RPZL 260 Litre Frost Free Fridge",
            "specs": {"brand": "lg", "capacity_l": 260, "door_type": "double_door", "model_codes": ["GL-I292RPZL"]},
        },
        "expected": "exact",
    },
    {
        "id": "fridge_capacity_variant",
        "category": "refrigerator",
        "left": {
            "title": "LG 260L Refrigerator",
            "specs": {"brand": "lg", "capacity_l": 260, "family": "lg_frost_free"},
        },
        "right": {
            "title": "LG 360L Refrigerator",
            "specs": {"brand": "lg", "capacity_l": 360, "family": "lg_frost_free"},
        },
        "expected": "variant",
    },
    # --- Washing machine ---
    {
        "id": "washer_exact_cross_retailer",
        "category": "washing_machine",
        "left": {
            "title": "LG 8 Kg Front Load Fully Automatic Washing Machine",
            "specs": {"brand": "lg", "capacity_kg": 8, "load_type": "front_load", "automation_type": "fully_automatic", "model_codes": ["FHM1207SDW"]},
        },
        "right": {
            "title": "LG FHM1207SDW 8kg Front Loading Washer",
            "specs": {"brand": "lg", "capacity_kg": 8, "load_type": "front_load", "automation_type": "fully_automatic", "model_codes": ["FHM1207SDW"]},
        },
        "expected": "exact",
    },
    {
        "id": "washer_capacity_variant",
        "category": "washing_machine",
        "left": {
            "title": "Samsung 7kg Front Load Washing Machine",
            "specs": {"brand": "samsung", "capacity_kg": 7, "load_type": "front_load"},
        },
        "right": {
            "title": "Samsung 9kg Front Load Washing Machine",
            "specs": {"brand": "samsung", "capacity_kg": 9, "load_type": "front_load"},
        },
        "expected": "variant",
    },
    # --- TWS / Headphones ---
    {
        "id": "headphones_exact_noise",
        "category": "headphones",
        "left": {
            "title": "Sony WH-1000XM5 Wireless Noise Cancelling Headphones",
            "specs": {"brand": "sony", "family": "wh1000xm5", "model_codes": ["WH1000XM5"], "connectivity": "wireless", "anc": True},
        },
        "right": {
            "title": "Sony WH1000XM5 ANC Bluetooth Headphone Free Delivery",
            "specs": {"brand": "sony", "family": "wh1000xm5", "model_codes": ["WH1000XM5"], "connectivity": "wireless", "anc": True},
        },
        "expected": "exact",
    },
    {
        "id": "tws_generation_variant",
        "category": "tws",
        "left": {
            "title": "Sony WF-1000XM4 ANC Earbuds",
            "specs": {"brand": "sony", "family": "wf1000xm4", "model_codes": ["WF1000XM4"], "anc": True},
        },
        "right": {
            "title": "Sony WF-1000XM5 ANC Earbuds",
            "specs": {"brand": "sony", "family": "wf1000xm5", "model_codes": ["WF1000XM5"], "anc": True},
        },
        "expected": "conflict",
    },
    # --- Camera ---
    {
        "id": "camera_exact_body_alias",
        "category": "camera",
        "left": {
            "title": "Sony A7 IV body only mirrorless",
            "specs": {
                "brand": "sony",
                "family": "alpha_7",
                "model_codes": ["ILCE-7M4", "A7IV"],
                "body_only": True,
                "kit_lens": None,
                "camera_type": "mirrorless",
            },
        },
        "right": {
            "title": "Sony Alpha 7 IV ILCE-7M4 Body Mirrorless Camera",
            "specs": {
                "brand": "sony",
                "family": "alpha_7",
                "model_codes": ["ILCE-7M4"],
                "body_only": True,
                "kit_lens": None,
                "camera_type": "mirrorless",
            },
        },
        "expected": "exact",
    },
    {
        "id": "camera_body_vs_kit",
        "category": "camera",
        "left": {
            "title": "Sony A7 IV body only",
            "specs": {"brand": "sony", "model_codes": ["ILCE-7M4"], "body_only": True, "kit_lens": None},
        },
        "right": {
            "title": "Sony A7 IV 28-70mm kit",
            "specs": {"brand": "sony", "model_codes": ["ILCE-7M4"], "body_only": False, "kit_lens": "28-70mm"},
        },
        "expected": "variant",
    },
    {
        "id": "camera_r50_body_vs_kit",
        "category": "camera",
        "left": {
            "title": "Canon EOS R50 body only mirrorless",
            "specs": {"brand": "canon", "model_codes": ["R50"], "body_only": True, "kit_lens": None},
        },
        "right": {
            "title": "Canon EOS R50 18-45mm kit mirrorless",
            "specs": {"brand": "canon", "model_codes": ["R50"], "body_only": False, "kit_lens": "18-45mm"},
        },
        "expected": "variant",
    },
    # --- Expanded high-risk coverage ---
    {
        "id": "phone_model_suffix_conflict",
        "category": "smartphone",
        "left": {
            "title": "Samsung Galaxy S24 Ultra SM-S928B 256GB",
            "specs": {"brand": "samsung", "family": "galaxy_s24_ultra", "storage_gb": 256, "model_codes": ["SM-S928B"]},
        },
        "right": {
            "title": "Samsung Galaxy S24 SM-S921B 256GB",
            "specs": {"brand": "samsung", "family": "galaxy_s24", "storage_gb": 256, "model_codes": ["SM-S921B"]},
        },
        "expected": "conflict",
    },
    {
        "id": "phone_exact_flipkart_style",
        "category": "smartphone",
        "left": {
            "title": "Apple iPhone 15 (Blue, 128 GB)",
            "specs": {"brand": "apple", "family": "iphone_15", "storage_gb": 128, "model_codes": ["IPHONE15"]},
        },
        "right": {
            "title": "iPhone 15 128GB Blue Best Seller",
            "specs": {"brand": "apple", "family": "iphone_15", "storage_gb": 128, "model_codes": ["IPHONE15"]},
        },
        "expected": "exact",
    },
    {
        "id": "phone_ram_variant",
        "category": "smartphone",
        "left": {
            "title": "OnePlus 12 8GB 256GB",
            "specs": {"brand": "oneplus", "family": "oneplus_12", "ram_gb": 8, "storage_gb": 256, "model_codes": ["CPH2581"]},
        },
        "right": {
            "title": "OnePlus 12 16GB 256GB",
            "specs": {"brand": "oneplus", "family": "oneplus_12", "ram_gb": 16, "storage_gb": 256, "model_codes": ["CPH2581"]},
        },
        "expected": "variant",
    },
    {
        "id": "tv_size_variant",
        "category": "television",
        "left": {
            "title": "Sony Bravia 3 43 inch 4K Google TV",
            "specs": {"brand": "sony", "family": "bravia_3", "screen_size_inch": 43, "model_codes": ["K43S30"]},
        },
        "right": {
            "title": "Sony Bravia 3 55 inch 4K Google TV",
            "specs": {"brand": "sony", "family": "bravia_3", "screen_size_inch": 55, "model_codes": ["K55S30"]},
        },
        "expected": "variant",
    },
    {
        "id": "tv_generation_conflict",
        "category": "television",
        "left": {
            "title": "LG OLED C3 55 inch",
            "specs": {"brand": "lg", "family": "oled_c3", "screen_size_inch": 55, "model_codes": ["OLED55C3"]},
        },
        "right": {
            "title": "LG OLED C4 55 inch",
            "specs": {"brand": "lg", "family": "oled_c4", "screen_size_inch": 55, "model_codes": ["OLED55C4"]},
        },
        "expected": "conflict",
    },
    {
        "id": "tv_exact_noise",
        "category": "television",
        "left": {
            "title": "Samsung 55 inch Crystal 4K UA55DU7700 Limited Offer",
            "specs": {"brand": "samsung", "family": "crystal", "screen_size_inch": 55, "model_codes": ["UA55DU7700"]},
        },
        "right": {
            "title": "Samsung UA55DU7700 55\" Crystal UHD 4K Smart TV",
            "specs": {"brand": "samsung", "family": "crystal", "screen_size_inch": 55, "model_codes": ["UA55DU7700"]},
        },
        "expected": "exact",
    },
    {
        "id": "fridge_door_conflict",
        "category": "refrigerator",
        "left": {
            "title": "Samsung 253L Single Door Refrigerator",
            "specs": {"brand": "samsung", "capacity_l": 253, "door_type": "single_door", "family": "samsung_253"},
        },
        "right": {
            "title": "Samsung 253L Double Door Refrigerator",
            "specs": {"brand": "samsung", "capacity_l": 253, "door_type": "double_door", "family": "samsung_253"},
        },
        "expected": "variant",
    },
    {
        "id": "fridge_exact_model",
        "category": "refrigerator",
        "left": {
            "title": "Whirlpool 265 L Frost Free Double Door Refrigerator",
            "specs": {"brand": "whirlpool", "capacity_l": 265, "door_type": "double_door", "model_codes": ["IFINVCNM265"]},
        },
        "right": {
            "title": "Whirlpool IFINVCNM265 265L Frost Free Double Door",
            "specs": {"brand": "whirlpool", "capacity_l": 265, "door_type": "double_door", "model_codes": ["IFINVCNM265"]},
        },
        "expected": "exact",
    },
    {
        "id": "washer_load_conflict",
        "category": "washing_machine",
        "left": {
            "title": "LG 7kg Front Load Washing Machine",
            "specs": {"brand": "lg", "capacity_kg": 7, "load_type": "front_load"},
        },
        "right": {
            "title": "LG 7kg Top Load Washing Machine",
            "specs": {"brand": "lg", "capacity_kg": 7, "load_type": "top_load"},
        },
        "expected": "conflict",
    },
    {
        "id": "washer_exact_samsung",
        "category": "washing_machine",
        "left": {
            "title": "Samsung 8 kg Fully Automatic Front Load WW80T4040CE",
            "specs": {"brand": "samsung", "capacity_kg": 8, "load_type": "front_load", "automation_type": "fully_automatic", "model_codes": ["WW80T4040CE"]},
        },
        "right": {
            "title": "Samsung WW80T4040CE 8kg Front Loading Fully Automatic Washer",
            "specs": {"brand": "samsung", "capacity_kg": 8, "load_type": "front_load", "automation_type": "fully_automatic", "model_codes": ["WW80T4040CE"]},
        },
        "expected": "exact",
    },
    {
        "id": "tws_exact_noise",
        "category": "tws",
        "left": {
            "title": "Samsung Galaxy Buds3 Pro Best Seller Free Delivery",
            "specs": {"brand": "samsung", "family": "buds3_pro", "model_codes": ["SM-R630"], "anc": True},
        },
        "right": {
            "title": "Samsung Galaxy Buds 3 Pro SM-R630 ANC Earbuds",
            "specs": {"brand": "samsung", "family": "buds3_pro", "model_codes": ["SM-R630"], "anc": True},
        },
        "expected": "exact",
    },
    {
        "id": "tws_battery_marketing_exact",
        "category": "tws",
        "left": {
            "title": "boAt Airdopes 141 42 Hours Playback",
            "specs": {"brand": "boat", "family": "airdopes_141", "model_codes": ["AIRDOPES141"]},
        },
        "right": {
            "title": "boAt Airdopes 141 Up to 42H Battery TWS",
            "specs": {"brand": "boat", "family": "airdopes_141", "model_codes": ["AIRDOPES141"]},
        },
        "expected": "exact",
    },
    {
        "id": "headphones_wired_wireless_conflict",
        "category": "headphones",
        "left": {
            "title": "Sony WH-1000XM5 Wireless Headphones",
            "specs": {"brand": "sony", "family": "wh1000xm5", "model_codes": ["WH1000XM5"], "connectivity": "wireless"},
        },
        "right": {
            "title": "Sony MDR-ZX110 Wired Headphones",
            "specs": {"brand": "sony", "family": "mdr_zx110", "model_codes": ["MDRZX110"], "connectivity": "wired"},
        },
        "expected": "conflict",
    },
    {
        "id": "headphones_generation_conflict",
        "category": "headphones",
        "left": {
            "title": "Sony WH-1000XM4 Wireless ANC",
            "specs": {"brand": "sony", "family": "wh1000xm4", "model_codes": ["WH1000XM4"], "connectivity": "wireless"},
        },
        "right": {
            "title": "Sony WH-1000XM5 Wireless ANC",
            "specs": {"brand": "sony", "family": "wh1000xm5", "model_codes": ["WH1000XM5"], "connectivity": "wireless"},
        },
        "expected": "conflict",
    },
    {
        "id": "laptop_storage_variant",
        "category": "laptop",
        "left": {
            "title": "HP 15s Intel i5 16GB 512GB",
            "specs": {"brand": "hp", "family": "hp_15s", "model_codes": ["FQ5327TU"], "ram_gb": 16, "storage_gb": 512, "cpu_series": "intel core i5"},
        },
        "right": {
            "title": "HP 15s Intel i5 16GB 1TB",
            "specs": {"brand": "hp", "family": "hp_15s", "model_codes": ["FQ5327TU"], "ram_gb": 16, "storage_gb": 1024, "cpu_series": "intel core i5"},
        },
        "expected": "variant",
    },
    {
        "id": "laptop_cpu_variant",
        "category": "laptop",
        "left": {
            "title": "Lenovo IdeaPad Slim 3 Ryzen 5 8GB 512GB 82XQ01WDIN",
            "specs": {
                "brand": "lenovo",
                "family": "ideapad_slim_3",
                "model_codes": ["82XQ01WDIN"],
                "ram_gb": 8,
                "storage_gb": 512,
                "cpu_series": "amd ryzen 5",
                "cpu_models": ["ryzen 5 7520u"],
            },
        },
        "right": {
            "title": "Lenovo IdeaPad Slim 3 Ryzen 7 8GB 512GB 82XQ01XEIN",
            "specs": {
                "brand": "lenovo",
                "family": "ideapad_slim_3",
                "model_codes": ["82XQ01XEIN"],
                "ram_gb": 8,
                "storage_gb": 512,
                "cpu_series": "amd ryzen 7",
                "cpu_models": ["ryzen 7 7730u"],
            },
        },
        "expected": "variant",
    },
    {
        "id": "laptop_brand_conflict",
        "category": "laptop",
        "left": {
            "title": "Dell Inspiron 15 16GB 512GB",
            "specs": {"brand": "dell", "family": "inspiron_15", "ram_gb": 16, "storage_gb": 512},
        },
        "right": {
            "title": "HP Pavilion 15 16GB 512GB",
            "specs": {"brand": "hp", "family": "pavilion_15", "ram_gb": 16, "storage_gb": 512},
        },
        "expected": "conflict",
    },
    {
        "id": "camera_kit_lens_variant",
        "category": "camera",
        "left": {
            "title": "Canon EOS R50 18-45mm kit",
            "specs": {"brand": "canon", "model_codes": ["R50"], "body_only": False, "kit_lens": "18-45mm"},
        },
        "right": {
            "title": "Canon EOS R50 18-150mm kit",
            "specs": {"brand": "canon", "model_codes": ["R50"], "body_only": False, "kit_lens": "18-150mm"},
        },
        "expected": "variant",
    },
    {
        "id": "camera_brand_conflict",
        "category": "camera",
        "left": {
            "title": "Sony A7 IV body",
            "specs": {"brand": "sony", "model_codes": ["ILCE-7M4"], "body_only": True},
        },
        "right": {
            "title": "Canon EOS R6 Mark II body",
            "specs": {"brand": "canon", "model_codes": ["R6M2"], "body_only": True},
        },
        "expected": "conflict",
    },
    {
        "id": "camera_exact_a7iv_alias2",
        "category": "camera",
        "left": {
            "title": "Sony ILCE-7M4 Mirrorless Camera Body",
            "specs": {"brand": "sony", "family": "alpha_7", "model_codes": ["ILCE-7M4"], "body_only": True},
        },
        "right": {
            "title": "Sony Alpha 7 IV Body Only ILCE7M4",
            "specs": {"brand": "sony", "family": "alpha_7", "model_codes": ["ILCE-7M4", "ILCE7M4"], "body_only": True},
        },
        "expected": "exact",
    },
    # --- Hardening: CPU prefix / weak series / dual capacity ---
    {
        "id": "laptop_cpu_prefix_exact_victus",
        "category": "laptop",
        "left": {
            "title": "HP Victus 15-fa2197TX Intel Core i5 13th Gen 16GB 512GB RTX 3050",
            "specs": {
                "brand": "hp",
                "family": "victus_15",
                "model_codes": ["15-FA2197TX"],
                "cpu_models": ["intel_core_i:5"],
                "cpu_series": "intel_core_i:5",
                "gpu": "rtx3050",
                "ram_gb": 16,
                "storage_gb": 512,
                "screen_inch": 15.6,
            },
        },
        "right": {
            "title": "HP Victus 15 15-fa2197TX Intel Core i5-13420H 16GB 512GB RTX 3050",
            "specs": {
                "brand": "hp",
                "family": "victus_15",
                "model_codes": ["15-FA2197TX"],
                "cpu_models": ["intel_core_i:5:13420h"],
                "cpu_series": "intel_core_i:5:13420h",
                "gpu": "rtx3050",
                "ram_gb": 16,
                "storage_gb": 512,
                "screen_inch": 15.6,
            },
        },
        "expected": "exact",
    },
    {
        "id": "laptop_weak_series_gpu_variant",
        "category": "laptop",
        "left": {
            "title": "Lenovo LOQ 15IRX9 Intel Core i5 RTX 3050 16GB 512GB",
            "specs": {
                "brand": "lenovo",
                "family": "loq_15",
                "model_codes": ["15IRX9"],
                "cpu_models": ["intel_core_i:5"],
                "gpu": "rtx3050",
                "ram_gb": 16,
                "storage_gb": 512,
                "screen_inch": 15.6,
            },
        },
        "right": {
            "title": "Lenovo LOQ 15IRX9 Intel Core i5-13450HX RTX 4050 16GB 512GB",
            "specs": {
                "brand": "lenovo",
                "family": "loq_15",
                "model_codes": ["15IRX9"],
                "cpu_models": ["intel_core_i:5:13450hx"],
                "gpu": "rtx4050",
                "ram_gb": 16,
                "storage_gb": 512,
                "screen_inch": 15.6,
            },
        },
        "expected": "variant",
    },
    {
        "id": "washer_dual_capacity_exact",
        "category": "washing_machine",
        "left": {
            "title": "LG WashTower 13 kg/10 kg Fully Automatic Front Load Washer Dryer Combo FWT1310BG",
            "specs": {
                "brand": "lg",
                "capacity_kg": 13.0,
                "dry_capacity_kg": 10.0,
                "load_type": "front_load",
                "automation_type": "fully_automatic",
                "model_codes": ["FWT1310BG"],
            },
        },
        "right": {
            "title": "LG 13-10 kg Fully Automatic Front Loading Washing Machine FWT1310BG",
            "specs": {
                "brand": "lg",
                "capacity_kg": 13.0,
                "dry_capacity_kg": 10.0,
                "load_type": "front_load",
                "automation_type": "fully_automatic",
                "model_codes": ["FWT1310BG"],
            },
        },
        "expected": "exact",
    },
    # --- Engine V1 near-miss negatives (false exact merge must fail tests) ---
    {
        "id": "phone_ram_sku_variant",
        "category": "smartphone",
        "left": {
            "title": "OnePlus 12 8GB 256GB",
            "specs": {"brand": "oneplus", "family": "oneplus_12", "ram_gb": 8, "storage_gb": 256, "model_codes": ["CPH2581"]},
        },
        "right": {
            "title": "OnePlus 12 16GB 256GB",
            "specs": {"brand": "oneplus", "family": "oneplus_12", "ram_gb": 16, "storage_gb": 256, "model_codes": ["CPH2581"]},
        },
        "expected": "variant",
    },
    {
        "id": "tv_screen_size_variant",
        "category": "television",
        "left": {
            "title": "Sony Bravia 55 inch 4K OLED",
            "specs": {"brand": "sony", "family": "bravia_oled", "screen_size_inch": 55, "model_codes": ["XR55A80L"]},
        },
        "right": {
            "title": "Sony Bravia 65 inch 4K OLED",
            "specs": {"brand": "sony", "family": "bravia_oled", "screen_size_inch": 65, "model_codes": ["XR65A80L"]},
        },
        "expected": "variant",
    },
    {
        "id": "laptop_gpu_sku_variant",
        "category": "laptop",
        "left": {
            "title": "ASUS TUF Gaming F15 FX507VV i7 RTX 4060 16GB 512GB",
            "specs": {
                "brand": "asus",
                "family": "tuf_f15",
                "model_codes": ["FX507VV"],
                "cpu_models": ["intel_core_i:7"],
                "gpu": "rtx4060",
                "ram_gb": 16,
                "storage_gb": 512,
            },
        },
        "right": {
            "title": "ASUS TUF Gaming F15 FX507VV i7 RTX 4070 16GB 512GB",
            "specs": {
                "brand": "asus",
                "family": "tuf_f15",
                "model_codes": ["FX507VV"],
                "cpu_models": ["intel_core_i:7"],
                "gpu": "rtx4070",
                "ram_gb": 16,
                "storage_gb": 512,
            },
        },
        "expected": "variant",
    },
    {
        "id": "fridge_capacity_variant",
        "category": "refrigerator",
        "left": {
            "title": "Samsung 253L Double Door Refrigerator",
            "specs": {"brand": "samsung", "family": "samsung_double_door", "capacity_l": 253, "model_codes": ["RT28C3733S8"]},
        },
        "right": {
            "title": "Samsung 324L Double Door Refrigerator",
            "specs": {"brand": "samsung", "family": "samsung_double_door", "capacity_l": 324, "model_codes": ["RT34C4523S8"]},
        },
        "expected": "variant",
    },
    {
        "id": "washer_kg_variant",
        "category": "washing_machine",
        "left": {
            "title": "LG 7kg Fully Automatic Front Load",
            "specs": {"brand": "lg", "capacity_kg": 7.0, "load_type": "front_load", "model_codes": ["FHV1207Z2M"]},
        },
        "right": {
            "title": "LG 8kg Fully Automatic Front Load",
            "specs": {"brand": "lg", "capacity_kg": 8.0, "load_type": "front_load", "model_codes": ["FHV1408Z2M"]},
        },
        "expected": "variant",
    },
    {
        "id": "camera_body_vs_kit_variant",
        "category": "camera",
        "left": {
            "title": "Sony Alpha ILCE-7M4 Mirrorless Camera Body Only",
            "specs": {"brand": "sony", "family": "alpha_7", "model_codes": ["ILCE-7M4"], "body_only": True},
        },
        "right": {
            "title": "Sony Alpha ILCE-7M4 Mirrorless Camera 28-70mm Kit",
            "specs": {"brand": "sony", "family": "alpha_7", "model_codes": ["ILCE-7M4"], "body_only": False, "kit_lens": "28-70mm"},
        },
        "expected": "variant",
    },
    {
        "id": "headphones_generation_variant",
        "category": "headphones",
        "left": {
            "title": "Sony WH-1000XM4 Wireless Headphones",
            "specs": {"brand": "sony", "family": "wh1000x", "model_codes": ["WH-1000XM4"], "generation": "xm4"},
        },
        "right": {
            "title": "Sony WH-1000XM5 Wireless Headphones",
            "specs": {"brand": "sony", "family": "wh1000x", "model_codes": ["WH-1000XM5"], "generation": "xm5"},
        },
        "expected": "variant",
    },
    {
        "id": "tws_generation_variant",
        "category": "tws",
        "left": {
            "title": "Apple AirPods Pro 1st Generation",
            "specs": {"brand": "apple", "family": "airpods_pro", "model_codes": ["MLWK3"], "generation": "1"},
        },
        "right": {
            "title": "Apple AirPods Pro 2nd Generation",
            "specs": {"brand": "apple", "family": "airpods_pro", "model_codes": ["MTJV3"], "generation": "2"},
        },
        "expected": "variant",
    },
]


def golden_pairs() -> list[dict[str, Any]]:
    from mayabu.domain.matching_golden_extra import EXTRA_GOLDEN_PAIRS

    return list(GOLDEN_PAIRS) + list(EXTRA_GOLDEN_PAIRS)


def score_golden() -> dict[str, Any]:
    """Curated-benchmark metrics only. Not marketplace accuracy."""
    from collections import Counter

    from mayabu.domain.matching import assess_product_match

    pairs = golden_pairs()
    expected_exact = 0
    predicted_exact = 0
    true_exact = 0
    false_exact = 0
    variant_ok = 0
    variant_total = 0
    conflict_ok = 0
    conflict_total = 0
    unmatched = 0
    category_counts: Counter[str] = Counter()
    for pair in pairs:
        category_counts[str(pair["category"])] += 1
        left = {
            "title": pair["left"]["title"],
            "category": pair["category"],
            "specs": {**pair["left"].get("specs", {}), "category": pair["category"]},
        }
        right = {
            "title": pair["right"]["title"],
            "canonical_title": pair["right"]["title"],
            "category": pair["category"],
            "specs": {**pair["right"].get("specs", {}), "category": pair["category"]},
        }
        assessment = assess_product_match(left, right)
        expected = pair["expected"]
        exact_pred = assessment.relation == "exact" and assessment.merge_allowed
        if expected == "exact":
            expected_exact += 1
            if exact_pred:
                true_exact += 1
        if exact_pred:
            predicted_exact += 1
            if expected != "exact":
                false_exact += 1
        if expected == "variant":
            variant_total += 1
            if assessment.relation in {"variant", "conflict"} and not assessment.merge_allowed:
                variant_ok += 1
        if expected == "conflict":
            conflict_total += 1
            if assessment.relation == "conflict" and not assessment.merge_allowed:
                conflict_ok += 1
        if assessment.relation in {"related", "unmatched"} or assessment.needs_review:
            unmatched += 1
    sample = len(pairs)
    precision = (true_exact / predicted_exact) if predicted_exact else 1.0
    recall = (true_exact / expected_exact) if expected_exact else 0.0
    return {
        "sample_count": sample,
        "expected_exact": expected_exact,
        "predicted_exact": predicted_exact,
        "true_exact": true_exact,
        "false_exact_merges": false_exact,
        "exact_precision": round(precision, 4),
        "exact_recall": round(recall, 4),
        "variant_correctness": round((variant_ok / variant_total) if variant_total else 1.0, 4),
        "variant_ok": variant_ok,
        "variant_total": variant_total,
        "conflict_correctness": round((conflict_ok / conflict_total) if conflict_total else 1.0, 4),
        "conflict_ok": conflict_ok,
        "conflict_total": conflict_total,
        "unmatched_rate": round(unmatched / sample, 4) if sample else 0.0,
        "category_counts": dict(sorted(category_counts.items())),
        "scope": "curated_benchmark_only",
    }

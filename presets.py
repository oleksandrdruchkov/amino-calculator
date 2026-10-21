"""Шаблони наборів продуктів для AminoCalc.

Кожен шаблон: список (fdc_id, грами, підпис). Назви й поживні значення беруться з бази
за fdc_id, тому тут зберігається лише склад набору. Щоб додати новий шаблон,
додайте ще один запис у PRESETS.
"""

PRESETS = {
    "irish_breakfast": {
        "title": "Full Irish breakfast (1 serving)",
        "note": (
            "All rows are quality grade A. Sausages are given as raw weight "
            "(120 g raw ~ 100 g fried). White pudding and soda bread are not in the "
            "database, so wholemeal bread is used instead."
        ),
        "items": [
            (9001752, 50,  "Bacon"),
            (7000982, 120, "Pork sausages (raw)"),
            (9002066, 100, "Fried eggs"),
            (6003770, 35,  "Black pudding"),
            (9001225, 80,  "Tomato"),
            (9001335, 60,  "Mushrooms"),
            (7001808, 130, "Baked beans"),
            (7000672, 70,  "Wholemeal bread"),
            (7001052, 10,  "Butter"),
        ],
    },
    "vegetarian_irish_breakfast": {
        "title": "Vegetarian Irish breakfast (1 serving)",
        "note": (
            "Ovo-lacto vegetarian version: bacon, pork sausages and black pudding are "
            "replaced by vegetarian bratwurst (tofu and wheat protein, from BLS 4.0). "
            "Soda bread is not in the database, so wholemeal bread is used instead."
        ),
        "items": [
            (6000290, 90,  "Vegetarian bratwurst"),
            (9002066, 100, "Fried eggs"),
            (9001225, 80,  "Tomato"),
            (9001335, 60,  "Mushrooms"),
            (7001808, 130, "Baked beans"),
            (7000672, 70,  "Wholemeal bread"),
            (7001052, 10,  "Butter"),
        ],
    },

    "dal_rice": {
        "title": "Dal with rice (vegan)",
        "note": "Lentils + brown rice: classic legume + grain pairing.",
        "items": [
            ("lentils mature seeds cooked boiled", 200, "Lentils, cooked"),
            ("rice brown long-grain cooked", 150, "Brown rice, cooked"),
            ("onions raw", 40, "Onion"),
            ("tomatoes red ripe raw", 80, "Tomato"),
            ("oil olive salad or cooking", 8, "Olive oil"),
        ],
    },
    "tofu_stirfry": {
        "title": "Tofu stir-fry with rice (vegan)",
        "note": "Firm tofu, broccoli, carrot, soy sauce, brown rice.",
        "items": [
            ("tofu raw firm", 150, "Firm tofu"),
            ("broccoli cooked boiled drained without salt", 100, "Broccoli, cooked"),
            ("carrots raw", 60, "Carrot"),
            ("soy sauce shoyu", 10, "Soy sauce"),
            ("rice brown long-grain cooked", 150, "Brown rice, cooked"),
            ("oil olive salad or cooking", 8, "Oil"),
        ],
    },
    "chili_sin_carne": {
        "title": "Chili sin carne (vegan)",
        "note": "Kidney beans in tomato sauce with corn and pepper.",
        "items": [
            ("kidney beans mature seeds cooked boiled", 200, "Kidney beans, cooked"),
            ("tomatoes red ripe canned packed in tomato juice", 150, "Canned tomatoes"),
            ("corn sweet yellow cooked boiled", 60, "Sweet corn"),
            ("onions raw", 40, "Onion"),
            ("peppers sweet red raw", 50, "Red pepper"),
            ("oil olive salad or cooking", 5, "Olive oil"),
        ],
    },
    "hummus_plate": {
        "title": "Hummus plate with pita (vegan)",
        "note": "Hummus, whole-wheat pita, cucumber, tomato.",
        "items": [
            ("hummus commercial", 100, "Hummus"),
            ("pita whole-wheat", 60, "Whole-wheat pita"),
            ("cucumber with peel raw", 80, "Cucumber"),
            ("tomatoes red ripe raw", 80, "Tomato"),
            ("oil olive salad or cooking", 5, "Olive oil"),
        ],
    },
    "shakshuka": {
        "title": "Shakshuka with bread (vegetarian)",
        "note": "Two eggs in tomato-pepper sauce, whole-wheat bread.",
        "items": [
            ("egg whole raw fresh", 100, "Eggs (2)"),
            ("tomatoes red ripe canned packed in tomato juice", 200, "Canned tomatoes"),
            ("onions raw", 50, "Onion"),
            ("peppers sweet red raw", 60, "Red pepper"),
            ("oil olive salad or cooking", 10, "Olive oil"),
            ("bread whole-wheat commercially prepared", 60, "Whole-wheat bread"),
        ],
    },

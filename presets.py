"""Шаблони наборів продуктів для AminoCalc.

Кожен шаблон: список (продукт, грами, підпис), де «продукт» — це або fdc_id,
або текстовий запит (слова без «-» мають бути в назві, слова з «-» виключаються).
Назви й поживні значення беруться з бази, тому тут зберігається лише склад набору.
Щоб додати новий шаблон, додайте ще один запис у PRESETS.
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
        "note": "Lentils + brown rice: classic legume + grain pairing. Cooking/olive oil is not included (not in the database), so calories are understated by roughly 40-90 kcal.",
        "items": [
            ("lentil mature seeds cooked boiled", 200, "Lentils, cooked"),
            ("rice brown long-grain cooked", 150, "Brown rice, cooked"),
            ("onion raw", 40, "Onion"),
            ("tomato red ripe raw", 80, "Tomato"),
        ],
    },
    "tofu_stirfry": {
        "title": "Tofu stir-fry with rice (vegan)",
        "note": "Firm tofu, broccoli, carrot, soy sauce, brown rice. Cooking/olive oil is not included (not in the database), so calories are understated by roughly 40-90 kcal.",
        "items": [
            ("tofu raw firm", 150, "Firm tofu"),
            ("broccoli cooked boiled drained without salt", 100, "Broccoli, cooked"),
            ("carrot raw", 60, "Carrot"),
            ("soy sauce shoyu", 10, "Soy sauce"),
            ("rice brown long-grain cooked", 150, "Brown rice, cooked"),
        ],
    },
    "chili_sin_carne": {
        "title": "Chili sin carne (vegan)",
        "note": "Kidney beans in tomato sauce with corn and pepper. Cooking/olive oil is not included (not in the database), so calories are understated by roughly 40-90 kcal.",
        "items": [
            ("kidney bean mature seeds cooked boiled", 200, "Kidney beans, cooked"),
            ("tomato red ripe canned packed in tomato juice", 150, "Canned tomatoes"),
            ("corn sweet yellow cooked boiled", 60, "Sweet corn"),
            ("onion raw", 40, "Onion"),
            ("pepper sweet red raw", 50, "Red pepper"),
        ],
    },
    "hummus_plate": {
        "title": "Hummus plate with pita (vegan)",
        "note": (
            "Hummus is built from its ingredients (about 100 g of hummus: chickpeas, "
            "tahini, lemon juice, garlic), served with whole-wheat pita, cucumber and "
            "tomato. Olive oil and salt are not included, so calories are slightly "
            "understated."
        ),
        "items": [
            ("chickpea mature seeds cooked boiled", 70, "Chickpeas, cooked"),
            ("tahini", 15, "Tahini"),
            ("lemon juice raw", 10, "Lemon juice"),
            ("garlic raw", 3, "Garlic"),
            ("pita whole-wheat", 60, "Whole-wheat pita"),
            ("cucumber with peel raw", 80, "Cucumber"),
            ("tomato red ripe raw", 80, "Tomato"),
        ],
    },
    "shakshuka": {
        "title": "Shakshuka with bread (vegetarian)",
        "note": "Two eggs in tomato-pepper sauce, whole-wheat bread. Cooking/olive oil is not included (not in the database), so calories are understated by roughly 40-90 kcal.",
        "items": [
            ("egg whole raw fresh", 100, "Eggs (2)"),
            ("tomato red ripe canned packed in tomato juice", 200, "Canned tomatoes"),
            ("onion raw", 50, "Onion"),
            ("pepper sweet red raw", 60, "Red pepper"),
            ("bread whole-wheat commercially prepared", 60, "Whole-wheat bread"),
        ],
    },

    "vegan_zefir": {
        "title": "Vegan zefir, aquafaba + agar (1 serving = 3 pieces)",
        "note": (
            "Serving = about 1/4 of a batch (3 pieces). Values per 100 g are typed in "
            "manually (USDA-style reference values; aquafaba is an approximation), not "
            "taken from the database. It is almost all sugar (about 75 g per serving) "
            "and has negligible protein, so the amino acid score is not meaningful here."
        ),
        "items": [
            ({"calories": 387, "protein": 0.0, "fat": 0.0, "carbs": 100.0, "fiber": 0.0},
             75, "Granulated sugar"),
            ({"calories": 42, "protein": 0.2, "fat": 0.1, "carbs": 11.3, "fiber": 1.2},
             38, "Apple puree, unsweetened"),
            ({"calories": 5, "protein": 0.8, "fat": 0.0, "carbs": 0.6, "fiber": 0.0},
             25, "Aquafaba (approx.)"),
            ({"calories": 306, "protein": 6.2, "fat": 0.3, "carbs": 80.9, "fiber": 7.7},
             1, "Agar-agar"),
        ],
    },
}

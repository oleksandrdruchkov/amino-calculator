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
}

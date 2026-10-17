"""
AminoCalc - переглянута версія для порівняння з оригіналом.

Усі змінені місця позначені коментарями [FIX-n]:
  FIX-1  NULL-безпечні суми + охоплення даних («no data» замість хибного 0)
  FIX-2  У каталог потрапляють лише продукти з повним набором 11 амінокислот
  FIX-3  Рекомендації: ранжування за мг/г білка, відсікання аномалій і малобілкових
  FIX-4  Категорії за цілими словами (regex), а не за підрядком
  FIX-5  Нейтральні підписи грейдів, без вигаданих 'B' / 'usda_sr_legacy' за замовчуванням
  FIX-6  Засвоєння: показуємо і чистий AAS, і скор зі засвоєнням (зважене за білком)
  FIX-7  «Fuel» подано як модельну оцінку
  FIX-8  Нульовий білок не дає «зеленого» балансу
  FIX-9  Натрій як ліміт, а не ціль
  FIX-10 Один запит замість SELECT * + PRAGMA на кожне додавання
  FIX-11 Каталог як словники, ключі за fdc_id (без колізій міток)
  FIX-12 try/except навколо бази, пошук текстом замість selectbox на ~17 000 позицій
  FIX-13 Застереження, підпис еталонного профілю, мінімальна порція 1 г
"""

import re

import libsql_client
import pandas as pd
import streamlit as st

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION & MOBILE-FIRST ADAPTIVE STYLES
# ---------------------------------------------------------
st.set_page_config(
    page_title="AminoCalc",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
    .block-container {
        padding-top: 1.0rem !important;
        padding-bottom: 2.0rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
    }
    div[data-testid="stMetric"] {
        background: rgba(125, 125, 125, 0.08) !important;
        border-radius: 8px !important;
        padding: 10px 14px !important;
        border: 1px solid rgba(125, 125, 125, 0.2) !important;
        margin-bottom: 8px !important;
    }
    div[data-testid="stMetricValue"] { font-size: 1.35rem !important; }
    div[data-testid="stMetricLabel"] { font-size: 0.85rem !important; opacity: 0.85; }
    .stButton button { width: 100% !important; border-radius: 6px !important; }
</style>
""",
    unsafe_allow_html=True,
)

# Еталонний амінокислотний профіль ВООЗ/ФАО 2007, дорослі (мг на 1 г білка)
WHO_REFERENCE = {
    "Histidine": 15.0,
    "Isoleucine": 30.0,
    "Leucine": 59.0,
    "Lysine": 45.0,
    "Met + Cys": 22.0,
    "Phe + Tyr": 38.0,
    "Threonine": 23.0,
    "Tryptophan": 6.0,
    "Valine": 39.0,
}

# Добова потреба (мг/кг/день, WHO/FAO 2007)
WHO_DAILY_REQ_PER_KG = {
    "Histidine": 10.0,
    "Isoleucine": 20.0,
    "Leucine": 39.0,
    "Lysine": 30.0,
    "Met + Cys": 15.0,
    "Phe + Tyr": 25.0,
    "Threonine": 15.0,
    "Tryptophan": 4.0,
    "Valine": 26.0,
}

# Які колонки БД входять до кожної групи
AA_GROUP_COLS = {
    "Histidine": ["histidine"],
    "Isoleucine": ["isoleucine"],
    "Leucine": ["leucine"],
    "Lysine": ["lysine"],
    "Met + Cys": ["methionine", "cystine"],
    "Phe + Tyr": ["phenylalanine", "tyrosine"],
    "Threonine": ["threonine"],
    "Tryptophan": ["tryptophan"],
    "Valine": ["valine"],
}
AA_COLS = [c for cols in AA_GROUP_COLS.values() for c in cols]  # усі 11

# Орієнтовні добові норми (RDA / DV)
DAILY_VALUES = {
    "calcium": 1000.0,
    "iron": 14.0,
    "magnesium": 400.0,
    "phosphorus": 700.0,
    "potassium": 3500.0,
    "sodium": 2000.0,
    "zinc": 11.0,
    "copper": 0.9,
    "selenium": 55.0,
    "vitamin_c": 90.0,
    "thiamin_b1": 1.2,
    "riboflavin_b2": 1.3,
    "niacin_b3": 16.0,
    "vitamin_b6": 1.7,
    "folate_b9": 400.0,
    "vitamin_b12": 2.4,
    "vitamin_a_rae": 900.0,
    "vitamin_e": 15.0,
    "vitamin_d": 15.0,
    "vitamin_k": 120.0,
    "fiber": 30.0,
}
LIMIT_NUTRIENTS = {"sodium"}  # [FIX-9] верхня межа, а не ціль


def fmt(value, nd=1, unit=""):
    """Безпечне форматування: None -> '—'."""
    return "—" if value is None else f"{value:.{nd}f}{unit}"


# ---------------------------------------------------------
# 2. ПІДКЛЮЧЕННЯ ДО TURSO ТА КАТАЛОГ
# ---------------------------------------------------------
@st.cache_resource
def get_db():
    return libsql_client.create_client_sync(
        url=st.secrets["TURSO_DATABASE_URL"],
        auth_token=st.secrets["TURSO_READONLY_TOKEN"],
    )


def db_rows(sql, params=None):
    """[FIX-10/11] Один виклик, результат одразу у вигляді словників."""
    res = get_db().execute(sql, params or [])
    return [dict(zip(res.columns, row)) for row in res.rows]


def is_complete(row):
    """
    [FIX-2] Продукт придатний для скору, лише якщо відомі всі 11 амінокислот
    і білок > 0. Нуль = «немає даних» (так експортовано IFCT та частину інших баз).
    Компроміс: продукти з реальним нулем (наприклад, желатин без триптофану)
    теж відсіюються.
    """
    if not (row.get("protein") or 0) > 0:
        return False
    return all((row.get(c) or 0) > 0 for c in AA_COLS)


@st.cache_data(ttl=3600)
def load_food_catalog():
    rows = db_rows(
        """
        SELECT fdc_id, name, calories, protein, fat, carbs, fiber,
               COALESCE(source_db, 'unknown') AS source_db,        -- [FIX-5]
               COALESCE(quality_grade, 'unknown') AS quality_grade, -- [FIX-5]
               histidine, isoleucine, leucine, lysine, methionine, cystine,
               phenylalanine, tyrosine, threonine, tryptophan, valine
        FROM foods
        """
    )
    total = len(rows)
    complete = [r for r in rows if is_complete(r)]
    return complete, total


def fetch_full_item(fdc_id):
    rows = db_rows("SELECT * FROM foods WHERE fdc_id = ?", [fdc_id])
    return rows[0] if rows else None


try:  # [FIX-12]
    foods_catalog, catalog_total = load_food_catalog()
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not load the food database: {exc}")
    st.stop()

# ---------------------------------------------------------
# 3. ШАПКА ТА ПРОФІЛЬ
# ---------------------------------------------------------
st.title("🥗 AminoCalc")
st.caption(
    "Amino Acid Score & Micronutrient Profiler • WHO/FAO 2007 adult reference"
    " pattern (>18 y) • 7 open food composition databases"  # [FIX-13]
)

with st.expander("⚙️ Your Profile & Targets", expanded=False):
    col_w, col_p = st.columns(2)
    with col_w:
        body_weight = st.number_input(
            "Body Weight (kg)", min_value=30.0, max_value=200.0, value=75.0, step=0.5
        )
    with col_p:
        protein_target_per_kg = st.number_input(
            "Target Protein (g/kg)", min_value=0.8, max_value=3.5, value=1.2, step=0.1
        )
    target_protein_total = body_weight * protein_target_per_kg
    st.info(
        f"Daily Target: **{target_protein_total:.1f} g** ({protein_target_per_kg} g/kg)"
    )

if "cart" not in st.session_state:
    st.session_state.cart = []

# ---------------------------------------------------------
# 4. ФІЛЬТР ГРЕЙДУ  [FIX-5]
# ---------------------------------------------------------
RELIABILITY_LABELS = {
    "all": "🌐 All grades (incl. estimated and unknown)",
    "standard": "🟡 Grades A & B",
    "lab_only": "🟢 Grade A only",
}
selected_reliability = st.radio(
    "Data quality grade:",
    options=list(RELIABILITY_LABELS.keys()),
    format_func=lambda x: RELIABILITY_LABELS[x],
    index=0,
    help=(
        "Grades are assigned in the database and are not re-verified by this app. "
        "Grade C generally means estimated or imputed values."
    ),
)
st.caption(
    f"Showing foods with a complete amino acid set: {len(foods_catalog):,} of"
    f" {catalog_total:,} records."
)

if selected_reliability == "lab_only":
    filtered_by_grade = [r for r in foods_catalog if r["quality_grade"] == "A"]
elif selected_reliability == "standard":
    filtered_by_grade = [r for r in foods_catalog if r["quality_grade"] in ("A", "B")]
else:
    filtered_by_grade = foods_catalog

# ---------------------------------------------------------
# 5. ВИБІР БАЗИ ТА ПОШУК  [FIX-12]
# ---------------------------------------------------------
st.subheader("1. Add Food Item")

db_choices = {
    "all": "🌐 All Sources",
    "bls_de_4_0": "🇩🇪 BLS 4.0 (Germany)",
    "usda_sr_legacy": "🇺🇸 USDA Legacy (USA)",
    "kfct_kr": "🇰🇷 KFCT 10.4 (South Korea)",
    "mext_jp": "🇯🇵 MEXT 2023 (Japan)",
    "frida_dk": "🇩🇰 Frida 5.5 (Denmark)",
    "ifct_india": "🇮🇳 IFCT 2017 (India)",
    "fao_upulses": "🌐 FAO uPulses (UN FAO)",
}
flag_map = {
    "bls_de_4_0": "🇩🇪",
    "usda_sr_legacy": "🇺🇸",
    "kfct_kr": "🇰🇷",
    "mext_jp": "🇯🇵",
    "frida_dk": "🇩🇰",
    "ifct_india": "🇮🇳",
    "fao_upulses": "🌐",
}

col_db, col_query = st.columns([1, 2])
with col_db:
    selected_db = st.selectbox(
        "Source DB:", options=list(db_choices.keys()), format_func=lambda x: db_choices[x]
    )

if selected_db == "all":
    active_catalog = filtered_by_grade
else:
    active_catalog = [r for r in filtered_by_grade if r["source_db"] == selected_db]

with col_query:
    query = st.text_input(
        "Search food item:",
        placeholder=f"Type part of a name ({len(active_catalog):,} foods available)...",
    )

terms = [t for t in query.lower().split() if t]
matches = (
    [r for r in active_catalog if all(t in r["name"].lower() for t in terms)][:50]
    if terms
    else []
)
by_id = {r["fdc_id"]: r for r in matches}  # [FIX-11] ключ = fdc_id


def food_label(fdc_id):
    r = by_id[fdc_id]
    return (
        f"{flag_map.get(r['source_db'], '📍')} {r['name']} [{r['quality_grade']}]"
        f" ({fmt(r['calories'], 0)} kcal | P: {fmt(r['protein'])}g)"
    )


def add_to_cart(fdc_id, grams):
    item = fetch_full_item(fdc_id)  # [FIX-10]
    if item is None:
        st.warning("Food not found in the database.")
        return
    item["grams"] = grams
    item["dig"] = float(item.get("digestibility") or 1.0)  # [FIX-6]
    st.session_state.cart.append(item)
    st.toast(f"Added {grams}g of {item['name'][:25]}...")
    st.rerun()


if terms and not matches:
    st.caption("No foods match this search (or they lack complete amino acid data).")
elif matches:
    selected_id = st.selectbox(
        f"Results (showing up to 50):",
        options=[None] + list(by_id.keys()),
        format_func=lambda x: "" if x is None else food_label(x),
    )
    if selected_id is not None:
        sel = by_id[selected_id]
        with st.container(border=True):
            st.markdown(f"**{sel['name']}**")
            st.caption(
                f"Grade: **{sel['quality_grade']}** | Source: **{sel['source_db']}** |"
                f" Per 100g: **{fmt(sel['calories'], 0)} kcal** | P:"
                f" **{fmt(sel['protein'])}g** | F: **{fmt(sel['fat'])}g** | C:"
                f" **{fmt(sel['carbs'])}g**"
            )
            c_portion, c_btn = st.columns([2, 1])
            with c_portion:
                portion = st.number_input(  # [FIX-13] мінімум 1 г
                    "Portion (g)",
                    min_value=1,
                    max_value=2000,
                    value=100,
                    step=5,
                    key=f"inp_{selected_id}",
                )
            with c_btn:
                st.write("")
                if st.button("➕ Add", key=f"btn_{selected_id}", use_container_width=True):
                    add_to_cart(selected_id, portion)

# ---------------------------------------------------------
# 6. РАЦІОН ТА РОЗРАХУНКИ
# ---------------------------------------------------------
cart = st.session_state.cart

if cart:
    st.divider()
    st.subheader(f"2. Current Meal Plan ({len(cart)})")

    item_to_remove = None
    for idx, it in enumerate(cart):
        c_it, c_dig, c_del = st.columns([5, 2, 1])
        with c_it:
            st.write(
                f"• **{it['name']}** — {it['grams']}g"
                f" ({(it.get('protein') or 0) * it['grams'] / 100:.1f}g P)"
                f" [{it.get('quality_grade') or 'unknown'}]"
            )
        with c_dig:  # [FIX-6] ручне перевизначення засвоєння
            it["dig"] = st.number_input(
                "Digestibility",
                min_value=0.3,
                max_value=1.0,
                value=float(it.get("dig", 1.0)),
                step=0.01,
                key=f"dig_{idx}",
                help="1.00 = no correction (also used when the database has no value).",
            )
        with c_del:
            if st.button("✕", key=f"del_{idx}", help="Remove"):
                item_to_remove = idx

    if item_to_remove is not None:
        cart.pop(item_to_remove)
        st.rerun()

    if st.button("🗑️ Clear Plan", use_container_width=True):
        st.session_state.cart = []
        st.rerun()

    def sum_nutrient(col):
        """[FIX-1] None трактується як відсутнє, а не падає з TypeError."""
        return sum((it.get(col) or 0.0) * it["grams"] / 100 for it in cart)

    def coverage(col):
        """[FIX-1] Скільки продуктів у раціоні мають значення для цієї колонки."""
        return sum(1 for it in cart if it.get(col) is not None), len(cart)

    total_cals = sum_nutrient("calories")
    total_protein = sum_nutrient("protein")
    total_fat = sum_nutrient("fat")
    total_carbs = sum_nutrient("carbs")
    total_fiber = sum_nutrient("fiber")

    aa_totals_mg = {
        group: sum(sum_nutrient(c) for c in cols) * 1000
        for group, cols in AA_GROUP_COLS.items()
    }

    scores = {}
    if total_protein > 0:
        for aa, ref in WHO_REFERENCE.items():
            scores[aa] = round((aa_totals_mg[aa] / total_protein) / ref, 2)

    # [FIX-6] середнє засвоєння, зважене за вкладом кожного продукту в білок
    weighted_dig = (
        sum(
            (it.get("protein") or 0) * it["grams"] / 100 * it.get("dig", 1.0)
            for it in cart
        )
        / total_protein
        if total_protein > 0
        else 1.0
    )

    limiting_aa = min(scores, key=scores.get) if scores else "N/A"
    min_score = scores[limiting_aa] if scores else 0.0
    aas_ratio = min(min_score, 1.0)
    adjusted_ratio = aas_ratio * weighted_dig

    # ---------------------------------------------------------
    # 7. МЕТРИКИ
    # ---------------------------------------------------------
    st.divider()
    st.subheader("3. Protein Quality")

    use_dig = st.toggle(
        "Use digestibility-adjusted score for the usable-protein estimate", value=False
    )
    usable_ratio = adjusted_ratio if use_dig else aas_ratio
    est_usable = total_protein * usable_ratio
    est_fuel = total_protein - est_usable  # [FIX-7] модельна оцінка

    r1c1, r1c2 = st.columns(2)
    with r1c1:
        st.metric(
            "Total Protein",
            f"{total_protein:.1f} g",
            f"Target: {target_protein_total:.1f} g",
        )
    with r1c2:
        st.metric(
            "Amino Acid Score",
            f"{aas_ratio * 100:.0f}%",
            f"Limiting: {limiting_aa}",
            delta_color="normal" if aas_ratio >= 1.0 else "inverse",
        )

    r2c1, r2c2 = st.columns(2)
    with r2c1:
        st.metric("Avg. digestibility", f"{weighted_dig * 100:.0f}%", "protein-weighted")
    with r2c2:
        st.metric("Digestibility-adjusted score", f"{adjusted_ratio * 100:.0f}%")

    r3c1, r3c2 = st.columns(2)
    with r3c1:
        st.metric("Est. usable protein", f"{est_usable:.1f} g")
    with r3c2:
        st.metric(
            "Est. oxidized (model)",
            f"{est_fuel:.1f} g",
            "simplified estimate",
            delta_color="off",
        )

    if total_protein <= 0:  # [FIX-8]
        st.info("The meal plan contains no protein, so no amino acid score can be computed.")
    elif aas_ratio < 1.0:
        st.markdown(
            f"""
            <div style="background: rgba(239, 83, 80, 0.15); border-left: 4px solid #ef5350; padding: 12px 14px; border-radius: 6px; margin: 12px 0;">
                <b style="color: #ef5350; font-size: 1.0rem;">Deficit in {limiting_aa} ({min_score * 100:.0f}% of the reference pattern)</b><br>
                <span style="opacity: 0.9; font-size: 0.88rem;">
                    In this simplified model, the limiting amino acid caps protein use at
                    <b>{min_score * 100:.0f}%</b>; the rest is assumed to be used as energy.
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # [FIX-4] категорії за цілими словами
        CATEGORY_PATTERNS = [
            (
                "🌱 Legumes & Soy",
                r"\b(soy|soya|soybeans?|tofu|beans?|lentils?|chickpeas?|peas?|edamame|lupin\w*|tempeh|miso)\b",
            ),
            (
                "🐟 Fish & Seafood",
                r"\b(fish|salmon|tuna|cod|shrimps?|prawns?|crabs?|mackerel|sardines?|seafood|algae)\b",
            ),
            ("🧀 Dairy & Eggs", r"\b(milk|cheese|yogh?urt|eggs?|curd|whey|casein)\b"),
            (
                "🥩 Meat & Poultry",
                r"\b(chicken|turkey|beef|pork|meat|lamb|duck|veal)\b",
            ),
            (
                "🥜 Seeds & Nuts",
                r"\b(seeds?|nuts?|almonds?|peanuts?|walnuts?|sesame|chia|cashews?)\b",
            ),
        ]

        def get_food_category(name):
            n = name.lower()
            for label, pattern in CATEGORY_PATTERNS:
                if re.search(pattern, n):
                    return label
            return "🌾 Grains & Other"

        target_cols = AA_GROUP_COLS.get(limiting_aa, ["lysine"])
        ref_mg_per_g = WHO_REFERENCE.get(limiting_aa, 45.0)

        def mg_per_g_protein(row):
            """[FIX-3] Густина амінокислоти в білку, а не абсолют на 100 г продукту."""
            prot = row.get("protein") or 0
            if prot <= 0:
                return 0.0
            return sum(row.get(c) or 0.0 for c in target_cols) * 1000 / prot

        # [FIX-3] ≥5 г білка/100 г (реально з'їсти) і відсікання ≥3× еталона (схоже на помилку даних)
        candidates = [
            r
            for r in active_catalog
            if (r.get("protein") or 0) >= 5
            and 0 < mg_per_g_protein(r) <= 3 * ref_mg_per_g
        ]
        candidates.sort(key=mg_per_g_protein, reverse=True)

        diversified = {}
        for item in candidates:
            cat = get_food_category(item["name"])
            if cat not in diversified:
                diversified[cat] = item
            if len(diversified) >= 5:
                break

        with st.container(border=True):
            st.markdown(f"💡 **Foods dense in {limiting_aa} (by mg per g of protein)**")
            st.caption(
                "One pick per food group; only foods with at least 5 g protein per"
                " 100 g and plausible values are listed."
            )
            for cat_label, cand in diversified.items():
                rec1, rec2 = st.columns([4, 1])
                with rec1:
                    st.write(f"**{cat_label}**: {cand['name'][:42]}")
                    st.caption(
                        f"⭐ **{mg_per_g_protein(cand):.0f} mg {limiting_aa}/g protein**"
                        f" (reference {ref_mg_per_g:.0f}) | {fmt(cand['protein'])}g protein"
                        f" | {fmt(cand['calories'], 0)} kcal (per 100g)"
                    )
                with rec2:
                    if st.button("➕ 100g", key=f"rec_add_{cand['fdc_id']}_{cat_label}"):
                        add_to_cart(cand["fdc_id"], 100)
    else:
        st.markdown(
            """
            <div style="background: rgba(76, 175, 80, 0.15); border-left: 4px solid #4caf50; padding: 12px 14px; border-radius: 6px; margin: 12px 0;">
                <b style="color: #4caf50; font-size: 1.0rem;">Amino acid score 100%+</b><br>
                <span style="opacity: 0.9; font-size: 0.88rem;">All essential amino acid groups meet the reference pattern.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ---------------------------------------------------------
    # 8. ВКЛАДКИ
    # ---------------------------------------------------------
    tab_aa, tab_macros, tab_min, tab_vit, tab_fats = st.tabs(
        ["🥩 Aminos", "🍞 Macros", "⚡ Minerals", "💊 Vitamins", "🥑 Lipids"]
    )

    def value_with_coverage(col, nd=1, unit=""):
        """[FIX-1] '—' якщо даних немає, зірочка якщо дані є не для всіх продуктів."""
        have, n = coverage(col)
        if have == 0:
            return "no data"
        mark = "*" if have < n else ""
        return f"{sum_nutrient(col):.{nd}f}{unit}{mark}"

    with tab_aa:
        st.markdown(
            f"##### Daily Amino Acid Targets (**{body_weight:.1f} kg** body weight):"
        )
        aa_data = []
        for aa in WHO_REFERENCE:
            daily_req_mg = WHO_DAILY_REQ_PER_KG[aa] * body_weight
            actual_mg = aa_totals_mg[aa]
            req_met_pct = actual_mg / daily_req_mg * 100 if daily_req_mg > 0 else 0
            score_pct = scores.get(aa, 0) * 100
            if aa == limiting_aa and min_score < 1.0:
                dot = "🔴"
            elif req_met_pct < 100.0 or score_pct < 100.0:
                dot = "🟡"
            else:
                dot = "🟢"
            aa_data.append(
                {
                    "": dot,
                    "Amino Acid": aa,
                    "Intake (g)": f"{actual_mg / 1000:.2f}g",
                    "Daily Target (g)": f"{daily_req_mg / 1000:.2f}g",
                    "Daily Met (%)": f"{req_met_pct:.0f}%",
                    "Score vs pattern": f"{score_pct:.0f}%",
                }
            )
        st.dataframe(pd.DataFrame(aa_data), use_container_width=True, hide_index=True)
        st.caption("🔴 Limiting | 🟡 Below 100% | 🟢 Sufficient")

        st.write("##### Daily Requirement Coverage (% of target):")
        req_chart_df = pd.DataFrame(
            {
                "Amino Acid": list(WHO_REFERENCE.keys()),
                "Coverage (%)": [
                    aa_totals_mg[aa] / (WHO_DAILY_REQ_PER_KG[aa] * body_weight) * 100
                    for aa in WHO_REFERENCE
                ],
            }
        ).set_index("Amino Acid")
        st.bar_chart(req_chart_df)

    with tab_macros:
        mc1, mc2 = st.columns(2)
        with mc1:
            st.metric("Calories", value_with_coverage("calories", 0, " kcal"))
            st.metric("Total Fat", value_with_coverage("fat", 1, " g"))
        with mc2:
            st.metric("Carbohydrates", value_with_coverage("carbs", 1, " g"))
            fiber_have, _ = coverage("fiber")
            st.metric(
                "Dietary Fiber",
                value_with_coverage("fiber", 1, " g"),
                (
                    f"{min(total_fiber / DAILY_VALUES['fiber'] * 100, 100):.0f}% RDA"
                    if fiber_have
                    else None
                ),
            )
        st.caption("* = value missing for some foods in the plan; real total may be higher.")

    def render_micro_table(items, name_header):
        """[FIX-1/9] Таблиця мікронутрієнтів з охопленням і лімітним натрієм."""
        rows = []
        for label, key, unit in items:
            have, n = coverage(key)
            target = DAILY_VALUES[key]
            if have == 0:
                rows.append(
                    {
                        "": "⚪",
                        name_header: label,
                        "Intake": "no data",
                        "Target": f"{target:.0f} {unit}",
                        "Met": "—",
                    }
                )
                continue
            val = sum_nutrient(key)
            pct = val / target * 100
            if key in LIMIT_NUTRIENTS:
                dot = "🟢" if pct <= 100 else "🔴"
            else:
                dot = "🟢" if pct >= 100 else ("🟡" if pct >= 70 else "🔴")
            mark = "*" if have < n else ""
            rows.append(
                {
                    "": dot,
                    name_header: label + (" (limit)" if key in LIMIT_NUTRIENTS else ""),
                    "Intake": f"{val:.1f} {unit}{mark}",
                    "Target": f"{target:.0f} {unit}",
                    "Met": f"{pct:.0f}%",
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption("⚪ no data for any food in the plan | * partial data")

    with tab_min:
        render_micro_table(
            [
                ("Calcium", "calcium", "mg"),
                ("Iron", "iron", "mg"),
                ("Magnesium", "magnesium", "mg"),
                ("Phosphorus", "phosphorus", "mg"),
                ("Potassium", "potassium", "mg"),
                ("Sodium", "sodium", "mg"),
                ("Zinc", "zinc", "mg"),
                ("Copper", "copper", "mg"),
                ("Selenium", "selenium", "mcg"),
            ],
            "Mineral",
        )

    with tab_vit:
        render_micro_table(
            [
                ("Vitamin C", "vitamin_c", "mg"),
                ("Thiamin (B1)", "thiamin_b1", "mg"),
                ("Riboflavin (B2)", "riboflavin_b2", "mg"),
                ("Niacin (B3)", "niacin_b3", "mg"),
                ("Vitamin B6", "vitamin_b6", "mg"),
                ("Folate (B9)", "folate_b9", "mcg"),
                ("Vitamin B12", "vitamin_b12", "mcg"),
                ("Vitamin A (RAE)", "vitamin_a_rae", "mcg"),
                ("Vitamin E", "vitamin_e", "mg"),
                ("Vitamin D", "vitamin_d", "mcg"),
                ("Vitamin K", "vitamin_k", "mcg"),
            ],
            "Vitamin",
        )

    with tab_fats:
        st.write(f"- Saturated: **{value_with_coverage('fat_saturated', 1, ' g')}**")
        st.write(f"- Monounsaturated: **{value_with_coverage('fat_monounsaturated', 1, ' g')}**")
        st.write(f"- Polyunsaturated: **{value_with_coverage('fat_polyunsaturated', 1, ' g')}**")
        st.write(f"- Cholesterol: **{value_with_coverage('cholesterol', 0, ' mg')}**")

        sat = sum_nutrient("fat_saturated")
        mono = sum_nutrient("fat_monounsaturated")
        poly = sum_nutrient("fat_polyunsaturated")
        if (sat + mono + poly) > 0:
            fat_df = pd.DataFrame(
                {"Fat Type": ["SFA", "MUFA", "PUFA"], "Grams": [sat, mono, poly]}
            ).set_index("Fat Type")
            st.bar_chart(fat_df)

st.divider()
st.caption(  # [FIX-13]
    "Educational tool, not medical advice. Values come from open food composition"
    " databases and may be incomplete or estimated."
)

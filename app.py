import re
import streamlit as st
import libsql_client
import pandas as pd

# 1. Конфігурація сторінки
st.set_page_config(
    page_title="AminoCalc",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Адаптивний CSS під мобільні екрани
st.markdown("""
<style>
    @media (max-width: 768px) {
        .block-container {
            padding: 1.2rem 0.6rem !important;
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.3rem !important;
        }
        .stButton button {
            width: 100% !important;
            margin-top: 0.2rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# Еталонні профілі ВООЗ/ФАО 2007 (мг на 1 г білка)
WHO_REFERENCE = {
    "Histidine": 15.0,
    "Isoleucine": 30.0,
    "Leucine": 59.0,
    "Lysine": 45.0,
    "Met + Cys": 22.0,
    "Phe + Tyr": 38.0,
    "Threonine": 23.0,
    "Tryptophan": 6.0,
    "Valine": 39.0
}

# Добова потреба на 1 кг маси тіла (мг/кг/день)
WHO_DAILY_REQ_PER_KG = {
    "Histidine": 10.0,
    "Isoleucine": 20.0,
    "Leucine": 39.0,
    "Lysine": 30.0,
    "Met + Cys": 15.0,
    "Phe + Tyr": 25.0,
    "Threonine": 15.0,
    "Tryptophan": 4.0,
    "Valine": 26.0
}

# Орієнтовні добові норми мікронутрієнтів для дорослих (RDA / DV)
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
    "fiber": 30.0
}

STOP_WORDS = {"without", "with", "and", "the", "in", "of", "for", "no"}

@st.cache_resource
def get_db():
    return libsql_client.create_client_sync(
        url=st.secrets["TURSO_DATABASE_URL"],
        auth_token=st.secrets["TURSO_READONLY_TOKEN"]
    )

client = get_db()

@st.cache_data(ttl=3600)
def load_food_catalog():
    # Кешуємо каталог для миттєвого пошуку
    res = client.execute("SELECT fdc_id, name, calories, protein, fat, carbs, fiber FROM foods")
    return res.rows

foods_catalog = load_food_catalog()

st.title("🥗 AminoCalc")
st.caption("Protein Quality, Amino Acid Score & Complete Micronutrient Profiler (WHO/FAO 2007)")

# Налаштування профілю
with st.expander("⚙️ Your Profile & Targets", expanded=False):
    col_w, col_p = st.columns(2)
    with col_w:
        body_weight = st.number_input("Body Weight (kg)", min_value=30.0, max_value=200.0, value=75.0, step=0.5)
    with col_p:
        protein_target_per_kg = st.number_input("Target Protein (g/kg)", min_value=0.8, max_value=3.5, value=1.2, step=0.1)
    
    target_protein_total = body_weight * protein_target_per_kg
    st.info(f"🎯 Daily Protein Target: **{target_protein_total:.1f} g** ({protein_target_per_kg} g/kg)")

# Ініціалізація стану сесії
if "cart" not in st.session_state:
    st.session_state.cart = []

if "search_key_id" not in st.session_state:
    st.session_state.search_key_id = 0

# 1. Пошук продуктів
st.subheader("1. Search & Add Food")
search_term = st.text_input(
    "Search food item (e.g., salmon, bread, egg, oats, chickpeas, chicken breast):",
    placeholder="Type food name...",
    key=f"search_input_{st.session_state.search_key_id}"
)

if search_term:
    raw_tokens = [w.strip(",. ") for w in search_term.strip().lower().split()]
    tokens = [w for w in raw_tokens if len(w) > 0 and w not in STOP_WORDS]
    
    if tokens:
        results = []
        
        for row in foods_catalog:
            fdc_id, name, kcal, prot, fat, carbs, fiber = row
            name_lower = name.lower()
            
            # Перевірка збігу токенів за межами слів
            matches_all = True
            for t in tokens:
                if t in ("skin", "skinless"):
                    if "skin" not in name_lower:
                        matches_all = False
                        break
                else:
                    pattern = rf"\b{re.escape(t)}"
                    if not re.search(pattern, name_lower):
                        matches_all = False
                        break
            
            if matches_all:
                score = 0
                for t in tokens:
                    if t in ("skin", "skinless"):
                        if "skin not eaten" in name_lower or "without skin" in name_lower:
                            score += 150
                        elif "with skin" in name_lower:
                            score += 30
                        else:
                            score += 50
                    else:
                        if name_lower.startswith(t):
                            score += 100
                        elif f", {t}" in name_lower:
                            score += 90
                        elif f" {t}" in name_lower:
                            score += 50
                        else:
                            score += 20
                
                if any(k in tokens for k in ("skin", "skinless")) and "skin not eaten" in name_lower:
                    score += 100
                
                score += min(prot * 0.5, 15)
                
                results.append((score, {
                    "fdc_id": fdc_id,
                    "name": name,
                    "calories": kcal,
                    "protein": prot,
                    "fat": fat,
                    "carbs": carbs,
                    "fiber": fiber
                }))
        
        results.sort(key=lambda x: x[0], reverse=True)
        final_items = [x[1] for x in results[:18]]
        
        if final_items:
            for item_data in final_items:
                fdc_id = item_data["fdc_id"]
                name = item_data["name"]
                kcal = item_data.get("calories", 0)
                prot = item_data.get("protein", 0)
                fat = item_data.get("fat", 0)
                carbs = item_data.get("carbs", 0)
                
                with st.container(border=True):
                    st.markdown(f"**{name}**")
                    st.caption(f"Per 100g: **{kcal:.0f} kcal** | P: **{prot:.1f}g** | F: **{fat:.1f}g** | C: **{carbs:.1f}g**")
                    
                    c_inp, c_btn = st.columns([2, 1])
                    with c_inp:
                        portion = st.number_input("Portion (g)", min_value=10, max_value=2000, value=100, step=10, key=f"inp_{fdc_id}")
                    with c_btn:
                        st.write("")
                        if st.button("➕ Add", key=f"btn_{fdc_id}", use_container_width=True):
                            full_row = client.execute("SELECT * FROM foods WHERE fdc_id = ?", [fdc_id]).rows[0]
                            col_names = [c[1] for c in client.execute("PRAGMA table_info(foods)").rows]
                            item_to_add = dict(zip(col_names, full_row))
                            item_to_add["grams"] = portion
                            st.session_state.cart.append(item_to_add)
                            st.toast(f"Added {portion}g of {name[:25]}...!")
                            
                            # Безпечне очищення: змінюємо номер версії віджета, щоб скинути ввід без помилок
                            st.session_state.search_key_id += 1
                            st.rerun()
        else:
            st.info("No matching foods found.")

# 2. Обраний раціон та аналітика
if st.session_state.cart:
    st.divider()
    st.subheader(f"2. Your Meal Plan ({len(st.session_state.cart)} items)")
    
    # Безпечне видалення без IndexError
    item_to_remove = None
    for idx, it in enumerate(st.session_state.cart):
        col_item, col_del = st.columns([5, 1])
        with col_item:
            st.write(f"• **{it['name']}** — {it['grams']}g ({(it['protein'] * it['grams'] / 100):.1f}g protein)")
        with col_del:
            if st.button("✕", key=f"del_{idx}", help="Remove item"):
                item_to_remove = idx

    if item_to_remove is not None:
        st.session_state.cart.pop(item_to_remove)
        st.rerun()

    if st.button("🗑️ Clear Meal Plan", use_container_width=True):
        st.session_state.cart = []
        st.rerun()

    def sum_nutrient(col):
        return sum(it.get(col, 0) * (it["grams"] / 100) for it in st.session_state.cart)

    total_cals = sum_nutrient("calories")
    total_protein = sum_nutrient("protein")
    total_fat = sum_nutrient("fat")
    total_carbs = sum_nutrient("carbs")
    total_fiber = sum_nutrient("fiber")

    aa_totals_mg = {
        "Histidine": sum_nutrient("histidine") * 1000,
        "Isoleucine": sum_nutrient("isoleucine") * 1000,
        "Leucine": sum_nutrient("leucine") * 1000,
        "Lysine": sum_nutrient("lysine") * 1000,
        "Met + Cys": (sum_nutrient("methionine") + sum_nutrient("cystine")) * 1000,
        "Phe + Tyr": (sum_nutrient("phenylalanine") + sum_nutrient("tyrosine")) * 1000,
        "Threonine": sum_nutrient("threonine") * 1000,
        "Tryptophan": sum_nutrient("tryptophan") * 1000,
        "Valine": sum_nutrient("valine") * 1000
    }

    scores = {}
    if total_protein > 0:
        for aa, ref in WHO_REFERENCE.items():
            mg_per_g_protein = aa_totals_mg[aa] / total_protein
            scores[aa] = round(mg_per_g_protein / ref, 2)

    limiting_aa = min(scores, key=scores.get) if scores else "N/A"
    min_score = scores[limiting_aa] if scores else 1.0
    pdcaas = min(min_score, 1.0)
    effective_protein = total_protein * pdcaas

    st.divider()
    st.subheader("3. Comprehensive Nutrition Analysis")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Calories", f"{total_cals:.0f} kcal")
    m2.metric("Total Protein", f"{total_protein:.1f} g", f"Target: {target_protein_total:.1f} g")
    m3.metric("PDCAAS Score", f"{pdcaas * 100:.0f}%", f"Limiting: {limiting_aa}")
    m4.metric("Usable (Net) Protein", f"{effective_protein:.1f} g")

    tab_aa, tab_macros, tab_min, tab_vit, tab_fats = st.tabs([
        "🥩 Protein & Aminos",
        "🍞 Macros & Fiber",
        "⚡ Minerals",
        "💊 Vitamins",
        "🥑 Lipids & Fats"
    ])

    with tab_aa:
        st.write("##### Amino Acid Profile (% of WHO Requirement):")
        score_df = pd.DataFrame({
            "Amino Acid": list(scores.keys()),
            "Score (%)": [v * 100 for v in scores.values()]
        }).set_index("Amino Acid")
        st.bar_chart(score_df)

        detail_rows = []
        for aa in WHO_REFERENCE.keys():
            daily_req = WHO_DAILY_REQ_PER_KG[aa] * body_weight
            actual_mg = aa_totals_mg[aa]
            pct = (actual_mg / daily_req) * 100 if daily_req > 0 else 0
            detail_rows.append({
                "Amino Acid": aa,
                "Intake (mg)": int(actual_mg),
                "Daily Requirement (mg)": int(daily_req),
                "Requirement Met": f"{pct:.0f}%",
                "Quality Score": f"{scores.get(aa, 0)*100:.0f}%"
            })
        st.dataframe(pd.DataFrame(detail_rows), use_container_width=True)

    with tab_macros:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Protein", f"{total_protein:.1f} g")
        c2.metric("Carbohydrates", f"{total_carbs:.1f} g")
        c3.metric("Dietary Fiber", f"{total_fiber:.1f} g", f"{int(total_fiber / DAILY_VALUES['fiber'] * 100)}% RDA")
        c4.metric("Fats", f"{total_fat:.1f} g")
        st.write(f"- **Water content:** {sum_nutrient('water'):.1f} g")
        st.write(f"- **Ash (mineral residues):** {sum_nutrient('ash'):.1f} g")

    with tab_min:
        st.write("##### Minerals & Daily Targets:")
        minerals_data = [
            ("Calcium (Ca)", sum_nutrient("calcium"), DAILY_VALUES["calcium"], "mg"),
            ("Iron (Fe)", sum_nutrient("iron"), DAILY_VALUES["iron"], "mg"),
            ("Magnesium (Mg)", sum_nutrient("magnesium"), DAILY_VALUES["magnesium"], "mg"),
            ("Phosphorus (P)", sum_nutrient("phosphorus"), DAILY_VALUES["phosphorus"], "mg"),
            ("Potassium (K)", sum_nutrient("potassium"), DAILY_VALUES["potassium"], "mg"),
            ("Sodium (Na)", sum_nutrient("sodium"), DAILY_VALUES["sodium"], "mg"),
            ("Zinc (Zn)", sum_nutrient("zinc"), DAILY_VALUES["zinc"], "mg"),
            ("Copper (Cu)", sum_nutrient("copper"), DAILY_VALUES["copper"], "mg"),
            ("Selenium (Se)", sum_nutrient("selenium"), DAILY_VALUES["selenium"], "mcg")
        ]
        st.dataframe(pd.DataFrame([{
            "Mineral": m[0],
            "Amount": f"{m[1]:.1f} {m[3]}",
            "Daily RDA": f"{m[2]:.0f} {m[3]}",
            "Fulfilled": f"{(m[1] / m[2]) * 100:.0f}%"
        } for m in minerals_data]), use_container_width=True)

    with tab_vit:
        st.write("##### Vitamins Spectrum & Daily Targets:")
        vitamins_data = [
            ("Vitamin C", sum_nutrient("vitamin_c"), DAILY_VALUES["vitamin_c"], "mg"),
            ("Vitamin B1 (Thiamin)", sum_nutrient("thiamin_b1"), DAILY_VALUES["thiamin_b1"], "mg"),
            ("Vitamin B2 (Riboflavin)", sum_nutrient("riboflavin_b2"), DAILY_VALUES["riboflavin_b2"], "mg"),
            ("Vitamin B3 (Niacin)", sum_nutrient("niacin_b3"), DAILY_VALUES["niacin_b3"], "mg"),
            ("Vitamin B6", sum_nutrient("vitamin_b6"), DAILY_VALUES["vitamin_b6"], "mg"),
            ("Vitamin B9 (Folate)", sum_nutrient("folate_b9"), DAILY_VALUES["folate_b9"], "mcg"),
            ("Vitamin B12", sum_nutrient("vitamin_b12"), DAILY_VALUES["vitamin_b12"], "mcg"),
            ("Vitamin A (RAE)", sum_nutrient("vitamin_a_rae"), DAILY_VALUES["vitamin_a_rae"], "mcg"),
            ("Vitamin E", sum_nutrient("vitamin_e"), DAILY_VALUES["vitamin_e"], "mg"),
            ("Vitamin D", sum_nutrient("vitamin_d"), DAILY_VALUES["vitamin_d"], "mcg"),
            ("Vitamin K", sum_nutrient("vitamin_k"), DAILY_VALUES["vitamin_k"], "mcg")
        ]
        st.dataframe(pd.DataFrame([{
            "Vitamin": v[0],
            "Amount": f"{v[1]:.2f} {v[3]}",
            "Daily RDA": f"{v[2]:.0f} {v[3]}",
            "Fulfilled": f"{(v[1] / v[2]) * 100:.0f}%"
        } for v in vitamins_data]), use_container_width=True)

    with tab_fats:
        sat = sum_nutrient("fat_saturated")
        mono = sum_nutrient("fat_monounsaturated")
        poly = sum_nutrient("fat_polyunsaturated")
        chol = sum_nutrient("cholesterol")

        c_f1, c_f2 = st.columns(2)
        with c_f1:
            st.write("**Lipid Breakdown:**")
            st.write(f"- Saturated Fat: **{sat:.1f} g**")
            st.write(f"- Monounsaturated Fat: **{mono:.1f} g**")
            st.write(f"- Polyunsaturated Fat: **{poly:.1f} g**")
            st.write(f"- Cholesterol: **{chol:.0f} mg**")
        with c_f2:
            if (sat + mono + poly) > 0:
                fat_chart_df = pd.DataFrame({
                    "Fat Type": ["Saturated", "Monounsaturated", "Polyunsaturated"],
                    "Grams": [sat, mono, poly]
                }).set_index("Fat Type")
                st.bar_chart(fat_chart_df)

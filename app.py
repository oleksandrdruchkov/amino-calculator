import re
import streamlit as st
import libsql_client
import pandas as pd

# 1. Page Configuration
st.set_page_config(
    page_title="AminoCalc",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Responsive mobile styles
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

# WHO/FAO/UNU 2007 Reference Pattern for Adults (mg/g protein)
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

# WHO Daily Requirement per kg body weight (mg/kg/day)
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

# Daily Values / RDA for Micronutrients
DAILY_VALUES = {
    "calcium": 1000.0,      # mg
    "iron": 14.0,           # mg
    "magnesium": 400.0,     # mg
    "phosphorus": 700.0,    # mg
    "potassium": 3500.0,    # mg
    "sodium": 2000.0,       # mg
    "zinc": 11.0,           # mg
    "copper": 0.9,          # mg
    "selenium": 55.0,       # mcg
    "vitamin_c": 90.0,      # mg
    "thiamin_b1": 1.2,      # mg
    "riboflavin_b2": 1.3,   # mg
    "niacin_b3": 16.0,      # mg
    "vitamin_b6": 1.7,      # mg
    "folate_b9": 400.0,     # mcg
    "vitamin_b12": 2.4,     # mcg
    "vitamin_a_rae": 900.0, # mcg
    "vitamin_e": 15.0,      # mg
    "vitamin_d": 15.0,      # mcg (600 IU)
    "vitamin_k": 120.0,     # mcg
    "fiber": 30.0           # g
}

@st.cache_resource
def get_db():
    return libsql_client.create_client_sync(
        url=st.secrets["TURSO_DATABASE_URL"],
        auth_token=st.secrets["TURSO_READONLY_TOKEN"]
    )

client = get_db()

st.title("🥗 AminoCalc")
st.caption("Protein Quality, Amino Acid Score & Complete Micronutrient Profiler (WHO/FAO 2007)")

# User Profile Settings
with st.expander("⚙️ Your Profile & Targets", expanded=False):
    col_w, col_p = st.columns(2)
    with col_w:
        body_weight = st.number_input("Body Weight (kg)", min_value=30.0, max_value=200.0, value=75.0, step=0.5)
    with col_p:
        protein_target_per_kg = st.number_input("Target Protein (g/kg)", min_value=0.8, max_value=3.5, value=1.2, step=0.1)
    
    target_protein_total = body_weight * protein_target_per_kg
    st.info(f"🎯 Daily Protein Target: **{target_protein_total:.1f} g** ({protein_target_per_kg} g/kg)")

if "cart" not in st.session_state:
    st.session_state.cart = []

# 1. Search & Add Food (Word-boundary filtered & token ranked)
st.subheader("1. Search & Add Food")
search_term = st.text_input(
    "Search food item (e.g., bread, salmon, egg, oats, chickpeas, chicken breast):",
    placeholder="Type food name..."
)

if search_term:
    raw_tokens = [w.strip(",. ") for w in search_term.strip().lower().split()]
    tokens = [w for w in raw_tokens if len(w) > 0]
    
    if tokens:
        where_conditions = " AND ".join(["LOWER(name) LIKE ?" for _ in tokens])
        query = f"SELECT * FROM foods WHERE {where_conditions}"
        params = [f"%{t}%" for t in tokens]
        
        raw_res = client.execute(query, params)
        col_names = [c[1] for c in client.execute("PRAGMA table_info(foods)").rows]
        
        candidates = [dict(zip(col_names, row)) for row in raw_res.rows]
        
        # Word-boundary filtering (\b) to eliminate partial substring matches (e.g. bread in breaded)
        filtered_candidates = []
        first_token = tokens[0]
        
        for item in candidates:
            item_name_lower = item["name"].lower()
            
            # Require all search tokens as whole words or word prefixes
            matches_all = True
            for t in tokens:
                pattern = rf"\b{re.escape(t)}"
                if not re.search(pattern, item_name_lower):
                    matches_all = False
                    break
            
            if matches_all:
                # Ranking score:
                # 100: starts with token (e.g., "Bread, ...", "Salmon, ...")
                # 85: exact category match in USDA format (e.g., "Fish, salmon, ...")
                # 60: token exists elsewhere as a standalone word
                score = 0
                if item_name_lower.startswith(first_token):
                    score = 100
                elif f", {first_token}" in item_name_lower:
                    score = 85
                elif f" {first_token}" in item_name_lower:
                    score = 60
                else:
                    score = 40
                
                # Small bonus for protein to sort within the same relevance bracket
                score += min(item.get("protein", 0), 15)
                filtered_candidates.append((score, item))
        
        filtered_candidates.sort(key=lambda x: x[0], reverse=True)
        final_items = [x[1] for x in filtered_candidates[:12]]
        
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
                    
                    with st.expander("🔎 View 100g Nutrition Details"):
                        st.write(
                            f"**Minerals:** Ca: {item_data.get('calcium',0):.0f}mg | Fe: {item_data.get('iron',0):.1f}mg | "
                            f"Mg: {item_data.get('magnesium',0):.0f}mg | K: {item_data.get('potassium',0):.0f}mg | Zn: {item_data.get('zinc',0):.1f}mg"
                        )
                        st.write(
                            f"**Vitamins:** Vit C: {item_data.get('vitamin_c',0):.1f}mg | Vit B12: {item_data.get('vitamin_b12',0):.2f}mcg | "
                            f"Folate: {item_data.get('folate_b9',0):.0f}mcg | Vit B6: {item_data.get('vitamin_b6',0):.2f}mg"
                        )
                        st.write(
                            f"**Fats:** Saturated: {item_data.get('fat_saturated',0):.1f}g | Fiber: {item_data.get('fiber',0):.1f}g"
                        )
                    
                    c_inp, c_btn = st.columns([2, 1])
                    with c_inp:
                        portion = st.number_input("Portion (g)", min_value=10, max_value=2000, value=100, step=10, key=f"inp_{fdc_id}")
                    with c_btn:
                        st.write("")
                        if st.button("➕ Add", key=f"btn_{fdc_id}", use_container_width=True):
                            item_to_add = dict(item_data)
                            item_to_add["grams"] = portion
                            st.session_state.cart.append(item_to_add)
                            st.toast(f"Added {portion}g of {name[:25]}...!")
                            st.rerun()
        else:
            st.info("No matching foods found.")

# 2. Meal Plan & Analytics
if st.session_state.cart:
    st.divider()
    st.subheader(f"2. Your Meal Plan ({len(st.session_state.cart)} items)")
    
    for idx, it in enumerate(st.session_state.cart):
        col_item, col_del = st.columns([5, 1])
        with col_item:
            st.write(f"• **{it['name']}** — {it['grams']}g ({(it['protein'] * it['grams'] / 100):.1f}g protein)")
        with col_del:
            if st.button("✕", key=f"del_{idx}", help="Remove item"):
                st.session_state.cart.pop(idx)
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

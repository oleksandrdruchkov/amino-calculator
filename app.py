import streamlit as st
import libsql_client
import pandas as pd

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION & MOBILE-FIRST ADAPTIVE STYLES
# ---------------------------------------------------------
st.set_page_config(
    page_title="AminoCalc",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Adaptive CSS for Dark/Light mode and smartphone screens
st.markdown("""
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
    div[data-testid="stMetricValue"] { 
        font-size: 1.35rem !important; 
    }
    div[data-testid="stMetricLabel"] { 
        font-size: 0.85rem !important; 
        opacity: 0.85;
    }
    .stButton button { 
        width: 100% !important; 
        border-radius: 6px !important; 
    }
</style>
""", unsafe_allow_html=True)

# WHO/FAO 2007 Reference Pattern (mg per 1 g of protein)
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

# Daily requirement per 1 kg body weight (mg/kg/day)
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

# Reference Daily Values (RDA / DV)
DAILY_VALUES = {
    "calcium": 1000.0, "iron": 14.0, "magnesium": 400.0, "phosphorus": 700.0,
    "potassium": 3500.0, "sodium": 2000.0, "zinc": 11.0, "copper": 0.9, "selenium": 55.0,
    "vitamin_c": 90.0, "thiamin_b1": 1.2, "riboflavin_b2": 1.3, "niacin_b3": 16.0,
    "vitamin_b6": 1.7, "folate_b9": 400.0, "vitamin_b12": 2.4, "vitamin_a_rae": 900.0,
    "vitamin_e": 15.0, "vitamin_d": 15.0, "vitamin_k": 120.0, "fiber": 30.0
}

# ---------------------------------------------------------
# 2. DATABASE CONNECTION & DATA CACHING
# ---------------------------------------------------------
@st.cache_resource
def get_db():
    return libsql_client.create_client_sync(
        url=st.secrets["TURSO_DATABASE_URL"],
        auth_token=st.secrets["TURSO_READONLY_TOKEN"]
    )

client = get_db()

@st.cache_data(ttl=3600)
def load_food_catalog():
    # Only load foods with verified amino acid measurements
    res = client.execute("""
        SELECT fdc_id, name, calories, protein, fat, carbs, fiber,
               COALESCE(source_db, 'usda_sr_legacy') AS source_db,
               histidine, isoleucine, leucine, lysine, methionine, cystine,
               phenylalanine, tyrosine, threonine, tryptophan, valine
        FROM foods 
        WHERE (
            COALESCE(histidine, 0) + COALESCE(isoleucine, 0) + COALESCE(leucine, 0) + 
            COALESCE(lysine, 0) + COALESCE(methionine, 0) + COALESCE(cystine, 0) + 
            COALESCE(phenylalanine, 0) + COALESCE(tyrosine, 0) + COALESCE(threonine, 0) + 
            COALESCE(tryptophan, 0) + COALESCE(valine, 0)
        ) > 0
    """)
    return res.rows

foods_catalog = load_food_catalog()

# ---------------------------------------------------------
# 3. HEADER & TARGET PROFILE
# ---------------------------------------------------------
st.title("🥗 AminoCalc")
st.caption("Protein Quality, Amino Acid Score & Complete Micronutrient Profiler (WHO/FAO 2007)")

with st.expander("⚙️ Profile & Targets", expanded=False):
    col_w, col_p = st.columns(2)
    with col_w:
        body_weight = st.number_input("Body Weight (kg)", min_value=30.0, max_value=200.0, value=75.0, step=0.5)
    with col_p:
        protein_target_per_kg = st.number_input("Target Protein (g/kg)", min_value=0.8, max_value=3.5, value=1.2, step=0.1)
    
    target_protein_total = body_weight * protein_target_per_kg
    st.info(f"Daily Target: **{target_protein_total:.1f} g** ({protein_target_per_kg} g/kg)")

if "cart" not in st.session_state:
    st.session_state.cart = []

# ---------------------------------------------------------
# 4. FAST FOOD SEARCH (AUTOCOMPLETE SELECTBOX)
# ---------------------------------------------------------
st.subheader("1. Add Food Item")

db_choices = {
    "all": "🌐 All Sources",
    "usda_sr_legacy": "🇺🇸 USDA Legacy",
    "cofid_uk": "🇬🇧 CoFID UK",
    "bls_de_4_0": "🇩🇪 BLS 4.0 DE",
    "kfct_kr": "🇰🇷 KFCT KR"
}

col_db, col_select = st.columns([1, 2])

with col_db:
    selected_db = st.selectbox(
        "Source DB:",
        options=list(db_choices.keys()),
        format_func=lambda x: db_choices[x]
    )

if selected_db == "all":
    active_catalog = foods_catalog
else:
    active_catalog = [r for r in foods_catalog if r[7] == selected_db]

flag_map = {
    "usda_sr_legacy": "🇺🇸",
    "cofid_uk": "🇬🇧",
    "bls_de_4_0": "🇩🇪",
    "kfct_kr": "🇰🇷"
}

food_options = {}
for r in active_catalog:
    fdc_id, name, kcal, prot, fat, carbs, fiber, src_db = r[:8]
    flag = flag_map.get(src_db, "📍")
    label = f"{flag} {name} ({kcal:.0f} kcal | P: {prot:.1f}g)"
    food_options[label] = r

with col_select:
    selected_food_label = st.selectbox(
        "Search food item:",
        options=[""] + list(food_options.keys()),
        index=0,
        placeholder="Type to filter: salmon, oats, egg, tofu, beef..."
    )

if selected_food_label and selected_food_label in food_options:
    selected_item = food_options[selected_food_label]
    fdc_id, name, kcal, prot, fat, carbs, fiber, src_db = selected_item[:8]

    with st.container(border=True):
        st.markdown(f"**{name}**")
        st.caption(f"Per 100g: **{kcal:.0f} kcal** | P: **{prot:.1f}g** | F: **{fat:.1f}g** | C: **{carbs:.1f}g**")
        
        c_portion, c_btn = st.columns([2, 1])
        with c_portion:
            portion = st.number_input("Portion (g)", min_value=10, max_value=2000, value=100, step=10, key=f"inp_{fdc_id}")
        with c_btn:
            st.write("")
            if st.button("➕ Add", key=f"btn_{fdc_id}", use_container_width=True):
                full_row = client.execute("SELECT * FROM foods WHERE fdc_id = ?", [fdc_id]).rows[0]
                col_names = [c[1] for c in client.execute("PRAGMA table_info(foods)").rows]
                item_dict = dict(zip(col_names, full_row))
                item_dict["grams"] = portion
                st.session_state.cart.append(item_dict)
                st.toast(f"Added {portion}g of {name[:20]}...")
                st.rerun()

# ---------------------------------------------------------
# 5. MEAL PLAN & CALCULATIONS
# ---------------------------------------------------------
if st.session_state.cart:
    st.divider()
    st.subheader(f"2. Current Meal Plan ({len(st.session_state.cart)})")

    item_to_remove = None
    for idx, it in enumerate(st.session_state.cart):
        c_it, c_del = st.columns([5, 1])
        with c_it:
            st.write(f"• **{it['name']}** — {it['grams']}g ({(it['protein'] * it['grams'] / 100):.1f}g P)")
        with c_del:
            if st.button("✕", key=f"del_{idx}", help="Remove"):
                item_to_remove = idx

    if item_to_remove is not None:
        st.session_state.cart.pop(item_to_remove)
        st.rerun()

    if st.button("🗑️ Clear Plan", use_container_width=True):
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
    usable_ratio = min(min_score, 1.0)
    building_protein = total_protein * usable_ratio
    fuel_protein = total_protein - building_protein

    # ---------------------------------------------------------
    # 6. METRICS & DEFICIT ALERT
    # ---------------------------------------------------------
    st.divider()
    st.subheader("3. Protein Utilization")

    row1_c1, row1_c2 = st.columns(2)
    with row1_c1:
        st.metric("Total Protein", f"{total_protein:.1f} g", f"Target: {target_protein_total:.1f} g")
    with row1_c2:
        st.metric("AAS Quality", f"{usable_ratio * 100:.0f}%", f"Limiting: {limiting_aa}", delta_color="normal" if usable_ratio >= 1.0 else "inverse")

    row2_c1, row2_c2 = st.columns(2)
    with row2_c1:
        st.metric("Net Usable", f"{building_protein:.1f} g", f"{usable_ratio * 100:.0f}% efficient")
    with row2_c2:
        st.metric("Oxidized / Fuel", f"{fuel_protein:.1f} g", f"{(1 - usable_ratio) * 100:.0f}% excess", delta_color="inverse")

    if usable_ratio < 1.0:
        st.markdown(f"""
        <div style="background: rgba(239, 83, 80, 0.15); border-left: 4px solid #ef5350; padding: 12px 14px; border-radius: 6px; margin: 12px 0;">
            <b style="color: #ef5350; font-size: 1.0rem;">Deficit in {limiting_aa} ({min_score * 100:.0f}% of WHO target)</b><br>

import streamlit as st
import libsql_client
import pandas as pd

st.set_page_config(
    page_title="Protein Quality & Amino Acid Calculator",
    page_icon="🥗",
    layout="wide"
)

# WHO/FAO/UNU 2007 Reference Pattern for Adults (mg amino acid per 1 g of protein)
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

@st.cache_resource
def get_db():
    return libsql_client.create_client_sync(
        url=st.secrets["TURSO_DATABASE_URL"],
        auth_token=st.secrets["TURSO_READONLY_TOKEN"]
    )

client = get_db()

st.title("🥗 Protein Quality, Amino Acid Score & PDCAAS Calculator")
st.caption("Database: USDA SR Legacy | Standard: WHO/FAO/UNU 2007 Reference Pattern")

# Sidebar: User inputs
with st.sidebar:
    st.header("Profile & Targets")
    body_weight = st.number_input("Body Weight (kg):", min_value=30.0, max_value=200.0, value=75.0, step=0.5)
    protein_target_per_kg = st.number_input("Target Protein (g/kg):", min_value=0.8, max_value=3.5, value=1.2, step=0.1)
    target_protein_total = body_weight * protein_target_per_kg
    st.metric("Daily Protein Target", f"{target_protein_total:.1f} g")

if "cart" not in st.session_state:
    st.session_state.cart = []

# Search Section
st.subheader("1. Search & Add Foods")
search_term = st.text_input("Search food item (e.g., egg, oats, salmon, chicken breast, lentils, milk):")

if search_term:
    query = """
    SELECT fdc_id, name, calories, protein, fat, carbs, fiber
    FROM foods 
    WHERE name LIKE ? 
    ORDER BY protein DESC 
    LIMIT 8
    """
    res = client.execute(query, [f"%{search_term}%"])
    
    if res.rows:
        for r in res.rows:
            col_name, col_g, col_add = st.columns([5, 2, 1])
            col_name.write(f"**{r[1]}**  \n*(per 100g: {r[2]:.0f} kcal | Protein: {r[3]:.1f}g | Fat: {r[4]:.1f}g | Carbs: {r[5]:.1f}g)*")
            grams = col_g.number_input("Portion (g)", min_value=10, max_value=2000, value=100, step=10, key=f"inp_{r[0]}")
            if col_add.button("Add", key=f"btn_{r[0]}"):
                full_row = client.execute("SELECT * FROM foods WHERE fdc_id = ?", [r[0]]).rows[0]
                col_names = [c[1] for c in client.execute("PRAGMA table_info(foods)").rows]
                item = dict(zip(col_names, full_row))
                item["grams"] = grams
                st.session_state.cart.append(item)
                st.rerun()
    else:
        st.info("No matching foods found.")

# Nutrition & Quality Analysis
if st.session_state.cart:
    st.divider()
    st.subheader("2. Selected Diet / Meal Items")
    
    cart_df = pd.DataFrame([{
        "Food Description": it["name"],
        "Portion (g)": it["grams"],
        "Calories (kcal)": round(it["calories"] * (it["grams"] / 100), 1),
        "Protein (g)": round(it["protein"] * (it["grams"] / 100), 1),
        "Fat (g)": round(it["fat"] * (it["grams"] / 100), 1),
        "Carbs (g)": round(it["carbs"] * (it["grams"] / 100), 1)
    } for it in st.session_state.cart])
    
    st.dataframe(cart_df, use_container_width=True)
    
    if st.button("🗑️ Clear Meal Plan"):
        st.session_state.cart = []
        st.rerun()

    # Totals
    total_grams = sum(it["grams"] for it in st.session_state.cart)
    total_cals = sum(it["calories"] * (it["grams"] / 100) for it in st.session_state.cart)
    total_protein = sum(it["protein"] * (it["grams"] / 100) for it in st.session_state.cart)
    total_fat = sum(it["fat"] * (it["grams"] / 100) for it in st.session_state.cart)
    total_carbs = sum(it["carbs"] * (it["grams"] / 100) for it in st.session_state.cart)
    total_fiber = sum(it["fiber"] * (it["grams"] / 100) for it in st.session_state.cart)

    # Essential Amino Acid Totals (mg)
    aa_totals_mg = {
        "Histidine": sum(it["histidine"] * 1000 * (it["grams"] / 100) for it in st.session_state.cart),
        "Isoleucine": sum(it["isoleucine"] * 1000 * (it["grams"] / 100) for it in st.session_state.cart),
        "Leucine": sum(it["leucine"] * 1000 * (it["grams"] / 100) for it in st.session_state.cart),
        "Lysine": sum(it["lysine"] * 1000 * (it["grams"] / 100) for it in st.session_state.cart),
        "Met + Cys": sum((it["methionine"] + it["cystine"]) * 1000 * (it["grams"] / 100) for it in st.session_state.cart),
        "Phe + Tyr": sum((it["phenylalanine"] + it["tyrosine"]) * 1000 * (it["grams"] / 100) for it in st.session_state.cart),
        "Threonine": sum(it["threonine"] * 1000 * (it["grams"] / 100) for it in st.session_state.cart),
        "Tryptophan": sum(it["tryptophan"] * 1000 * (it["grams"] / 100) for it in st.session_state.cart),
        "Valine": sum(it["valine"] * 1000 * (it["grams"] / 100) for it in st.session_state.cart)
    }

    # Amino Acid Score Calculation
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
    st.subheader("3. Protein Quality & Score Analysis")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Protein", f"{total_protein:.1f} g", f"Target: {target_protein_total:.1f} g")
    m2.metric("Meal PDCAAS", f"{pdcaas * 100:.0f}%", f"Raw Score: {min_score * 100:.0f}%")
    m3.metric("Limiting Amino Acid", limiting_aa)
    m4.metric("Usable (Net) Protein", f"{effective_protein:.1f} g")

    st.write("##### Amino Acid Profile relative to WHO Standard (100% = Requirement met per gram of protein):")
    score_display_df = pd.DataFrame({
        "Amino Acid": list(scores.keys()),
        "Score (%)": [v * 100 for v in scores.values()]
    }).set_index("Amino Acid")
    
    st.bar_chart(score_display_df)

    # Detailed Daily Requirements Breakdown
    with st.expander("📊 Detailed Amino Acid Breakdown (mg vs Daily RDA)"):
        detail_rows = []
        for aa in WHO_REFERENCE.keys():
            daily_req = WHO_DAILY_REQ_PER_KG[aa] * body_weight
            actual_mg = aa_totals_mg[aa]
            pct = (actual_mg / daily_req) * 100 if daily_req > 0 else 0
            detail_rows.append({
                "Amino Acid": aa,
                "Intake (mg)": f"{actual_mg:.0f}",
                "Daily Requirement (mg)": f"{daily_req:.0f}",
                "Requirement Fulfilled": f"{pct:.1f}%",
                "Profile Score": f"{scores.get(aa, 0)*100:.0f}%"
            })
        st.table(pd.DataFrame(detail_rows))

    # Micronutrients Breakdown
    with st.expander("💊 Key Micronutrients (Vitamins & Minerals)"):
        total_ca = sum(it.get("calcium", 0) * (it["grams"] / 100) for it in st.session_state.cart)
        total_fe = sum(it.get("iron", 0) * (it["grams"] / 100) for it in st.session_state.cart)
        total_mg = sum(it.get("magnesium", 0) * (it["grams"] / 100) for it in st.session_state.cart)
        total_k = sum(it.get("potassium", 0) * (it["grams"] / 100) for it in st.session_state.cart)
        total_zn = sum(it.get("zinc", 0) * (it["grams"] / 100) for it in st.session_state.cart)
        total_c = sum(it.get("vitamin_c", 0) * (it["grams"] / 100) for it in st.session_state.cart)
        total_b12 = sum(it.get("vitamin_b12", 0) * (it["grams"] / 100) for it in st.session_state.cart)

        col_min, col_vit = st.columns(2)
        with col_min:
            st.write("**Essential Minerals:**")
            st.write(f"- Calcium (Ca): {total_ca:.1f} mg")
            st.write(f"- Iron (Fe): {total_fe:.1f} mg")
            st.write(f"- Magnesium (Mg): {total_mg:.1f} mg")
            st.write(f"- Potassium (K): {total_k:.1f} mg")
            st.write(f"- Zinc (Zn): {total_zn:.1f} mg")
        with col_vit:
            st.write("**Vitamins & Fiber:**")
            st.write(f"- Vitamin C: {total_c:.1f} mg")
            st.write(f"- Vitamin B12: {total_b12:.2f} mcg")
            st.write(f"- Dietary Fiber: {total_fiber:.1f} g")

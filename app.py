import streamlit as st
import libsql_client
import pandas as pd

# Конфігурація сторінки
st.set_page_config(
    page_title="AminoCalc",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Адаптивний CSS: оптимізує відступи, шрифти та сенсорні зони для смартфонів
st.markdown("""
<style>
    @media (max-width: 768px) {
        .block-container {
            padding: 1.5rem 0.8rem !important;
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.4rem !important;
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

@st.cache_resource
def get_db():
    return libsql_client.create_client_sync(
        url=st.secrets["TURSO_DATABASE_URL"],
        auth_token=st.secrets["TURSO_READONLY_TOKEN"]
    )

client = get_db()

st.title("🥗 AminoCalc")
st.caption("Protein Quality, Amino Acid Score & PDCAAS (WHO/FAO/UNU 2007)")

# Налаштування профілю (зручно і на мобільному, і на ПК)
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

# 1. Пошук продуктів
st.subheader("1. Search & Add Food")
search_term = st.text_input("Search food item (e.g., egg, oats, salmon, chickpeas, chicken breast):", placeholder="Type food name...")

if search_term:
    query = """
    SELECT fdc_id, name, calories, protein, fat, carbs, fiber
    FROM foods 
    WHERE name LIKE ? 
    ORDER BY protein DESC 
    LIMIT 6
    """
    res = client.execute(query, [f"%{search_term}%"])
    
    if res.rows:
        for r in res.rows:
            fdc_id, name, kcal, prot, fat, carbs, fiber = r
            
            # Адаптивний контейнер: сам підлаштовує колонки під ширину пристрою
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
                        item = dict(zip(col_names, full_row))
                        item["grams"] = portion
                        st.session_state.cart.append(item)
                        st.toast(f"Added {portion}g of {name[:25]}...!")
                        st.rerun()
    else:
        st.info("No matching foods found.")

# 2. Обраний раціон та аналітика
if st.session_state.cart:
    st.divider()
    st.subheader(f"2. Your Meal Plan ({len(st.session_state.cart)} items)")
    
    # Список доданих продуктів із видаленням
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

    # Підсумок макросів
    total_grams = sum(it["grams"] for it in st.session_state.cart)
    total_cals = sum(it["calories"] * (it["grams"] / 100) for it in st.session_state.cart)
    total_protein = sum(it["protein"] * (it["grams"] / 100) for it in st.session_state.cart)
    total_fat = sum(it["fat"] * (it["grams"] / 100) for it in st.session_state.cart)
    total_carbs = sum(it["carbs"] * (it["grams"] / 100) for it in st.session_state.cart)
    total_fiber = sum(it["fiber"] * (it["grams"] / 100) for it in st.session_state.cart)

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

    # Метрики: на десктопі будуть 4 в ряд, на мобільному самі компактно розіб'ються на блоки
    m1, m2, m3, m4 = st.columns([1, 1, 1, 1])
    m1.metric("Total Protein", f"{total_protein:.1f} g", f"Target: {target_protein_total:.1f} g")
    m2.metric("PDCAAS Score", f"{pdcaas * 100:.0f}%", f"Raw: {min_score * 100:.0f}%")
    m3.metric("Limiting Amino Acid", limiting_aa)
    m4.metric("Usable (Net) Protein", f"{effective_protein:.1f} g")

    st.write("##### Amino Acid Profile (% of WHO Requirement):")
    score_df = pd.DataFrame({
        "Amino Acid": list(scores.keys()),
        "Score (%)": [v * 100 for v in scores.values()]
    }).set_index("Amino Acid")
    
    st.bar_chart(score_df)

    with st.expander("📊 Detailed Amino Acid Breakdown (mg vs Daily RDA)"):
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
                "Profile Score": f"{scores.get(aa, 0)*100:.0f}%"
            })
        st.dataframe(pd.DataFrame(detail_rows), use_container_width=True)

    with st.expander("💊 Key Micronutrients (Vitamins & Minerals)"):
        st.write(f"- **Calories:** {total_cals:.0f} kcal")
        st.write(f"- **Carbohydrates:** {total_carbs:.1f} g (Fiber: {total_fiber:.1f} g)")
        st.write(f"- **Fats:** {total_fat:.1f} g")
        st.write(f"- **Calcium:** {sum(it.get('calcium', 0) * (it['grams'] / 100) for it in st.session_state.cart):.0f} mg")
        st.write(f"- **Iron:** {sum(it.get('iron', 0) * (it['grams'] / 100) for it in st.session_state.cart):.1f} mg")
        st.write(f"- **Zinc:** {sum(it.get('zinc', 0) * (it['grams'] / 100) for it in st.session_state.cart):.1f} mg")
        st.write(f"- **Vitamin B12:** {sum(it.get('vitamin_b12', 0) * (it['grams'] / 100) for it in st.session_state.cart):.2f} mcg")

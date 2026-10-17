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

# Адаптивний CSS: темна/світла теми та оптимізація для смартфонів
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
""",
    unsafe_allow_html=True,
)

# Еталонний амінокислотний профіль ВООЗ/ФАО 2007 (мг на 1 г білка)
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

# Добова потреба на 1 кг маси тіла (мг/кг/день, WHO/FAO 2007)
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

# Орієнтовні добові норми мікронутрієнтів (RDA / DV)
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


# ---------------------------------------------------------
# 2. ПІДКЛЮЧЕННЯ ДО TURSO ТА КЕШУВАННЯ КАТАЛОГУ
# ---------------------------------------------------------
@st.cache_resource
def get_db():
  return libsql_client.create_client_sync(
      url=st.secrets["TURSO_DATABASE_URL"],
      auth_token=st.secrets["TURSO_READONLY_TOKEN"],
  )


client = get_db()


@st.cache_data(ttl=3600)
def load_food_catalog():
  # Завантажуємо 20 ключових колонок: метадані, макроси та 11 незамінних/спаринг АК
  res = client.execute("""
        SELECT fdc_id, name, calories, protein, fat, carbs, fiber,
               COALESCE(source_db, 'usda_sr_legacy') AS source_db,
               COALESCE(quality_grade, 'B') AS quality_grade,
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
# 3. ШАПКА ТА НАЛАШТУВАННЯ ПРОФІЛЮ КОРИСТУВАЧА
# ---------------------------------------------------------
st.title("🥗 AminoCalc")
st.caption(
    "Protein Quality, Amino Acid Score & Complete Micronutrient Profiler"
    " (WHO/FAO 2007) • 7 World Databases"
)

with st.expander("⚙️ Your Profile & Targets", expanded=False):
  col_w, col_p = st.columns(2)
  with col_w:
    body_weight = st.number_input(
        "Body Weight (kg)",
        min_value=30.0,
        max_value=200.0,
        value=75.0,
        step=0.5,
    )
  with col_p:
    protein_target_per_kg = st.number_input(
        "Target Protein (g/kg)",
        min_value=0.8,
        max_value=3.5,
        value=1.2,
        step=0.1,
    )

  target_protein_total = body_weight * protein_target_per_kg
  st.info(
      f"Daily Target: **{target_protein_total:.1f} g** ({protein_target_per_kg}"
      " g/kg)"
  )

if "cart" not in st.session_state:
  st.session_state.cart = []

# ---------------------------------------------------------
# 4. ФІЛЬТР НАДІЙНОСТІ ДАНИХ (DATA RELIABILITY)
# ---------------------------------------------------------
rel_col1, rel_col2 = st.columns([3, 2])

with rel_col1:
  selected_reliability = st.radio(
      "🔬 Data Reliability / Verification Level:",
      options=["all", "standard", "lab_only"],
      format_func=lambda x: {
          "all": (
              f"🌐 All Data (Lab + Standard + Estimated /"
              f" {len(foods_catalog):,} items)"
          ),
          "standard": (
              "🟡 Standard Reference & Lab (Grade A & B / Exclude pure recipes)"
          ),
          "lab_only": (
              "🟢 Lab Verified Only (Grade A: HPLC / ISO Direct Assays)"
          ),
      }[x],
      index=0,
      horizontal=False,
      help=(
          "Filter by scientific rigor: Grade A (Direct chromatography assays),"
          " Grade B (Standard reference tables), Grade C (Recipe/calculated"
          " estimates)."
      ),
  )

with rel_col2:
  if selected_reliability == "lab_only":
    st.info(
        "🔬 **Grade A**: Over 5,000 foods verified by direct HPLC assays (Frida"
        " DK, KFCT KR, MEXT JP, FAO, IFCT, USDA lab lots)."
    )
  elif selected_reliability == "standard":
    st.info(
        "📊 **Grade A & B**: Official reference tables + direct laboratory"
        " assays. Excludes pure commercial recipe estimates."
    )
  else:
    st.caption(
        f"ℹ️ **All Levels**: Complete worldwide coverage"
        f" ({len(foods_catalog):,} items) including prepared dishes and"
        " traditional bakery."
    )

# Фільтрація каталогу за грейдом
if selected_reliability == "lab_only":
  filtered_by_grade = [r for r in foods_catalog if r[8] == "A"]
elif selected_reliability == "standard":
  filtered_by_grade = [r for r in foods_catalog if r[8] in ("A", "B")]
else:
  filtered_by_grade = foods_catalog

# ---------------------------------------------------------
# 5. ДЖЕРЕЛО БАЗИ ТА ШВИДКИЙ ПОШУК ПРОДУКТУ
# ---------------------------------------------------------
st.subheader("1. Add Food Item")

# 7 світових джерел у базі Turso
db_choices = {
    "all": "🌐 All Sources (7 Databases)",
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

col_db, col_select = st.columns([1, 2])

with col_db:
  selected_db = st.selectbox(
      "Source DB:",
      options=list(db_choices.keys()),
      format_func=lambda x: db_choices[x],
  )

if selected_db == "all":
  active_catalog = filtered_by_grade
else:
  active_catalog = [r for r in filtered_by_grade if r[7] == selected_db]

# Формування списку автодоповнення
food_options = {}
for r in active_catalog:
  fdc_id, name, kcal, prot, fat, carbs, fiber, src_db, q_grade = r[:9]
  flag = flag_map.get(src_db, "📍")
  grade_badge = f"[{q_grade}]"
  label = f"{flag} {name} {grade_badge} ({kcal:.0f} kcal | P: {prot:.1f}g)"
  food_options[label] = r

with col_select:
  selected_food_label = st.selectbox(
      "Search food item:",
      options=[""] + list(food_options.keys()),
      index=0,
      placeholder=f"Type to filter among {len(active_catalog):,} available foods...",
  )

if selected_food_label and selected_food_label in food_options:
  selected_item = food_options[selected_food_label]
  fdc_id, name, kcal, prot, fat, carbs, fiber, src_db, q_grade = selected_item[
      :9
  ]

  with st.container(border=True):
    st.markdown(f"**{name}**")
    st.caption(
        f"Grade: **{q_grade}** | Source: **{src_db}** | Per 100g: **{kcal:.0f}"
        f" kcal** | P: **{prot:.1f}g** | F: **{fat:.1f}g** | C: **{carbs:.1f}g**"
    )

    c_portion, c_btn = st.columns([2, 1])
    with c_portion:
      portion = st.number_input(
          "Portion (g)",
          min_value=10,
          max_value=2000,
          value=100,
          step=10,
          key=f"inp_{fdc_id}",
      )
    with c_btn:
      st.write("")
      if st.button("➕ Add", key=f"btn_{fdc_id}", use_container_width=True):
        full_row = client.execute(
            "SELECT * FROM foods WHERE fdc_id = ?", [fdc_id]
        ).rows[0]
        col_names = [
            c[1] for c in client.execute("PRAGMA table_info(foods)").rows
        ]
        item_dict = dict(zip(col_names, full_row))
        item_dict["grams"] = portion
        st.session_state.cart.append(item_dict)
        st.toast(f"Added {portion}g of {name[:25]}...")
        st.rerun()

# ---------------------------------------------------------
# 6. ПОТОЧНИЙ РАЦІОН ТА БІОХІМІЧНІ РОЗРАХУНКИ
# ---------------------------------------------------------
if st.session_state.cart:
  st.divider()
  st.subheader(f"2. Current Meal Plan ({len(st.session_state.cart)})")

  item_to_remove = None
  for idx, it in enumerate(st.session_state.cart):
    c_it, c_del = st.columns([5, 1])
    with c_it:
      st.write(
          f"• **{it['name']}** — {it['grams']}g ({(it['protein'] * it['grams'] / 100):.1f}g"
          f" P) [{it.get('quality_grade', 'B')}]"
      )
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
    return sum(
        it.get(col, 0) * (it["grams"] / 100) for it in st.session_state.cart
    )

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
      "Met + Cys": (sum_nutrient("methionine") + sum_nutrient("cystine"))
      * 1000,
      "Phe + Tyr": (sum_nutrient("phenylalanine") + sum_nutrient("tyrosine"))
      * 1000,
      "Threonine": sum_nutrient("threonine") * 1000,
      "Tryptophan": sum_nutrient("tryptophan") * 1000,
      "Valine": sum_nutrient("valine") * 1000,
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
  # 7. МЕТРИКИ ТА ДЕФІЦИТНЕ ПОПЕРЕДЖЕННЯ
  # ---------------------------------------------------------
  st.divider()
  st.subheader("3. Protein Utilization")

  row1_c1, row1_c2 = st.columns(2)
  with row1_c1:
    st.metric(
        "Total Protein",
        f"{total_protein:.1f} g",
        f"Target: {target_protein_total:.1f} g",
    )
  with row1_c2:
    st.metric(
        "AAS Quality",
        f"{usable_ratio * 100:.0f}%",
        f"Limiting: {limiting_aa}",
        delta_color="normal" if usable_ratio >= 1.0 else "inverse",
    )

  row2_c1, row2_c2 = st.columns(2)
  with row2_c1:
    st.metric(
        "Net Usable",
        f"{building_protein:.1f} g",
        f"{usable_ratio * 100:.0f}% efficient",
    )
  with row2_c2:
    st.metric(
        "Oxidized / Fuel",
        f"{fuel_protein:.1f} g",
        f"{(1 - usable_ratio) * 100:.0f}% excess",
        delta_color="inverse",
    )

  if usable_ratio < 1.0:
    st.markdown(
        f"""
        <div style="background: rgba(239, 83, 80, 0.15); border-left: 4px solid #ef5350; padding: 12px 14px; border-radius: 6px; margin: 12px 0;">
            <b style="color: #ef5350; font-size: 1.0rem;">Deficit in {limiting_aa} ({min_score * 100:.0f}% of WHO target)</b><br>
            <span style="opacity: 0.9; font-size: 0.88rem;">
                Body protein synthesis is capped at <b>{min_score * 100:.0f}%</b> by Liebig's Law. 
                Remaining <b>{fuel_protein:.1f} g</b> of protein is oxidized for energy.
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ТОП-5 диверсифікованих джерел для ліквідації дефіциту
    with st.container(border=True):
      st.markdown(
          f"💡 **Top 5 Diverse Food Sources High in {limiting_aa} to Fix"
          " Deficit**"
      )
      st.caption("Pick from different food groups to balance your meal:")

      # Індекси АК у вибірці (з урахуванням додавання quality_grade на позицію [8])
      col_pos_map = {
          "Histidine": [9],
          "Isoleucine": [10],
          "Leucine": [11],
          "Lysine": [12],
          "Met + Cys": [13, 14],
          "Phe + Tyr": [15, 16],
          "Threonine": [17],
          "Tryptophan": [18],
          "Valine": [19],
      }
      indices = col_pos_map.get(limiting_aa, [12])

      def get_target_aa_amount(row):
        return sum(row[idx] or 0.0 for idx in indices)

      def get_food_category(n_str):
        n = n_str.lower()
        if any(
            k in n
            for k in [
                "soy",
                "tofu",
                "bean",
                "lentil",
                "chickpea",
                "pea",
                "edamame",
                "lupin",
                "tempeh",
                "miso",
            ]
        ):
          return "🌱 Legumes & Soy"
        elif any(
            k in n
            for k in [
                "fish",
                "salmon",
                "tuna",
                "cod",
                "shrimp",
                "crab",
                "mackerel",
                "sardine",
                "seafood",
                "algae",
            ]
        ):
          return "🐟 Fish & Seafood"
        elif any(
            k in n
            for k in [
                "milk",
                "cheese",
                "yogurt",
                "egg",
                "curd",
                "whey",
                "casein",
            ]
        ):
          return "🧀 Dairy & Eggs"
        elif any(
            k in n
            for k in [
                "chicken",
                "turkey",
                "beef",
                "pork",
                "meat",
                "lamb",
                "duck",
                "veal",
            ]
        ):
          return "🥩 Meat & Poultry"
        elif any(
            k in n
            for k in [
                "seed",
                "nut",
                "almond",
                "peanut",
                "walnut",
                "sesame",
                "chia",
                "cashew",
                "pumpkin",
            ]
        ):
          return "🥜 Seeds & Nuts"
        return "🌾 Grains & Other"

      sorted_candidates = sorted(
          active_catalog, key=get_target_aa_amount, reverse=True
      )

      diversified_picks = {}
      for item in sorted_candidates:
        cat = get_food_category(item[1])
        if cat not in diversified_picks and get_target_aa_amount(item) > 0:
          diversified_picks[cat] = item
        if len(diversified_picks) >= 5:
          break

      for cat_label, cand in diversified_picks.items():
        c_id, c_name, c_kcal, c_prot, c_fat, c_carbs, c_fib, c_src, c_gr = cand[
            :9
        ]
        aa_val_g = get_target_aa_amount(cand)

        rec_col1, rec_col2 = st.columns([4, 1])
        with rec_col1:
          st.write(f"**{cat_label}**: {c_name[:42]}")
          st.caption(
              f"⭐ **{aa_val_g:.2f}g {limiting_aa}** | {c_prot:.1f}g Protein |"
              f" {c_kcal:.0f} kcal (per 100g)"
          )
        with rec_col2:
          if st.button("➕ 100g", key=f"rec_add_{c_id}_{cat_label}"):
            full_row = client.execute(
                "SELECT * FROM foods WHERE fdc_id = ?", [c_id]
            ).rows[0]
            col_names = [
                c[1] for c in client.execute("PRAGMA table_info(foods)").rows
            ]
            item_dict = dict(zip(col_names, full_row))
            item_dict["grams"] = 100
            st.session_state.cart.append(item_dict)
            st.toast(f"Added 100g of {c_name[:20]}!")
            st.rerun()
  else:
    st.markdown(
        """
        <div style="background: rgba(76, 175, 80, 0.15); border-left: 4px solid #4caf50; padding: 12px 14px; border-radius: 6px; margin: 12px 0;">
            <b style="color: #4caf50; font-size: 1.0rem;">Complete Amino Acid Balance (100%+)</b><br>
            <span style="opacity: 0.9; font-size: 0.88rem;">All essential amino acids meet WHO standards. Full protein utilization achieved.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

  # ---------------------------------------------------------
  # 8. ВКЛАДКИ З АНАЛІТИКОЮ (AMINOS, MACROS, MINERALS, VITAMINS, FATS)
  # ---------------------------------------------------------
  tab_aa, tab_macros, tab_min, tab_vit, tab_fats = st.tabs(
      ["🥩 Aminos", "🍞 Macros", "⚡ Minerals", "💊 Vitamins", "🥑 Lipids"]
  )

  with tab_aa:
    st.markdown(
        f"##### Daily Amino Acid Targets (Tailored for **{body_weight:.1f} kg**"
        " Body Weight):"
    )

    aa_data = []
    for aa in WHO_REFERENCE.keys():
      daily_req_mg = WHO_DAILY_REQ_PER_KG[aa] * body_weight
      actual_mg = aa_totals_mg[aa]
      req_met_pct = (
          (actual_mg / daily_req_mg) * 100 if daily_req_mg > 0 else 0
      )
      score_pct = scores.get(aa, 0) * 100

      if aa == limiting_aa and min_score < 1.0:
        dot = "🔴"
      elif req_met_pct < 100.0 or score_pct < 100.0:
        dot = "🟡"
      else:
        dot = "🟢"

      aa_data.append({
          "": dot,
          "Amino Acid": aa,
          "Intake (g)": f"{actual_mg / 1000:.2f}g",
          "Daily Target (g)": f"{daily_req_mg / 1000:.2f}g",
          "Daily Met (%)": f"{req_met_pct:.0f}%",
          "Protein Quality Score": f"{score_pct:.0f}%",
      })

    st.dataframe(
        pd.DataFrame(aa_data),
        use_container_width=True,
        hide_index=True,
        column_config={
            "": st.column_config.TextColumn(width="small"),
            "Amino Acid": st.column_config.TextColumn(width="medium"),
            "Intake (g)": st.column_config.TextColumn(width="small"),
            "Daily Target (g)": st.column_config.TextColumn(width="medium"),
            "Daily Met (%)": st.column_config.TextColumn(width="small"),
            "Protein Quality Score": st.column_config.TextColumn(
                width="medium"
            ),
        },
    )

    st.caption("🔴 Limiting Deficit | 🟡 Suboptimal (<100%) | 🟢 Sufficient")

    st.write("##### Daily Requirement Coverage (% of target):")
    req_chart_df = pd.DataFrame({
        "Amino Acid": list(WHO_REFERENCE.keys()),
        "Coverage (%)": [
            (aa_totals_mg[aa] / (WHO_DAILY_REQ_PER_KG[aa] * body_weight)) * 100
            for aa in WHO_REFERENCE.keys()
        ],
    }).set_index("Amino Acid")
    st.bar_chart(req_chart_df)

  with tab_macros:
    mc1, mc2 = st.columns(2)
    with mc1:
      st.metric("Calories", f"{total_cals:.0f} kcal")
      st.metric("Total Fat", f"{total_fat:.1f} g")
    with mc2:
      st.metric("Carbohydrates", f"{total_carbs:.1f} g")
      st.metric(
          "Dietary Fiber",
          f"{total_fiber:.1f} g",
          f"{min(total_fiber / DAILY_VALUES['fiber'] * 100, 100):.0f}% RDA",
      )

  with tab_min:
    minerals_data = [
        ("Calcium", "calcium", "mg"),
        ("Iron", "iron", "mg"),
        ("Magnesium", "magnesium", "mg"),
        ("Phosphorus", "phosphorus", "mg"),
        ("Potassium", "potassium", "mg"),
        ("Sodium", "sodium", "mg"),
        ("Zinc", "zinc", "mg"),
        ("Copper", "copper", "mg"),
        ("Selenium", "selenium", "mcg"),
    ]
    m_rows = []
    for label, key, unit in minerals_data:
      val = sum_nutrient(key)
      target = DAILY_VALUES[key]
      pct = val / target * 100
      dot = "🟢" if pct >= 100 else ("🟡" if pct >= 70 else "🔴")
      m_rows.append({
          "": dot,
          "Mineral": label,
          "Intake": f"{val:.1f} {unit}",
          "Target": f"{target:.0f} {unit}",
          "Met": f"{pct:.0f}%",
      })
    st.dataframe(
        pd.DataFrame(m_rows), use_container_width=True, hide_index=True
    )

  with tab_vit:
    vitamins_data = [
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
    ]
    v_rows = []
    for label, key, unit in vitamins_data:
      val = sum_nutrient(key)
      target = DAILY_VALUES[key]
      pct = val / target * 100
      dot = "🟢" if pct >= 100 else ("🟡" if pct >= 70 else "🔴")
      v_rows.append({
          "": dot,
          "Vitamin": label,
          "Intake": f"{val:.1f} {unit}",
          "Target": f"{target:.0f} {unit}",
          "Met": f"{pct:.0f}%",
      })
    st.dataframe(
        pd.DataFrame(v_rows), use_container_width=True, hide_index=True
    )

  with tab_fats:
    sat = sum_nutrient("fat_saturated")
    mono = sum_nutrient("fat_monounsaturated")
    poly = sum_nutrient("fat_polyunsaturated")
    chol = sum_nutrient("cholesterol")

    st.write(f"- Saturated: **{sat:.1f} g**")
    st.write(f"- Monounsaturated: **{mono:.1f} g**")
    st.write(f"- Polyunsaturated: **{poly:.1f} g**")
    st.write(f"- Cholesterol: **{chol:.0f} mg**")

    if (sat + mono + poly) > 0:
      fat_df = pd.DataFrame({
          "Fat Type": ["SFA", "MUFA", "PUFA"],
          "Grams": [sat, mono, poly],
      }).set_index("Fat Type")
      st.bar_chart(fat_df)

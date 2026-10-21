"""
AminoCalc — Protein Quality, Amino Acid Score & Complete Micronutrient Profiler.
WHO/FAO/UNU 2007 reference standard • 7 integrated world databases.
"""

import html
import io
import json
import re
from xml.sax.saxutils import escape as xml_escape

import libsql_client
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from presets import PRESETS

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
AA_COLS = [c for cols in AA_GROUP_COLS.values() for c in cols]

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
LIMIT_NUTRIENTS = {"sodium"}


def fmt(value, nd=1, unit=""):
    return "—" if value is None else f"{value:.{nd}f}{unit}"


# ---------------------------------------------------------
# 1b. ЕКСПОРТ: ДРУК НА ОДИН АРКУШ A4 ТА PDF
# ---------------------------------------------------------
STATUS_LABELS = {"lim": "Limiting", "low": "Below 100%", "ok": "Sufficient"}


def aa_status(aa, req_met_pct, score_pct, limiting_aa, aas_ratio):
    """Та сама логіка кольорів, що й на вкладці «Aminos»."""
    if aa == limiting_aa and aas_ratio < 1.0:
        return "lim"
    if req_met_pct < 100.0 or score_pct < 100.0:
        return "low"
    return "ok"


def build_print_html(
    cart,
    aa_totals_mg,
    scores,
    limiting_aa,
    totals,
    weight_kg,
    target_protein,
    aas_ratio,
    weighted_dig,
    adjusted_ratio,
    auto_print=False,
):
    """Самодостатня HTML-сторінка формату A4. Якщо вміст вищий за аркуш,
    він автоматично масштабується, щоб усе вмістилося на одній сторінці."""
    e = html.escape

    food_rows = "".join(
        f"<tr><td>{e(str(it['name']))}</td>"
        f"<td class='n'>{it['grams']}</td>"
        f"<td class='n'>{(it.get('protein') or 0) * it['grams'] / 100:.1f}</td>"
        f"<td class='n'>{(it.get('calories') or 0) * it['grams'] / 100:.0f}</td>"
        f"<td class='n'>{it.get('dig', 1.0):.2f}</td></tr>"
        for it in cart
    )

    aa_rows = ""
    for aa in WHO_REFERENCE:
        daily_mg = WHO_DAILY_REQ_PER_KG[aa] * weight_kg
        actual = aa_totals_mg[aa]
        met = actual / daily_mg * 100 if daily_mg else 0
        score = scores.get(aa, 0) * 100
        status = aa_status(aa, met, score, limiting_aa, aas_ratio)
        aa_rows += (
            f"<tr class='r-{status}'><td>{e(aa)}</td>"
            f"<td class='n'>{actual:.0f}</td>"
            f"<td class='n'>{daily_mg:.0f}</td>"
            f"<td class='n'>{actual - daily_mg:+.0f}</td>"
            f"<td class='n'>{met:.0f}%</td>"
            f"<td class='n'>{score:.0f}%</td>"
            f"<td class='s-{status}'>{STATUS_LABELS[status]}</td></tr>"
        )

    total_grams = sum(it["grams"] for it in cart)
    auto = (
        "window.addEventListener('load', function(){"
        " setTimeout(function(){ window.print(); }, 300); });"
        if auto_print
        else ""
    )

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>AminoCalc — meal plan</title>
<style>
  @page {{ size: A4 portrait; margin: 10mm; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: Arial, sans-serif; color:#111; margin:0; font-size:11px; }}
  @media screen {{ body {{ margin:16px; }} }}
  #page {{ width:190mm; }}
  h1 {{ font-size:17px; margin:0 0 2px; }}
  h2 {{ font-size:12px; margin:10px 0 4px; border-bottom:1px solid #999; padding-bottom:2px; }}
  table {{ border-collapse:collapse; width:100%; }}
  th, td {{ border:1px solid #bbb; padding:2px 6px; text-align:left; }}
  th {{ background:#eee; }}
  td.n, th.n {{ text-align:right; }}
  tr.r-lim td {{ background:#fdeceb; font-weight:bold; }}
  tr.r-low td {{ background:#fff8e1; }}
  td.s-lim {{ background:#ef9a9a !important; font-weight:bold; }}
  td.s-low {{ background:#ffe082 !important; }}
  td.s-ok  {{ background:#a5d6a7 !important; }}
  .legend span {{ display:inline-block; padding:1px 8px; margin-right:8px; border:1px solid #999; }}
  .legend .l1 {{ background:#ef9a9a; }} .legend .l2 {{ background:#ffe082; }} .legend .l3 {{ background:#a5d6a7; }}
  .sum {{ display:flex; gap:18px; flex-wrap:wrap; margin:6px 0; }}
  .sum div b {{ display:block; font-size:13px; }}
  .foot {{ margin-top:10px; font-size:9px; color:#555; }}
  @media print {{
    * {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  }}
</style></head><body><div id="page">
<h1>AminoCalc — meal plan</h1>
<div>WHO/FAO/UNU 2007 adult pattern • body weight {weight_kg:.1f} kg •
protein target {target_protein:.1f} g</div>

<h2>Foods</h2>
<table><tr><th>Food</th><th class='n'>g</th><th class='n'>Protein, g</th>
<th class='n'>kcal</th><th class='n'>Digest.</th></tr>
{food_rows}
<tr><th>Total</th><th class='n'>{total_grams}</th>
<th class='n'>{totals['protein']:.1f}</th><th class='n'>{totals['cal']:.0f}</th><th></th></tr>
</table>

<div class="sum">
  <div>Amino acid score<b>{aas_ratio * 100:.0f}%</b></div>
  <div>Limiting AA<b>{e(limiting_aa)}</b></div>
  <div>Avg. digestibility<b>{weighted_dig * 100:.0f}%</b></div>
  <div>Digestibility-adjusted<b>{adjusted_ratio * 100:.0f}%</b></div>
  <div>Fat / Carbs / Fiber<b>{totals['fat']:.0f} / {totals['carbs']:.0f} / {totals['fiber']:.0f} g</b></div>
</div>

<h2>Essential amino acids</h2>
<table><tr><th>Amino acid</th><th class='n'>Intake, mg</th><th class='n'>Daily target, mg</th>
<th class='n'>Surplus / deficit, mg</th><th class='n'>Target met</th>
<th class='n'>Score vs pattern</th><th>Status</th></tr>
{aa_rows}</table>
<div class="legend" style="margin-top:6px">
  <span class="l1">Limiting</span><span class="l2">Below 100%</span><span class="l3">Sufficient</span>
</div>
<div style="font-size:9px;color:#444;margin-top:4px">
<b>Limiting</b> — lowest score vs the WHO pattern; it caps how much of the protein is fully used.
<b>Below 100%</b> — daily target or pattern not reached. <b>Sufficient</b> — both reached.
Target met = intake / daily target; score = amino acid per g protein / WHO pattern.
</div>

<div class="foot">Educational tool, not medical advice. Values come from open food
composition databases and may be incomplete or estimated.</div>
</div>
<script>
  function fit() {{
    var p = document.getElementById('page');
    p.style.zoom = 1;
    var maxH = 277 / 25.4 * 96;
    var h = p.offsetHeight;
    if (h > maxH) {{ p.style.zoom = (maxH / h) * 0.97; }}
  }}
  window.addEventListener('load', fit);
  window.addEventListener('beforeprint', fit);
  {auto}
</script>
</body></html>"""


_PUNCT_MAP = str.maketrans(
    {"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", "×": "x", "°": " deg"}
)


def pdf_name(name):
    """Назва продукту для PDF зі стандартним шрифтом (Latin-1).
    Дужки лише з не-латинським текстом (корейські/японські/китайські
    переклади назв) прибираються, решта не-Latin-1 символів відкидається,
    тож замість «???» виходить чиста англомовна назва."""
    s = str(name).translate(_PUNCT_MAP)
    prev = None
    while prev != s:
        prev = s
        s = re.sub(
            r"\([^()]*\)",
            lambda m: m.group(0) if re.search(r"[A-Za-z]", m.group(0)) else "",
            s,
        )
    s = s.encode("latin-1", "ignore").decode("latin-1")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+([,;)\]])", r"\1", s)
    s = re.sub(r"([(\[])\s+", r"\1", s)
    s = re.sub(r"(,\s*)+$", "", s).strip()
    return s or "(name not printable)"


def build_pdf_bytes(
    cart,
    aa_totals_mg,
    scores,
    limiting_aa,
    totals,
    weight_kg,
    target_protein,
    aas_ratio,
    weighted_dig,
    adjusted_ratio,
):
    """PDF формату A4 на одну сторінку (вміст стискається, якщо не влазить)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        KeepInFrame,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    def t(s):
        # Стандартні шрифти PDF знають лише latin-1
        return str(s).encode("latin-1", "replace").decode("latin-1")

    styles = getSampleStyleSheet()
    h1, h2, small = styles["Title"], styles["Heading3"], styles["BodyText"]
    h1.fontSize, h1.alignment = 16, 0
    small.fontSize = 8
    from reportlab.lib.styles import ParagraphStyle

    cell = ParagraphStyle("cell", parent=small, fontSize=8, leading=9.5)

    def make_table(data, col_w, row_colors=None, cell_colors=None, text_left_cols=(0,)):
        tbl = Table(data, colWidths=[w * mm for w in col_w], repeatRows=1)
        style = [
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]
        for col in text_left_cols:
            style.append(("ALIGN", (col, 0), (col, -1), "LEFT"))
        for row_i, (bg, bold) in (row_colors or {}).items():
            if bg:
                style.append(("BACKGROUND", (0, row_i), (-1, row_i), colors.HexColor(bg)))
            if bold:
                style.append(("FONTNAME", (0, row_i), (-1, row_i), "Helvetica-Bold"))
        for (col_i, row_i), bg in (cell_colors or {}).items():
            style.append(("BACKGROUND", (col_i, row_i), (col_i, row_i), colors.HexColor(bg)))
        tbl.setStyle(TableStyle(style))
        return tbl

    foods = [["Food", "g", "Protein, g", "kcal", "Digest."]]
    for it in cart:
        foods.append(
            [
                Paragraph(xml_escape(pdf_name(it["name"])), cell),
                it["grams"],
                f"{(it.get('protein') or 0) * it['grams'] / 100:.1f}",
                f"{(it.get('calories') or 0) * it['grams'] / 100:.0f}",
                f"{it.get('dig', 1.0):.2f}",
            ]
        )
    foods.append(
        [
            "Total",
            sum(it["grams"] for it in cart),
            f"{totals['protein']:.1f}",
            f"{totals['cal']:.0f}",
            "",
        ]
    )

    aa_rows = [
        [
            "Amino acid",
            "Intake, mg",
            "Daily target, mg",
            "Surplus/deficit, mg",
            "Target met",
            "Score vs pattern",
            "Status",
        ]
    ]
    row_colors, cell_colors = {}, {}
    row_palette = {"lim": ("#fdeceb", True), "low": ("#fff8e1", False), "ok": (None, False)}
    cell_palette = {"lim": "#ef9a9a", "low": "#ffe082", "ok": "#a5d6a7"}
    for i, aa in enumerate(WHO_REFERENCE, start=1):
        daily = WHO_DAILY_REQ_PER_KG[aa] * weight_kg
        actual = aa_totals_mg[aa]
        met = actual / daily * 100 if daily else 0
        score = scores.get(aa, 0) * 100
        status = aa_status(aa, met, score, limiting_aa, aas_ratio)
        aa_rows.append(
            [
                t(aa),
                f"{actual:.0f}",
                f"{daily:.0f}",
                f"{actual - daily:+.0f}",
                f"{met:.0f}%" if daily else "-",
                f"{score:.0f}%",
                STATUS_LABELS[status],
            ]
        )
        row_colors[i] = row_palette[status]
        cell_colors[(6, i)] = cell_palette[status]

    story = [
        Paragraph("AminoCalc - meal plan", h1),
        Paragraph(
            f"WHO/FAO/UNU 2007 adult pattern | body weight {weight_kg:.1f} kg | "
            f"protein target {target_protein:.1f} g",
            small,
        ),
        Spacer(1, 4),
        Paragraph("Foods", h2),
        make_table(foods, [100, 18, 24, 20, 20]),
        Spacer(1, 6),
        Paragraph(
            f"<b>Amino acid score:</b> {aas_ratio * 100:.0f}% &nbsp; "
            f"<b>Limiting:</b> {t(limiting_aa)} &nbsp; "
            f"<b>Avg. digestibility:</b> {weighted_dig * 100:.0f}% &nbsp; "
            f"<b>Digestibility-adjusted:</b> {adjusted_ratio * 100:.0f}%",
            small,
        ),
        Paragraph(
            f"<b>Fat / Carbs / Fiber:</b> {totals['fat']:.0f} / {totals['carbs']:.0f} / "
            f"{totals['fiber']:.0f} g",
            small,
        ),
        Paragraph("Essential amino acids", h2),
        make_table(
            aa_rows,
            [27, 22, 27, 30, 22, 28, 28],
            row_colors,
            cell_colors,
            text_left_cols=(0, 6),
        ),
        Spacer(1, 4),
        Paragraph(
            '<font backColor="#ef9a9a">&nbsp;Limiting&nbsp;</font> &nbsp; '
            '<font backColor="#ffe082">&nbsp;Below 100%&nbsp;</font> &nbsp; '
            '<font backColor="#a5d6a7">&nbsp;Sufficient&nbsp;</font>',
            small,
        ),
        Spacer(1, 3),
        Paragraph(
            "<b>Limiting</b> - lowest score vs the WHO pattern; it caps how much of the "
            "protein is fully used. <b>Below 100%</b> - daily target or pattern not "
            "reached. <b>Sufficient</b> - both reached. Target met = intake / daily "
            "target; score = amino acid per g protein / WHO pattern.",
            small,
        ),
        Spacer(1, 8),
        Paragraph(
            "Educational tool, not medical advice. Values come from open food "
            "composition databases and may be incomplete or estimated.",
            small,
        ),
    ]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title="AminoCalc meal plan",
    )
    # KeepInFrame(shrink) гарантує одну сторінку
    doc.build([KeepInFrame(doc.width, doc.height, story, mode="shrink")])
    return buf.getvalue()


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
    res = get_db().execute(sql, params or [])
    return [dict(zip(res.columns, row)) for row in res.rows]


def is_complete(row):
    if not (row.get("protein") or 0) > 0:
        return False
    return any((row.get(c) or 0) > 0 for c in AA_COLS)


@st.cache_data(ttl=3600)
def load_food_catalog():
    rows = db_rows(
        """
        SELECT fdc_id, name, calories, protein, fat, carbs, fiber,
               COALESCE(source_db, 'unknown') AS source_db,
               COALESCE(quality_grade, 'unknown') AS quality_grade,
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


def fetch_items_by_ids(ids):
    ids = list(ids)
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = db_rows(f"SELECT * FROM foods WHERE fdc_id IN ({placeholders})", ids)
    return {r["fdc_id"]: r for r in rows}


def make_cart_item(item, grams):
    """Готує елемент кошика. uid потрібен, щоб ключі віджетів не збивалися
    після видалення чи заміни продуктів."""
    st.session_state.uid_counter = st.session_state.get("uid_counter", 0) + 1
    item["grams"] = grams
    item["dig"] = float(item.get("digestibility") or 1.0)
    item["uid"] = st.session_state.uid_counter
    return item


@st.cache_data(ttl=3600)
def resolve_food_query(query):
    """Шаблоны могут ссылаться на продукт по тексту вместо fdc_id.
    'kidney beans cooked boiled -canned' -> fdc_id лучшего совпадения или None.
    Слова без минуса должны встречаться в названии, со знаком «-» — нет.
    Приоритет: есть данные по лизину -> USDA SR Legacy -> грейд A/B -> короткое имя."""
    words = [re.sub(r"[^\w\-]", "", w.lower()) for w in query.split()]
    inc = [w for w in words if w and not w.startswith("-")]
    exc = [w[1:] for w in words if w.startswith("-") and len(w) > 1]
    if not inc:
        return None
    where = ["LOWER(name) LIKE ?"] * len(inc) + ["LOWER(name) NOT LIKE ?"] * len(exc)
    params = [f"%{w}%" for w in inc + exc]
    rows = db_rows(
        f"""
        SELECT fdc_id FROM foods
        WHERE {" AND ".join(where)}
        ORDER BY
          CASE WHEN lysine IS NOT NULL AND lysine > 0 THEN 0 ELSE 1 END,
          CASE source_db WHEN 'usda_sr_legacy' THEN 0 ELSE 1 END,
          CASE quality_grade WHEN 'A' THEN 0 WHEN 'B' THEN 1 ELSE 2 END,
          LENGTH(name)
        LIMIT 1
        """,
        params,
    )
    return rows[0]["fdc_id"] if rows else None


def load_preset(key, servings=1.0, replace=True):
    """Загружает шаблон в корзину. Элемент шаблона — (fdc_id ИЛИ текстовый запрос,
    граммы, подпись). Возвращает подписи продуктов, которых нет в базе."""
    resolved = []
    for ref, grams, label in PRESETS[key]["items"]:
        fdc_id = resolve_food_query(ref) if isinstance(ref, str) else ref
        resolved.append((fdc_id, grams, label))
    found = fetch_items_by_ids([i for i, _, _ in resolved if i is not None])
    new_items, missing = [], []
    for fdc_id, grams, label in resolved:
        row = found.get(fdc_id) if fdc_id is not None else None
        if row is None:
            missing.append(label)
        else:
            new_items.append(make_cart_item(dict(row), max(1, round(grams * servings))))
    if replace:
        st.session_state.cart = new_items
    else:
        st.session_state.cart.extend(new_items)
    return missing


try:
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
    " pattern (>18 y) • 7 open food composition databases"
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
# 4. ФІЛЬТР ГРЕЙДУ
# ---------------------------------------------------------
RELIABILITY_LABELS = {
    "all": f"🌐 All grades ({len(foods_catalog):,} items)",
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
    f"Showing foods with verified amino acid data: {len(foods_catalog):,} of"
    f" {catalog_total:,} records."
)

if selected_reliability == "lab_only":
    filtered_by_grade = [r for r in foods_catalog if r["quality_grade"] == "A"]
elif selected_reliability == "standard":
    filtered_by_grade = [r for r in foods_catalog if r["quality_grade"] in ("A", "B")]
else:
    filtered_by_grade = foods_catalog

# ---------------------------------------------------------
# 5. ВИБІР БАЗИ ТА ПОШУК
# ---------------------------------------------------------
st.subheader("1. Add Food Item")

with st.expander("📋 Sample meals (templates)", expanded=False):
    preset_key = st.selectbox(
        "Template:",
        options=list(PRESETS.keys()),
        format_func=lambda k: PRESETS[k]["title"],
        key="preset_choice",
    )
    preset = PRESETS[preset_key]
    st.caption(preset["note"])
    st.caption(" • ".join(f"{label} {grams} g" for _, grams, label in preset["items"]))
    servings = st.number_input(
        "Servings", min_value=0.5, max_value=5.0, value=1.0, step=0.5, key="preset_servings"
    )
    pc1, pc2 = st.columns(2)
    with pc1:
        if st.button("Load (replace plan)", key="preset_load", use_container_width=True):
            st.session_state.preset_missing = load_preset(preset_key, servings, replace=True)
            st.rerun()
    with pc2:
        if st.button("Add to plan", key="preset_add", use_container_width=True):
            st.session_state.preset_missing = load_preset(preset_key, servings, replace=False)
            st.rerun()

_missing = st.session_state.pop("preset_missing", None)
if _missing:
    st.warning("Not found in the database: " + ", ".join(_missing))

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
by_id = {r["fdc_id"]: r for r in matches}


def food_label(fdc_id):
    r = by_id[fdc_id]
    return (
        f"{flag_map.get(r['source_db'], '📍')} {r['name']} [{r['quality_grade']}]"
        f" ({fmt(r['calories'], 0)} kcal | P: {fmt(r['protein'])}g)"
    )


def add_to_cart(fdc_id, grams):
    item = fetch_full_item(fdc_id)
    if item is None:
        st.warning("Food not found in the database.")
        return
    st.session_state.cart.append(make_cart_item(item, grams))
    st.toast(f"Added {grams}g of {item['name'][:25]}...")
    st.rerun()


if terms and not matches:
    st.caption("No foods match this search (or they lack complete amino acid data).")
elif matches:
    selected_id = st.selectbox(
        "Results (showing up to 50):",
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
                portion = st.number_input(
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
        with c_dig:
            it["dig"] = st.number_input(
                "Digestibility",
                min_value=0.3,
                max_value=1.0,
                value=float(it.get("dig", 1.0)),
                step=0.01,
                key=f"dig_{it.get('uid', idx)}",
                help="1.00 = no correction (also used when the database has no value).",
            )
        with c_del:
            if st.button("✕", key=f"del_{it.get('uid', idx)}", help="Remove"):
                item_to_remove = idx

    if item_to_remove is not None:
        cart.pop(item_to_remove)
        st.rerun()

    if st.button("🗑️ Clear Plan", use_container_width=True):
        st.session_state.cart = []
        st.rerun()

    def sum_nutrient(col):
        return sum((it.get(col) or 0.0) * it["grams"] / 100 for it in cart)

    def coverage(col):
        return sum(1 for it in cart if (it.get(col) or 0.0) > 0), len(cart)

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
    est_fuel = total_protein - est_usable

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

    # ---------------------------------------------------------
    # 7b. ДРУК (A4, 1 аркуш) ТА PDF
    # ---------------------------------------------------------
    export_totals = {
        "protein": total_protein,
        "cal": total_cals,
        "fat": total_fat,
        "carbs": total_carbs,
        "fiber": total_fiber,
    }
    export_args = (
        cart,
        aa_totals_mg,
        scores,
        limiting_aa,
        export_totals,
        body_weight,
        target_protein_total,
        aas_ratio,
        weighted_dig,
        adjusted_ratio,
    )

    print_html = build_print_html(*export_args, auto_print=True)
    # "</" всередині <script> закрив би тег — екрануємо
    print_js = json.dumps(print_html).replace("</", "<\\/")

    pr1, pr2 = st.columns(2)
    with pr1:
        components.html(
            f"""
            <button id="p" style="width:100%;padding:8px;border-radius:6px;
              border:1px solid #888;background:transparent;color:inherit;
              font-size:14px;cursor:pointer;">🖨️ Print (A4, 1 page)</button>
            <script>
              const doc = {print_js};
              document.getElementById('p').onclick = function() {{
                const w = window.open('', '_blank');
                if (!w) {{ alert('Pop-up blocked — use the PDF button.'); return; }}
                w.document.open();
                w.document.write(doc);
                w.document.close();
              }};
            </script>
            """,
            height=48,
        )
    with pr2:
        try:
            pdf_bytes = build_pdf_bytes(*export_args)
            st.download_button(
                "📄 Download PDF (A4)",
                data=pdf_bytes,
                file_name="aminocalc_meal_plan.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as exc:  # noqa: BLE001
            st.caption(f"PDF unavailable: {exc}")

    if total_protein <= 0:
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
            prot = row.get("protein") or 0
            if prot <= 0:
                return 0.0
            return sum(row.get(c) or 0.0 for c in target_cols) * 1000 / prot

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
    # 8. ВКЛАДКИ З АНАЛІТИКОЮ ТА ЛОКАЛЬНИМИ ЗАСТЕРЕЖЕННЯМИ
    # ---------------------------------------------------------
    tab_aa, tab_macros, tab_min, tab_vit, tab_fats = st.tabs(
        ["🥩 Aminos", "🍞 Macros", "⚡ Minerals", "💊 Vitamins", "🥑 Lipids"]
    )

    def value_with_coverage(col, nd=1, unit=""):
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
        # Локальна примітка (Варіант 2)
        st.caption(
            "ℹ️ **Note on minerals:** Secondary metrics. National databases vary in"
            " testing breadth (e.g. German BLS omits Selenium). 'No data' means no"
            " laboratory assay was performed in that country's database, not a dietary"
            " deficiency."
        )
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
        # Локальна примітка (Варіант 2)
        st.caption(
            "ℹ️ **Note on vitamins:** Secondary metrics. Testing coverage differs"
            " across national tables. Amino acid analysis is 100% complete across all"
            " foods, while missing vitamins default to unmeasured ('no data')."
        )
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
st.caption(
    "Educational tool, not medical advice. Values come from open food composition"
    " databases and may be incomplete or estimated."
)

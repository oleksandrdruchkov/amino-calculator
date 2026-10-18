# 🥗 AminoCalc — Protein Quality & Micronutrient Profiler

**AminoCalc** is a high-precision nutritional analytics engine and interactive web application built with **Streamlit** and **Turso (distributed libSQL/SQLite)**[cite: 1]. 

Unlike traditional macro counters that treat all protein as equal, AminoCalc evaluates biological protein quality using the official **WHO/FAO/UNU 2007** reference pattern[cite: 1]. It computes the exact **Amino Acid Score (AAS)**, accounts for **individual food digestibility**, estimates **net usable building protein**, and tracks a complete spectrum of micronutrients across 7 global food composition databases[cite: 1].

---

## 🚀 Key Features & Calculations

### 1. Protein Quality & Amino Acid Scoring (AAS & Digestibility)
* **Complete EAA Matrix:** Computes intake for all 9 essential amino acid groups: Histidine, Isoleucine, Leucine, Lysine, Threonine, Tryptophan, Valine, alongside composite sparing pairs: Methionine + Cystine, and Phenylalanine + Tyrosine.
* **WHO/FAO/UNU 2007 Standard:** Benchmarks amino acid concentrations (mg per 1 g of total protein) against the international adult reference pattern[cite: 1].
* **Liebig’s Law of the Minimum:** Automatically detects the **Limiting Amino Acid** capping total protein utilization[cite: 1].
* **Digestibility-Adjusted Usable Protein:** 
  * Allows assigning individual digestibility coefficients (0.30–1.00) to each food item.
  * Calculates protein-weighted average digestibility for the entire meal plan.
  * Provides an optional toggle to adjust net usable building protein vs. modeled oxidized fuel (energy overflow) based on AAS and true digestibility[cite: 1].

### 2. Tailored Daily Requirements
* Dynamically calculates total daily protein and milligram-level amino acid targets based on the user's **body weight (kg)** and **protein target (g/kg)**[cite: 1].
* Visualizes progress through interactive requirement fulfillment bars and color-coded status badges (🔴 Limiting/Deficit, 🟡 Below 100%, 🟢 Sufficient)[cite: 1].

### 3. Smart Deficit Balancing (Category-Diversified Recommendations)
* When a limiting amino acid deficit occurs ($AAS < 100\%$), the engine scans verified records in the active catalog and identifies top foods richest in that specific amino acid (ranked by **mg of amino acid per 1 g of protein**).
* Uses word-boundary regex categorization to pick diverse options across 5 distinct food groups:
  * 🌱 Legumes & Soy
  * 🐟 Fish & Seafood
  * 🧀 Dairy & Eggs
  * 🥩 Meat & Poultry
  * 🥜 Seeds & Nuts
* Enforces biological sanity checks (minimum 5 g protein per 100 g; cuts off lab outliers above $3\times$ reference standard).

### 4. Sample Meal Plans & Template System
* Integrated preset engine (`presets.py`) allowing one-click loading or appending of multi-component daily templates.
* Configurable serving multipliers with missing ingredient detection if an item is not present in the active local/remote slice.

### 5. Data Completeness & Secondary Nutrient Tracking
* Tracks **20+ macro- and micronutrients** grouped into clean analytics tabs:
  * **Macros & Fiber:** Calories, Total Protein, Fat, Carbohydrates, Dietary Fiber (against RDA).
  * **Minerals:** Calcium, Iron, Magnesium, Phosphorus, Potassium, Sodium, Zinc, Copper, Selenium.
  * **Vitamins:** Vitamin C, Thiamin (B1), Riboflavin (B2), Niacin (B3), Vitamin B6, Folate (B9), Vitamin B12, Vitamin A (RAE), Vitamin E, Vitamin D, Vitamin K.
  * **Lipid Profile:** Saturated, Monounsaturated, and Polyunsaturated Fatty Acids + Dietary Cholesterol.
* **Assay-Aware Reporting:** Differentiates between actual zero-content and unmeasured nutrients. Items lacking lab assays display `no data`, while partial plan coverage is flagged with an asterisk (`*`) to prevent false dietary deficiency warnings[cite: 1].
* **Upper Limit Handling:** Nutrients like **Sodium** are tracked as upper intake thresholds rather than targets (flags red when exceeded).

---

## 🗄️ Integrated Databases & Scientific Rigor

AminoCalc unifies data across 7 verified open food composition tables, strictly filtering out entries with incomplete amino acid assays[cite: 1]:

| Source Flag | Database Name | Origin | Regional Focus / Strengths |
| :---: | :--- | :---: | :--- |
| 🇩🇪 | **BLS 4.0** (Bundeslebensmittelschlüssel) | Germany | European grains, rye bakery, dairy products[cite: 1] |
| 🇺🇸 | **USDA SR Legacy** | United States | Core reference baseline for raw and processed foods[cite: 1] |
| 🇰🇷 | **KFCT 10.4** | South Korea | Fermented soy foods, algae, East Asian seafood[cite: 1] |
| 🇯🇵 | **MEXT 2023** | Japan | Traditional Japanese fish varieties, sea vegetables[cite: 1] |
| 🇩🇰 | **Frida 5.5** | Denmark | Scandinavian produce, rigorous HPLC assays[cite: 1] |
| 🇮🇳 | **IFCT 2017** | India | Millets, pulses, spices, tropical plant foods[cite: 1] |
| 🌐 | **FAO uPulses 1.0** | UN FAO | Global reference standard for legumes and pulses[cite: 1] |

### Verification Levels (Quality Grades)
* **🟢 Grade A (Lab Only):** Analytical measurements strictly derived from direct chromatographic assays (HPLC / ISO-compliant methods).
* **🟡 Grade A & B (Standard):** Combines direct lab assays with official national reference tables, excluding commercial calculated estimates.
* **🌐 All Grades:** Complete catalog including estimated or imputed preparations.

---

## 🛠️ Architecture & Tech Stack

* **UI & Core Logic:** [Streamlit](https://streamlit.io/) with adaptive mobile-first styling and dynamic session state management

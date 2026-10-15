# ---------------------------------------------------------
        # TOP 5 DIVERSIFIED FOOD RECOMMENDATIONS TO FIX DEFICIT
        # ---------------------------------------------------------
        with st.container(border=True):
            st.markdown(f"💡 **Top 5 Diverse Food Sources High in {limiting_aa}**")
            st.caption(f"Pick from different food groups to balance your meal:")

            # Map amino acid to relevant column indices in catalog
            col_pos_map = {
                "Histidine": [8],
                "Isoleucine": [9],
                "Leucine": [10],
                "Lysine": [11],
                "Met + Cys": [12, 13],
                "Phe + Tyr": [14, 15],
                "Threonine": [16],
                "Tryptophan": [17],
                "Valine": [18]
            }
            indices = col_pos_map.get(limiting_aa, [11])

            def get_target_aa_amount(row):
                return sum(row[idx] or 0.0 for idx in indices)

            # Heuristic food grouping logic
            def get_food_category(name):
                n = name.lower()
                if any(k in n for k in ["soy", "tofu", "bean", "lentil", "chickpea", "pea", "edamame", "lupin", "tempeh", "miso"]):
                    return "🌱 Legumes & Soy"
                elif any(k in n for k in ["fish", "salmon", "tuna", "cod", "shrimp", "crab", "mackerel", "sardine", "seafood"]):
                    return "🐟 Fish & Seafood"
                elif any(k in n for k in ["milk", "cheese", "yogurt", "egg", "curd", "whey", "casein"]):
                    return "🧀 Dairy & Eggs"
                elif any(k in n for k in ["chicken", "turkey", "beef", "pork", "meat", "lamb", "duck", "veal"]):
                    return "🥩 Meat & Poultry"
                elif any(k in n for k in ["seed", "nut", "almond", "peanut", "walnut", "sesame", "chia", "cashew", "pumpkin"]):
                    return "🥜 Seeds & Nuts"
                return "🌾 Other Sources"

            # Sort catalog by target amino acid density
            sorted_candidates = sorted(active_catalog, key=get_target_aa_amount, reverse=True)

            # Pick the #1 champion from each food group to ensure variety
            diversified_picks = {}
            for item in sorted_candidates:
                cat = get_food_category(item[1])
                # Skip raw flours/powders or non-edible fractions if needed
                if cat not in diversified_picks and get_target_aa_amount(item) > 0:
                    diversified_picks[cat] = item
                if len(diversified_picks) >= 5:
                    break

            # Render diversified list
            for cat_label, cand in diversified_picks.items():
                c_id, c_name, c_kcal, c_prot, c_fat, c_carbs, c_fib, c_src = cand[:8]
                aa_val_g = get_target_aa_amount(cand)
                
                rec_col1, rec_col2 = st.columns([4, 1])
                with rec_col1:
                    st.write(f"**{cat_label}**: {c_name[:40]}")
                    st.caption(f"⭐ **{aa_val_g:.2f}g {limiting_aa}** | {c_prot:.1f}g Protein | {c_kcal:.0f} kcal (per 100g)")
                with rec_col2:
                    if st.button("➕ 100g", key=f"rec_add_{c_id}_{cat_label}"):
                        full_row = client.execute("SELECT * FROM foods WHERE fdc_id = ?", [c_id]).rows[0]
                        col_names = [c[1] for c in client.execute("PRAGMA table_info(foods)").rows]
                        item_dict = dict(zip(col_names, full_row))
                        item_dict["grams"] = 100
                        st.session_state.cart.append(item_dict)
                        st.toast(f"Added 100g of {c_name[:20]}!")
                        st.rerun()

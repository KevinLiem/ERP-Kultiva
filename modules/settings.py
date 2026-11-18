import streamlit as st
import pandas as pd
from modules.db import (
    db_query, db_execute, get_uoms
)

def render_settings():
    st.title("⚙️ Units of Measure & Conversions")
    st.markdown("""
    <div style="background:#e8f5e9;border-left:4px solid #4caf50;padding:12px;border-radius:6px;margin-bottom:12px">
    <b>Master Settings — Kultiva ERP Database</b><br>
    Configure and customize measurement units, factor ratios, and active conversions directly in your independent database.
    </div>""", unsafe_allow_html=True)

    tab_view, tab_edit, tab_conv = st.tabs([
        "📋 View All UoMs", "✏️ Edit / Register UoM", "🔄 Conversion Calculator"
    ])

    # ── VIEW ──────────────────────────────────────────────────────────────
    with tab_view:
        uoms = db_query("SELECT * FROM uoms ORDER BY id ASC")
        if uoms:
            df = pd.DataFrame(uoms)
            c1, c2 = st.columns(2)
            c1.metric("Total UoMs Configured", len(df))
            c2.metric("Active Units", len(df[df["active"] == 1]))

            disp = df[["name", "category", "uom_type", "factor", "rounding", "active"]].copy()
            disp.columns = ["Unit Name", "Category", "Type", "Conversion Factor", "Precision", "Active"]
            disp["Active"] = disp["Active"].apply(lambda x: "✅ Active" if x == 1 else "❌ Inactive")
            st.dataframe(disp, use_container_width=True, hide_index=True)

    # ── EDIT / CREATE ─────────────────────────────────────────────────────
    with tab_edit:
        st.markdown('<div class="section-header">✏️ Edit Existing UoM</div>', unsafe_allow_html=True)
        uoms = db_query("SELECT * FROM uoms ORDER BY name ASC")
        if uoms:
            uom_opts = {u["name"]: u for u in uoms}
            sel_uom_name = st.selectbox("Select Unit to Modify", ["-- Select --"] + list(uom_opts.keys()))
            if sel_uom_name != "-- Select --":
                sel_uom = uom_opts[sel_uom_name]
                c1, c2, c3 = st.columns(3)
                new_name = c1.text_input("Unit Name", value=sel_uom["name"], key="edit_uom_name")
                new_cat  = c2.text_input("Category", value=sel_uom["category"] or "General", key="edit_uom_cat")
                new_type = c3.selectbox("Type", ["reference", "bigger", "smaller", "relative"],
                    index=["reference", "bigger", "smaller", "relative"].index(sel_uom["uom_type"]) if sel_uom["uom_type"] in ["reference", "bigger", "smaller", "relative"] else 0)

                col_f1, col_f2, col_f3 = st.columns(3)
                new_factor = col_f1.number_input("Factor vs Base Reference", value=float(sel_uom["factor"]), min_value=0.000001, step=0.001)
                new_round = col_f2.number_input("Rounding Precision", value=float(sel_uom["rounding"]), min_value=0.000001, step=0.01)
                new_active = col_f3.checkbox("Is Active", value=bool(sel_uom["active"]))

                if st.button("💾 Save Changes to UoM", type="primary"):
                    db_execute("""
                        UPDATE uoms SET name = ?, category = ?, uom_type = ?, factor = ?, rounding = ?, active = ?
                        WHERE id = ?
                    """, (new_name, new_cat, new_type, new_factor, new_round, 1 if new_active else 0, sel_uom["id"]))
                    st.success(f"✅ UoM '{new_name}' updated in Kultiva DB!")
                    st.rerun()

        st.markdown('<div class="section-header">➕ Register New UoM</div>', unsafe_allow_html=True)
        with st.expander("Register New Unit"):
            nc1, nc2, nc3 = st.columns(3)
            n_name = nc1.text_input("Unit Name (e.g. Karton, Pcs, Dus) *", key="n_uom_name")
            n_cat  = nc2.text_input("Category (e.g. Weight, Unit, Volume)", value="Unit", key="n_uom_cat")
            n_type = nc3.selectbox("Type", ["reference", "bigger", "smaller", "relative"], key="n_uom_type")
            nf1, nf2 = st.columns(2)
            n_factor = nf1.number_input("Factor vs Base Reference", value=1.0, min_value=0.000001, step=0.001, key="n_uom_factor")
            n_round  = nf2.number_input("Rounding", value=0.01, min_value=0.000001, step=0.01, key="n_uom_round")

            if st.button("✅ Create New Unit in DB", key="btn_create_uom"):
                if not n_name:
                    st.error("Unit name is required.")
                else:
                    db_execute("""
                        INSERT INTO uoms (name, category, uom_type, factor, rounding, active)
                        VALUES (?, ?, ?, ?, ?, 1)
                    """, (n_name, n_cat, n_type, n_factor, n_round))
                    st.success(f"✅ Unit '{n_name}' successfully added to database!")
                    st.rerun()

    # ── CONVERSION CALCULATOR ─────────────────────────────────────────────
    with tab_conv:
        st.markdown('<div class="section-header">🔄 Unit Conversion Engine</div>', unsafe_allow_html=True)
        all_uoms = db_query("SELECT * FROM uoms WHERE active = 1 ORDER BY name ASC")
        uom_map = {u["name"]: u for u in all_uoms}
        u_names = sorted(uom_map.keys())

        if u_names:
            c1, c2, c3 = st.columns(3)
            from_u = c1.selectbox("From Unit", u_names, key="calc_from")
            qty_val = c2.number_input("Quantity Input", value=100.0, step=1.0, key="calc_qty")
            to_u = c3.selectbox("To Unit", u_names, index=1 if len(u_names) > 1 else 0, key="calc_to")

            if from_u and to_u:
                f_obj = uom_map[from_u]
                t_obj = uom_map[to_u]

                # Convert using factor ratios
                base_qty = qty_val * f_obj["factor"]
                converted_qty = base_qty / t_obj["factor"] if t_obj["factor"] else 0.0

                st.markdown(f"""
                <div style="background:#e8f5e9;border-radius:12px;padding:22px;text-align:center;margin-top:14px">
                    <h2 style="color:#2e7d32;margin:0">
                        {qty_val:,.2f} {from_u} = <span style="font-size:1.45em;font-weight:bold;color:#1b5e20">{converted_qty:,.4f} {to_u}</span>
                    </h2>
                    <p style="color:#666;margin:8px 0 0">Normalized via base factor: {base_qty:,.4f}</p>
                </div>
                """, unsafe_allow_html=True)

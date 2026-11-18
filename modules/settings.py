import streamlit as st
import pandas as pd
from modules.odoo_client import (
    odoo_read, odoo_create, odoo_write, to_df, get_uoms, flatten_m2o
)

def render_settings():
    st.title("⚙️ Units of Measure & Conversions")
    st.markdown("""
    <div style="background:#e8f5e9;border-left:4px solid #4caf50;padding:12px;border-radius:6px;margin-bottom:12px">
    Master settings for Units of Measure (UoM). These sync directly with Odoo. Changes here affect product pricing,
    stock moves, and purchase/sale order lines.
    </div>""", unsafe_allow_html=True)

    tab_view,tab_edit,tab_conv,tab_cat = st.tabs([
        "📋 View All UoMs","✏️ Edit / Create UoM","🔄 Conversion Calculator","🗂️ UoM Categories"
    ])

    # ── VIEW ──────────────────────────────────────────────────────────────
    with tab_view:
        with st.spinner():
            uoms = get_uoms()
        if uoms:
            df = to_df(uoms)
            c1,c2 = st.columns(2)
            c1.metric("Total UoMs", len(df))
            c2.metric("Categories", df["category_id"].nunique())

            cats = ["All"] + sorted(df["category_id"].dropna().unique().tolist())
            cat_sel = st.selectbox("Filter by Category", cats)
            df_f = df if cat_sel == "All" else df[df["category_id"]==cat_sel]

            disp = df_f[["name","category_id","uom_type","factor","factor_inv","active"]].copy()
            disp.columns = ["Unit Name","Category","Type","Factor","Factor Inv","Active"]
            disp["Type"] = disp["Type"].map({
                "reference":"⭐ Reference","bigger":"📈 Bigger","smaller":"📉 Smaller"
            }).fillna(disp["Type"])
            disp["Active"] = disp["Active"].apply(lambda x: "✅" if x else "❌")
            st.dataframe(disp,use_container_width=True,hide_index=True)

            by_cat = df.groupby("category_id")["name"].apply(list).reset_index()
            by_cat.columns = ["Category","Units"]
            by_cat["Units"] = by_cat["Units"].apply(lambda x: " | ".join(x))
            st.markdown('<div class="section-header">📂 Units by Category</div>', unsafe_allow_html=True)
            st.dataframe(by_cat,use_container_width=True,hide_index=True)

    # ── EDIT / CREATE ─────────────────────────────────────────────────────
    with tab_edit:
        with st.spinner():
            uoms = get_uoms()
            uom_cats = odoo_read("uom.category",[],["id","name"],limit=50)

        st.markdown('<div class="section-header">✏️ Edit Existing UoM</div>', unsafe_allow_html=True)
        if uoms:
            uom_opts = {u["name"]: u for u in uoms}
            sel_uom_name = st.selectbox("Select UoM to Edit", ["-- Select --"] + list(uom_opts.keys()))
            if sel_uom_name != "-- Select --":
                sel_uom = uom_opts[sel_uom_name]
                cat_map = {c["name"]: c["id"] for c in uom_cats}
                cat_names = sorted(cat_map.keys())

                c1,c2,c3 = st.columns(3)
                new_name = c1.text_input("Unit Name", value=sel_uom["name"], key="edit_uom_name")
                curr_cat = flatten_m2o(sel_uom["category_id"])
                new_cat  = c2.selectbox("Category", cat_names,
                    index=cat_names.index(curr_cat) if curr_cat in cat_names else 0,
                    key="edit_uom_cat")
                uom_types = ["reference","bigger","smaller"]
                new_type = c3.selectbox("Type", uom_types,
                    index=uom_types.index(sel_uom["uom_type"]) if sel_uom["uom_type"] in uom_types else 0,
                    key="edit_uom_type")

                col_f1,col_f2,col_f3 = st.columns(3)
                new_factor = col_f1.number_input("Factor (ratio to reference)",
                    value=float(sel_uom["factor"]), min_value=0.00001, step=0.001, key="edit_uom_factor",
                    help="For 'bigger': how many base units = 1 of this. For 'smaller': 1/factor.")
                new_active = col_f3.checkbox("Active", value=bool(sel_uom["active"]), key="edit_uom_active")
                st.caption(f"Factor inverse: **{1/new_factor:.6f}** (auto-calculated by Odoo)")

                if st.button("💾 Save UoM Changes", type="primary"):
                    vals = {
                        "name": new_name,
                        "category_id": cat_map[new_cat],
                        "uom_type": new_type,
                        "factor": new_factor,
                        "active": new_active,
                    }
                    res = odoo_write("uom.uom", sel_uom["id"], vals)
                    if res:
                        st.success(f"✅ UoM '{new_name}' updated!")
                        st.cache_data.clear()
                    else:
                        st.error("Failed to update. Check permissions.")

        st.markdown('<div class="section-header">➕ Create New UoM</div>', unsafe_allow_html=True)
        with st.expander("Create New Unit of Measure"):
            uom_cats_fresh = odoo_read("uom.category",[],["id","name"],limit=50)
            cat_map_new = {c["name"]: c["id"] for c in uom_cats_fresh}

            nc1,nc2,nc3 = st.columns(3)
            n_name   = nc1.text_input("Unit Name *", key="new_uom_name")
            n_cat    = nc2.selectbox("Category *", sorted(cat_map_new.keys()), key="new_uom_cat")
            n_type   = nc3.selectbox("Type", ["reference","bigger","smaller"], key="new_uom_type")
            nf1,nf2  = st.columns(2)
            n_factor = nf1.number_input("Factor", value=1.0, min_value=0.00001, step=0.001, key="new_uom_factor",
                help="Ratio vs. reference unit in this category")
            n_rounding = nf2.number_input("Rounding Precision", value=0.01, min_value=0.00001, step=0.001, key="new_uom_rounding")

            if st.button("✅ Create UoM", key="create_uom"):
                if not n_name:
                    st.error("Unit name is required.")
                else:
                    new_id = odoo_create("uom.uom",{
                        "name": n_name,
                        "category_id": cat_map_new[n_cat],
                        "uom_type": n_type,
                        "factor": n_factor,
                        "rounding": n_rounding,
                        "active": True,
                    })
                    if new_id:
                        st.success(f"✅ UoM '{n_name}' created! (ID: {new_id})")
                        st.cache_data.clear()

    # ── CONVERSION CALCULATOR ─────────────────────────────────────────────
    with tab_conv:
        st.markdown('<div class="section-header">🔄 Unit Conversion Calculator</div>', unsafe_allow_html=True)
        st.info("Convert quantities between units in the same category.")

        with st.spinner():
            uoms = get_uoms()
        uom_by_cat = {}
        for u in uoms:
            cat = flatten_m2o(u["category_id"])
            if cat not in uom_by_cat:
                uom_by_cat[cat] = []
            uom_by_cat[cat].append(u)

        cats_avail = sorted(uom_by_cat.keys())
        sel_cat = st.selectbox("Category", cats_avail, key="conv_cat")

        if sel_cat and sel_cat in uom_by_cat:
            units_in_cat = {u["name"]: u for u in uom_by_cat[sel_cat]}
            unit_names = sorted(units_in_cat.keys())
            ref_unit = next((u for u in uom_by_cat[sel_cat] if u["uom_type"]=="reference"), None)

            c1,c2,c3 = st.columns(3)
            from_unit = c1.selectbox("From Unit", unit_names, key="conv_from")
            qty_in    = c2.number_input("Quantity", value=1.0, min_value=0.0, step=0.5, key="conv_qty")
            to_unit   = c3.selectbox("To Unit", unit_names,
                index=1 if len(unit_names)>1 else 0, key="conv_to")

            if from_unit and to_unit and from_unit in units_in_cat and to_unit in units_in_cat:
                fu = units_in_cat[from_unit]
                tu = units_in_cat[to_unit]

                def to_base(qty, uom):
                    if uom["uom_type"] == "reference":
                        return qty
                    elif uom["uom_type"] == "bigger":
                        return qty * uom["factor"]
                    else:
                        return qty / uom["factor"] if uom["factor"] else qty

                def from_base(qty_base, uom):
                    if uom["uom_type"] == "reference":
                        return qty_base
                    elif uom["uom_type"] == "bigger":
                        return qty_base / uom["factor"] if uom["factor"] else qty_base
                    else:
                        return qty_base * uom["factor"]

                base_qty = to_base(qty_in, fu)
                result   = from_base(base_qty, tu)

                st.markdown(f"""
                <div style="background:#e8f5e9;border-radius:12px;padding:20px;text-align:center;margin-top:12px">
                    <h2 style="color:#2e7d32;margin:0">
                        {qty_in:,.4f} {from_unit} = <span style="font-size:1.5em">{result:,.4f} {to_unit}</span>
                    </h2>
                    <p style="color:#666;margin:8px 0 0">via {ref_unit['name'] if ref_unit else 'base'} = {base_qty:,.4f}</p>
                </div>
                """, unsafe_allow_html=True)

                st.markdown('<div class="section-header">📊 Full Conversion Table</div>', unsafe_allow_html=True)
                rows = []
                for un, uom in units_in_cat.items():
                    base = to_base(1.0, uom)
                    rows.append({"Unit": un, "Type": uom["uom_type"], "1 unit = (base)": round(base,6)})
                df_ct = pd.DataFrame(rows)
                st.dataframe(df_ct,use_container_width=True,hide_index=True)

    # ── UoM CATEGORIES ────────────────────────────────────────────────────
    with tab_cat:
        st.markdown('<div class="section-header">🗂️ UoM Categories</div>', unsafe_allow_html=True)
        with st.spinner():
            cats = odoo_read("uom.category",[],["id","name"],limit=50)
        if cats:
            df_cats = pd.DataFrame(cats)
            df_cats.columns = ["ID","Category Name"]
            st.dataframe(df_cats,use_container_width=True,hide_index=True)

        st.markdown("**Create New Category:**")
        with st.expander("New Category"):
            nc_name = st.text_input("Category Name *", key="new_cat_name")
            if st.button("✅ Create Category"):
                if not nc_name:
                    st.error("Name required.")
                else:
                    cid = odoo_create("uom.category",{"name": nc_name})
                    if cid:
                        st.success(f"✅ Category '{nc_name}' created!")
                        st.cache_data.clear()

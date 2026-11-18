import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import timedelta
from modules.odoo_client import (
    odoo_read, odoo_create, odoo_write, odoo_action,
    to_df, get_products, get_uoms, get_lots
)

def render_inventory():
    st.title("📋 Inventory & Lot Tracking")
    tab_stock, tab_lots, tab_adj, tab_moves = st.tabs([
        "📦 Stock Levels","🏷️ Lot Tracking","🔧 Adjust Stock","🔄 Stock Moves"
    ])

    # ── STOCK LEVELS ──────────────────────────────────────────────────────
    with tab_stock:
        with st.spinner():
            quants = odoo_read("stock.quant",
                [["location_id.usage","=","internal"]],
                ["product_id","location_id","quantity","reserved_quantity",
                 "product_uom_id","lot_id","inventory_quantity"],
                limit=1000)
        if quants:
            df = to_df(quants)
            df["available"] = (df["quantity"] - df["reserved_quantity"]).clip(lower=0)

            wh_all = ["All"] + sorted(df["location_id"].dropna().unique().tolist())
            wh_sel = st.selectbox("Filter by Location", wh_all)
            df_f = df if wh_sel == "All" else df[df["location_id"]==wh_sel]

            c1,c2,c3,c4 = st.columns(4)
            c1.metric("SKUs", len(df_f))
            c2.metric("On Hand", f"{df_f['quantity'].sum():,.0f}")
            c3.metric("Reserved", f"{df_f['reserved_quantity'].sum():,.0f}")
            c4.metric("Available", f"{df_f['available'].sum():,.0f}")

            srch = st.text_input("🔍 Search product")
            if srch:
                df_f = df_f[df_f["product_id"].str.contains(srch,case=False,na=False)]

            disp = df_f[["product_id","lot_id","location_id","quantity","reserved_quantity","available"]].copy()
            disp.columns = ["Product","Lot/Serial","Location","On Hand","Reserved","Available"]
            st.dataframe(disp,use_container_width=True,hide_index=True)

            by_loc = df.groupby("location_id")["quantity"].sum().nlargest(12).reset_index()
            by_loc.columns = ["Location","Stock Units"]
            fig = px.bar(by_loc,x="Location",y="Stock Units",
                title="Stock by Location",color_discrete_sequence=["#4caf50"])
            fig.update_layout(height=300,xaxis_tickangle=-30)
            st.plotly_chart(fig,use_container_width=True)

    # ── LOT TRACKING ──────────────────────────────────────────────────────
    with tab_lots:
        st.markdown('<div class="section-header">🏷️ Lot / Serial Number Tracking</div>', unsafe_allow_html=True)

        prod_map, prod_recs = get_products()
        col1, col2 = st.columns(2)
        with col1:
            filter_prod = st.selectbox("Filter by Product (optional)",
                ["-- All Products --"] + sorted(prod_map.keys()))
        with col2:
            lot_search = st.text_input("🔍 Search Lot Number")

        with st.spinner("Loading lots..."):
            lot_domain = []
            if filter_prod != "-- All Products --":
                lot_domain = [["product_id","=",prod_map[filter_prod]["id"]]]
            lots = odoo_read("stock.lot", lot_domain,
                ["name","product_id","product_qty","expiration_date","company_id","ref"],
                limit=500)

        if lots:
            df_l = to_df(lots)
            if lot_search:
                df_l = df_l[df_l["name"].str.contains(lot_search,case=False,na=False)]

            c1,c2 = st.columns(2)
            c1.metric("Total Lots", len(df_l))
            c2.metric("Total Qty", f"{df_l['product_qty'].sum():,.2f}")

            disp = df_l[["name","product_id","product_qty","expiration_date","company_id"]].copy()
            disp.columns = ["Lot Number","Product","Qty on Hand","Expiry Date","Company"]
            disp["Qty on Hand"] = disp["Qty on Hand"].apply(lambda x: f"{float(x):,.2f}" if x else "0")
            st.dataframe(disp,use_container_width=True,hide_index=True)

            df_l["expiration_date"] = pd.to_datetime(df_l["expiration_date"],errors="coerce")
            expiring = df_l[df_l["expiration_date"].notna() &
                           (df_l["expiration_date"] <= pd.Timestamp.now()+timedelta(days=30))]
            if not expiring.empty:
                st.warning(f"⚠️ {len(expiring)} lot(s) expiring within 30 days!")
                disp_e = expiring[["name","product_id","product_qty","expiration_date"]].copy()
                disp_e.columns = ["Lot","Product","Qty","Expiry"]
                disp_e["Expiry"] = disp_e["Expiry"].dt.strftime("%d %b %Y")
                st.dataframe(disp_e,use_container_width=True,hide_index=True)

        st.markdown('<div class="section-header">➕ Create New Lot</div>', unsafe_allow_html=True)
        with st.expander("Create Lot"):
            nl_prod = st.selectbox("Product *", ["-- Select --"] + sorted(prod_map.keys()), key="nl_prod")
            nl_name = st.text_input("Lot Number *", key="nl_name")
            nl_ref  = st.text_input("Internal Reference", key="nl_ref")
            nl_exp  = st.date_input("Expiry Date", key="nl_exp")
            if st.button("Create Lot", key="create_lot"):
                if nl_prod == "-- Select --" or not nl_name:
                    st.error("Product and Lot Number are required.")
                else:
                    lid = odoo_create("stock.lot",{
                        "product_id": prod_map[nl_prod]["id"],
                        "name": nl_name,
                        "ref": nl_ref,
                        "expiration_date": nl_exp.strftime("%Y-%m-%d"),
                        "company_id": 1,
                    })
                    if lid:
                        st.success(f"✅ Lot '{nl_name}' created! (ID: {lid})")
                        st.cache_data.clear()

    # ── INVENTORY ADJUSTMENT ──────────────────────────────────────────────
    with tab_adj:
        st.markdown('<div class="section-header">🔧 Inventory Adjustment</div>', unsafe_allow_html=True)
        st.info("💡 Directly updates stock quantity and creates an inventory adjustment entry in Odoo.")

        with st.spinner():
            locs = odoo_read("stock.location",
                [["usage","=","internal"]],["id","complete_name"],limit=50)

        prod_map_adj, _ = get_products()

        col1, col2, col3 = st.columns(3)
        adj_prod = col1.selectbox("Product *", ["-- Select --"] + sorted(prod_map_adj.keys()), key="adj_prod")
        loc_opts = {l["complete_name"]: l["id"] for l in locs}
        adj_loc  = col2.selectbox("Location *", ["-- Select --"] + sorted(loc_opts.keys()), key="adj_loc")

        lot_opts_adj = {"None": None}
        if adj_prod != "-- Select --":
            lots_adj = get_lots(prod_map_adj[adj_prod]["id"])
            for lt in lots_adj:
                lot_opts_adj[lt["name"]] = lt["id"]
        adj_lot = col3.selectbox("Lot (optional)", list(lot_opts_adj.keys()), key="adj_lot")

        adj_qty = st.number_input("New Quantity on Hand *", min_value=0.0, value=0.0, step=1.0, key="adj_qty")
        adj_reason = st.text_input("Reason / Note", key="adj_reason")

        if st.button("🔧 Apply Adjustment", type="primary"):
            if adj_prod == "-- Select --" or adj_loc == "-- Select --":
                st.error("Product and Location are required.")
            else:
                pid  = prod_map_adj[adj_prod]["id"]
                lid  = loc_opts[adj_loc]
                lot_id = lot_opts_adj[adj_lot]

                domain_q = [["product_id","=",pid],["location_id","=",lid]]
                if lot_id:
                    domain_q.append(["lot_id","=",lot_id])
                existing = odoo_read("stock.quant",domain_q,["id","quantity"],limit=1)

                if existing:
                    qid = existing[0]["id"]
                    odoo_write("stock.quant",qid,{"inventory_quantity":adj_qty})
                    res = odoo_action("stock.quant","action_apply_inventory",qid)
                    if res is not None:
                        st.success(f"✅ Stock adjusted to {adj_qty} units for '{adj_prod}'!")
                        st.cache_data.clear()
                else:
                    vals = {
                        "product_id": pid,
                        "location_id": lid,
                        "inventory_quantity": adj_qty,
                    }
                    if lot_id: vals["lot_id"] = lot_id
                    qid = odoo_create("stock.quant", vals)
                    if qid:
                        odoo_action("stock.quant","action_apply_inventory",qid)
                        st.success(f"✅ Stock created & set to {adj_qty} units!")
                        st.cache_data.clear()

    # ── STOCK MOVES ───────────────────────────────────────────────────────
    with tab_moves:
        with st.spinner():
            moves = odoo_read("stock.move",[["state","=","done"]],
                ["name","product_id","location_id","location_dest_id",
                 "product_uom_qty","date","lot_ids"],
                limit=200, order="date desc")
        if moves:
            df_m = to_df(moves)
            df_m["date"] = pd.to_datetime(df_m["date"],errors="coerce").dt.strftime("%d %b %Y %H:%M")
            disp_m = df_m[["product_id","location_id","location_dest_id","product_uom_qty","date"]].copy()
            disp_m.columns = ["Product","From","To","Qty","Date"]
            st.dataframe(disp_m,use_container_width=True,hide_index=True)

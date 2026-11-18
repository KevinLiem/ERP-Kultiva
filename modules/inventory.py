import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from modules.db import (
    db_query, db_query_df, db_execute, get_products, get_uoms, get_lots
)

def render_inventory():
    st.title("📋 Inventory & Lot Tracking")
    tab_stock, tab_lots, tab_adj, tab_moves = st.tabs([
        "📦 Stock Levels","🏷️ Lot Tracking","🔧 Adjust Stock","🔄 Stock Moves"
    ])

    # ── STOCK LEVELS ──────────────────────────────────────────────────────
    with tab_stock:
        df = db_query_df("""
            SELECT product_id, product_name, lot_name, location_name, quantity, reserved_quantity 
            FROM stock_quants 
            WHERE quantity > 0
            ORDER BY product_name ASC
        """)
        if not df.empty:
            df["available"] = (df["quantity"] - df["reserved_quantity"]).clip(lower=0)

            wh_all = ["All"] + sorted([x for x in df["location_name"].dropna().unique().tolist() if x])
            wh_sel = st.selectbox("Filter by Location", wh_all)
            df_f = df if wh_sel == "All" else df[df["location_name"]==wh_sel]

            c1,c2,c3,c4 = st.columns(4)
            c1.metric("SKUs with Stock", len(df_f["product_id"].unique()))
            c2.metric("On Hand Units", f"{df_f['quantity'].sum():,.0f}")
            c3.metric("Reserved", f"{df_f['reserved_quantity'].sum():,.0f}")
            c4.metric("Available", f"{df_f['available'].sum():,.0f}")

            srch = st.text_input("🔍 Search Product / Lot", key="stock_srch")
            if srch:
                df_f = df_f[df_f["product_name"].str.contains(srch,case=False,na=False)|
                            df_f["lot_name"].str.contains(srch,case=False,na=False)]

            disp = df_f[["product_name","lot_name","location_name","quantity","reserved_quantity","available"]].copy()
            disp.columns = ["Product","Lot / Serial","Location","On Hand","Reserved","Available"]
            st.dataframe(disp, use_container_width=True, hide_index=True)

            by_loc = df.groupby("location_name")["quantity"].sum().nlargest(12).reset_index()
            by_loc.columns = ["Location","Stock Units"]
            fig = px.bar(by_loc, x="Location", y="Stock Units",
                title="Stock by Location", color_discrete_sequence=["#4caf50"])
            fig.update_layout(height=300, xaxis_tickangle=-30)
            st.plotly_chart(fig, use_container_width=True)

    # ── LOT TRACKING ──────────────────────────────────────────────────────
    with tab_lots:
        st.markdown('<div class="section-header">🏷️ Lot / Serial Number Tracking</div>', unsafe_allow_html=True)
        prod_map, prod_recs = get_products()
        col1, col2 = st.columns(2)
        with col1:
            filter_prod = st.selectbox("Filter by Product (Optional)",
                ["-- All Products --"] + sorted(prod_map.keys()))
        with col2:
            lot_search = st.text_input("🔍 Search Lot Number")

        q = "SELECT id, name, product_name, product_qty, expiration_date, ref FROM stock_lots WHERE 1=1"
        params = []
        if filter_prod != "-- All Products --":
            q += " AND product_id = ?"
            params.append(prod_map[filter_prod]["id"])
        if lot_search:
            q += " AND name LIKE ?"
            params.append(f"%{lot_search}%")
        q += " ORDER BY id DESC LIMIT 500"

        df_l = db_query_df(q, params=params if params else None)
        if not df_l.empty:
            c1,c2 = st.columns(2)
            c1.metric("Total Lots Found", len(df_l))
            c2.metric("Total Qty", f"{df_l['product_qty'].sum():,.2f}")

            disp = df_l[["name","product_name","product_qty","expiration_date","ref"]].copy()
            disp.columns = ["Lot Number","Product","Qty on Hand","Expiry Date","Reference"]
            disp["Qty on Hand"] = disp["Qty on Hand"].apply(lambda x: f"{float(x):,.2f}" if x else "0")
            st.dataframe(disp, use_container_width=True, hide_index=True)

            # Expiry warning
            df_l["expiration_date"] = pd.to_datetime(df_l["expiration_date"], errors="coerce")
            expiring = df_l[df_l["expiration_date"].notna() &
                           (df_l["expiration_date"] <= pd.Timestamp.now()+timedelta(days=30))]
            if not expiring.empty:
                st.warning(f"⚠️ {len(expiring)} lot(s) expiring within 30 days!")
                disp_e = expiring[["name","product_name","product_qty","expiration_date"]].copy()
                disp_e.columns = ["Lot","Product","Qty","Expiry"]
                disp_e["Expiry"] = disp_e["Expiry"].dt.strftime("%d %b %Y")
                st.dataframe(disp_e, use_container_width=True, hide_index=True)

        st.markdown('<div class="section-header">➕ Register New Lot</div>', unsafe_allow_html=True)
        with st.expander("Create Lot"):
            nl_prod = st.selectbox("Product *", ["-- Select --"] + sorted(prod_map.keys()), key="nl_prod")
            nl_name = st.text_input("Lot Number *", key="nl_name")
            nl_ref  = st.text_input("Internal Reference", key="nl_ref")
            nl_exp  = st.date_input("Expiry Date", key="nl_exp")
            if st.button("Create Lot", key="create_lot"):
                if nl_prod == "-- Select --" or not nl_name:
                    st.error("Product and Lot Number are required.")
                else:
                    lid = db_execute("""
                        INSERT INTO stock_lots (name, product_id, product_name, product_qty, expiration_date, ref)
                        VALUES (?, ?, ?, 0.0, ?, ?)
                    """, (nl_name, prod_map[nl_prod]["id"], nl_prod, nl_exp.strftime("%Y-%m-%d"), nl_ref))
                    st.success(f"✅ Lot '{nl_name}' created in Database! (ID: {lid})")
                    st.rerun()

    # ── INVENTORY ADJUSTMENT ──────────────────────────────────────────────
    with tab_adj:
        st.markdown('<div class="section-header">🔧 Inventory Adjustment</div>', unsafe_allow_html=True)
        st.info("💡 Directly update stock quantity and track adjustments in Kultiva DB.")

        locs = db_query("SELECT id, complete_name FROM locations WHERE usage = 'internal' ORDER BY complete_name ASC")
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
        adj_lot = col3.selectbox("Lot (Optional)", list(lot_opts_adj.keys()), key="adj_lot")

        # Current stock lookup
        current_stock = 0.0
        if adj_prod != "-- Select --" and adj_loc != "-- Select --":
            pid = prod_map_adj[adj_prod]["id"]
            lid = loc_opts[adj_loc]
            existing = db_query("SELECT quantity FROM stock_quants WHERE product_id = ? AND location_id = ?", (pid, lid))
            if existing:
                current_stock = existing[0]["quantity"]

        st.caption(f"Current Quantity on Hand: **{current_stock:,.2f}**")
        adj_qty = st.number_input("New Quantity on Hand *", min_value=0.0, value=float(current_stock), step=1.0, key="adj_qty")
        adj_reason = st.text_input("Reason / Note", key="adj_reason")

        if st.button("🔧 Apply Adjustment", type="primary"):
            if adj_prod == "-- Select --" or adj_loc == "-- Select --":
                st.error("Product and Location are required.")
            else:
                pid  = prod_map_adj[adj_prod]["id"]
                lid  = loc_opts[adj_loc]
                lot_name = adj_lot if adj_lot != "None" else ""

                existing = db_query("SELECT id FROM stock_quants WHERE product_id = ? AND location_id = ?", (pid, lid))
                if existing:
                    db_execute("UPDATE stock_quants SET quantity = ?, lot_name = ? WHERE id = ?", (adj_qty, lot_name, existing[0]["id"]))
                else:
                    db_execute("""
                        INSERT INTO stock_quants (product_id, product_name, location_id, location_name, lot_name, quantity, reserved_quantity)
                        VALUES (?, ?, ?, ?, ?, ?, 0.0)
                    """, (pid, adj_prod, lid, adj_loc, lot_name, adj_qty))

                # Log stock move record
                db_execute("""
                    INSERT INTO stock_moves (product_id, product_name, product_uom_qty, quantity, location_name, location_dest_name, state, date)
                    VALUES (?, ?, ?, ?, 'Inventory Adjustment', ?, 'done', ?)
                """, (pid, adj_prod, abs(adj_qty - current_stock), adj_qty, adj_loc, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

                st.success(f"✅ Stock adjusted to {adj_qty} units for '{adj_prod}'!")
                st.rerun()

    # ── STOCK MOVES ───────────────────────────────────────────────────────
    with tab_moves:
        df_m = db_query_df("""
            SELECT product_name, location_name, location_dest_name, product_uom_qty, date 
            FROM stock_moves 
            ORDER BY id DESC LIMIT 200
        """)
        if not df_m.empty:
            df_m["date"] = pd.to_datetime(df_m["date"], errors="coerce").dt.strftime("%d %b %Y %H:%M")
            df_m.columns = ["Product","From","To","Qty","Date"]
            st.dataframe(df_m, use_container_width=True, hide_index=True)

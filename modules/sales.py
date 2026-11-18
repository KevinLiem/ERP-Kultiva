import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from modules.odoo_client import (
    odoo_read, odoo_create, odoo_write, odoo_action,
    to_df, fmt_idr, status_badge, flatten_m2o,
    get_partners, get_products, get_uoms
)

def render_sales():
    sub = st.radio("", ["📋 List", "➕ Create New", "✏️ Edit Existing"],
        horizontal=True, label_visibility="collapsed")

    # ── LIST ──────────────────────────────────────────────────────────────
    if sub == "📋 List":
        st.title("📦 Sales Orders")
        col_f1,col_f2,col_f3 = st.columns(3)
        with col_f1:
            st_filter = st.multiselect("Status", ["draft","sent","sale","done","cancel"],
                default=["draft","sent","sale"])
        with col_f2:
            d_from = st.date_input("From", datetime.now()-timedelta(days=90))
        with col_f3:
            d_to = st.date_input("To", datetime.now())

        with st.spinner():
            so = odoo_read("sale.order",
                [["state","in",st_filter],
                 ["date_order",">=",d_from.strftime("%Y-%m-%d 00:00:00")],
                 ["date_order","<=",d_to.strftime("%Y-%m-%d 23:59:59")]],
                ["name","partner_id","state","amount_total","amount_untaxed",
                 "date_order","user_id","invoice_status","commitment_date"],
                limit=500, order="date_order desc")

        if so:
            df = to_df(so)
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Orders", len(df))
            c2.metric("Total Revenue", fmt_idr(df["amount_total"].sum()))
            c3.metric("Confirmed", len(df[df["state"]=="sale"]))
            c4.metric("Avg Value", fmt_idr(df["amount_total"].mean()))

            srch = st.text_input("🔍 Search")
            if srch:
                df = df[df["partner_id"].str.contains(srch,case=False,na=False)|
                        df["name"].str.contains(srch,case=False,na=False)]

            disp = df[["name","partner_id","state","amount_untaxed","amount_total","date_order"]].copy()
            disp.columns = ["Order","Customer","Status","Subtotal","Total","Date"]
            disp["Total"] = disp["Total"].apply(fmt_idr)
            disp["Subtotal"] = disp["Subtotal"].apply(fmt_idr)
            disp["Date"] = pd.to_datetime(disp["Date"]).dt.strftime("%d %b %Y")
            disp["Status"] = disp["Status"].apply(status_badge)
            st.dataframe(disp, use_container_width=True, hide_index=True)

            # Quick actions
            st.markdown('<div class="section-header">⚡ Quick Actions</div>', unsafe_allow_html=True)
            so_names = {r["name"]: r["id"] for r in so}
            sel_so = st.selectbox("Select Order", list(so_names.keys()))
            if sel_so:
                sel_id = so_names[sel_so]
                sel_state = next(r["state"] for r in so if r["id"]==sel_id)
                ca, cb, cc = st.columns(3)
                if sel_state == "draft":
                    if ca.button("✅ Confirm Order"):
                        res = odoo_action("sale.order","action_confirm",sel_id)
                        if res is not None:
                            st.success(f"Order {sel_so} confirmed!")
                            st.cache_data.clear(); st.rerun()
                if sel_state == "sale":
                    if cb.button("🚚 View Deliveries"):
                        picks = odoo_read("stock.picking",
                            [["sale_id","=",sel_id]],["id","name","state"])
                        st.info(f"Deliveries: {[p['name'] for p in picks]}")
                if cc.button("🗑️ Cancel Order") and sel_state in ["draft","sent"]:
                    odoo_action("sale.order","action_cancel",sel_id)
                    st.warning(f"Order {sel_so} cancelled."); st.cache_data.clear(); st.rerun()

    # ── CREATE ────────────────────────────────────────────────────────────
    elif sub == "➕ Create New":
        st.title("➕ Create Sales Order")

        with st.spinner("Loading master data..."):
            cust_map, cust_recs = get_partners(customer=True)
            prod_map, prod_recs  = get_products()
            uoms = get_uoms()

        # Header
        st.markdown('<div class="section-header">📋 Order Header</div>', unsafe_allow_html=True)
        c1,c2,c3 = st.columns(3)
        cust_names = ["-- Select Customer --"] + sorted(cust_map.keys())
        sel_cust = c1.selectbox("Customer *", cust_names)
        ord_date = c2.date_input("Order Date", datetime.now())
        commitment = c3.date_input("Delivery Date (Optional)", datetime.now()+timedelta(days=7))
        note = st.text_area("Notes / Terms", height=60)

        # Lines
        st.markdown('<div class="section-header">📦 Order Lines</div>', unsafe_allow_html=True)
        prod_names = ["-- Select Product --"] + sorted(prod_map.keys())

        col_p, col_q, col_u, col_pr, col_add = st.columns([3,1,1.5,1.5,1])
        with col_p: np_sel = st.selectbox("Product", prod_names, key="so_prod_sel")
        with col_q: np_qty = st.number_input("Qty", min_value=0.001, value=1.0, step=0.5, key="so_qty")
        with col_u:
            uom_names_all = [u["name"] for u in uoms]
            np_uom = st.selectbox("UoM", uom_names_all if uom_names_all else ["Unit"], key="so_uom")
        with col_pr:
            default_price = 0.0
            if np_sel != "-- Select Product --":
                default_price = prod_map[np_sel]["list_price"]
            np_price = st.number_input("Unit Price", min_value=0.0, value=float(default_price), step=100.0, key="so_price")
        with col_add:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("➕ Add", key="so_add_line"):
                if np_sel == "-- Select Product --":
                    st.warning("Select a product first.")
                else:
                    uom_id = next((u["id"] for u in uoms if u["name"]==np_uom), None)
                    st.session_state.so_lines.append({
                        "product_name": np_sel,
                        "product_id":   prod_map[np_sel]["id"],
                        "qty":          np_qty,
                        "uom":          np_uom,
                        "uom_id":       uom_id,
                        "price":        np_price,
                        "subtotal":     np_qty * np_price,
                    })

        # Show lines table
        if st.session_state.so_lines:
            df_lines = pd.DataFrame(st.session_state.so_lines)
            df_lines["subtotal"] = df_lines["subtotal"].apply(fmt_idr)
            st.dataframe(df_lines[["product_name","qty","uom","price","subtotal"]].rename(columns={
                "product_name":"Product","qty":"Qty","uom":"UoM","price":"Unit Price","subtotal":"Subtotal"
            }), use_container_width=True, hide_index=True)
            total = sum(l["qty"]*l["price"] for l in st.session_state.so_lines)
            st.markdown(f"**Grand Total: {fmt_idr(total)}**")
            if st.button("🗑️ Clear All Lines"):
                st.session_state.so_lines = []
                st.rerun()

        # Submit
        st.markdown("---")
        col_s1, col_s2 = st.columns(2)
        if col_s1.button("💾 Save as Draft", type="primary"):
            if sel_cust == "-- Select Customer --":
                st.error("Please select a customer.")
            elif not st.session_state.so_lines:
                st.error("Add at least one order line.")
            else:
                with st.spinner("Creating order..."):
                    so_id = odoo_create("sale.order", {
                        "partner_id": cust_map[sel_cust],
                        "date_order": ord_date.strftime("%Y-%m-%d %H:%M:%S"),
                        "commitment_date": commitment.strftime("%Y-%m-%d %H:%M:%S"),
                        "note": note,
                    })
                    if so_id:
                        for ln in st.session_state.so_lines:
                            odoo_create("sale.order.line", {
                                "order_id":        so_id,
                                "product_id":      ln["product_id"],
                                "product_uom_qty": ln["qty"],
                                "product_uom":     ln["uom_id"],
                                "price_unit":      ln["price"],
                            })
                        st.session_state.so_lines = []
                        st.cache_data.clear()
                        st.success(f"✅ Sales Order created! ID: {so_id}")

        if col_s2.button("✅ Save & Confirm"):
            if sel_cust == "-- Select Customer --":
                st.error("Please select a customer.")
            elif not st.session_state.so_lines:
                st.error("Add at least one order line.")
            else:
                with st.spinner("Creating & confirming..."):
                    so_id = odoo_create("sale.order", {
                        "partner_id": cust_map[sel_cust],
                        "date_order": ord_date.strftime("%Y-%m-%d %H:%M:%S"),
                        "commitment_date": commitment.strftime("%Y-%m-%d %H:%M:%S"),
                        "note": note,
                    })
                    if so_id:
                        for ln in st.session_state.so_lines:
                            odoo_create("sale.order.line", {
                                "order_id":        so_id,
                                "product_id":      ln["product_id"],
                                "product_uom_qty": ln["qty"],
                                "product_uom":     ln["uom_id"],
                                "price_unit":      ln["price"],
                            })
                        odoo_action("sale.order","action_confirm",so_id)
                        st.session_state.so_lines = []
                        st.cache_data.clear()
                        st.success(f"✅ Sales Order #{so_id} confirmed!")

    # ── EDIT ──────────────────────────────────────────────────────────────
    elif sub == "✏️ Edit Existing":
        st.title("✏️ Edit Sales Order")

        with st.spinner():
            so_list = odoo_read("sale.order",[["state","in",["draft","sent"]]],
                ["id","name","partner_id","state","amount_total","note",
                 "date_order","commitment_date"], limit=200, order="date_order desc")

        if not so_list:
            st.info("No editable orders (draft/sent) found.")
        else:
            so_opts = {f"{r['name']} — {flatten_m2o(r['partner_id'])}": r["id"] for r in so_list}
            sel = st.selectbox("Select Order to Edit", list(so_opts.keys()))
            if sel:
                eid = so_opts[sel]
                rec = next(r for r in so_list if r["id"]==eid)

                lines = odoo_read("sale.order.line",[["order_id","=",eid]],
                    ["id","product_id","product_uom_qty","price_unit","product_uom","price_subtotal"])

                st.markdown('<div class="section-header">📋 Order Details</div>', unsafe_allow_html=True)
                cust_map, _ = get_partners(customer=True)
                prod_map, _ = get_products()
                uoms        = get_uoms()

                c1,c2 = st.columns(2)
                curr_cust = flatten_m2o(rec["partner_id"])
                cust_list = sorted(cust_map.keys())
                new_cust = c1.selectbox("Customer", cust_list,
                    index=cust_list.index(curr_cust) if curr_cust in cust_list else 0)
                new_note = c2.text_area("Notes", value=rec.get("note","") or "", height=60)

                st.markdown('<div class="section-header">📦 Order Lines</div>', unsafe_allow_html=True)
                if lines:
                    df_l = to_df(lines)
                    df_l["subtotal_fmt"] = df_l["price_subtotal"].apply(fmt_idr)
                    st.dataframe(df_l[["product_id","product_uom_qty","price_unit",
                                       "product_uom","subtotal_fmt"]].rename(columns={
                        "product_id":"Product","product_uom_qty":"Qty",
                        "price_unit":"Price","product_uom":"UoM","subtotal_fmt":"Subtotal"
                    }), use_container_width=True, hide_index=True)

                st.markdown("**Add a new line:**")
                p_names = ["-- Select --"] + sorted(prod_map.keys())
                ec1,ec2,ec3,ec4,ec5 = st.columns([3,1,1.5,1.5,1])
                ep = ec1.selectbox("Product", p_names, key="edit_so_prod")
                eq = ec2.number_input("Qty", min_value=0.001, value=1.0, key="edit_so_qty")
                eu_names = [u["name"] for u in uoms]
                eu = ec3.selectbox("UoM", eu_names, key="edit_so_uom")
                ep_price = float(prod_map[ep]["list_price"]) if ep != "-- Select --" else 0.0
                epr = ec4.number_input("Price", value=ep_price, key="edit_so_price")
                ec5.markdown("<br>", unsafe_allow_html=True)
                if ec5.button("➕", key="edit_so_add"):
                    if ep != "-- Select --":
                        uom_id = next((u["id"] for u in uoms if u["name"]==eu), None)
                        odoo_create("sale.order.line",{
                            "order_id": eid,
                            "product_id": prod_map[ep]["id"],
                            "product_uom_qty": eq,
                            "product_uom": uom_id,
                            "price_unit": epr,
                        })
                        st.success("Line added!"); st.cache_data.clear(); st.rerun()

                st.markdown("---")
                col_a, col_b, col_c = st.columns(3)
                if col_a.button("💾 Save Changes", type="primary"):
                    odoo_write("sale.order", eid, {
                        "partner_id": cust_map[new_cust],
                        "note": new_note,
                    })
                    st.success("✅ Order updated!"); st.cache_data.clear()
                if col_b.button("✅ Confirm Order"):
                    odoo_action("sale.order","action_confirm",eid)
                    st.success("Order confirmed!"); st.cache_data.clear(); st.rerun()
                if col_c.button("🗑️ Cancel Order"):
                    odoo_action("sale.order","action_cancel",eid)
                    st.warning("Order cancelled."); st.cache_data.clear(); st.rerun()

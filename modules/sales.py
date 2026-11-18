import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from modules.db import (
    db_query, db_query_df, db_execute, fmt_idr, status_badge,
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
            d_from = st.date_input("From", datetime.now()-timedelta(days=180))
        with col_f3:
            d_to = st.date_input("To", datetime.now())

        st_filter_str = "('" + "', '".join(st_filter) + "')" if st_filter else "('')"
        d_from_str = d_from.strftime("%Y-%m-%d 00:00:00")
        d_to_str = d_to.strftime("%Y-%m-%d 23:59:59")

        df = db_query_df(f"""
            SELECT id, name, partner_name, state, amount_untaxed, amount_total, date_order 
            FROM sale_orders
            WHERE state IN {st_filter_str}
              AND date_order >= ? AND date_order <= ?
            ORDER BY id DESC
        """, (d_from_str, d_to_str))

        if not df.empty:
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Orders", len(df))
            c2.metric("Total Revenue", fmt_idr(df["amount_total"].sum()))
            c3.metric("Confirmed", len(df[df["state"]=="sale"]))
            c4.metric("Avg Value", fmt_idr(df["amount_total"].mean()))

            srch = st.text_input("🔍 Search Order / Customer")
            if srch:
                df = df[df["partner_name"].str.contains(srch,case=False,na=False)|
                        df["name"].str.contains(srch,case=False,na=False)]

            disp = df[["name","partner_name","state","amount_untaxed","amount_total","date_order"]].copy()
            disp.columns = ["Order","Customer","Status","Subtotal","Total","Date"]
            disp["Total"] = disp["Total"].apply(fmt_idr)
            disp["Subtotal"] = disp["Subtotal"].apply(fmt_idr)
            disp["Date"] = pd.to_datetime(disp["Date"], errors="coerce").dt.strftime("%d %b %Y")
            disp["Status"] = disp["Status"].apply(status_badge)
            st.dataframe(disp, use_container_width=True, hide_index=True)

            # Quick actions
            st.markdown('<div class="section-header">⚡ Quick Actions</div>', unsafe_allow_html=True)
            so_records = db_query("SELECT id, name, state FROM sale_orders ORDER BY id DESC LIMIT 100")
            so_map = {f"{r['name']} ({r['state']})": r for r in so_records}
            sel_so_label = st.selectbox("Select Order", list(so_map.keys()))
            if sel_so_label:
                sel_rec = so_map[sel_so_label]
                sel_id = sel_rec["id"]
                sel_state = sel_rec["state"]
                ca, cb, cc = st.columns(3)
                if sel_state in ["draft", "sent"]:
                    if ca.button("✅ Confirm Order"):
                        db_execute("UPDATE sale_orders SET state = 'sale' WHERE id = ?", (sel_id,))
                        # Automatically create an outgoing delivery picking in database
                        so_data = db_query("SELECT * FROM sale_orders WHERE id = ?", (sel_id,))[0]
                        pick_name = f"WH/OUT/{so_data['name']}"
                        pick_id = db_execute("""
                            INSERT INTO stock_pickings (name, partner_id, partner_name, picking_type_code, picking_type_name, state, scheduled_date, origin, sale_id)
                            VALUES (?, ?, ?, 'outgoing', 'Delivery Orders', 'assigned', ?, ?, ?)
                        """, (pick_name, so_data["partner_id"], so_data["partner_name"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), so_data["name"], sel_id))
                        # Create stock moves from lines
                        lines = db_query("SELECT * FROM sale_order_lines WHERE order_id = ?", (sel_id,))
                        for ln in lines:
                            db_execute("""
                                INSERT INTO stock_moves (picking_id, product_id, product_name, product_uom_qty, quantity, product_uom, state, date)
                                VALUES (?, ?, ?, ?, ?, ?, 'assigned', ?)
                            """, (pick_id, ln["product_id"], ln["product_name"], ln["product_uom_qty"], ln["product_uom_qty"], ln["product_uom"], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        st.success(f"Order {so_data['name']} confirmed and Delivery Note generated!")
                        st.rerun()

                if sel_state == "sale":
                    if cb.button("🚚 View Deliveries"):
                        picks = db_query("SELECT name, state FROM stock_pickings WHERE sale_id = ?", (sel_id,))
                        if picks:
                            st.info(f"Associated Deliveries: {', '.join([p['name'] + ' (' + p['state'] + ')' for p in picks])}")
                        else:
                            st.info("No delivery order found for this sales order.")

                if sel_state in ["draft", "sent"]:
                    if cc.button("🗑️ Cancel Order"):
                        db_execute("UPDATE sale_orders SET state = 'cancel' WHERE id = ?", (sel_id,))
                        st.warning("Order cancelled.")
                        st.rerun()
        else:
            st.info("No orders found for the selected filter range.")

    # ── CREATE ────────────────────────────────────────────────────────────
    elif sub == "➕ Create New":
        st.title("➕ Create Sales Order")

        cust_map, cust_recs = get_partners(customer=True)
        prod_map, prod_recs = get_products()
        uoms = get_uoms()

        st.markdown('<div class="section-header">📋 Order Header</div>', unsafe_allow_html=True)
        c1,c2,c3 = st.columns(3)
        cust_names = ["-- Select Customer --"] + sorted(cust_map.keys())
        sel_cust = c1.selectbox("Customer *", cust_names)
        ord_date = c2.date_input("Order Date", datetime.now())
        commitment = c3.date_input("Delivery Date (Optional)", datetime.now()+timedelta(days=7))
        note = st.text_area("Notes / Terms", height=60)

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
                    st.session_state.so_lines.append({
                        "product_name": np_sel,
                        "product_id":   prod_map[np_sel]["id"],
                        "qty":          np_qty,
                        "uom":          np_uom,
                        "price":        np_price,
                        "subtotal":     np_qty * np_price,
                    })

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

        st.markdown("---")
        col_s1, col_s2 = st.columns(2)
        if col_s1.button("💾 Save as Draft", type="primary"):
            if sel_cust == "-- Select Customer --":
                st.error("Please select a customer.")
            elif not st.session_state.so_lines:
                st.error("Add at least one order line.")
            else:
                total_val = sum(l["qty"] * l["price"] for l in st.session_state.so_lines)
                last_order = db_query("SELECT id FROM sale_orders ORDER BY id DESC LIMIT 1")
                next_num = (last_order[0]["id"] + 1) if last_order else 1
                so_name = f"SO{next_num:05d}"
                so_id = db_execute("""
                    INSERT INTO sale_orders (name, partner_id, partner_name, date_order, commitment_date, state, amount_untaxed, amount_total, note)
                    VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?)
                """, (so_name, cust_map[sel_cust], sel_cust, ord_date.strftime("%Y-%m-%d %H:%M:%S"), commitment.strftime("%Y-%m-%d %H:%M:%S"), total_val, total_val, note))
                for ln in st.session_state.so_lines:
                    db_execute("""
                        INSERT INTO sale_order_lines (order_id, product_id, product_name, product_uom_qty, product_uom, price_unit, price_subtotal)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (so_id, ln["product_id"], ln["product_name"], ln["qty"], ln["uom"], ln["price"], ln["subtotal"]))
                st.session_state.so_lines = []
                st.success(f"✅ Sales Order {so_name} saved into Kultiva Database!")

        if col_s2.button("✅ Save & Confirm"):
            if sel_cust == "-- Select Customer --":
                st.error("Please select a customer.")
            elif not st.session_state.so_lines:
                st.error("Add at least one order line.")
            else:
                total_val = sum(l["qty"] * l["price"] for l in st.session_state.so_lines)
                last_order = db_query("SELECT id FROM sale_orders ORDER BY id DESC LIMIT 1")
                next_num = (last_order[0]["id"] + 1) if last_order else 1
                so_name = f"SO{next_num:05d}"
                so_id = db_execute("""
                    INSERT INTO sale_orders (name, partner_id, partner_name, date_order, commitment_date, state, amount_untaxed, amount_total, note)
                    VALUES (?, ?, ?, ?, ?, 'sale', ?, ?, ?)
                """, (so_name, cust_map[sel_cust], sel_cust, ord_date.strftime("%Y-%m-%d %H:%M:%S"), commitment.strftime("%Y-%m-%d %H:%M:%S"), total_val, total_val, note))
                for ln in st.session_state.so_lines:
                    db_execute("""
                        INSERT INTO sale_order_lines (order_id, product_id, product_name, product_uom_qty, product_uom, price_unit, price_subtotal)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (so_id, ln["product_id"], ln["product_name"], ln["qty"], ln["uom"], ln["price"], ln["subtotal"]))
                # Create Delivery Picking
                pick_name = f"WH/OUT/{so_name}"
                pick_id = db_execute("""
                    INSERT INTO stock_pickings (name, partner_id, partner_name, picking_type_code, picking_type_name, state, scheduled_date, origin, sale_id)
                    VALUES (?, ?, ?, 'outgoing', 'Delivery Orders', 'assigned', ?, ?, ?)
                """, (pick_name, cust_map[sel_cust], sel_cust, commitment.strftime("%Y-%m-%d %H:%M:%S"), so_name, so_id))
                for ln in st.session_state.so_lines:
                    db_execute("""
                        INSERT INTO stock_moves (picking_id, product_id, product_name, product_uom_qty, quantity, product_uom, state, date)
                        VALUES (?, ?, ?, ?, ?, ?, 'assigned', ?)
                    """, (pick_id, ln["product_id"], ln["product_name"], ln["qty"], ln["qty"], ln["uom"], ord_date.strftime("%Y-%m-%d %H:%M:%S")))
                st.session_state.so_lines = []
                st.success(f"✅ Sales Order {so_name} confirmed & Delivery Note {pick_name} generated!")

    # ── EDIT ──────────────────────────────────────────────────────────────
    elif sub == "✏️ Edit Existing":
        st.title("✏️ Edit Sales Order")

        so_list = db_query("SELECT * FROM sale_orders WHERE state IN ('draft', 'sent') ORDER BY id DESC")
        if not so_list:
            st.info("No editable orders (draft/sent) found.")
        else:
            so_opts = {f"{r['name']} — {r['partner_name']}": r for r in so_list}
            sel = st.selectbox("Select Order to Edit", list(so_opts.keys()))
            if sel:
                rec = so_opts[sel]
                eid = rec["id"]
                lines = db_query("SELECT * FROM sale_order_lines WHERE order_id = ?", (eid,))

                st.markdown('<div class="section-header">📋 Order Details</div>', unsafe_allow_html=True)
                cust_map, _ = get_partners(customer=True)
                prod_map, _ = get_products()
                uoms = get_uoms()

                c1,c2 = st.columns(2)
                cust_list = sorted(cust_map.keys())
                curr_cust = rec["partner_name"]
                new_cust = c1.selectbox("Customer", cust_list,
                    index=cust_list.index(curr_cust) if curr_cust in cust_list else 0)
                new_note = c2.text_area("Notes", value=rec.get("note") or "", height=60)

                st.markdown('<div class="section-header">📦 Current Order Lines</div>', unsafe_allow_html=True)
                if lines:
                    df_l = pd.DataFrame(lines)
                    df_l["subtotal_fmt"] = df_l["price_subtotal"].apply(fmt_idr)
                    st.dataframe(df_l[["product_name","product_uom_qty","price_unit",
                                       "product_uom","subtotal_fmt"]].rename(columns={
                        "product_name":"Product","product_uom_qty":"Qty",
                        "price_unit":"Price","product_uom":"UoM","subtotal_fmt":"Subtotal"
                    }), use_container_width=True, hide_index=True)

                st.markdown("**Add Line:**")
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
                        sub_t = eq * epr
                        db_execute("""
                            INSERT INTO sale_order_lines (order_id, product_id, product_name, product_uom_qty, product_uom, price_unit, price_subtotal)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (eid, prod_map[ep]["id"], ep, eq, eu, epr, sub_t))
                        # Update order total
                        db_execute("""
                            UPDATE sale_orders SET amount_total = (SELECT SUM(price_subtotal) FROM sale_order_lines WHERE order_id = ?),
                                                   amount_untaxed = (SELECT SUM(price_subtotal) FROM sale_order_lines WHERE order_id = ?)
                            WHERE id = ?
                        """, (eid, eid, eid))
                        st.success("Line added!")
                        st.rerun()

                st.markdown("---")
                col_a, col_b, col_c = st.columns(3)
                if col_a.button("💾 Save Changes", type="primary"):
                    db_execute("""
                        UPDATE sale_orders SET partner_id = ?, partner_name = ?, note = ? WHERE id = ?
                    """, (cust_map[new_cust], new_cust, new_note, eid))
                    st.success("✅ Order updated!")
                if col_b.button("✅ Confirm Order"):
                    db_execute("UPDATE sale_orders SET state = 'sale' WHERE id = ?", (eid,))
                    # Generate Delivery Order
                    pick_name = f"WH/OUT/{rec['name']}"
                    pick_id = db_execute("""
                        INSERT INTO stock_pickings (name, partner_id, partner_name, picking_type_code, picking_type_name, state, scheduled_date, origin, sale_id)
                        VALUES (?, ?, ?, 'outgoing', 'Delivery Orders', 'assigned', ?, ?, ?)
                    """, (pick_name, cust_map[new_cust], new_cust, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), rec["name"], eid))
                    for ln in lines:
                        db_execute("""
                            INSERT INTO stock_moves (picking_id, product_id, product_name, product_uom_qty, quantity, product_uom, state, date)
                            VALUES (?, ?, ?, ?, ?, ?, 'assigned', ?)
                        """, (pick_id, ln["product_id"], ln["product_name"], ln["product_uom_qty"], ln["product_uom_qty"], ln["product_uom"], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    st.success("Order confirmed and Delivery Note generated!")
                    st.rerun()
                if col_c.button("🗑️ Cancel Order"):
                    db_execute("UPDATE sale_orders SET state = 'cancel' WHERE id = ?", (eid,))
                    st.warning("Order cancelled.")
                    st.rerun()

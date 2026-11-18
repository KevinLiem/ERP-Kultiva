import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from modules.db import (
    db_query, db_query_df, db_execute, fmt_idr, status_badge,
    get_partners, get_products, get_uoms, get_lots
)

def render_purchasing():
    sub = st.radio("", ["📋 List","➕ Create PO","✏️ Edit PO","📥 Receive / Accept"],
        horizontal=True, label_visibility="collapsed")

    # ── LIST ──────────────────────────────────────────────────────────────
    if sub == "📋 List":
        st.title("🛒 Purchase Orders")
        df = db_query_df("""
            SELECT id, name, partner_name, state, amount_total, date_order 
            FROM purchase_orders 
            ORDER BY id DESC
        """)
        if not df.empty:
            df["date_order"] = pd.to_datetime(df["date_order"], errors="coerce")
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Total POs", len(df))
            c2.metric("Confirmed", len(df[df["state"]=="purchase"]))
            c3.metric("Draft", len(df[df["state"]=="draft"]))
            c4.metric("Total Value", fmt_idr(df["amount_total"].sum()))

            srch = st.text_input("🔍 Search PO / Vendor")
            if srch:
                df = df[df["partner_name"].str.contains(srch,case=False,na=False)|
                        df["name"].str.contains(srch,case=False,na=False)]

            disp = df[["name","partner_name","state","amount_total","date_order"]].copy()
            disp.columns = ["PO","Vendor","Status","Total","Date"]
            disp["Total"] = disp["Total"].apply(fmt_idr)
            disp["Date"] = disp["Date"].dt.strftime("%d %b %Y")
            disp["Status"] = disp["Status"].apply(status_badge)
            st.dataframe(disp, use_container_width=True, hide_index=True)

            # Quick confirm
            po_records = db_query("SELECT id, name, partner_name, state FROM purchase_orders ORDER BY id DESC LIMIT 100")
            po_opts = {f"{r['name']} — {r['partner_name']} ({r['state']})": r for r in po_records}
            sel_po_name = st.selectbox("Select PO for Action", list(po_opts.keys()))
            if sel_po_name:
                sel_po = po_opts[sel_po_name]
                ca,cb,cc = st.columns(3)
                if sel_po["state"] == "draft":
                    if ca.button("✅ Confirm PO"):
                        db_execute("UPDATE purchase_orders SET state = 'purchase' WHERE id = ?", (sel_po["id"],))
                        # Create incoming receipt picking
                        rcpt_name = f"WH/IN/{sel_po['name']}"
                        pick_id = db_execute("""
                            INSERT INTO stock_pickings (name, partner_id, partner_name, picking_type_code, picking_type_name, state, scheduled_date, origin, purchase_id)
                            VALUES (?, 0, ?, 'incoming', 'Receipts', 'assigned', ?, ?, ?)
                        """, (rcpt_name, sel_po["partner_name"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), sel_po["name"], sel_po["id"]))
                        lines = db_query("SELECT * FROM purchase_order_lines WHERE order_id = ?", (sel_po["id"],))
                        for ln in lines:
                            db_execute("""
                                INSERT INTO stock_moves (picking_id, product_id, product_name, product_uom_qty, quantity, product_uom, state, date)
                                VALUES (?, ?, ?, ?, ?, ?, 'assigned', ?)
                            """, (pick_id, ln["product_id"], ln["product_name"], ln["product_qty"], ln["product_qty"], ln["product_uom"], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        st.success(f"PO {sel_po['name']} confirmed and Incoming Receipt created!")
                        st.rerun()

                if sel_po["state"] == "draft":
                    if cc.button("🗑️ Cancel PO"):
                        db_execute("UPDATE purchase_orders SET state = 'cancel' WHERE id = ?", (sel_po["id"],))
                        st.warning("PO cancelled.")
                        st.rerun()

    # ── CREATE PO ─────────────────────────────────────────────────────────
    elif sub == "➕ Create PO":
        st.title("➕ Create Purchase Order")

        vend_map, vend_recs = get_partners(vendor=True)
        prod_map, prod_recs = get_products()
        uoms = get_uoms()

        st.markdown('<div class="section-header">📋 PO Header</div>', unsafe_allow_html=True)
        c1,c2,c3 = st.columns(3)
        vend_names = ["-- Select Vendor --"] + sorted(vend_map.keys())
        sel_vend = c1.selectbox("Vendor *", vend_names)
        po_date  = c2.date_input("Order Date", datetime.now())
        po_del   = c3.date_input("Delivery Date", datetime.now()+timedelta(days=14))
        po_note  = st.text_area("Notes", height=60)

        st.markdown('<div class="section-header">📦 PO Lines</div>', unsafe_allow_html=True)
        p_names = ["-- Select Product --"] + sorted(prod_map.keys())
        cp1,cp2,cp3,cp4,cp5 = st.columns([3,1,1.5,1.5,1])
        cp_prod  = cp1.selectbox("Product", p_names, key="po_prod")
        cp_qty   = cp2.number_input("Qty", min_value=0.001, value=1.0, key="po_qty")
        uom_names = [u["name"] for u in uoms]
        cp_uom   = cp3.selectbox("UoM", uom_names, key="po_uom")
        def_cost = float(prod_map[cp_prod]["standard_price"]) if cp_prod != "-- Select Product --" else 0.0
        cp_price = cp4.number_input("Unit Cost", min_value=0.0, value=def_cost, step=100.0, key="po_price")
        cp5.markdown("<br>",unsafe_allow_html=True)
        if cp5.button("➕ Add", key="po_add_line"):
            if cp_prod == "-- Select Product --":
                st.warning("Select a product.")
            else:
                st.session_state.po_lines.append({
                    "product_name": cp_prod,
                    "product_id":   prod_map[cp_prod]["id"],
                    "qty":          cp_qty,
                    "uom":          cp_uom,
                    "price":        cp_price,
                    "subtotal":     cp_qty*cp_price,
                })

        if st.session_state.po_lines:
            df_pl = pd.DataFrame(st.session_state.po_lines)
            df_pl["subtotal"] = df_pl["subtotal"].apply(fmt_idr)
            st.dataframe(df_pl[["product_name","qty","uom","price","subtotal"]].rename(columns={
                "product_name":"Product","qty":"Qty","uom":"UoM","price":"Unit Cost","subtotal":"Subtotal"
            }),use_container_width=True,hide_index=True)
            total_po = sum(l["qty"]*l["price"] for l in st.session_state.po_lines)
            st.markdown(f"**Total: {fmt_idr(total_po)}**")
            if st.button("🗑️ Clear Lines"):
                st.session_state.po_lines = []; st.rerun()

        st.markdown("---")
        col_s1,col_s2 = st.columns(2)
        if col_s1.button("💾 Save Draft", type="primary"):
            if sel_vend == "-- Select Vendor --":
                st.error("Select a vendor.")
            elif not st.session_state.po_lines:
                st.error("Add at least one line.")
            else:
                total_val = sum(l["qty"] * l["price"] for l in st.session_state.po_lines)
                last_po = db_query("SELECT id FROM purchase_orders ORDER BY id DESC LIMIT 1")
                next_num = (last_po[0]["id"] + 1) if last_po else 1
                po_name = f"PO{next_num:05d}"
                po_id = db_execute("""
                    INSERT INTO purchase_orders (name, partner_id, partner_name, date_order, date_planned, state, amount_total, notes)
                    VALUES (?, ?, ?, ?, ?, 'draft', ?, ?)
                """, (po_name, vend_map[sel_vend], sel_vend, po_date.strftime("%Y-%m-%d %H:%M:%S"), po_del.strftime("%Y-%m-%d %H:%M:%S"), total_val, po_note))
                for ln in st.session_state.po_lines:
                    db_execute("""
                        INSERT INTO purchase_order_lines (order_id, product_id, product_name, product_qty, product_uom, price_unit, price_subtotal, name)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (po_id, ln["product_id"], ln["product_name"], ln["qty"], ln["uom"], ln["price"], ln["subtotal"], ln["product_name"]))
                st.session_state.po_lines = []
                st.success(f"✅ Purchase Order {po_name} created in Kultiva DB!")

        if col_s2.button("✅ Save & Confirm"):
            if sel_vend == "-- Select Vendor --":
                st.error("Select a vendor.")
            elif not st.session_state.po_lines:
                st.error("Add at least one line.")
            else:
                total_val = sum(l["qty"] * l["price"] for l in st.session_state.po_lines)
                last_po = db_query("SELECT id FROM purchase_orders ORDER BY id DESC LIMIT 1")
                next_num = (last_po[0]["id"] + 1) if last_po else 1
                po_name = f"PO{next_num:05d}"
                po_id = db_execute("""
                    INSERT INTO purchase_orders (name, partner_id, partner_name, date_order, date_planned, state, amount_total, notes)
                    VALUES (?, ?, ?, ?, ?, 'purchase', ?, ?)
                """, (po_name, vend_map[sel_vend], sel_vend, po_date.strftime("%Y-%m-%d %H:%M:%S"), po_del.strftime("%Y-%m-%d %H:%M:%S"), total_val, po_note))
                for ln in st.session_state.po_lines:
                    db_execute("""
                        INSERT INTO purchase_order_lines (order_id, product_id, product_name, product_qty, product_uom, price_unit, price_subtotal, name)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (po_id, ln["product_id"], ln["product_name"], ln["qty"], ln["uom"], ln["price"], ln["subtotal"], ln["product_name"]))
                # Create receipt picking
                rcpt_name = f"WH/IN/{po_name}"
                pick_id = db_execute("""
                    INSERT INTO stock_pickings (name, partner_id, partner_name, picking_type_code, picking_type_name, state, scheduled_date, origin, purchase_id)
                    VALUES (?, ?, ?, 'incoming', 'Receipts', 'assigned', ?, ?, ?)
                """, (rcpt_name, vend_map[sel_vend], sel_vend, po_del.strftime("%Y-%m-%d %H:%M:%S"), po_name, po_id))
                for ln in st.session_state.po_lines:
                    db_execute("""
                        INSERT INTO stock_moves (picking_id, product_id, product_name, product_uom_qty, quantity, product_uom, state, date)
                        VALUES (?, ?, ?, ?, ?, ?, 'assigned', ?)
                    """, (pick_id, ln["product_id"], ln["product_name"], ln["qty"], ln["qty"], ln["uom"], po_date.strftime("%Y-%m-%d %H:%M:%S")))
                st.session_state.po_lines = []
                st.success(f"✅ PO {po_name} confirmed & Incoming Receipt generated!")

    # ── EDIT PO ───────────────────────────────────────────────────────────
    elif sub == "✏️ Edit PO":
        st.title("✏️ Edit Purchase Order")
        po_list = db_query("SELECT * FROM purchase_orders WHERE state IN ('draft', 'sent') ORDER BY id DESC")
        if not po_list:
            st.info("No editable POs (draft/sent) found.")
        else:
            vend_map, _ = get_partners(vendor=True)
            prod_map, _ = get_products()
            uoms = get_uoms()
            po_opts = {f"{r['name']} — {r['partner_name']}": r for r in po_list}
            sel = st.selectbox("Select PO", list(po_opts.keys()))
            if sel:
                rec = po_opts[sel]
                eid = rec["id"]
                lines = db_query("SELECT * FROM purchase_order_lines WHERE order_id = ?", (eid,))

                curr_vend = rec["partner_name"]
                vend_list = sorted(vend_map.keys())
                new_vend = st.selectbox("Vendor", vend_list,
                    index=vend_list.index(curr_vend) if curr_vend in vend_list else 0)
                new_note = st.text_area("Notes", value=rec.get("notes") or "")

                if lines:
                    df_l = pd.DataFrame(lines)
                    df_l["price_subtotal"] = df_l["price_subtotal"].apply(fmt_idr)
                    st.dataframe(df_l[["product_name","product_qty","price_unit","product_uom","price_subtotal"]].rename(columns={
                        "product_name":"Product","product_qty":"Qty","price_unit":"Unit Cost",
                        "product_uom":"UoM","price_subtotal":"Subtotal"
                    }),use_container_width=True,hide_index=True)

                st.markdown("**Add Line:**")
                ep_names = ["-- Select --"] + sorted(prod_map.keys())
                ec1,ec2,ec3,ec4,ec5 = st.columns([3,1,1.5,1.5,1])
                ep = ec1.selectbox("Product",ep_names,key="epo_prod")
                eq = ec2.number_input("Qty",min_value=0.001,value=1.0,key="epo_qty")
                eu_names = [u["name"] for u in uoms]
                eu = ec3.selectbox("UoM",eu_names,key="epo_uom")
                ep_cost = float(prod_map[ep]["standard_price"]) if ep!="-- Select --" else 0.0
                epr = ec4.number_input("Cost",value=ep_cost,key="epo_price")
                ec5.markdown("<br>",unsafe_allow_html=True)
                if ec5.button("➕",key="epo_add"):
                    if ep != "-- Select --":
                        sub_t = eq * epr
                        db_execute("""
                            INSERT INTO purchase_order_lines (order_id, product_id, product_name, product_qty, product_uom, price_unit, price_subtotal, name)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (eid, prod_map[ep]["id"], ep, eq, eu, epr, sub_t, ep))
                        db_execute("""
                            UPDATE purchase_orders SET amount_total = (SELECT SUM(price_subtotal) FROM purchase_order_lines WHERE order_id = ?)
                            WHERE id = ?
                        """, (eid, eid))
                        st.success("Line added!")
                        st.rerun()

                st.markdown("---")
                ca,cb,cc = st.columns(3)
                if ca.button("💾 Save",type="primary"):
                    db_execute("""
                        UPDATE purchase_orders SET partner_id = ?, partner_name = ?, notes = ? WHERE id = ?
                    """, (vend_map[new_vend], new_vend, new_note, eid))
                    st.success("✅ PO updated!")
                if cb.button("✅ Confirm PO"):
                    db_execute("UPDATE purchase_orders SET state = 'purchase' WHERE id = ?", (eid,))
                    rcpt_name = f"WH/IN/{rec['name']}"
                    pick_id = db_execute("""
                        INSERT INTO stock_pickings (name, partner_id, partner_name, picking_type_code, picking_type_name, state, scheduled_date, origin, purchase_id)
                        VALUES (?, ?, ?, 'incoming', 'Receipts', 'assigned', ?, ?, ?)
                    """, (rcpt_name, vend_map[new_vend], new_vend, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), rec["name"], eid))
                    for ln in lines:
                        db_execute("""
                            INSERT INTO stock_moves (picking_id, product_id, product_name, product_uom_qty, quantity, product_uom, state, date)
                            VALUES (?, ?, ?, ?, ?, ?, 'assigned', ?)
                        """, (pick_id, ln["product_id"], ln["product_name"], ln["product_qty"], ln["product_qty"], ln["product_uom"], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    st.success("PO confirmed and receipt created!")
                    st.rerun()
                if cc.button("🗑️ Cancel PO"):
                    db_execute("UPDATE purchase_orders SET state = 'cancel' WHERE id = ?", (eid,))
                    st.warning("Cancelled.")
                    st.rerun()

    # ── RECEIVE / ACCEPT PURCHASE ─────────────────────────────────────────
    elif sub == "📥 Receive / Accept":
        st.title("📥 Receive / Accept Purchases")
        st.markdown("""
        <div style="background:#e8f5e9;border-left:4px solid #4caf50;padding:12px;border-radius:6px;margin-bottom:12px">
        Select a confirmed PO → inspect incoming line items → assign Lots/Batches → Validate to increment local warehouse inventory.
        </div>""", unsafe_allow_html=True)

        po_confirmed = db_query("SELECT id, name, partner_name FROM purchase_orders WHERE state = 'purchase' ORDER BY id DESC")
        if not po_confirmed:
            st.info("No confirmed POs ready to receive. Confirm a PO first.")
        else:
            po_rcv_opts = {f"{r['name']} — {r['partner_name']}": r["id"] for r in po_confirmed}
            sel_rcv = st.selectbox("Select Confirmed PO", list(po_rcv_opts.keys()))

            if sel_rcv:
                po_id = po_rcv_opts[sel_rcv]
                receipts = db_query("SELECT * FROM stock_pickings WHERE purchase_id = ? ORDER BY id DESC", (po_id,))
                if not receipts:
                    st.warning("No receipt found for this PO.")
                else:
                    for rcpt in receipts:
                        rcpt_id = rcpt["id"]
                        rcpt_name = rcpt["name"]
                        rcpt_state = rcpt["state"]
                        st.markdown(f"**Receipt:** {rcpt_name} — Status: {status_badge(rcpt_state)}")

                        if rcpt_state == "done":
                            st.success("✅ This receipt has already been validated and added to inventory.")
                            continue

                        moves_in = db_query("SELECT * FROM stock_moves WHERE picking_id = ?", (rcpt_id,))
                        if moves_in:
                            st.markdown('<div class="section-header">📦 Lines to Receive</div>', unsafe_allow_html=True)
                            rcv_data = []
                            for mv in moves_in:
                                col1,col2,col3,col4 = st.columns([3,1.5,1.5,2])
                                prod_name = mv["product_name"]
                                col1.write(f"**{prod_name}**")
                                demanded = mv["product_uom_qty"]
                                col2.write(f"Demanded: {demanded:,.2f}")
                                recv_qty = col3.number_input(
                                    "Recv Qty", min_value=0.0,
                                    value=float(demanded),
                                    step=0.5, key=f"rcv_qty_{mv['id']}")

                                lots_avail = get_lots(mv["product_id"])
                                lot_names = ["No Lot"] + [lt["name"] for lt in lots_avail]
                                recv_lot = col4.selectbox("Lot / Batch", lot_names, key=f"rcv_lot_{mv['id']}")
                                rcv_data.append({
                                    "move_id": mv["id"],
                                    "product_id": mv["product_id"],
                                    "product_name": mv["product_name"],
                                    "qty": recv_qty,
                                    "lot": recv_lot,
                                })

                            st.markdown("---")
                            if st.button("✅ Validate Receipt & Update Stock", type="primary", key=f"validate_{rcpt_id}"):
                                for rd in rcv_data:
                                    # Update move quantity
                                    db_execute("UPDATE stock_moves SET quantity = ?, state = 'done' WHERE id = ?", (rd["qty"], rd["move_id"]))
                                    # Add to stock_quants (Main warehouse lot_stock_id=8 or first internal)
                                    existing_quant = db_query("""
                                        SELECT id, quantity FROM stock_quants 
                                        WHERE product_id = ? AND location_id = 8
                                    """, (rd["product_id"],))
                                    if existing_quant:
                                        db_execute("""
                                            UPDATE stock_quants SET quantity = quantity + ? WHERE id = ?
                                        """, (rd["qty"], existing_quant[0]["id"]))
                                    else:
                                        db_execute("""
                                            INSERT INTO stock_quants (product_id, product_name, location_id, location_name, quantity, reserved_quantity)
                                            VALUES (?, ?, 8, 'WH/KJ/Stock Dadap', ?, 0)
                                        """, (rd["product_id"], rd["product_name"], rd["qty"]))
                                    # Update lot qty if assigned
                                    if rd["lot"] != "No Lot":
                                        db_execute("UPDATE stock_lots SET product_qty = product_qty + ? WHERE name = ?", (rd["qty"], rd["lot"]))

                                db_execute("UPDATE stock_pickings SET state = 'done', date_done = ? WHERE id = ?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), rcpt_id))
                                st.success(f"✅ Receipt {rcpt_name} validated! Stock successfully updated in Kultiva Database.")
                                st.rerun()

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from modules.odoo_client import (
    odoo_read, odoo_create, odoo_write, odoo_action, odoo_call,
    to_df, fmt_idr, status_badge, flatten_m2o,
    get_partners, get_products, get_uoms, get_lots
)

def render_purchasing():
    sub = st.radio("", ["📋 List","➕ Create PO","✏️ Edit PO","📥 Receive / Accept"],
        horizontal=True, label_visibility="collapsed")

    # ── LIST ──────────────────────────────────────────────────────────────
    if sub == "📋 List":
        st.title("🛒 Purchase Orders")
        with st.spinner():
            po = odoo_read("purchase.order",[],
                ["name","partner_id","state","amount_total","date_order",
                 "date_approve","user_id","invoice_status"],
                limit=300, order="date_order desc")
        if po:
            df = to_df(po)
            df["date_order"] = pd.to_datetime(df["date_order"],errors="coerce")
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Total POs", len(df))
            c2.metric("Confirmed", len(df[df["state"]=="purchase"]))
            c3.metric("Draft", len(df[df["state"]=="draft"]))
            c4.metric("Total Value", fmt_idr(df["amount_total"].sum()))

            srch = st.text_input("🔍 Search")
            if srch:
                df = df[df["partner_id"].str.contains(srch,case=False,na=False)|
                        df["name"].str.contains(srch,case=False,na=False)]

            disp = df[["name","partner_id","state","amount_total","date_order"]].copy()
            disp.columns = ["PO","Vendor","Status","Total","Date"]
            disp["Total"] = disp["Total"].apply(fmt_idr)
            disp["Date"] = disp["Date"].dt.strftime("%d %b %Y")
            disp["Status"] = disp["Status"].apply(status_badge)
            st.dataframe(disp,use_container_width=True,hide_index=True)

            # Quick confirm
            po_opts = {f"{r['name']} — {flatten_m2o(r['partner_id'])}": r for r in po}
            sel_po_name = st.selectbox("Select PO for action", list(po_opts.keys()))
            if sel_po_name:
                sel_po = po_opts[sel_po_name]
                ca,cb,cc = st.columns(3)
                if sel_po["state"] == "draft":
                    if ca.button("✅ Confirm PO"):
                        odoo_action("purchase.order","button_confirm",sel_po["id"])
                        st.success("PO confirmed!"); st.cache_data.clear(); st.rerun()
                if sel_po["state"] in ["draft"]:
                    if cc.button("🗑️ Cancel"):
                        odoo_action("purchase.order","button_cancel",sel_po["id"])
                        st.warning("PO cancelled."); st.cache_data.clear(); st.rerun()

    # ── CREATE PO ─────────────────────────────────────────────────────────
    elif sub == "➕ Create PO":
        st.title("➕ Create Purchase Order")

        vend_map, vend_recs = get_partners(vendor=True)
        prod_map, prod_recs  = get_products()
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
                uom_id = next((u["id"] for u in uoms if u["name"]==cp_uom),None)
                st.session_state.po_lines.append({
                    "product_name": cp_prod,
                    "product_id":   prod_map[cp_prod]["id"],
                    "qty":          cp_qty,
                    "uom":          cp_uom,
                    "uom_id":       uom_id,
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
                with st.spinner("Creating PO..."):
                    po_id = odoo_create("purchase.order",{
                        "partner_id": vend_map[sel_vend],
                        "date_order": po_date.strftime("%Y-%m-%d %H:%M:%S"),
                        "date_planned": po_del.strftime("%Y-%m-%d %H:%M:%S"),
                        "notes": po_note,
                    })
                    if po_id:
                        for ln in st.session_state.po_lines:
                            odoo_create("purchase.order.line",{
                                "order_id":    po_id,
                                "product_id":  ln["product_id"],
                                "product_qty": ln["qty"],
                                "product_uom": ln["uom_id"],
                                "price_unit":  ln["price"],
                                "date_planned": po_del.strftime("%Y-%m-%d %H:%M:%S"),
                                "name":        ln["product_name"],
                            })
                        st.session_state.po_lines = []
                        st.cache_data.clear()
                        st.success(f"✅ PO created! ID: {po_id}")

        if col_s2.button("✅ Save & Confirm"):
            if sel_vend == "-- Select Vendor --":
                st.error("Select a vendor.")
            elif not st.session_state.po_lines:
                st.error("Add at least one line.")
            else:
                with st.spinner():
                    po_id = odoo_create("purchase.order",{
                        "partner_id": vend_map[sel_vend],
                        "date_order": po_date.strftime("%Y-%m-%d %H:%M:%S"),
                        "date_planned": po_del.strftime("%Y-%m-%d %H:%M:%S"),
                        "notes": po_note,
                    })
                    if po_id:
                        for ln in st.session_state.po_lines:
                            odoo_create("purchase.order.line",{
                                "order_id":    po_id,
                                "product_id":  ln["product_id"],
                                "product_qty": ln["qty"],
                                "product_uom": ln["uom_id"],
                                "price_unit":  ln["price"],
                                "date_planned": po_del.strftime("%Y-%m-%d %H:%M:%S"),
                                "name":        ln["product_name"],
                            })
                        odoo_action("purchase.order","button_confirm",po_id)
                        st.session_state.po_lines = []
                        st.cache_data.clear()
                        st.success(f"✅ PO #{po_id} confirmed!")

    # ── EDIT PO ───────────────────────────────────────────────────────────
    elif sub == "✏️ Edit PO":
        st.title("✏️ Edit Purchase Order")
        with st.spinner():
            po_list = odoo_read("purchase.order",[["state","in",["draft","sent"]]],
                ["id","name","partner_id","state","amount_total","notes"],
                limit=100, order="date_order desc")

        if not po_list:
            st.info("No editable POs (draft/sent) found.")
        else:
            vend_map, _ = get_partners(vendor=True)
            prod_map, _ = get_products()
            uoms = get_uoms()
            po_opts = {f"{r['name']} — {flatten_m2o(r['partner_id'])}": r["id"] for r in po_list}
            sel = st.selectbox("Select PO", list(po_opts.keys()))
            if sel:
                eid = po_opts[sel]
                rec = next(r for r in po_list if r["id"]==eid)
                lines = odoo_read("purchase.order.line",[["order_id","=",eid]],
                    ["id","product_id","product_qty","price_unit","product_uom","price_subtotal"])

                curr_vend = flatten_m2o(rec["partner_id"])
                vend_list = sorted(vend_map.keys())
                new_vend = st.selectbox("Vendor", vend_list,
                    index=vend_list.index(curr_vend) if curr_vend in vend_list else 0)
                new_note = st.text_area("Notes", value=rec.get("notes","") or "")

                if lines:
                    df_l = to_df(lines)
                    df_l["price_subtotal"] = df_l["price_subtotal"].apply(fmt_idr)
                    st.dataframe(df_l[["product_id","product_qty","price_unit","product_uom","price_subtotal"]].rename(columns={
                        "product_id":"Product","product_qty":"Qty","price_unit":"Unit Cost",
                        "product_uom":"UoM","price_subtotal":"Subtotal"
                    }),use_container_width=True,hide_index=True)

                # Add line
                st.markdown("**Add line:**")
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
                        uom_id = next((u["id"] for u in uoms if u["name"]==eu),None)
                        odoo_create("purchase.order.line",{
                            "order_id": eid,
                            "product_id": prod_map[ep]["id"],
                            "product_qty": eq,
                            "product_uom": uom_id,
                            "price_unit": epr,
                            "date_planned": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "name": ep,
                        })
                        st.success("Line added!"); st.cache_data.clear(); st.rerun()

                st.markdown("---")
                ca,cb,cc = st.columns(3)
                if ca.button("💾 Save",type="primary"):
                    odoo_write("purchase.order",eid,{
                        "partner_id": vend_map[new_vend],
                        "notes": new_note,
                    })
                    st.success("✅ PO updated!"); st.cache_data.clear()
                if cb.button("✅ Confirm PO"):
                    odoo_action("purchase.order","button_confirm",eid)
                    st.success("PO confirmed!"); st.cache_data.clear(); st.rerun()
                if cc.button("🗑️ Cancel PO"):
                    odoo_action("purchase.order","button_cancel",eid)
                    st.warning("Cancelled."); st.cache_data.clear(); st.rerun()

    # ── RECEIVE / ACCEPT PURCHASE ─────────────────────────────────────────
    elif sub == "📥 Receive / Accept":
        st.title("📥 Receive / Accept Purchases")
        st.markdown("""
        <div style="background:#e8f5e9;border-left:4px solid #4caf50;padding:12px;border-radius:6px;margin-bottom:12px">
        Select a confirmed PO → view incoming receipt → set quantities received (with lots if tracked) → Validate to update stock.
        </div>""", unsafe_allow_html=True)

        with st.spinner():
            po_confirmed = odoo_read("purchase.order",
                [["state","=","purchase"]],
                ["id","name","partner_id","amount_total","date_order"],
                limit=100, order="date_order desc")

        if not po_confirmed:
            st.info("No confirmed POs to receive. Confirm a PO first.")
        else:
            po_rcv_opts = {f"{r['name']} — {flatten_m2o(r['partner_id'])}": r["id"] for r in po_confirmed}
            sel_rcv = st.selectbox("Select Confirmed PO", list(po_rcv_opts.keys()))

            if sel_rcv:
                po_id = po_rcv_opts[sel_rcv]

                with st.spinner("Loading receipts..."):
                    receipts = odoo_read("stock.picking",
                        [["purchase_id","=",po_id]],
                        ["id","name","state","scheduled_date","picking_type_id"],
                        limit=10)

                if not receipts:
                    st.warning("No receipt found for this PO.")
                else:
                    for rcpt in receipts:
                        rcpt_id    = rcpt["id"]
                        rcpt_name  = rcpt["name"]
                        rcpt_state = rcpt["state"]
                        st.markdown(f"**Receipt:** {rcpt_name} — Status: {status_badge(rcpt_state)}")

                        if rcpt_state == "done":
                            st.success("✅ This receipt has already been validated.")
                            continue
                        if rcpt_state == "cancel":
                            st.error("❌ This receipt is cancelled.")
                            continue

                        moves_in = odoo_read("stock.move",
                            [["picking_id","=",rcpt_id]],
                            ["id","product_id","product_uom_qty","quantity","product_uom","lot_ids","state"],
                            limit=50)

                        if moves_in:
                            st.markdown('<div class="section-header">📦 Lines to Receive</div>', unsafe_allow_html=True)

                            rcv_data = []
                            for mv in moves_in:
                                col1,col2,col3,col4 = st.columns([3,1.5,1.5,2])
                                prod_name = flatten_m2o(mv["product_id"])
                                col1.write(f"**{prod_name}**")
                                demanded = mv["product_uom_qty"]
                                col2.write(f"Demanded: {demanded:,.2f}")
                                recv_qty = col3.number_input(
                                    "Recv Qty", min_value=0.0,
                                    value=float(demanded),
                                    step=0.5, key=f"rcv_qty_{mv['id']}")

                                lots_avail = get_lots(mv["product_id"][0] if isinstance(mv["product_id"],list) else None)
                                lot_names = ["No Lot"] + [lt["name"] for lt in lots_avail]
                                recv_lot = col4.selectbox("Lot",lot_names,key=f"rcv_lot_{mv['id']}")
                                rcv_data.append({
                                    "move_id": mv["id"],
                                    "product_id": mv["product_id"],
                                    "qty": recv_qty,
                                    "lot": recv_lot,
                                })

                            st.markdown("---")
                            col_v1,col_v2 = st.columns(2)
                            if col_v1.button("✅ Validate Receipt (Full)", type="primary", key=f"validate_{rcpt_id}"):
                                with st.spinner("Validating..."):
                                    for rd in rcv_data:
                                        odoo_write("stock.move", rd["move_id"],
                                            {"quantity": rd["qty"]})

                                    res = odoo_action("stock.picking","button_validate",rcpt_id)
                                    if res is not None:
                                        if isinstance(res, dict) and res.get("res_model"):
                                            st.info("Backorder dialog triggered — validating immediately.")
                                            odoo_call("stock.picking","_action_done",[[rcpt_id]])
                                        st.success(f"✅ Receipt {rcpt_name} validated! Stock updated.")
                                        st.cache_data.clear(); st.rerun()

                            if col_v2.button("⏩ Create Backorder", key=f"backorder_{rcpt_id}"):
                                st.info("Partial receive: validate and a backorder will be created for remaining qty.")

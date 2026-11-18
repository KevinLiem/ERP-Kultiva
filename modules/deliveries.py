import streamlit as st
import pandas as pd
from datetime import datetime
from modules.odoo_client import (
    odoo_read, odoo_action, to_df, status_badge, flatten_m2o
)

def render_deliveries():
    st.title("🚚 Deliveries & Surat Jalan")
    tab_del,tab_sj = st.tabs(["📋 Deliveries","📄 Surat Jalan"])

    # ── DELIVERIES ────────────────────────────────────────────────────────
    with tab_del:
        col_f1,col_f2 = st.columns(2)
        type_filter = col_f1.selectbox("Type",["All","outgoing","incoming","internal"])
        state_filter = col_f2.multiselect("Status",
            ["draft","confirmed","assigned","done","cancel"],
            default=["confirmed","assigned","done"])

        domain = [["state","in",state_filter]]
        if type_filter != "All":
            domain.append(["picking_type_code","=",type_filter])

        with st.spinner():
            picks = odoo_read("stock.picking",domain,
                ["name","partner_id","state","scheduled_date","date_done",
                 "picking_type_id","origin","picking_type_code"],
                limit=400,order="scheduled_date desc")

        if picks:
            df = to_df(picks)
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Total", len(df))
            c2.metric("Done", len(df[df["state"]=="done"]))
            c3.metric("Ready", len(df[df["state"]=="assigned"]))
            c4.metric("Waiting", len(df[df["state"].isin(["confirmed","waiting"])]))

            srch = st.text_input("🔍 Search")
            df_f = df
            if srch:
                df_f = df[df["partner_id"].str.contains(srch,case=False,na=False)|
                         df["name"].str.contains(srch,case=False,na=False)]

            disp = df_f[["name","partner_id","picking_type_id","state","scheduled_date","origin"]].copy()
            disp.columns = ["Ref","Partner","Type","Status","Scheduled","Source"]
            disp["Status"] = disp["Status"].apply(status_badge)
            disp["Scheduled"] = pd.to_datetime(disp["Scheduled"],errors="coerce").dt.strftime("%d %b %Y")
            st.dataframe(disp,use_container_width=True,hide_index=True)

            st.markdown('<div class="section-header">⚡ Validate Delivery</div>', unsafe_allow_html=True)
            ready_picks = {r["name"]: r["id"] for r in picks if r["state"]=="assigned"}
            if ready_picks:
                sel_pick = st.selectbox("Select Ready Delivery", list(ready_picks.keys()))
                if st.button("✅ Validate Delivery", type="primary"):
                    res = odoo_action("stock.picking","button_validate",ready_picks[sel_pick])
                    if res is not None:
                        st.success(f"✅ {sel_pick} validated!")
                        st.cache_data.clear(); st.rerun()
            else:
                st.info("No deliveries in 'Ready' state.")

    # ── SURAT JALAN ───────────────────────────────────────────────────────
    with tab_sj:
        st.markdown('<div class="section-header">📄 Surat Jalan (Delivery Order)</div>', unsafe_allow_html=True)
        st.markdown("Select any delivery to generate a Surat Jalan.")

        with st.spinner():
            all_picks = odoo_read("stock.picking",
                [["picking_type_code","=","outgoing"]],
                ["id","name","partner_id","state","scheduled_date","date_done","origin","company_id"],
                limit=300,order="scheduled_date desc")

        if all_picks:
            sj_opts = {f"{r['name']} — {flatten_m2o(r['partner_id'])}": r for r in all_picks}
            sel_sj_name = st.selectbox("Select Delivery", list(sj_opts.keys()))

            if sel_sj_name:
                sj_rec = sj_opts[sel_sj_name]
                sj_id  = sj_rec["id"]

                with st.spinner("Loading delivery lines..."):
                    sj_moves = odoo_read("stock.move",
                        [["picking_id","=",sj_id],["state","=","done"]],
                        ["product_id","product_uom_qty","quantity","product_uom","lot_ids","description_picking"],
                        limit=50)
                    sj_move_lines = odoo_read("stock.move.line",
                        [["picking_id","=",sj_id]],
                        ["product_id","quantity","product_uom_id","lot_id","location_dest_id"],
                        limit=100)

                company = odoo_read("res.company",[],["name","street","city","phone","email","website"],limit=1)
                comp = company[0] if company else {}

                partner_name = flatten_m2o(sj_rec["partner_id"])
                sched_date   = sj_rec.get("scheduled_date","")
                done_date    = sj_rec.get("date_done","")
                origin       = sj_rec.get("origin","")

                sj_html = f"""
                <div class="surat-jalan">
                    <div style="display:flex;justify-content:space-between;border-bottom:2px solid #333;padding-bottom:12px;margin-bottom:12px">
                        <div>
                            <h2 style="margin:0;font-size:1.3rem">🌱 {flatten_m2o(sj_rec.get('company_id','Kultiva'))}</h2>
                            <p style="margin:4px 0;font-size:.8rem">{comp.get('street','')}<br>{comp.get('city','')}</p>
                            <p style="margin:0;font-size:.8rem">📞 {comp.get('phone','')} | 📧 {comp.get('email','')}</p>
                        </div>
                        <div style="text-align:right">
                            <h2 style="margin:0;font-size:1.3rem;color:#2e7d32">SURAT JALAN</h2>
                            <p style="margin:4px 0"><b>No:</b> {sj_rec['name']}</p>
                            <p style="margin:0"><b>Tanggal:</b> {sched_date[:10] if sched_date else ''}</p>
                        </div>
                    </div>
                    <table style="width:100%;margin-bottom:16px;font-size:.85rem">
                        <tr>
                            <td style="width:50%;vertical-align:top">
                                <b>Kepada:</b><br>
                                {partner_name}<br>
                            </td>
                            <td style="width:50%;vertical-align:top">
                                <b>Referensi SO:</b> {origin}<br>
                                <b>Tgl Kirim:</b> {sched_date[:10] if sched_date else 'TBD'}<br>
                                <b>Tgl Selesai:</b> {done_date[:10] if done_date else '-'}<br>
                                <b>Status:</b> {status_badge(sj_rec['state'])}
                            </td>
                        </tr>
                    </table>
                    <table style="width:100%;border-collapse:collapse;font-size:.83rem">
                        <thead>
                            <tr style="background:#2e7d32;color:white">
                                <th style="padding:8px;border:1px solid #555;text-align:left">No</th>
                                <th style="padding:8px;border:1px solid #555;text-align:left">Produk</th>
                                <th style="padding:8px;border:1px solid #555;text-align:left">No. Lot/Batch</th>
                                <th style="padding:8px;border:1px solid #555;text-align:right">Qty</th>
                                <th style="padding:8px;border:1px solid #555;text-align:left">Satuan</th>
                            </tr>
                        </thead>
                        <tbody>
                """

                if sj_move_lines:
                    for i, ml in enumerate(sj_move_lines, 1):
                        prod  = flatten_m2o(ml["product_id"])
                        lot   = flatten_m2o(ml.get("lot_id","")) or "-"
                        qty   = ml.get("quantity", 0)
                        uom   = flatten_m2o(ml.get("product_uom_id",""))
                        row_bg = "#f9f9f9" if i % 2 == 0 else "white"
                        sj_html += f"""
                            <tr style="background:{row_bg}">
                                <td style="padding:7px;border:1px solid #ddd">{i}</td>
                                <td style="padding:7px;border:1px solid #ddd">{prod}</td>
                                <td style="padding:7px;border:1px solid #ddd">{lot}</td>
                                <td style="padding:7px;border:1px solid #ddd;text-align:right">{qty:,.2f}</td>
                                <td style="padding:7px;border:1px solid #ddd">{uom}</td>
                            </tr>"""
                elif sj_moves:
                    for i, mv in enumerate(sj_moves, 1):
                        prod = flatten_m2o(mv["product_id"])
                        qty  = mv.get("quantity", mv.get("product_uom_qty",0))
                        uom  = flatten_m2o(mv.get("product_uom",""))
                        row_bg = "#f9f9f9" if i % 2 == 0 else "white"
                        sj_html += f"""
                            <tr style="background:{row_bg}">
                                <td style="padding:7px;border:1px solid #ddd">{i}</td>
                                <td style="padding:7px;border:1px solid #ddd">{prod}</td>
                                <td style="padding:7px;border:1px solid #ddd">-</td>
                                <td style="padding:7px;border:1px solid #ddd;text-align:right">{qty:,.2f}</td>
                                <td style="padding:7px;border:1px solid #ddd">{uom}</td>
                            </tr>"""

                sj_html += """
                        </tbody>
                    </table>
                    <div style="margin-top:40px;display:flex;justify-content:space-between;font-size:.82rem">
                        <div style="text-align:center">
                            <p>Disiapkan oleh,</p>
                            <br><br><br>
                            <p style="border-top:1px solid #333;padding-top:4px">( _________________ )</p>
                        </div>
                        <div style="text-align:center">
                            <p>Dikirim oleh,</p>
                            <br><br><br>
                            <p style="border-top:1px solid #333;padding-top:4px">( _________________ )</p>
                        </div>
                        <div style="text-align:center">
                            <p>Diterima oleh,</p>
                            <br><br><br>
                            <p style="border-top:1px solid #333;padding-top:4px">( _________________ )</p>
                        </div>
                    </div>
                    <p style="margin-top:20px;font-size:.75rem;color:#666;text-align:center">
                        Dokumen ini diterbitkan oleh sistem Kultiva ERP • """ + datetime.now().strftime('%d %B %Y %H:%M') + """
                    </p>
                </div>
                """

                st.markdown(sj_html, unsafe_allow_html=True)
                st.markdown("---")
                st.info("💡 To print: use **Ctrl+P** or **right-click → Print** in your browser. Set margins to None for best result.")

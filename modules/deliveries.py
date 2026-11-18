import streamlit as st
import pandas as pd
from datetime import datetime
from modules.db import (
    db_query, db_query_df, db_execute, status_badge
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

        state_filter_str = "('" + "', '".join(state_filter) + "')" if state_filter else "('')"
        q = f"SELECT * FROM stock_pickings WHERE state IN {state_filter_str}"
        params = []
        if type_filter != "All":
            q += " AND picking_type_code = ?"
            params.append(type_filter)
        q += " ORDER BY id DESC LIMIT 400"

        df = db_query_df(q, params=params if params else None)
        if not df.empty:
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Total Deliveries", len(df))
            c2.metric("Done", len(df[df["state"]=="done"]))
            c3.metric("Ready", len(df[df["state"]=="assigned"]))
            c4.metric("Waiting/Confirmed", len(df[df["state"].isin(["confirmed","waiting"])]))

            srch = st.text_input("🔍 Search Reference / Partner")
            if srch:
                df = df[df["partner_name"].str.contains(srch,case=False,na=False)|
                        df["name"].str.contains(srch,case=False,na=False)]

            disp = df[["name","partner_name","picking_type_name","state","scheduled_date","origin"]].copy()
            disp.columns = ["Ref","Partner","Type","Status","Scheduled","Source"]
            disp["Status"] = disp["Status"].apply(status_badge)
            disp["Scheduled"] = pd.to_datetime(disp["Scheduled"], errors="coerce").dt.strftime("%d %b %Y")
            st.dataframe(disp, use_container_width=True, hide_index=True)

            st.markdown('<div class="section-header">⚡ Validate Delivery Order</div>', unsafe_allow_html=True)
            ready_picks = db_query("SELECT id, name FROM stock_pickings WHERE state = 'assigned' AND picking_type_code = 'outgoing' ORDER BY id DESC LIMIT 50")
            if ready_picks:
                pick_opts = {p["name"]: p["id"] for p in ready_picks}
                sel_pick = st.selectbox("Select Ready Delivery", list(pick_opts.keys()))
                if st.button("✅ Validate Delivery & Deduct Inventory", type="primary"):
                    p_id = pick_opts[sel_pick]
                    # Update stock_moves to done and deduct from stock_quants
                    moves = db_query("SELECT product_id, product_name, quantity FROM stock_moves WHERE picking_id = ?", (p_id,))
                    for mv in moves:
                        db_execute("""
                            UPDATE stock_quants SET quantity = MAX(0, quantity - ?) 
                            WHERE product_id = ?
                        """, (mv["quantity"], mv["product_id"]))
                    db_execute("UPDATE stock_moves SET state = 'done' WHERE picking_id = ?", (p_id,))
                    db_execute("UPDATE stock_pickings SET state = 'done', date_done = ? WHERE id = ?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), p_id))
                    st.success(f"✅ Delivery {sel_pick} marked Done and stock deducted from Kultiva DB!")
                    st.rerun()
            else:
                st.info("No delivery orders currently in 'Ready / Assigned' status.")

    # ── SURAT JALAN ───────────────────────────────────────────────────────
    with tab_sj:
        st.markdown('<div class="section-header">📄 Surat Jalan (Delivery Order)</div>', unsafe_allow_html=True)
        st.markdown("Select any outgoing delivery order to generate an official Surat Jalan document.")

        all_picks = db_query("""
            SELECT id, name, partner_name, state, scheduled_date, date_done, origin 
            FROM stock_pickings 
            WHERE picking_type_code = 'outgoing' 
            ORDER BY id DESC LIMIT 300
        """)
        if all_picks:
            sj_opts = {f"{r['name']} — {r['partner_name']}": r for r in all_picks}
            sel_sj_name = st.selectbox("Select Delivery Order", list(sj_opts.keys()))

            if sel_sj_name:
                sj_rec = sj_opts[sel_sj_name]
                sj_id  = sj_rec["id"]

                moves = db_query("SELECT * FROM stock_moves WHERE picking_id = ?", (sj_id,))
                partner_name = sj_rec["partner_name"] or "Pelanggan"
                sched_date   = sj_rec.get("scheduled_date") or ""
                done_date    = sj_rec.get("date_done") or ""
                origin       = sj_rec.get("origin") or "-"

                sj_html = f"""
                <div class="surat-jalan">
                    <div style="display:flex;justify-content:space-between;border-bottom:2px solid #333;padding-bottom:12px;margin-bottom:12px">
                        <div>
                            <h2 style="margin:0;font-size:1.3rem">🌱 PT KULTIVA CO. INDONESIA</h2>
                            <p style="margin:4px 0;font-size:.8rem">Kultiva Jakarta Central Facility<br>Tangerang / Jakarta, Indonesia</p>
                            <p style="margin:0;font-size:.8rem">📞 +62 21-8899-7711 | 📧 ppicjkt@kultivaco.com</p>
                        </div>
                        <div style="text-align:right">
                            <h2 style="margin:0;font-size:1.3rem;color:#2e7d32">SURAT JALAN</h2>
                            <p style="margin:4px 0"><b>No. Dokumen:</b> {sj_rec['name']}</p>
                            <p style="margin:0"><b>Tanggal Cetak:</b> {datetime.now().strftime('%d %b %Y')}</p>
                        </div>
                    </div>
                    <table style="width:100%;margin-bottom:16px;font-size:.85rem">
                        <tr>
                            <td style="width:50%;vertical-align:top">
                                <b>Penerima / Kepada:</b><br>
                                <span style="font-size:1.05em;font-weight:bold">{partner_name}</span><br>
                                Alamat Tujuan Pengiriman Sesuai PO / SO
                            </td>
                            <td style="width:50%;vertical-align:top">
                                <b>Referensi SO:</b> {origin}<br>
                                <b>Tgl Rencana Kirim:</b> {sched_date[:10] if sched_date else 'TBD'}<br>
                                <b>Tgl Selesai / Realisasi:</b> {done_date[:10] if done_date else '-'}<br>
                                <b>Status Dokumen:</b> {status_badge(sj_rec['state'])}
                            </td>
                        </tr>
                    </table>
                    <table style="width:100%;border-collapse:collapse;font-size:.83rem">
                        <thead>
                            <tr style="background:#2e7d32;color:white">
                                <th style="padding:8px;border:1px solid #555;text-align:left">No</th>
                                <th style="padding:8px;border:1px solid #555;text-align:left">Nama Produk / Barang</th>
                                <th style="padding:8px;border:1px solid #555;text-align:left">No. Lot / Batch</th>
                                <th style="padding:8px;border:1px solid #555;text-align:right">Kuantitas</th>
                                <th style="padding:8px;border:1px solid #555;text-align:left">Satuan</th>
                            </tr>
                        </thead>
                        <tbody>
                """

                if moves:
                    for i, mv in enumerate(moves, 1):
                        prod = mv["product_name"]
                        lot = mv.get("lot_name") or "-"
                        qty = mv.get("quantity", mv.get("product_uom_qty", 0.0))
                        uom = mv.get("product_uom") or "Unit"
                        row_bg = "#f9f9f9" if i % 2 == 0 else "white"
                        sj_html += f"""
                            <tr style="background:{row_bg}">
                                <td style="padding:7px;border:1px solid #ddd">{i}</td>
                                <td style="padding:7px;border:1px solid #ddd">{prod}</td>
                                <td style="padding:7px;border:1px solid #ddd">{lot}</td>
                                <td style="padding:7px;border:1px solid #ddd;text-align:right">{qty:,.2f}</td>
                                <td style="padding:7px;border:1px solid #ddd">{uom}</td>
                            </tr>"""
                else:
                    sj_html += """
                        <tr>
                            <td colspan="5" style="text-align:center;padding:15px;color:#888">Tidak ada baris barang yang terdaftar pada delivery order ini.</td>
                        </tr>
                    """

                sj_html += f"""
                        </tbody>
                    </table>
                    <div style="margin-top:40px;display:flex;justify-content:space-between;font-size:.82rem">
                        <div style="text-align:center">
                            <p>Disiapkan oleh / Gudang,</p>
                            <br><br><br>
                            <p style="border-top:1px solid #333;padding-top:4px">( PPIC / Admin WH )</p>
                        </div>
                        <div style="text-align:center">
                            <p>Dikirim oleh / Kurir,</p>
                            <br><br><br>
                            <p style="border-top:1px solid #333;padding-top:4px">( Driver / Ekspedisi )</p>
                        </div>
                        <div style="text-align:center">
                            <p>Diterima oleh / Customer,</p>
                            <br><br><br>
                            <p style="border-top:1px solid #333;padding-top:4px">( Tanda Tangan & Cap )</p>
                        </div>
                    </div>
                    <p style="margin-top:25px;font-size:.75rem;color:#666;text-align:center">
                        Dokumen resmi yang diterbitkan oleh Kultiva ERP Database • {datetime.now().strftime('%d %B %Y %H:%M:%S')}
                    </p>
                </div>
                """

                st.markdown(sj_html, unsafe_allow_html=True)
                st.markdown("---")
                st.info("💡 Klik **Ctrl+P** atau klik kanan → **Print** untuk mencetak Surat Jalan fisik.")

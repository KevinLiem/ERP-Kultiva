import streamlit as st
import pandas as pd
import plotly.express as px
from modules.db import db_count, db_query_df, fmt_idr, status_badge

def render_dashboard():
    st.markdown("""
    <div class="kultiva-header">
        <h1>🌱 Kultiva ERP Dashboard</h1>
        <p>Independent ERP System — Powered by Kultiva Enterprise DB</p>
    </div>""", unsafe_allow_html=True)

    with st.spinner("Loading KPIs..."):
        c1,c2,c3,c4,c5,c6 = st.columns(6)
        c1.metric("🧾 Sales Orders", db_count("sale_orders"))
        c2.metric("✅ Confirmed SO", db_count("sale_orders", "state IN ('sale', 'done')"))
        c3.metric("🛒 Open POs", db_count("purchase_orders", "state IN ('purchase', 'sent', 'draft')"))
        c4.metric("🚚 Deliveries", db_count("stock_pickings", "picking_type_code = 'outgoing'"))
        c5.metric("📦 Products", db_count("products", "active = 1"))
        c6.metric("👥 Customers", db_count("partners", "customer_rank > 0"))

    # Revenue
    st.markdown('<div class="section-header">📈 Revenue Trend</div>', unsafe_allow_html=True)
    with st.spinner():
        df_inv = db_query_df("""
            SELECT partner_name, amount_total, invoice_date 
            FROM invoices 
            WHERE move_type = 'out_invoice' AND state = 'posted' AND invoice_date != ''
            ORDER BY invoice_date ASC
        """)
    if not df_inv.empty:
        df_inv["invoice_date"] = pd.to_datetime(df_inv["invoice_date"], errors="coerce")
        df_inv["month"] = df_inv["invoice_date"].dt.to_period("M").astype(str)
        monthly = df_inv.groupby("month")["amount_total"].sum().reset_index()
        monthly.columns = ["Month","Revenue"]
        col_a, col_b = st.columns([2,1])
        with col_a:
            fig = px.bar(monthly, x="Month", y="Revenue", color_discrete_sequence=["#4caf50"],
                title="Monthly Revenue (IDR)", text_auto=".2s")
            fig.update_layout(height=300, margin=dict(t=40,b=0,l=0,r=0))
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            top = df_inv.groupby("partner_name")["amount_total"].sum().nlargest(7).reset_index()
            fig2 = px.pie(top, names="partner_name", values="amount_total", hole=0.4,
                title="Top Customers", color_discrete_sequence=px.colors.qualitative.Set2)
            fig2.update_layout(height=300, margin=dict(t=40,b=0,l=0,r=0))
            st.plotly_chart(fig2, use_container_width=True)

    # Recent SOs
    st.markdown('<div class="section-header">🕐 Recent Sales Orders</div>', unsafe_allow_html=True)
    df_so = db_query_df("""
        SELECT name, partner_name, state, amount_total, date_order 
        FROM sale_orders 
        ORDER BY id DESC LIMIT 10
    """)
    if not df_so.empty:
        df_so["amount_total"] = df_so["amount_total"].apply(fmt_idr)
        df_so["date_order"] = pd.to_datetime(df_so["date_order"], errors="coerce").dt.strftime("%d %b %Y")
        df_so["state"] = df_so["state"].apply(status_badge)
        df_so.columns = ["Order #","Customer","Status","Total","Date"]
        st.dataframe(df_so, use_container_width=True, hide_index=True)

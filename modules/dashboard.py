import streamlit as st
import pandas as pd
import plotly.express as px
from modules.odoo_client import odoo_read, odoo_count, to_df, fmt_idr, status_badge

def render_dashboard():
    st.markdown("""
    <div class="kultiva-header">
        <h1>🌱 Kultiva ERP Dashboard</h1>
        <p>Live operations overview — Odoo 19 Enterprise</p>
    </div>""", unsafe_allow_html=True)

    with st.spinner("Loading KPIs..."):
        c1,c2,c3,c4,c5,c6 = st.columns(6)
        c1.metric("🧾 Sales Orders", odoo_count("sale.order"))
        c2.metric("✅ Confirmed SO", odoo_count("sale.order",[["state","in",["sale","done"]]]))
        c3.metric("🛒 Open POs", odoo_count("purchase.order",[["state","in",["purchase","sent","draft"]]]))
        c4.metric("🚚 Deliveries", odoo_count("stock.picking",[["picking_type_code","=","outgoing"]]))
        c5.metric("📦 Products", odoo_count("product.template",[["active","=",True]]))
        c6.metric("👥 Customers", odoo_count("res.partner",[["customer_rank",">",0]]))

    # Revenue
    st.markdown('<div class="section-header">📈 Revenue Trend</div>', unsafe_allow_html=True)
    with st.spinner():
        inv = odoo_read("account.move",
            [["move_type","=","out_invoice"],["state","=","posted"]],
            ["partner_id","amount_total","invoice_date"], limit=300, order="invoice_date asc")
    if inv:
        df = to_df(inv)
        df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")
        df["month"] = df["invoice_date"].dt.to_period("M").astype(str)
        monthly = df.groupby("month")["amount_total"].sum().reset_index()
        monthly.columns = ["Month","Revenue"]
        col_a, col_b = st.columns([2,1])
        with col_a:
            fig = px.bar(monthly, x="Month", y="Revenue", color_discrete_sequence=["#4caf50"],
                title="Monthly Revenue (IDR)", text_auto=".2s")
            fig.update_layout(height=300, margin=dict(t=40,b=0,l=0,r=0))
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            top = df.groupby("partner_id")["amount_total"].sum().nlargest(7).reset_index()
            fig2 = px.pie(top, names="partner_id", values="amount_total", hole=0.4,
                title="Top Customers", color_discrete_sequence=px.colors.qualitative.Set2)
            fig2.update_layout(height=300, margin=dict(t=40,b=0,l=0,r=0))
            st.plotly_chart(fig2, use_container_width=True)

    # Recent SOs
    st.markdown('<div class="section-header">🕐 Recent Sales Orders</div>', unsafe_allow_html=True)
    so = odoo_read("sale.order",[],["name","partner_id","state","amount_total","date_order"],
        limit=10, order="date_order desc")
    if so:
        df = to_df(so)
        df["amount_total"] = df["amount_total"].apply(fmt_idr)
        df["date_order"] = pd.to_datetime(df["date_order"]).dt.strftime("%d %b %Y")
        df["state"] = df["state"].apply(status_badge)
        df.columns = ["ID","Order","Customer","Status","Total","Date"]
        st.dataframe(df[["Order","Customer","Status","Total","Date"]], use_container_width=True, hide_index=True)

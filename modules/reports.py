import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta
from modules.db import db_query_df, fmt_idr

def render_reports():
    st.title("📊 Reports & Analytics")
    report = st.selectbox("Select Report",[
        "Sales Performance","Top Customers","Top Products by Revenue",
        "Inventory Valuation by Location","Invoice Aging (AR)","Purchase Analysis",
        "Lot Expiry Report","Delivery Performance",
    ])

    if report == "Sales Performance":
        df = db_query_df("""
            SELECT name, partner_name, amount_total, date_order 
            FROM sale_orders 
            WHERE state IN ('sale', 'done') AND date_order != ''
            ORDER BY date_order ASC
        """)
        if not df.empty:
            df["date_order"] = pd.to_datetime(df["date_order"], errors="coerce")
            df["month"] = df["date_order"].dt.to_period("M").astype(str)
            monthly = df.groupby("month").agg(orders=("name","count"),revenue=("amount_total","sum")).reset_index()
            fig = go.Figure()
            fig.add_trace(go.Bar(x=monthly["month"],y=monthly["revenue"],name="Revenue",marker_color="#4caf50"))
            fig.add_trace(go.Scatter(x=monthly["month"],y=monthly["orders"],name="Orders",
                yaxis="y2",line=dict(color="#ff9800",width=3),mode="lines+markers"))
            fig.update_layout(yaxis2=dict(overlaying="y",side="right"),height=400,
                title="Monthly Sales Performance",legend=dict(x=0.01,y=0.99))
            st.plotly_chart(fig,use_container_width=True)
            monthly.columns = ["Month","Orders","Revenue (IDR)"]
            monthly["Revenue (IDR)"] = monthly["Revenue (IDR)"].apply(fmt_idr)
            st.dataframe(monthly,use_container_width=True,hide_index=True)

    elif report == "Top Customers":
        df = db_query_df("""
            SELECT partner_name as Customer, SUM(amount_total) as Revenue 
            FROM sale_orders 
            WHERE state IN ('sale', 'done') AND partner_name != ''
            GROUP BY partner_name 
            ORDER BY Revenue DESC LIMIT 20
        """)
        if not df.empty:
            fig = px.bar(df, x="Revenue", y="Customer", orientation="h",
                title="Top 20 Customers by Revenue", color_discrete_sequence=["#388e3c"])
            fig.update_layout(height=550)
            st.plotly_chart(fig, use_container_width=True)
            df_disp = df.copy()
            df_disp["Revenue"] = df_disp["Revenue"].apply(fmt_idr)
            st.dataframe(df_disp, use_container_width=True, hide_index=True)

    elif report == "Top Products by Revenue":
        df = db_query_df("""
            SELECT product_name as Product, SUM(product_uom_qty) as Total_Qty, SUM(price_subtotal) as Revenue 
            FROM sale_order_lines 
            WHERE product_name != ''
            GROUP BY product_name 
            ORDER BY Revenue DESC LIMIT 20
        """)
        if not df.empty:
            fig = px.bar(df, x="Revenue", y="Product", orientation="h",
                title="Top 20 Products by Sales Revenue", color_discrete_sequence=["#4caf50"])
            fig.update_layout(height=550)
            st.plotly_chart(fig, use_container_width=True)
            df_disp = df.copy()
            df_disp["Revenue"] = df_disp["Revenue"].apply(fmt_idr)
            st.dataframe(df_disp, use_container_width=True, hide_index=True)

    elif report == "Inventory Valuation by Location":
        df = db_query_df("""
            SELECT location_name as Location, SUM(quantity) as On_Hand, SUM(reserved_quantity) as Reserved 
            FROM stock_quants 
            WHERE location_name != ''
            GROUP BY location_name
        """)
        if not df.empty:
            df["Available"] = (df["On_Hand"] - df["Reserved"]).clip(lower=0)
            fig = px.bar(df, x="Location", y=["On_Hand","Reserved","Available"],
                barmode="group", color_discrete_sequence=["#4caf50","#ff9800","#2196f3"])
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df, use_container_width=True, hide_index=True)

    elif report == "Invoice Aging (AR)":
        df = db_query_df("""
            SELECT partner_name, amount_residual, invoice_date_due 
            FROM invoices 
            WHERE move_type = 'out_invoice' AND state = 'posted' AND payment_state != 'paid' AND amount_residual > 0
        """)
        if not df.empty:
            df["invoice_date_due"] = pd.to_datetime(df["invoice_date_due"], errors="coerce")
            today = pd.Timestamp.now()
            df["days_overdue"] = (today - df["invoice_date_due"]).dt.days
            def bucket(d):
                if pd.isna(d): return "Unknown"
                if d <= 0:  return "Current"
                if d <= 30: return "1-30 days"
                if d <= 60: return "31-60 days"
                if d <= 90: return "61-90 days"
                return "90+ days"
            df["Aging"] = df["days_overdue"].apply(bucket)
            aging = df.groupby("Aging")["amount_residual"].sum().reset_index()
            order_map = {"Current":0,"1-30 days":1,"31-60 days":2,"61-90 days":3,"90+ days":4,"Unknown":5}
            aging["_o"] = aging["Aging"].map(order_map)
            aging = aging.sort_values("_o").drop("_o", axis=1)
            aging.columns = ["Aging Bucket","Outstanding"]
            fig = px.bar(aging, x="Aging Bucket", y="Outstanding", title="Accounts Receivable Aging",
                color="Aging Bucket",
                color_discrete_map={"Current":"#4caf50","1-30 days":"#8bc34a",
                    "31-60 days":"#ff9800","61-90 days":"#ff5722","90+ days":"#f44336"})
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
            aging["Outstanding"] = aging["Outstanding"].apply(fmt_idr)
            st.dataframe(aging, use_container_width=True, hide_index=True)
        else:
            st.info("No outstanding unpaid invoices found.")

    elif report == "Purchase Analysis":
        df = db_query_df("""
            SELECT name, partner_name, amount_total, date_order 
            FROM purchase_orders 
            WHERE state IN ('purchase', 'done') AND date_order != ''
            ORDER BY date_order ASC
        """)
        if not df.empty:
            df["date_order"] = pd.to_datetime(df["date_order"], errors="coerce")
            df["month"] = df["date_order"].dt.to_period("M").astype(str)
            monthly = df.groupby("month")["amount_total"].sum().reset_index()
            monthly.columns = ["Month","Purchase Value"]
            fig = px.line(monthly, x="Month", y="Purchase Value", markers=True,
                title="Monthly Purchase Volume", color_discrete_sequence=["#f44336"])
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
            top = df.groupby("partner_name")["amount_total"].sum().nlargest(15).reset_index()
            top.columns = ["Vendor","Total"]
            top["Total"] = top["Total"].apply(fmt_idr)
            st.dataframe(top, use_container_width=True, hide_index=True)

    elif report == "Lot Expiry Report":
        df = db_query_df("SELECT name, product_name, product_qty, expiration_date FROM stock_lots WHERE expiration_date != ''")
        if not df.empty:
            df["expiration_date"] = pd.to_datetime(df["expiration_date"], errors="coerce")
            today = pd.Timestamp.now()
            df["days_to_expiry"] = (df["expiration_date"] - today).dt.days
            df_valid = df[df["expiration_date"].notna()].copy()
            bins = [-9999,0,30,90,365,9999]
            labels = ["🔴 Expired","🟠 <30 days","🟡 30-90 days","🟢 90-365 days","✅ >1 Year"]
            df_valid["Bucket"] = pd.cut(df_valid["days_to_expiry"], bins=bins, labels=labels)
            bucket_counts = df_valid["Bucket"].value_counts().reset_index()
            bucket_counts.columns = ["Category","Lots"]
            fig = px.pie(bucket_counts, names="Category", values="Lots",
                title="Lot Expiry Overview", hole=0.4,
                color_discrete_sequence=["#f44336","#ff9800","#ffc107","#4caf50","#2196f3"])
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
            df_valid_disp = df_valid[["name","product_name","product_qty","expiration_date","days_to_expiry"]].copy()
            df_valid_disp.columns = ["Lot","Product","Qty","Expiry Date","Days to Expiry"]
            df_valid_disp["Expiry Date"] = df_valid_disp["Expiry Date"].dt.strftime("%d %b %Y")
            df_valid_disp = df_valid_disp.sort_values("Days to Expiry")
            st.dataframe(df_valid_disp, use_container_width=True, hide_index=True)

    elif report == "Delivery Performance":
        df = db_query_df("""
            SELECT name, partner_name, state, scheduled_date, date_done 
            FROM stock_pickings 
            WHERE picking_type_code = 'outgoing'
        """)
        if not df.empty:
            df["scheduled_date"] = pd.to_datetime(df["scheduled_date"], errors="coerce")
            df["date_done"] = pd.to_datetime(df["date_done"], errors="coerce")
            df_done = df[df["state"]=="done"].copy()
            df_done["delay_days"] = (df_done["date_done"] - df_done["scheduled_date"]).dt.days
            on_time = len(df_done[df_done["delay_days"]<=0])
            late = len(df_done[df_done["delay_days"]>0])
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Total Outgoing Deliveries", len(df))
            c2.metric("Completed", len(df_done))
            c3.metric("✅ On Time", on_time)
            c4.metric("⚠️ Delayed", late)
            if not df_done.empty:
                fig = px.histogram(df_done, "delay_days", title="Delivery Delay Distribution (days)",
                    color_discrete_sequence=["#4caf50"], nbins=20)
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)

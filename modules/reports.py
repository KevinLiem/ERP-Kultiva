import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta
from modules.odoo_client import odoo_read, to_df, fmt_idr

def render_reports():
    st.title("📊 Reports & Analytics")
    report = st.selectbox("Select Report",[
        "Sales Performance","Top Customers","Top Products by Revenue",
        "Inventory Valuation by Location","Invoice Aging (AR)","Purchase Analysis",
        "Lot Expiry Report","Delivery Performance",
    ])

    if report == "Sales Performance":
        with st.spinner():
            so = odoo_read("sale.order",[["state","in",["sale","done"]]],
                ["name","partner_id","amount_total","date_order"],
                limit=500,order="date_order asc")
        if so:
            df = to_df(so)
            df["date_order"] = pd.to_datetime(df["date_order"])
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
        with st.spinner():
            so = odoo_read("sale.order",[["state","in",["sale","done"]]],
                ["partner_id","amount_total"],limit=500)
        if so:
            df = to_df(so)
            top = df.groupby("partner_id")["amount_total"].sum().nlargest(20).reset_index()
            top.columns = ["Customer","Revenue"]
            fig = px.bar(top,x="Revenue",y="Customer",orientation="h",
                title="Top 20 Customers by Revenue",color_discrete_sequence=["#388e3c"])
            fig.update_layout(height=550)
            st.plotly_chart(fig,use_container_width=True)
            top["Revenue"] = top["Revenue"].apply(fmt_idr)
            st.dataframe(top,use_container_width=True,hide_index=True)

    elif report == "Top Products by Revenue":
        with st.spinner():
            lines = odoo_read("sale.order.line",
                [["order_id.state","in",["sale","done"]]],
                ["product_id","product_uom_qty","price_subtotal"],limit=1000)
        if lines:
            df = to_df(lines)
            top = df.groupby("product_id").agg(
                qty=("product_uom_qty","sum"),revenue=("price_subtotal","sum")
            ).nlargest(20,"revenue").reset_index()
            top.columns = ["Product","Total Qty","Revenue"]
            fig = px.bar(top,x="Revenue",y="Product",orientation="h",
                title="Top 20 Products",color_discrete_sequence=["#4caf50"])
            fig.update_layout(height=550)
            st.plotly_chart(fig,use_container_width=True)
            top["Revenue"] = top["Revenue"].apply(fmt_idr)
            st.dataframe(top,use_container_width=True,hide_index=True)

    elif report == "Inventory Valuation by Location":
        with st.spinner():
            quants = odoo_read("stock.quant",
                [["location_id.usage","=","internal"]],
                ["product_id","location_id","quantity","reserved_quantity"],limit=500)
        if quants:
            df = to_df(quants)
            df["available"] = (df["quantity"]-df["reserved_quantity"]).clip(lower=0)
            by_loc = df.groupby("location_id")[["quantity","reserved_quantity","available"]].sum().reset_index()
            by_loc.columns = ["Location","On Hand","Reserved","Available"]
            fig = px.bar(by_loc,x="Location",y=["On Hand","Reserved","Available"],
                barmode="group",color_discrete_sequence=["#4caf50","#ff9800","#2196f3"])
            fig.update_layout(height=400)
            st.plotly_chart(fig,use_container_width=True)
            st.dataframe(by_loc,use_container_width=True,hide_index=True)

    elif report == "Invoice Aging (AR)":
        with st.spinner():
            inv = odoo_read("account.move",
                [["move_type","=","out_invoice"],["state","=","posted"],["payment_state","!=","paid"]],
                ["name","partner_id","amount_residual","invoice_date_due"],limit=300)
        if inv:
            df = to_df(inv)
            df["invoice_date_due"] = pd.to_datetime(df["invoice_date_due"],errors="coerce")
            today = pd.Timestamp.now()
            df["days_overdue"] = (today-df["invoice_date_due"]).dt.days
            def bucket(d):
                if pd.isna(d): return "Unknown"
                if d<=0:  return "Current"
                if d<=30: return "1-30 days"
                if d<=60: return "31-60 days"
                if d<=90: return "61-90 days"
                return "90+ days"
            df["Aging"] = df["days_overdue"].apply(bucket)
            aging = df.groupby("Aging")["amount_residual"].sum().reset_index()
            order_map = {"Current":0,"1-30 days":1,"31-60 days":2,"61-90 days":3,"90+ days":4,"Unknown":5}
            aging["_o"] = aging["Aging"].map(order_map)
            aging = aging.sort_values("_o").drop("_o",axis=1)
            aging.columns = ["Aging Bucket","Outstanding"]
            fig = px.bar(aging,x="Aging Bucket",y="Outstanding",title="AR Aging",
                color="Aging Bucket",
                color_discrete_map={"Current":"#4caf50","1-30 days":"#8bc34a",
                    "31-60 days":"#ff9800","61-90 days":"#ff5722","90+ days":"#f44336"})
            fig.update_layout(height=350)
            st.plotly_chart(fig,use_container_width=True)
            aging["Outstanding"] = aging["Outstanding"].apply(fmt_idr)
            st.dataframe(aging,use_container_width=True,hide_index=True)

    elif report == "Purchase Analysis":
        with st.spinner():
            po = odoo_read("purchase.order",[["state","in",["purchase","done"]]],
                ["partner_id","amount_total","date_order"],limit=500)
        if po:
            df = to_df(po)
            df["date_order"] = pd.to_datetime(df["date_order"])
            df["month"] = df["date_order"].dt.to_period("M").astype(str)
            monthly = df.groupby("month")["amount_total"].sum().reset_index()
            monthly.columns = ["Month","Purchase Value"]
            fig = px.line(monthly,x="Month",y="Purchase Value",markers=True,
                title="Monthly Purchase Volume",color_discrete_sequence=["#f44336"])
            fig.update_layout(height=350)
            st.plotly_chart(fig,use_container_width=True)
            top = df.groupby("partner_id")["amount_total"].sum().nlargest(15).reset_index()
            top.columns = ["Vendor","Total"]
            top["Total"] = top["Total"].apply(fmt_idr)
            st.dataframe(top,use_container_width=True,hide_index=True)

    elif report == "Lot Expiry Report":
        with st.spinner():
            lots = odoo_read("stock.lot",[],
                ["name","product_id","product_qty","expiration_date"],limit=500)
        if lots:
            df = to_df(lots)
            df["expiration_date"] = pd.to_datetime(df["expiration_date"],errors="coerce")
            today = pd.Timestamp.now()
            df["days_to_expiry"] = (df["expiration_date"]-today).dt.days
            df_valid = df[df["expiration_date"].notna()].copy()
            bins = [-9999,0,30,90,365,9999]
            labels = ["🔴 Expired","🟠 <30 days","🟡 30-90 days","🟢 90-365 days","✅ >1 Year"]
            df_valid["Bucket"] = pd.cut(df_valid["days_to_expiry"],bins=bins,labels=labels)
            bucket_counts = df_valid["Bucket"].value_counts().reset_index()
            bucket_counts.columns = ["Category","Lots"]
            fig = px.pie(bucket_counts,names="Category",values="Lots",
                title="Lot Expiry Overview",hole=0.4,
                color_discrete_sequence=["#f44336","#ff9800","#ffc107","#4caf50","#2196f3"])
            fig.update_layout(height=350)
            st.plotly_chart(fig,use_container_width=True)
            df_valid_disp = df_valid[["name","product_id","product_qty","expiration_date","days_to_expiry"]].copy()
            df_valid_disp.columns = ["Lot","Product","Qty","Expiry Date","Days to Expiry"]
            df_valid_disp["Expiry Date"] = df_valid_disp["Expiry Date"].dt.strftime("%d %b %Y")
            df_valid_disp = df_valid_disp.sort_values("Days to Expiry")
            st.dataframe(df_valid_disp,use_container_width=True,hide_index=True)

    elif report == "Delivery Performance":
        with st.spinner():
            picks = odoo_read("stock.picking",
                [["picking_type_code","=","outgoing"]],
                ["name","partner_id","state","scheduled_date","date_done"],
                limit=400)
        if picks:
            df = to_df(picks)
            df["scheduled_date"] = pd.to_datetime(df["scheduled_date"],errors="coerce")
            df["date_done"] = pd.to_datetime(df["date_done"],errors="coerce")
            df_done = df[df["state"]=="done"].copy()
            df_done["delay_days"] = (df_done["date_done"]-df_done["scheduled_date"]).dt.days
            on_time = len(df_done[df_done["delay_days"]<=0])
            late = len(df_done[df_done["delay_days"]>0])
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Total Deliveries", len(df))
            c2.metric("Done", len(df_done))
            c3.metric("✅ On Time", on_time)
            c4.metric("⚠️ Late", late)
            if not df_done.empty:
                fig = px.histogram(df_done,"delay_days",title="Delivery Delay Distribution (days)",
                    color_discrete_sequence=["#4caf50"],nbins=20)
                fig.update_layout(height=300)
                st.plotly_chart(fig,use_container_width=True)

import streamlit as st
import pandas as pd
import plotly.express as px
from modules.db import db_query, db_query_df, fmt_idr, status_badge

def render_invoicing():
    st.title("🧾 Invoicing (AR / AP)")
    tab1, tab2 = st.tabs(["📤 Customer Invoices", "📥 Vendor Bills"])

    with tab1:
        df = db_query_df("""
            SELECT name, partner_name, state, amount_total, invoice_date, payment_state 
            FROM invoices 
            WHERE move_type IN ('out_invoice', 'out_refund')
            ORDER BY id DESC
        """)
        if not df.empty:
            c1,c2,c3,c4 = st.columns(4)
            posted = df[df["state"]=="posted"]
            c1.metric("Total Invoices", len(df))
            c2.metric("Posted", len(posted))
            c3.metric("Total Invoiced", fmt_idr(posted["amount_total"].sum()))
            unpaid_df = posted[posted["payment_state"]=="not_paid"]
            c4.metric("🔴 Unpaid", fmt_idr(unpaid_df["amount_total"].sum()))

            srch = st.text_input("🔍 Search Invoices")
            if srch:
                df = df[df["partner_name"].str.contains(srch,case=False,na=False)|
                        df["name"].str.contains(srch,case=False,na=False)]
            disp = df[["name","partner_name","state","amount_total","invoice_date","payment_state"]].copy()
            disp.columns = ["Invoice","Customer","Status","Amount","Date","Payment"]
            disp["Amount"] = disp["Amount"].apply(fmt_idr)
            disp["Date"] = pd.to_datetime(disp["Date"], errors="coerce").dt.strftime("%d %b %Y")
            disp["Status"] = disp["Status"].apply(status_badge)
            disp["Payment"] = disp["Payment"].apply(status_badge)
            st.dataframe(disp, use_container_width=True, hide_index=True)

    with tab2:
        df_b = db_query_df("""
            SELECT name, partner_name, state, amount_total, invoice_date, payment_state 
            FROM invoices 
            WHERE move_type IN ('in_invoice', 'in_refund')
            ORDER BY id DESC
        """)
        if not df_b.empty:
            c1,c2,c3 = st.columns(3)
            c1.metric("Total Bills", len(df_b))
            c2.metric("Draft", len(df_b[df_b["state"]=="draft"]))
            c3.metric("Payable Amount", fmt_idr(df_b[df_b["state"]=="posted"]["amount_total"].sum()))

            disp_b = df_b[["name","partner_name","state","amount_total","invoice_date","payment_state"]].copy()
            disp_b.columns = ["Bill","Vendor","Status","Amount","Date","Payment"]
            disp_b["Amount"] = disp_b["Amount"].apply(fmt_idr)
            disp_b["Date"] = pd.to_datetime(disp_b["Date"], errors="coerce").dt.strftime("%d %b %Y")
            disp_b["Status"] = disp_b["Status"].apply(status_badge)
            st.dataframe(disp_b, use_container_width=True, hide_index=True)

def render_manufacturing():
    st.title("🏭 Manufacturing Orders")
    df = db_query_df("""
        SELECT name, product_name, state, product_qty, qty_producing, date_start, date_finished 
        FROM mrp_productions 
        ORDER BY id DESC
    """)
    if not df.empty:
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Total MOs", len(df))
        c2.metric("In Progress", len(df[df["state"].isin(["confirmed","progress"])]))
        c3.metric("Done", len(df[df["state"]=="done"]))
        c4.metric("Draft", len(df[df["state"]=="draft"]))

        col_a,col_b = st.columns(2)
        with col_a:
            sc = df["state"].value_counts().reset_index()
            sc.columns = ["State","Count"]
            fig = px.bar(sc, x="State", y="Count", title="MO Status Distribution",
                color_discrete_sequence=["#4caf50"])
            fig.update_layout(height=280)
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            tp = df.groupby("product_name")["product_qty"].sum().nlargest(8).reset_index()
            tp.columns = ["Product","Qty"]
            fig2 = px.bar(tp, x="Qty", y="Product", orientation="h",
                title="Top Products by Quantity Produced", color_discrete_sequence=["#388e3c"])
            fig2.update_layout(height=280)
            st.plotly_chart(fig2, use_container_width=True)

        df["state"] = df["state"].apply(status_badge)
        df["date_start"] = pd.to_datetime(df["date_start"], errors="coerce").dt.strftime("%d %b %Y")
        disp = df[["name","product_name","state","product_qty","qty_producing","date_start"]].copy()
        disp.columns = ["MO #","Product","Status","Planned Qty","Produced","Start Date"]
        st.dataframe(disp, use_container_width=True, hide_index=True)

def render_crm():
    st.title("👥 CRM & Accounts")
    tab_crm,tab_cust,tab_vend = st.tabs(["💼 CRM Pipeline","🏢 Customers","🏭 Vendors"])

    with tab_crm:
        df = db_query_df("SELECT name, partner_name, stage_name, expected_revenue, probability, user_name FROM crm_leads ORDER BY id DESC")
        if not df.empty:
            c1,c2,c3 = st.columns(3)
            c1.metric("Total Leads / Deals", len(df))
            c2.metric("Total Pipeline Value", fmt_idr(df["expected_revenue"].sum()))
            c3.metric("Avg Deal Size", fmt_idr(df["expected_revenue"].mean()))

            stage_dist = df.groupby("stage_name").agg(
                count=("name","count"), revenue=("expected_revenue","sum")).reset_index()
            fig = px.funnel(stage_dist.sort_values("count", ascending=False),
                x="count", y="stage_name", title="Sales Pipeline Funnel")
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

            disp = df[["name","partner_name","stage_name","expected_revenue","probability","user_name"]].copy()
            disp.columns = ["Opportunity","Partner","Stage","Expected Revenue","Prob %","Owner"]
            disp["Expected Revenue"] = disp["Expected Revenue"].apply(fmt_idr)
            st.dataframe(disp, use_container_width=True, hide_index=True)

    with tab_cust:
        df_c = db_query_df("SELECT name, email, phone, is_company, city, country FROM partners WHERE customer_rank > 0 ORDER BY name ASC")
        if not df_c.empty:
            srch = st.text_input("🔍 Search Customer")
            if srch:
                df_c = df_c[df_c["name"].str.contains(srch, case=False, na=False)]
            disp = df_c[["name","email","phone","is_company","city","country"]].copy()
            disp.columns = ["Name","Email","Phone","Company?","City","Country"]
            disp["Company?"] = disp["Company?"].apply(lambda x: "🏢 Company" if x == 1 else "👤 Individual")
            st.dataframe(disp, use_container_width=True, hide_index=True)

    with tab_vend:
        df_v = db_query_df("SELECT name, email, phone, supplier_rank, city FROM partners WHERE supplier_rank > 0 ORDER BY name ASC")
        if not df_v.empty:
            srch = st.text_input("🔍 Search Vendor", key="v_srch")
            if srch:
                df_v = df_v[df_v["name"].str.contains(srch, case=False, na=False)]
            disp = df_v[["name","email","phone","supplier_rank","city"]].copy()
            disp.columns = ["Vendor Name","Email","Phone","Transactions","City"]
            st.dataframe(disp, use_container_width=True, hide_index=True)

def render_hr():
    st.title("👨‍💼 HR & Employees")
    df = db_query_df("SELECT name, job_title, department_name, work_email, work_phone FROM hr_employees ORDER BY name ASC")
    if not df.empty:
        c1,c2 = st.columns(2)
        c1.metric("Registered Employees", len(df))
        c2.metric("Departments", len(df["department_name"].dropna().unique()))

        srch = st.text_input("🔍 Search Employee")
        if srch:
            df = df[df["name"].str.contains(srch, case=False, na=False)]
        disp = df[["name","job_title","department_name","work_email","work_phone"]].copy()
        disp.columns = ["Full Name","Job Role","Department","Email","Phone"]
        st.dataframe(disp, use_container_width=True, hide_index=True)

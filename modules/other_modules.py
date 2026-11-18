import streamlit as st
import pandas as pd
import plotly.express as px
from modules.odoo_client import odoo_read, to_df, fmt_idr, status_badge

def render_invoicing():
    st.title("🧾 Invoicing")
    tab1, tab2 = st.tabs(["📤 Customer Invoices", "📥 Vendor Bills"])

    with tab1:
        with st.spinner():
            inv = odoo_read("account.move",
                [["move_type","in",["out_invoice","out_refund"]]],
                ["name","partner_id","state","amount_total","invoice_date",
                 "invoice_date_due","payment_state","currency_id"],
                limit=300, order="invoice_date desc")
        if inv:
            df = to_df(inv)
            c1,c2,c3,c4 = st.columns(4)
            posted = df[df["state"]=="posted"]
            c1.metric("Total", len(df))
            c2.metric("Posted", len(posted))
            c3.metric("Total Invoiced", fmt_idr(posted["amount_total"].sum()))
            unpaid_df = posted[posted["payment_state"]=="not_paid"]
            c4.metric("🔴 Unpaid", fmt_idr(unpaid_df["amount_total"].sum()))

            srch = st.text_input("🔍 Search Invoices")
            if srch:
                df = df[df["partner_id"].str.contains(srch,case=False,na=False)|
                        df["name"].str.contains(srch,case=False,na=False)]
            disp = df[["name","partner_id","state","amount_total","invoice_date","payment_state"]].copy()
            disp.columns = ["Invoice","Customer","Status","Amount","Date","Payment"]
            disp["Amount"] = disp["Amount"].apply(fmt_idr)
            disp["Date"] = pd.to_datetime(disp["Date"]).dt.strftime("%d %b %Y")
            disp["Status"] = disp["Status"].apply(status_badge)
            disp["Payment"] = disp["Payment"].apply(status_badge)
            st.dataframe(disp, use_container_width=True, hide_index=True)

    with tab2:
        with st.spinner():
            bills = odoo_read("account.move",
                [["move_type","in",["in_invoice","in_refund"]]],
                ["name","partner_id","state","amount_total","invoice_date","payment_state"],
                limit=300, order="invoice_date desc")
        if bills:
            df_b = to_df(bills)
            c1,c2,c3 = st.columns(3)
            c1.metric("Total Bills", len(df_b))
            c2.metric("Draft", len(df_b[df_b["state"]=="draft"]))
            c3.metric("Payable", fmt_idr(df_b[df_b["state"]=="posted"]["amount_total"].sum()))

            disp_b = df_b[["name","partner_id","state","amount_total","invoice_date","payment_state"]].copy()
            disp_b.columns = ["Bill","Vendor","Status","Amount","Date","Payment"]
            disp_b["Amount"] = disp_b["Amount"].apply(fmt_idr)
            disp_b["Date"] = pd.to_datetime(disp_b["Date"]).dt.strftime("%d %b %Y")
            disp_b["Status"] = disp_b["Status"].apply(status_badge)
            st.dataframe(disp_b, use_container_width=True, hide_index=True)

def render_manufacturing():
    st.title("🏭 Manufacturing Orders")
    with st.spinner():
        mo = odoo_read("mrp.production",[],
            ["name","product_id","state","product_qty","qty_producing",
             "date_start","date_finished","company_id"],
            limit=300, order="date_start desc")
    if mo:
        df = to_df(mo)
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Total MOs", len(df))
        c2.metric("In Progress", len(df[df["state"].isin(["confirmed","progress"])]))
        c3.metric("Done", len(df[df["state"]=="done"]))
        c4.metric("Draft", len(df[df["state"]=="draft"]))

        col_a,col_b = st.columns(2)
        with col_a:
            sc = df["state"].value_counts().reset_index()
            sc.columns = ["State","Count"]
            fig = px.bar(sc,x="State",y="Count",title="MO Status",
                color_discrete_sequence=["#4caf50"])
            fig.update_layout(height=280); st.plotly_chart(fig,use_container_width=True)
        with col_b:
            tp = df.groupby("product_id")["product_qty"].sum().nlargest(8).reset_index()
            tp.columns = ["Product","Qty"]
            fig2 = px.bar(tp,x="Qty",y="Product",orientation="h",
                title="Top Products by Qty",color_discrete_sequence=["#388e3c"])
            fig2.update_layout(height=280); st.plotly_chart(fig2,use_container_width=True)

        df["state"] = df["state"].apply(status_badge)
        df["date_start"] = pd.to_datetime(df["date_start"],errors="coerce").dt.strftime("%d %b %Y")
        disp = df[["name","product_id","state","product_qty","qty_producing","date_start"]].copy()
        disp.columns = ["MO #","Product","Status","Planned Qty","Produced","Start"]
        st.dataframe(disp,use_container_width=True,hide_index=True)

def render_crm():
    st.title("👥 CRM & Accounts")
    tab_crm,tab_cust,tab_vend = st.tabs(["💼 CRM Pipeline","🏢 Customers","🏭 Vendors"])

    with tab_crm:
        with st.spinner():
            leads = odoo_read("crm.lead",[],
                ["name","partner_id","stage_id","expected_revenue","probability","user_id"],
                limit=200)
        if leads:
            df = to_df(leads)
            c1,c2,c3 = st.columns(3)
            c1.metric("Leads/Opps", len(df))
            c2.metric("Pipeline Value", fmt_idr(df["expected_revenue"].sum()))
            c3.metric("Avg Deal", fmt_idr(df["expected_revenue"].mean()))

            stage_dist = df.groupby("stage_id").agg(
                count=("name","count"),revenue=("expected_revenue","sum")).reset_index()
            fig = px.funnel(stage_dist.sort_values("count",ascending=False),
                x="count",y="stage_id",title="Pipeline Funnel")
            fig.update_layout(height=300)
            st.plotly_chart(fig,use_container_width=True)

            disp = df[["name","partner_id","stage_id","expected_revenue","probability","user_id"]].copy()
            disp.columns = ["Opportunity","Partner","Stage","Expected Revenue","Prob%","Owner"]
            disp["Expected Revenue"] = disp["Expected Revenue"].apply(fmt_idr)
            st.dataframe(disp,use_container_width=True,hide_index=True)

    with tab_cust:
        with st.spinner():
            custs = odoo_read("res.partner",[["customer_rank",">",0]],
                ["name","email","phone","is_company","city","country_id"],limit=300)
        if custs:
            df_c = to_df(custs)
            srch = st.text_input("🔍 Search customer")
            if srch: df_c = df_c[df_c["name"].str.contains(srch,case=False,na=False)]
            disp = df_c[["name","email","phone","is_company","city","country_id"]].copy()
            disp.columns = ["Name","Email","Phone","Company?","City","Country"]
            disp["Company?"] = disp["Company?"].apply(lambda x: "🏢" if x else "👤")
            st.dataframe(disp,use_container_width=True,hide_index=True)

    with tab_vend:
        with st.spinner():
            vends = odoo_read("res.partner",[["supplier_rank",">",0]],
                ["name","email","phone","supplier_rank","city","country_id"],limit=200)
        if vends:
            df_v = to_df(vends)
            srch = st.text_input("🔍 Search vendor",key="v_srch")
            if srch: df_v = df_v[df_v["name"].str.contains(srch,case=False,na=False)]
            disp = df_v[["name","email","phone","supplier_rank","city"]].copy()
            disp.columns = ["Name","Email","Phone","Transactions","City"]
            st.dataframe(disp,use_container_width=True,hide_index=True)

def render_hr():
    st.title("👨‍💼 HR & Employees")
    with st.spinner():
        emps = odoo_read("hr.employee",[],
            ["name","job_title","job_id","department_id","work_email","work_phone","company_id"],
            limit=200)
    if emps:
        df = to_df(emps)
        c1,c2,c3 = st.columns(3)
        c1.metric("Employees", len(df))
        c2.metric("Departments", df["department_id"].nunique())
        c3.metric("Job Roles", df["job_id"].nunique())

        col_a,col_b = st.columns(2)
        with col_a:
            dept = df["department_id"].value_counts().head(10).reset_index()
            dept.columns = ["Dept","Count"]
            fig = px.bar(dept,x="Dept",y="Count",title="By Department",
                color_discrete_sequence=["#4caf50"])
            fig.update_layout(height=280,xaxis_tickangle=-30)
            st.plotly_chart(fig,use_container_width=True)
        with col_b:
            jobs = df["job_title"].value_counts().head(8).reset_index()
            jobs.columns = ["Title","Count"]
            fig2 = px.pie(jobs,names="Title",values="Count",title="By Job Title",hole=0.4)
            fig2.update_layout(height=280)
            st.plotly_chart(fig2,use_container_width=True)

        srch = st.text_input("🔍 Search employee")
        df_f = df
        if srch: df_f = df[df["name"].str.contains(srch,case=False,na=False)]
        disp = df_f[["name","job_title","department_id","work_email","work_phone","company_id"]].copy()
        disp.columns = ["Name","Job Title","Department","Email","Phone","Company"]
        st.dataframe(disp,use_container_width=True,hide_index=True)

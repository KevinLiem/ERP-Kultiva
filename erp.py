import xmlrpc.client
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json

# ─── CONFIG ──────────────────────────────────────────────────────────────────
ODOO_URL = "https://kultiva.odoo.com"
ODOO_DB  = "kultiva"
ODOO_USER = "ppicjkt@kultivaco.com"
ODOO_KEY  = "e960e55aaa54b7c4d711d32c3eec857f9eb87407"

# ─── ODOO CLIENT ─────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_client():
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_KEY, {})
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", allow_none=True)
    return uid, models

def odoo(model, method, domain=None, fields=None, limit=1000, offset=0, order=None):
    uid, models = get_client()
    if domain is None:
        domain = []
    kwargs = {"limit": limit, "offset": offset}
    if fields:
        kwargs["fields"] = fields
    if order:
        kwargs["order"] = order
    try:
        if method == "search_read":
            return models.execute_kw(ODOO_DB, uid, ODOO_KEY, model, method, [domain], kwargs)
        elif method == "search_count":
            return models.execute_kw(ODOO_DB, uid, ODOO_KEY, model, method, [domain])
        elif method == "read_group":
            return models.execute_kw(ODOO_DB, uid, ODOO_KEY, model, method, [domain, fields, kwargs.get("groupby", [])], {})
        else:
            return models.execute_kw(ODOO_DB, uid, ODOO_KEY, model, method, [domain], kwargs)
    except Exception as e:
        st.error(f"Odoo error on {model}.{method}: {e}")
        return []

def odoo_count(model, domain=None):
    if domain is None:
        domain = []
    uid, models = get_client()
    try:
        return models.execute_kw(ODOO_DB, uid, ODOO_KEY, model, "search_count", [domain])
    except:
        return 0

def to_df(records, rename=None):
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    # Flatten many2one fields  [id, name] -> name
    for col in df.columns:
        if df[col].dtype == object:
            try:
                sample = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
                if isinstance(sample, list) and len(sample) == 2:
                    df[col] = df[col].apply(lambda x: x[1] if isinstance(x, list) else x)
            except:
                pass
    if rename:
        df = df.rename(columns=rename)
    return df

# ─── FORMATTING ──────────────────────────────────────────────────────────────
def fmt_idr(val):
    try:
        return f"Rp {float(val):,.0f}"
    except:
        return "Rp 0"

def fmt_usd(val):
    try:
        return f"$ {float(val):,.2f}"
    except:
        return "$ 0"

# ─── PAGE CONFIG ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Kultiva ERP",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── CUSTOM CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a2f1a 0%, #2d5a27 100%);
    }
    [data-testid="stSidebar"] * { color: #e8f5e9 !important; }
    [data-testid="stSidebar"] .stSelectbox label { color: #a5d6a7 !important; }

    /* Metric cards */
    [data-testid="metric-container"] {
        background: #f8fdf8;
        border: 1px solid #c8e6c9;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    [data-testid="metric-container"] [data-testid="stMetricLabel"] {
        font-weight: 600;
        color: #2e7d32 !important;
    }

    /* Header */
    .kultiva-header {
        background: linear-gradient(135deg, #1b5e20 0%, #388e3c 50%, #66bb6a 100%);
        padding: 20px 30px;
        border-radius: 16px;
        margin-bottom: 20px;
        color: white;
    }
    .kultiva-header h1 { color: white !important; margin: 0; font-size: 2rem; }
    .kultiva-header p  { color: #c8e6c9 !important; margin: 4px 0 0; }

    /* Section headers */
    .section-header {
        font-size: 1.1rem;
        font-weight: 700;
        color: #2e7d32;
        border-left: 4px solid #4caf50;
        padding-left: 10px;
        margin: 20px 0 10px;
    }

    /* Status badges */
    .badge-done    { background: #e8f5e9; color: #2e7d32; padding: 2px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }
    .badge-draft   { background: #fff9c4; color: #f57f17; padding: 2px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }
    .badge-cancel  { background: #ffebee; color: #c62828; padding: 2px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }
    .badge-sale    { background: #e3f2fd; color: #1565c0; padding: 2px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }
    .badge-posted  { background: #e8f5e9; color: #2e7d32; padding: 2px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ─── SIDEBAR NAV ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌱 Kultiva ERP")
    st.markdown("---")
    page = st.selectbox("Navigation", [
        "🏠 Dashboard",
        "📦 Sales",
        "🧾 Invoicing",
        "🏭 Manufacturing",
        "📋 Inventory",
        "🛒 Purchasing",
        "👥 CRM / Accounts",
        "🚚 Deliveries",
        "👨‍💼 HR & Employees",
        "📊 Reports",
    ])
    st.markdown("---")
    st.markdown("**🔗 Quick Links**")
    st.markdown("[Odoo Backend ↗](https://kultiva.odoo.com)")
    st.markdown("---")
    st.caption(f"Last refreshed: {datetime.now().strftime('%H:%M:%S')}")
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if page == "🏠 Dashboard":
    st.markdown("""
    <div class="kultiva-header">
        <h1>🌱 Kultiva ERP Dashboard</h1>
        <p>Real-time overview of Kultiva operations</p>
    </div>
    """, unsafe_allow_html=True)

    # ── KPI Row 1 ─────────────────────────────────────────────────────────
    with st.spinner("Loading KPIs..."):
        total_sales = odoo_count("sale.order", [["state", "in", ["sale", "done"]]])
        draft_sales = odoo_count("sale.order", [["state", "=", "draft"]])
        total_inv   = odoo_count("account.move", [["move_type","in",["out_invoice"]], ["state","=","posted"]])
        pending_del = odoo_count("stock.picking", [["picking_type_code","=","outgoing"],["state","in",["confirmed","assigned"]]])
        open_po     = odoo_count("purchase.order", [["state","in",["purchase","sent"]]])
        total_cust  = odoo_count("res.partner", [["customer_rank",">",0]])
        total_prods = odoo_count("product.template", [["active","=",True]])
        total_leads = odoo_count("crm.lead", [])

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("✅ Confirmed Orders",  total_sales,  f"+{draft_sales} drafts")
    c2.metric("🧾 Posted Invoices",   total_inv)
    c3.metric("🚚 Pending Deliveries",pending_del)
    c4.metric("🛒 Open POs",          open_po)

    c5,c6,c7,c8 = st.columns(4)
    c5.metric("👥 Customers",         total_cust)
    c6.metric("📦 Active Products",   total_prods)
    c7.metric("💼 CRM Leads",         total_leads)
    c8.metric("🏭 Total Deliveries",  odoo_count("stock.picking", [["picking_type_code","=","outgoing"]]))

    # ── Revenue chart ─────────────────────────────────────────────────────
    st.markdown('<div class="section-header">📈 Revenue Trend (Recent Invoices)</div>', unsafe_allow_html=True)

    with st.spinner("Loading revenue data..."):
        inv_data = odoo("account.move", "search_read",
            [["move_type","=","out_invoice"],["state","=","posted"]],
            ["name","partner_id","amount_total","invoice_date","currency_id"],
            limit=200, order="invoice_date desc")

    if inv_data:
        df_inv = to_df(inv_data)
        df_inv["invoice_date"] = pd.to_datetime(df_inv["invoice_date"], errors="coerce")
        df_inv = df_inv.dropna(subset=["invoice_date"])
        df_inv["month"] = df_inv["invoice_date"].dt.to_period("M").astype(str)
        monthly = df_inv.groupby("month")["amount_total"].sum().reset_index()
        monthly.columns = ["Month","Revenue"]
        monthly = monthly.sort_values("Month")

        col_a, col_b = st.columns([2,1])
        with col_a:
            fig = px.bar(monthly, x="Month", y="Revenue",
                title="Monthly Revenue (IDR)",
                color_discrete_sequence=["#4caf50"],
                text_auto=".2s")
            fig.update_layout(height=320, margin=dict(t=40,b=0,l=0,r=0))
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            top_cust = df_inv.groupby("partner_id")["amount_total"].sum().nlargest(8).reset_index()
            top_cust.columns = ["Customer","Revenue"]
            fig2 = px.pie(top_cust, names="Customer", values="Revenue",
                title="Revenue by Customer", hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set2)
            fig2.update_layout(height=320, margin=dict(t=40,b=0,l=0,r=0))
            st.plotly_chart(fig2, use_container_width=True)

    # ── Sales order status ─────────────────────────────────────────────────
    st.markdown('<div class="section-header">📦 Sales Order Status</div>', unsafe_allow_html=True)
    with st.spinner("Loading sales data..."):
        so_data = odoo("sale.order","search_read",[],
            ["name","partner_id","state","amount_total","date_order","user_id"],
            limit=300, order="date_order desc")

    if so_data:
        df_so = to_df(so_data)
        df_so["date_order"] = pd.to_datetime(df_so["date_order"], errors="coerce")
        df_so["Date"] = df_so["date_order"].dt.date

        col_x, col_y = st.columns(2)
        with col_x:
            status_counts = df_so["state"].value_counts().reset_index()
            status_counts.columns = ["Status","Count"]
            status_map = {"sale":"Confirmed","draft":"Draft","done":"Done","cancel":"Cancelled","sent":"Sent"}
            status_counts["Status"] = status_counts["Status"].map(status_map).fillna(status_counts["Status"])
            fig3 = px.bar(status_counts, x="Status", y="Count", title="Orders by Status",
                color="Status", color_discrete_sequence=["#4caf50","#ff9800","#2196f3","#f44336","#9c27b0"])
            fig3.update_layout(height=280, margin=dict(t=40,b=0,l=0,r=0), showlegend=False)
            st.plotly_chart(fig3, use_container_width=True)
        with col_y:
            top_so = df_so.groupby("partner_id")["amount_total"].sum().nlargest(6).reset_index()
            top_so.columns = ["Customer","Total (IDR)"]
            fig4 = px.bar(top_so, x="Total (IDR)", y="Customer", orientation="h",
                title="Top 6 Customers by Order Value",
                color_discrete_sequence=["#388e3c"])
            fig4.update_layout(height=280, margin=dict(t=40,b=0,l=0,r=0))
            st.plotly_chart(fig4, use_container_width=True)

    # ── Recent activity ────────────────────────────────────────────────────
    st.markdown('<div class="section-header">🕐 Recent Sales Orders</div>', unsafe_allow_html=True)
    if so_data:
        df_recent = to_df(so_data[:20])[["name","partner_id","state","amount_total","date_order"]]
        df_recent.columns = ["Order","Customer","Status","Amount (IDR)","Date"]
        df_recent["Amount (IDR)"] = df_recent["Amount (IDR)"].apply(fmt_idr)
        df_recent["Date"] = pd.to_datetime(df_recent["Date"]).dt.strftime("%d %b %Y")
        df_recent["Status"] = df_recent["Status"].map({"sale":"✅ Confirmed","draft":"📝 Draft",
            "done":"✔️ Done","cancel":"❌ Cancelled","sent":"📤 Sent"}).fillna(df_recent["Status"])
        st.dataframe(df_recent, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SALES
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📦 Sales":
    st.title("📦 Sales Orders")

    # Filters
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        status_filter = st.multiselect("Status", ["draft","sent","sale","done","cancel"],
            default=["draft","sent","sale","done"])
    with col_f2:
        date_from = st.date_input("From Date", value=datetime.now() - timedelta(days=90))
    with col_f3:
        date_to = st.date_input("To Date", value=datetime.now())

    domain = [["state","in", status_filter],
              ["date_order",">=", date_from.strftime("%Y-%m-%d 00:00:00")],
              ["date_order","<=", date_to.strftime("%Y-%m-%d 23:59:59")]]

    with st.spinner("Loading sales orders..."):
        so = odoo("sale.order","search_read", domain,
            ["name","partner_id","state","amount_total","amount_untaxed","date_order",
             "user_id","invoice_status","commitment_date","currency_id"],
            limit=500, order="date_order desc")

    if not so:
        st.info("No sales orders found for selected filters.")
    else:
        df = to_df(so)
        df["date_order"] = pd.to_datetime(df["date_order"])

        # Summary metrics
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Total Orders", len(df))
        c2.metric("Total Revenue", fmt_idr(df["amount_total"].sum()))
        c3.metric("Confirmed", len(df[df["state"]=="sale"]))
        c4.metric("Avg Order Value", fmt_idr(df["amount_total"].mean()))

        # Search
        search = st.text_input("🔍 Search order / customer")
        if search:
            df = df[df["partner_id"].str.contains(search, case=False, na=False) |
                    df["name"].str.contains(search, case=False, na=False)]

        # Display
        display_df = df[["name","partner_id","state","amount_untaxed","amount_total","date_order","user_id"]].copy()
        display_df.columns = ["Order #","Customer","Status","Subtotal","Total","Date","Salesperson"]
        display_df["Total"] = display_df["Total"].apply(fmt_idr)
        display_df["Subtotal"] = display_df["Subtotal"].apply(fmt_idr)
        display_df["Date"] = pd.to_datetime(display_df["Date"]).dt.strftime("%d %b %Y")
        display_df["Status"] = display_df["Status"].map({
            "sale":"✅ Confirmed","draft":"📝 Draft","done":"✔️ Done",
            "cancel":"❌ Cancelled","sent":"📤 Sent"}).fillna(display_df["Status"])

        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # Chart
        st.markdown('<div class="section-header">📈 Sales Trend</div>', unsafe_allow_html=True)
        df["week"] = df["date_order"].dt.to_period("W").astype(str)
        weekly = df.groupby("week").agg(orders=("name","count"), revenue=("amount_total","sum")).reset_index()
        fig = px.line(weekly, x="week", y="revenue", markers=True,
            title="Weekly Revenue", color_discrete_sequence=["#4caf50"])
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: INVOICING
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🧾 Invoicing":
    st.title("🧾 Invoicing")

    tab1, tab2 = st.tabs(["📤 Customer Invoices", "📥 Vendor Bills"])

    with tab1:
        with st.spinner("Loading invoices..."):
            inv = odoo("account.move","search_read",
                [["move_type","in",["out_invoice","out_refund"]]],
                ["name","partner_id","state","amount_total","amount_untaxed",
                 "invoice_date","invoice_date_due","payment_state","currency_id","move_type"],
                limit=300, order="invoice_date desc")

        if inv:
            df = to_df(inv)
            df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")

            c1,c2,c3,c4 = st.columns(4)
            posted = df[df["state"]=="posted"]
            c1.metric("Total Invoices", len(df))
            c2.metric("Posted", len(posted))
            c3.metric("Total Invoiced", fmt_idr(posted["amount_total"].sum()))
            c4.metric("Avg Invoice", fmt_idr(posted["amount_total"].mean()))

            search = st.text_input("🔍 Search invoice / customer", key="inv_search")
            if search:
                df = df[df["partner_id"].str.contains(search, case=False, na=False) |
                        df["name"].str.contains(search, case=False, na=False)]

            disp = df[["name","partner_id","move_type","state","amount_total","invoice_date","payment_state"]].copy()
            disp.columns = ["Invoice #","Customer","Type","Status","Amount","Date","Payment"]
            disp["Amount"] = disp["Amount"].apply(fmt_idr)
            disp["Date"] = disp["Date"].dt.strftime("%d %b %Y")
            disp["Status"] = disp["Status"].map({"posted":"✅ Posted","draft":"📝 Draft",
                "cancel":"❌ Cancelled"}).fillna(disp["Status"])
            disp["Payment"] = disp["Payment"].map({"paid":"✅ Paid","not_paid":"⏳ Unpaid",
                "in_payment":"🔄 In Payment","partial":"🟡 Partial"}).fillna(disp["Payment"])
            st.dataframe(disp, use_container_width=True, hide_index=True)

            # Aging chart
            st.markdown('<div class="section-header">📊 Invoice Status Breakdown</div>', unsafe_allow_html=True)
            pay_counts = df["payment_state"].value_counts().reset_index()
            pay_counts.columns = ["Payment Status","Count"]
            pay_counts["Payment Status"] = pay_counts["Payment Status"].map({
                "paid":"Paid","not_paid":"Unpaid","in_payment":"In Payment","partial":"Partial",
                "reversed":"Reversed"}).fillna(pay_counts["Payment Status"])
            fig = px.pie(pay_counts, names="Payment Status", values="Count",
                color_discrete_sequence=["#4caf50","#f44336","#2196f3","#ff9800","#9c27b0"],
                hole=0.4)
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        with st.spinner("Loading bills..."):
            bills = odoo("account.move","search_read",
                [["move_type","in",["in_invoice","in_refund"]]],
                ["name","partner_id","state","amount_total","invoice_date","payment_state","move_type"],
                limit=300, order="invoice_date desc")

        if bills:
            df_b = to_df(bills)
            c1,c2,c3 = st.columns(3)
            c1.metric("Total Bills", len(df_b))
            c2.metric("Pending Bills", len(df_b[df_b["state"]=="draft"]))
            c3.metric("Total Payable", fmt_idr(df_b[df_b["state"]=="posted"]["amount_total"].sum()))

            disp_b = df_b[["name","partner_id","state","amount_total","invoice_date","payment_state"]].copy()
            disp_b.columns = ["Bill #","Vendor","Status","Amount","Date","Payment"]
            disp_b["Amount"] = disp_b["Amount"].apply(fmt_idr)
            disp_b["Date"] = pd.to_datetime(disp_b["Date"]).dt.strftime("%d %b %Y")
            disp_b["Status"] = disp_b["Status"].map({"posted":"✅ Posted","draft":"📝 Draft",
                "cancel":"❌ Cancelled"}).fillna(disp_b["Status"])
            st.dataframe(disp_b, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: MANUFACTURING
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🏭 Manufacturing":
    st.title("🏭 Manufacturing")

    with st.spinner("Loading manufacturing orders..."):
        mo = odoo("mrp.production","search_read",[],
            ["name","product_id","state","product_qty","qty_producing",
             "date_start","date_finished","user_id","company_id"],
            limit=300, order="date_start desc")

    if mo:
        df = to_df(mo)
        df["date_start"] = pd.to_datetime(df["date_start"], errors="coerce")
        df["date_finished"] = pd.to_datetime(df["date_finished"], errors="coerce")

        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Total MOs", len(df))
        c2.metric("In Progress", len(df[df["state"].isin(["confirmed","progress"])]))
        c3.metric("Done", len(df[df["state"]=="done"]))
        c4.metric("Draft", len(df[df["state"]=="draft"]))

        # Status filter
        state_filter = st.multiselect("Filter Status",
            df["state"].unique().tolist(), default=df["state"].unique().tolist())
        df_f = df[df["state"].isin(state_filter)]

        # Chart
        col_a, col_b = st.columns(2)
        with col_a:
            sc = df["state"].value_counts().reset_index()
            sc.columns = ["State","Count"]
            fig = px.bar(sc, x="State", y="Count", title="MO Status",
                color_discrete_sequence=["#4caf50"])
            fig.update_layout(height=280)
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            top_prods = df.groupby("product_id")["product_qty"].sum().nlargest(8).reset_index()
            top_prods.columns = ["Product","Qty"]
            fig2 = px.bar(top_prods, x="Qty", y="Product", orientation="h",
                title="Top Products by Qty Produced", color_discrete_sequence=["#388e3c"])
            fig2.update_layout(height=280)
            st.plotly_chart(fig2, use_container_width=True)

        disp = df_f[["name","product_id","state","product_qty","qty_producing","date_start"]].copy()
        disp.columns = ["MO #","Product","Status","Planned Qty","Produced","Start Date"]
        disp["Status"] = disp["Status"].map({
            "draft":"📝 Draft","confirmed":"✅ Confirmed","progress":"🔄 In Progress",
            "done":"✔️ Done","cancel":"❌ Cancelled"}).fillna(disp["Status"])
        disp["Start Date"] = disp["Start Date"].dt.strftime("%d %b %Y")
        st.dataframe(disp, use_container_width=True, hide_index=True)
    else:
        st.info("No manufacturing orders found.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: INVENTORY
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📋 Inventory":
    st.title("📋 Inventory")

    tab_stock, tab_products, tab_moves = st.tabs(["📦 Stock Levels", "🏷️ Products", "🔄 Stock Moves"])

    with tab_stock:
        with st.spinner("Loading stock..."):
            quants = odoo("stock.quant","search_read",
                [["location_id.usage","=","internal"]],
                ["product_id","location_id","quantity","reserved_quantity","product_uom_id"],
                limit=500)

        if quants:
            df = to_df(quants)
            df["available"] = df["quantity"] - df["reserved_quantity"]
            df["available"] = df["available"].clip(lower=0)

            c1,c2,c3 = st.columns(3)
            c1.metric("SKUs in Stock", len(df))
            c2.metric("Total Units", f"{df['quantity'].sum():,.0f}")
            c3.metric("Reserved", f"{df['reserved_quantity'].sum():,.0f}")

            search = st.text_input("🔍 Search product / location", key="inv_search2")
            df_f = df
            if search:
                df_f = df[df["product_id"].str.contains(search, case=False, na=False) |
                          df["location_id"].str.contains(search, case=False, na=False)]

            disp = df_f[["product_id","location_id","quantity","reserved_quantity","available"]].copy()
            disp.columns = ["Product","Location","On Hand","Reserved","Available"]
            st.dataframe(disp, use_container_width=True, hide_index=True)

            # Location breakdown
            by_loc = df.groupby("location_id")["quantity"].sum().nlargest(10).reset_index()
            by_loc.columns = ["Location","Stock Units"]
            fig = px.bar(by_loc, x="Location", y="Stock Units",
                title="Stock by Location", color_discrete_sequence=["#4caf50"])
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

    with tab_products:
        with st.spinner("Loading products..."):
            prods = odoo("product.template","search_read",
                [["active","=",True]],
                ["name","type","list_price","categ_id","default_code","uom_id"],
                limit=742)

        if prods:
            df_p = to_df(prods)
            c1,c2,c3 = st.columns(3)
            c1.metric("Total Products", len(df_p))
            c2.metric("Storable", len(df_p[df_p["type"]=="product"]))
            c3.metric("Services", len(df_p[df_p["type"]=="service"]))

            search_p = st.text_input("🔍 Search products", key="prod_search")
            df_pf = df_p
            if search_p:
                df_pf = df_p[df_p["name"].str.contains(search_p, case=False, na=False)]

            # Category breakdown
            cat_counts = df_p["categ_id"].value_counts().head(10).reset_index()
            cat_counts.columns = ["Category","Count"]
            cat_counts["Category"] = cat_counts["Category"].apply(
                lambda x: x if isinstance(x, str) else "Uncategorised")
            fig = px.pie(cat_counts, names="Category", values="Count",
                title="Products by Category", hole=0.4)
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

            disp_p = df_pf[["name","default_code","type","categ_id","list_price"]].copy()
            disp_p.columns = ["Product","SKU","Type","Category","Sale Price"]
            disp_p["Type"] = disp_p["Type"].map({"product":"📦 Storable","consu":"🔧 Consumable",
                "service":"🛠️ Service"}).fillna(disp_p["Type"])
            disp_p["Sale Price"] = disp_p["Sale Price"].apply(fmt_idr)
            st.dataframe(disp_p, use_container_width=True, hide_index=True)

    with tab_moves:
        with st.spinner("Loading stock moves..."):
            moves = odoo("stock.move","search_read",
                [["state","=","done"]],
                ["name","product_id","location_id","location_dest_id","product_uom_qty","date"],
                limit=200, order="date desc")

        if moves:
            df_m = to_df(moves)
            df_m["date"] = pd.to_datetime(df_m["date"], errors="coerce")
            disp_m = df_m[["name","product_id","location_id","location_dest_id","product_uom_qty","date"]].copy()
            disp_m.columns = ["Move","Product","From","To","Qty","Date"]
            disp_m["Date"] = disp_m["Date"].dt.strftime("%d %b %Y")
            st.dataframe(disp_m, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: PURCHASING
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🛒 Purchasing":
    st.title("🛒 Purchase Orders")

    with st.spinner("Loading purchase orders..."):
        po = odoo("purchase.order","search_read",[],
            ["name","partner_id","state","amount_total","date_order","date_approve","user_id","currency_id"],
            limit=300, order="date_order desc")

    if po:
        df = to_df(po)
        df["date_order"] = pd.to_datetime(df["date_order"], errors="coerce")

        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Total POs", len(df))
        c2.metric("Confirmed", len(df[df["state"]=="purchase"]))
        c3.metric("Draft/Sent", len(df[df["state"].isin(["draft","sent"])]))
        c4.metric("Total Value", fmt_idr(df["amount_total"].sum()))

        # Vendor filter
        vendors = ["All"] + sorted(df["partner_id"].dropna().unique().tolist())
        v_sel = st.selectbox("Filter by Vendor", vendors)
        df_f = df if v_sel == "All" else df[df["partner_id"] == v_sel]

        # Chart
        col_a, col_b = st.columns(2)
        with col_a:
            top_v = df.groupby("partner_id")["amount_total"].sum().nlargest(8).reset_index()
            top_v.columns = ["Vendor","Total"]
            fig = px.bar(top_v, x="Total", y="Vendor", orientation="h",
                title="Top Vendors by PO Value", color_discrete_sequence=["#388e3c"])
            fig.update_layout(height=280)
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            sc = df["state"].value_counts().reset_index()
            sc.columns = ["State","Count"]
            fig2 = px.pie(sc, names="State", values="Count",
                title="PO Status", hole=0.4,
                color_discrete_sequence=["#4caf50","#ff9800","#f44336","#2196f3"])
            fig2.update_layout(height=280)
            st.plotly_chart(fig2, use_container_width=True)

        disp = df_f[["name","partner_id","state","amount_total","date_order"]].copy()
        disp.columns = ["PO #","Vendor","Status","Total","Date"]
        disp["Total"] = disp["Total"].apply(fmt_idr)
        disp["Date"] = disp["Date"].dt.strftime("%d %b %Y")
        disp["Status"] = disp["Status"].map({
            "draft":"📝 Draft","sent":"📤 Sent","purchase":"✅ Confirmed",
            "done":"✔️ Done","cancel":"❌ Cancelled"}).fillna(disp["Status"])
        st.dataframe(disp, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: CRM / ACCOUNTS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "👥 CRM / Accounts":
    st.title("👥 CRM & Accounts")

    tab_crm, tab_cust, tab_vend = st.tabs(["💼 CRM Pipeline", "🏢 Customers", "🏭 Vendors"])

    with tab_crm:
        with st.spinner("Loading CRM leads..."):
            leads = odoo("crm.lead","search_read",[],
                ["name","partner_id","stage_id","expected_revenue","probability","user_id","date_deadline"],
                limit=200)

        if leads:
            df = to_df(leads)
            c1,c2,c3 = st.columns(3)
            c1.metric("Total Leads/Opps", len(df))
            c2.metric("Total Pipeline Value", fmt_idr(df["expected_revenue"].sum()))
            c3.metric("Avg Deal Size", fmt_idr(df["expected_revenue"].mean()))

            # Stage distribution
            stage_dist = df.groupby("stage_id").agg(
                count=("name","count"), revenue=("expected_revenue","sum")).reset_index()
            stage_dist.columns = ["Stage","Count","Revenue"]
            fig = px.funnel(stage_dist.sort_values("Count", ascending=False),
                x="Count", y="Stage", title="CRM Pipeline Funnel")
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

            disp = df[["name","partner_id","stage_id","expected_revenue","probability","user_id"]].copy()
            disp.columns = ["Opportunity","Partner","Stage","Expected Revenue","Probability%","Owner"]
            disp["Expected Revenue"] = disp["Expected Revenue"].apply(fmt_idr)
            st.dataframe(disp, use_container_width=True, hide_index=True)

    with tab_cust:
        with st.spinner("Loading customers..."):
            custs = odoo("res.partner","search_read",
                [["customer_rank",">",0]],
                ["name","email","phone","is_company","customer_rank","street","city","country_id"],
                limit=300)

        if custs:
            df_c = to_df(custs)
            c1,c2 = st.columns(2)
            c1.metric("Total Customers", len(df_c))
            c2.metric("Companies", len(df_c[df_c["is_company"]==True]))

            search_c = st.text_input("🔍 Search customer", key="cust_search")
            df_cf = df_c
            if search_c:
                df_cf = df_c[df_c["name"].str.contains(search_c, case=False, na=False)]

            disp_c = df_cf[["name","email","phone","is_company","city","country_id"]].copy()
            disp_c.columns = ["Name","Email","Phone","Company?","City","Country"]
            disp_c["Company?"] = disp_c["Company?"].apply(lambda x: "🏢 Yes" if x else "👤 No")
            st.dataframe(disp_c, use_container_width=True, hide_index=True)

    with tab_vend:
        with st.spinner("Loading vendors..."):
            vends = odoo("res.partner","search_read",
                [["supplier_rank",">",0]],
                ["name","email","phone","is_company","supplier_rank","city","country_id"],
                limit=200)

        if vends:
            df_v = to_df(vends)
            c1,c2 = st.columns(2)
            c1.metric("Total Vendors", len(df_v))
            c2.metric("Top Supplier", df_v.nlargest(1,"supplier_rank")["name"].iloc[0])

            disp_v = df_v[["name","email","phone","supplier_rank","city","country_id"]].copy()
            disp_v.columns = ["Name","Email","Phone","Transactions","City","Country"]
            st.dataframe(disp_v, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: DELIVERIES
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🚚 Deliveries":
    st.title("🚚 Deliveries & Logistics")

    with st.spinner("Loading deliveries..."):
        picks = odoo("stock.picking","search_read",[],
            ["name","partner_id","state","scheduled_date","date_done",
             "picking_type_id","origin","picking_type_code"],
            limit=400, order="scheduled_date desc")

    if picks:
        df = to_df(picks)
        df["scheduled_date"] = pd.to_datetime(df["scheduled_date"], errors="coerce")
        df["date_done"] = pd.to_datetime(df["date_done"], errors="coerce")

        # Type filter
        pick_types = ["All"] + sorted(df["picking_type_code"].dropna().unique().tolist())
        type_sel = st.selectbox("Picking Type", pick_types)
        df_f = df if type_sel == "All" else df[df["picking_type_code"] == type_sel]

        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Total Pickings", len(df_f))
        c2.metric("Done", len(df_f[df_f["state"]=="done"]))
        c3.metric("Ready", len(df_f[df_f["state"]=="assigned"]))
        c4.metric("Waiting", len(df_f[df_f["state"].isin(["confirmed","waiting"])]))

        # Charts
        col_a, col_b = st.columns(2)
        with col_a:
            sc = df_f["state"].value_counts().reset_index()
            sc.columns = ["State","Count"]
            fig = px.pie(sc, names="State", values="Count",
                title="Delivery Status", hole=0.4,
                color_discrete_sequence=["#4caf50","#2196f3","#ff9800","#f44336","#9e9e9e"])
            fig.update_layout(height=280)
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            by_wh = df_f.groupby("picking_type_id")["name"].count().reset_index()
            by_wh.columns = ["Warehouse","Count"]
            fig2 = px.bar(by_wh, x="Warehouse", y="Count",
                title="Deliveries by Warehouse", color_discrete_sequence=["#388e3c"])
            fig2.update_layout(height=280)
            st.plotly_chart(fig2, use_container_width=True)

        search_d = st.text_input("🔍 Search delivery / partner", key="del_search")
        df_fs = df_f
        if search_d:
            df_fs = df_f[df_f["partner_id"].str.contains(search_d, case=False, na=False) |
                         df_f["name"].str.contains(search_d, case=False, na=False)]

        disp = df_fs[["name","partner_id","picking_type_id","state","scheduled_date","date_done","origin"]].copy()
        disp.columns = ["Ref","Partner","Type","Status","Scheduled","Done Date","Source"]
        disp["Status"] = disp["Status"].map({
            "done":"✅ Done","assigned":"📦 Ready","confirmed":"⏳ Confirmed",
            "waiting":"🕐 Waiting","draft":"📝 Draft","cancel":"❌ Cancelled"
        }).fillna(disp["Status"])
        disp["Scheduled"] = disp["Scheduled"].dt.strftime("%d %b %Y")
        disp["Done Date"] = disp["Done Date"].dt.strftime("%d %b %Y")
        st.dataframe(disp, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: HR
# ══════════════════════════════════════════════════════════════════════════════
elif page == "👨‍💼 HR & Employees":
    st.title("👨‍💼 HR & Employees")

    with st.spinner("Loading employees..."):
        emps = odoo("hr.employee","search_read",[],
            ["name","job_title","job_id","department_id","work_email",
             "work_phone","active","company_id"],
            limit=200)

    if emps:
        df = to_df(emps)

        c1,c2,c3 = st.columns(3)
        c1.metric("Total Employees", len(df))
        c2.metric("Departments", df["department_id"].nunique())
        c3.metric("Jobs", df["job_id"].nunique())

        col_a, col_b = st.columns(2)
        with col_a:
            dept_counts = df["department_id"].value_counts().head(10).reset_index()
            dept_counts.columns = ["Department","Count"]
            dept_counts["Department"] = dept_counts["Department"].apply(
                lambda x: x if isinstance(x, str) else "No Department")
            fig = px.bar(dept_counts, x="Department", y="Count",
                title="Employees by Department", color_discrete_sequence=["#4caf50"])
            fig.update_layout(height=300, xaxis_tickangle=-30)
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            job_counts = df["job_title"].value_counts().head(10).reset_index()
            job_counts.columns = ["Job Title","Count"]
            fig2 = px.pie(job_counts, names="Job Title", values="Count",
                title="Employees by Job Title", hole=0.4)
            fig2.update_layout(height=300)
            st.plotly_chart(fig2, use_container_width=True)

        search_e = st.text_input("🔍 Search employee", key="emp_search")
        df_f = df
        if search_e:
            df_f = df[df["name"].str.contains(search_e, case=False, na=False)]

        disp = df_f[["name","job_title","department_id","work_email","work_phone","company_id"]].copy()
        disp.columns = ["Name","Job Title","Department","Email","Phone","Company"]
        st.dataframe(disp, use_container_width=True, hide_index=True)

        # Time-off requests
        st.markdown('<div class="section-header">🏖️ Time-Off Requests</div>', unsafe_allow_html=True)
        with st.spinner("Loading time-off..."):
            leaves = odoo("hr.leave.allocation","search_read",[],
                ["employee_id","holiday_status_id","number_of_days","state","date_from"],
                limit=100)
        if leaves:
            df_l = to_df(leaves)
            st.dataframe(df_l[["employee_id","holiday_status_id","number_of_days","state"]],
                use_container_width=True, hide_index=True)
        else:
            st.info("No leave data accessible with current permissions.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: REPORTS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📊 Reports":
    st.title("📊 Reports & Analytics")

    report_type = st.selectbox("Select Report", [
        "Sales Performance",
        "Top Customers",
        "Top Products",
        "Inventory Valuation",
        "Invoice Aging",
        "Purchase Analysis",
    ])

    if report_type == "Sales Performance":
        with st.spinner("Loading..."):
            so = odoo("sale.order","search_read",
                [["state","in",["sale","done"]]],
                ["name","partner_id","amount_total","date_order","user_id"],
                limit=500, order="date_order desc")
        if so:
            df = to_df(so)
            df["date_order"] = pd.to_datetime(df["date_order"])
            df["month"] = df["date_order"].dt.to_period("M").astype(str)
            monthly = df.groupby("month").agg(
                orders=("name","count"), revenue=("amount_total","sum")).reset_index()
            monthly.columns = ["Month","Orders","Revenue (IDR)"]

            st.subheader("Monthly Sales Performance")
            fig = go.Figure()
            fig.add_trace(go.Bar(x=monthly["Month"], y=monthly["Revenue (IDR)"],
                name="Revenue", marker_color="#4caf50"))
            fig.add_trace(go.Scatter(x=monthly["Month"], y=monthly["Orders"],
                name="Orders", yaxis="y2", line=dict(color="#ff9800", width=3)))
            fig.update_layout(
                yaxis2=dict(overlaying="y", side="right"),
                height=400, legend=dict(x=0.01, y=0.99))
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(monthly, use_container_width=True, hide_index=True)

    elif report_type == "Top Customers":
        with st.spinner("Loading..."):
            so = odoo("sale.order","search_read",
                [["state","in",["sale","done"]]],
                ["partner_id","amount_total"], limit=500)
        if so:
            df = to_df(so)
            top = df.groupby("partner_id")["amount_total"].sum().nlargest(20).reset_index()
            top.columns = ["Customer","Total Revenue"]
            top["Total Revenue (IDR)"] = top["Total Revenue"].apply(fmt_idr)
            fig = px.bar(top, x="Total Revenue", y="Customer", orientation="h",
                title="Top 20 Customers by Revenue", color_discrete_sequence=["#388e3c"])
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(top[["Customer","Total Revenue (IDR)"]], use_container_width=True, hide_index=True)

    elif report_type == "Top Products":
        with st.spinner("Loading..."):
            lines = odoo("sale.order.line","search_read",
                [["order_id.state","in",["sale","done"]]],
                ["product_id","product_uom_qty","price_subtotal"],
                limit=1000)
        if lines:
            df = to_df(lines)
            top_p = df.groupby("product_id").agg(
                qty=("product_uom_qty","sum"),
                revenue=("price_subtotal","sum")).nlargest(20,"revenue").reset_index()
            top_p.columns = ["Product","Total Qty","Revenue"]
            top_p["Revenue (IDR)"] = top_p["Revenue"].apply(fmt_idr)
            fig = px.bar(top_p, x="Revenue", y="Product", orientation="h",
                title="Top 20 Products by Revenue", color_discrete_sequence=["#4caf50"])
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(top_p[["Product","Total Qty","Revenue (IDR)"]], use_container_width=True, hide_index=True)

    elif report_type == "Inventory Valuation":
        with st.spinner("Loading..."):
            quants = odoo("stock.quant","search_read",
                [["location_id.usage","=","internal"]],
                ["product_id","location_id","quantity","reserved_quantity"],
                limit=500)
        if quants:
            df = to_df(quants)
            df["available"] = (df["quantity"] - df["reserved_quantity"]).clip(lower=0)
            by_loc = df.groupby("location_id")[["quantity","reserved_quantity","available"]].sum().reset_index()
            by_loc.columns = ["Location","On Hand","Reserved","Available"]
            st.subheader("Stock by Location")
            fig = px.bar(by_loc, x="Location", y=["On Hand","Reserved","Available"],
                barmode="group", color_discrete_sequence=["#4caf50","#ff9800","#2196f3"])
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(by_loc, use_container_width=True, hide_index=True)

    elif report_type == "Invoice Aging":
        with st.spinner("Loading..."):
            inv = odoo("account.move","search_read",
                [["move_type","=","out_invoice"],["state","=","posted"],["payment_state","!=","paid"]],
                ["name","partner_id","amount_residual","invoice_date","invoice_date_due"],
                limit=300)
        if inv:
            df = to_df(inv)
            df["invoice_date_due"] = pd.to_datetime(df["invoice_date_due"], errors="coerce")
            today = pd.Timestamp.now()
            df["days_overdue"] = (today - df["invoice_date_due"]).dt.days

            def aging_bucket(d):
                if pd.isna(d): return "Unknown"
                if d <= 0: return "Current"
                if d <= 30: return "1-30 days"
                if d <= 60: return "31-60 days"
                if d <= 90: return "61-90 days"
                return "90+ days"

            df["Aging"] = df["days_overdue"].apply(aging_bucket)
            aging = df.groupby("Aging")["amount_residual"].sum().reset_index()
            aging.columns = ["Aging Bucket","Outstanding"]
            bucket_order = ["Current","1-30 days","31-60 days","61-90 days","90+ days","Unknown"]
            aging["Aging Bucket"] = pd.Categorical(aging["Aging Bucket"], categories=bucket_order, ordered=True)
            aging = aging.sort_values("Aging Bucket")

            fig = px.bar(aging, x="Aging Bucket", y="Outstanding",
                title="Invoice Aging Analysis", color="Aging Bucket",
                color_discrete_map={"Current":"#4caf50","1-30 days":"#8bc34a",
                    "31-60 days":"#ff9800","61-90 days":"#ff5722","90+ days":"#f44336"})
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
            aging["Outstanding"] = aging["Outstanding"].apply(fmt_idr)
            st.dataframe(aging, use_container_width=True, hide_index=True)

    elif report_type == "Purchase Analysis":
        with st.spinner("Loading..."):
            po = odoo("purchase.order","search_read",
                [["state","in",["purchase","done"]]],
                ["partner_id","amount_total","date_order"], limit=500)
        if po:
            df = to_df(po)
            df["date_order"] = pd.to_datetime(df["date_order"])
            df["month"] = df["date_order"].dt.to_period("M").astype(str)
            monthly = df.groupby("month")["amount_total"].sum().reset_index()
            monthly.columns = ["Month","Purchase Value"]
            fig = px.line(monthly, x="Month", y="Purchase Value", markers=True,
                title="Monthly Purchase Volume", color_discrete_sequence=["#f44336"])
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
            top_v = df.groupby("partner_id")["amount_total"].sum().nlargest(15).reset_index()
            top_v.columns = ["Vendor","Total Purchases"]
            top_v["Total Purchases (IDR)"] = top_v["Total Purchases"].apply(fmt_idr)
            st.subheader("Top Vendors by Purchase Value")
            st.dataframe(top_v[["Vendor","Total Purchases (IDR)"]], use_container_width=True, hide_index=True)

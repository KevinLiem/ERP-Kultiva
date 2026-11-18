import streamlit as st
from datetime import datetime

# Import sub-modules
from modules.dashboard import render_dashboard
from modules.sales import render_sales
from modules.purchasing import render_purchasing
from modules.inventory import render_inventory
from modules.deliveries import render_deliveries
from modules.settings import render_settings
from modules.reports import render_reports
from modules.other_modules import (
    render_invoicing, render_manufacturing, render_crm, render_hr
)

# ─── PAGE CONFIG ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Kultiva ERP",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#122912 0%,#1e4620 60%,#2d6a30 100%);
}
[data-testid="stSidebar"] * { color:#e8f5e9 !important; }
[data-testid="metric-container"] {
    background:#f1f8f1; border:1px solid #c8e6c9;
    border-radius:12px; padding:14px;
    box-shadow:0 2px 6px rgba(0,0,0,.07);
}
[data-testid="metric-container"] [data-testid="stMetricLabel"] {
    font-weight:700; color:#2e7d32 !important;
}
.kultiva-header {
    background:linear-gradient(135deg,#1b5e20 0%,#388e3c 60%,#66bb6a 100%);
    padding:18px 28px; border-radius:14px; margin-bottom:18px; color:white;
}
.kultiva-header h1 { color:white!important; margin:0; font-size:1.9rem; }
.kultiva-header p  { color:#c8e6c9!important; margin:4px 0 0; font-size:.95rem; }
.section-header {
    font-size:1.05rem; font-weight:700; color:#2e7d32;
    border-left:4px solid #4caf50; padding-left:10px; margin:18px 0 8px;
}
.surat-jalan {
    background:white; border:2px solid #333; border-radius:4px;
    padding:30px; font-family:'Courier New',monospace; font-size:.88rem;
}
</style>
""", unsafe_allow_html=True)

# ─── SESSION STATE INITIALIZATION ────────────────────────────────────────────
for k, v in {
    "so_lines": [], "po_lines": [],
    "page_so": "list", "page_po": "list",
    "edit_so_id": None, "edit_po_id": None,
    "sj_picking_id": None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── SIDEBAR NAVIGATION ──────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌱 Kultiva ERP")
    st.markdown("---")
    page = st.selectbox("Navigation", [
        "🏠 Dashboard",
        "📦 Sales Orders",
        "🧾 Invoicing",
        "🏭 Manufacturing",
        "📋 Inventory & Lots",
        "🛒 Purchasing",
        "👥 CRM / Accounts",
        "🚚 Deliveries & Surat Jalan",
        "👨‍💼 HR & Employees",
        "📊 Reports",
        "⚙️ Settings (Units & Conversions)",
    ])
    st.markdown("---")
    st.markdown("[Odoo ↗](https://kultiva.odoo.com)")
    st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

# ─── ROUTING ─────────────────────────────────────────────────────────────────
if page == "🏠 Dashboard":
    render_dashboard()
elif page == "📦 Sales Orders":
    render_sales()
elif page == "🧾 Invoicing":
    render_invoicing()
elif page == "🏭 Manufacturing":
    render_manufacturing()
elif page == "📋 Inventory & Lots":
    render_inventory()
elif page == "🛒 Purchasing":
    render_purchasing()
elif page == "👥 CRM / Accounts":
    render_crm()
elif page == "🚚 Deliveries & Surat Jalan":
    render_deliveries()
elif page == "👨‍💼 HR & Employees":
    render_hr()
elif page == "📊 Reports":
    render_reports()
elif page == "⚙️ Settings (Units & Conversions)":
    render_settings()

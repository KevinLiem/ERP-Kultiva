import xmlrpc.client
import streamlit as st
import pandas as pd
from datetime import datetime

ODOO_URL  = "https://kultiva.odoo.com"
ODOO_DB   = "kultiva"
ODOO_USER = "ppicjkt@kultivaco.com"
ODOO_KEY  = "e960e55aaa54b7c4d711d32c3eec857f9eb87407"

@st.cache_resource(show_spinner=False)
def get_client():
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_KEY, {})
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", allow_none=True)
    return uid, models

def odoo_call(model, method, args=None, kwargs=None):
    uid, models = get_client()
    if args is None: args = []
    if kwargs is None: kwargs = {}
    try:
        return models.execute_kw(ODOO_DB, uid, ODOO_KEY, model, method, args, kwargs)
    except Exception as e:
        st.error(f"Odoo error [{model}.{method}]: {e}")
        return None

def odoo_read(model, domain=None, fields=None, limit=1000, offset=0, order=None):
    if domain is None: domain = []
    kw = {"limit": limit, "offset": offset}
    if fields: kw["fields"] = fields
    if order:  kw["order"]  = order
    return odoo_call(model, "search_read", [domain], kw) or []

def odoo_count(model, domain=None):
    return odoo_call(model, "search_count", [domain or []]) or 0

def odoo_create(model, vals):
    return odoo_call(model, "create", [vals])

def odoo_write(model, ids, vals):
    if isinstance(ids, int): ids = [ids]
    return odoo_call(model, "write", [ids, vals])

def odoo_action(model, method, ids):
    if isinstance(ids, int): ids = [ids]
    return odoo_call(model, method, [ids])

def flatten_m2o(val):
    if isinstance(val, list) and len(val) == 2:
        return val[1]
    if val is False or val is None:
        return ""
    return val

def to_df(records):
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    for col in df.columns:
        df[col] = df[col].apply(lambda v: flatten_m2o(v) if isinstance(v, list) else v)
    return df

def fmt_idr(val):
    try: return f"Rp {float(val):,.0f}"
    except: return "Rp 0"

def fmt_num(val):
    try: return f"{float(val):,.2f}"
    except: return "0"

def status_badge(s):
    badges = {
        "draft":     "📝 Draft",
        "sent":      "📤 Sent",
        "sale":      "✅ Confirmed",
        "done":      "✔️ Done",
        "cancel":    "❌ Cancelled",
        "purchase":  "✅ Confirmed",
        "posted":    "✅ Posted",
        "confirmed": "✅ Confirmed",
        "progress":  "🔄 In Progress",
        "assigned":  "📦 Ready",
        "waiting":   "🕐 Waiting",
        "not_paid":  "⏳ Unpaid",
        "paid":      "✅ Paid",
        "in_payment":"🔄 In Payment",
        "partial":   "🟡 Partial",
    }
    return badges.get(str(s), str(s))

@st.cache_data(ttl=120, show_spinner=False)
def get_partners(customer=False, vendor=False):
    domain = []
    if customer: domain.append(["customer_rank",">",0])
    if vendor:   domain.append(["supplier_rank",">",0])
    recs = odoo_read("res.partner", domain, ["id","name","email","phone","is_company"], limit=500)
    return {r["name"]: r["id"] for r in recs}, recs

@st.cache_data(ttl=120, show_spinner=False)
def get_products():
    recs = odoo_read("product.product", [["active","=",True]],
        ["id","name","list_price","standard_price","uom_id","uom_po_id","type","categ_id","default_code"], limit=1000)
    return {r["name"]: r for r in recs}, recs

@st.cache_data(ttl=120, show_spinner=False)
def get_uoms():
    recs = odoo_read("uom.uom", [], ["id","name","category_id","factor","factor_inv","uom_type","active"], limit=200)
    return recs

@st.cache_data(ttl=120, show_spinner=False)
def get_warehouses():
    return odoo_read("stock.warehouse", [], ["id","name","code","lot_stock_id"], limit=20)

@st.cache_data(ttl=60, show_spinner=False)
def get_lots(product_id=None):
    domain = []
    if product_id:
        domain = [["product_id","=",product_id]]
    return odoo_read("stock.lot", domain,
        ["id","name","product_id","product_qty","expiration_date","company_id"], limit=500)

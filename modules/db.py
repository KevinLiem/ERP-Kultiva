import sqlite3
import pandas as pd
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "kultiva.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def db_query(query, params=None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        rows = [dict(r) for r in cur.fetchall()]
        return rows
    finally:
        conn.close()

def db_query_df(query, params=None):
    conn = get_connection()
    try:
        df = pd.read_sql_query(query, conn, params=params)
        return df
    finally:
        conn.close()

def db_execute(query, params=None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def db_count(table, where=""):
    conn = get_connection()
    try:
        cur = conn.cursor()
        q = f"SELECT COUNT(*) FROM {table}"
        if where:
            q += f" WHERE {where}"
        cur.execute(q)
        return cur.fetchone()[0]
    finally:
        conn.close()

# ─── FORMATTING HELPERS ──────────────────────────────────────────────────────
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

# ─── MASTER DATA FETCHERS ────────────────────────────────────────────────────
def get_partners(customer=False, vendor=False):
    conds = []
    if customer:
        conds.append("customer_rank > 0")
    if vendor:
        conds.append("supplier_rank > 0")
    where = (" WHERE " + " AND ".join(conds)) if conds else ""
    recs = db_query(f"SELECT * FROM partners{where} ORDER BY name ASC")
    return {r["name"]: r["id"] for r in recs}, recs

def get_products():
    recs = db_query("SELECT * FROM products WHERE active = 1 ORDER BY name ASC")
    return {r["name"]: r for r in recs}, recs

def get_uoms():
    return db_query("SELECT * FROM uoms WHERE active = 1 ORDER BY name ASC")

def get_warehouses():
    return db_query("SELECT * FROM warehouses ORDER BY name ASC")

def get_lots(product_id=None):
    if product_id:
        return db_query("SELECT * FROM stock_lots WHERE product_id = ? ORDER BY id DESC", (product_id,))
    return db_query("SELECT * FROM stock_lots ORDER BY id DESC LIMIT 500")

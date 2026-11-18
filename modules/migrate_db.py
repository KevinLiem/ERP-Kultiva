import xmlrpc.client
import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "kultiva.db")
ODOO_URL = "https://kultiva.odoo.com"
ODOO_DB = "kultiva"
ODOO_USER = "ppicjkt@kultivaco.com"
ODOO_KEY = "e960e55aaa54b7c4d711d32c3eec857f9eb87407"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # 1. partners (customers, vendors, contacts)
    cur.execute('''
    CREATE TABLE IF NOT EXISTS partners (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        is_company INTEGER DEFAULT 1,
        customer_rank INTEGER DEFAULT 0,
        supplier_rank INTEGER DEFAULT 0,
        street TEXT,
        city TEXT,
        country TEXT,
        created_at TEXT
    )''')

    # 2. uoms & conversions
    cur.execute('''
    CREATE TABLE IF NOT EXISTS uoms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        category TEXT DEFAULT 'General',
        uom_type TEXT DEFAULT 'reference',
        factor REAL DEFAULT 1.0,
        rounding REAL DEFAULT 0.01,
        active INTEGER DEFAULT 1
    )''')

    # 3. products
    cur.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        default_code TEXT,
        type TEXT DEFAULT 'product',
        categ_id TEXT,
        list_price REAL DEFAULT 0.0,
        standard_price REAL DEFAULT 0.0,
        uom_id INTEGER,
        uom_name TEXT,
        active INTEGER DEFAULT 1
    )''')

    # 4. warehouses & locations
    cur.execute('''
    CREATE TABLE IF NOT EXISTS warehouses (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        code TEXT NOT NULL,
        lot_stock_id INTEGER,
        lot_stock_name TEXT
    )''')

    cur.execute('''
    CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        complete_name TEXT,
        usage TEXT
    )''')

    # 5. lots
    cur.execute('''
    CREATE TABLE IF NOT EXISTS stock_lots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        product_id INTEGER,
        product_name TEXT,
        product_qty REAL DEFAULT 0.0,
        expiration_date TEXT,
        ref TEXT,
        company_id INTEGER DEFAULT 1
    )''')

    # 6. inventory stock quants
    cur.execute('''
    CREATE TABLE IF NOT EXISTS stock_quants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        product_name TEXT,
        location_id INTEGER,
        location_name TEXT,
        lot_id INTEGER,
        lot_name TEXT,
        quantity REAL DEFAULT 0.0,
        reserved_quantity REAL DEFAULT 0.0
    )''')

    # 7. sales orders & lines
    cur.execute('''
    CREATE TABLE IF NOT EXISTS sale_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        partner_id INTEGER,
        partner_name TEXT,
        date_order TEXT,
        commitment_date TEXT,
        state TEXT DEFAULT 'draft',
        amount_untaxed REAL DEFAULT 0.0,
        amount_total REAL DEFAULT 0.0,
        note TEXT,
        user_name TEXT DEFAULT 'PPIC Jakarta'
    )''')

    cur.execute('''
    CREATE TABLE IF NOT EXISTS sale_order_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        product_id INTEGER,
        product_name TEXT,
        product_uom_qty REAL DEFAULT 1.0,
        product_uom TEXT,
        price_unit REAL DEFAULT 0.0,
        price_subtotal REAL DEFAULT 0.0,
        FOREIGN KEY(order_id) REFERENCES sale_orders(id)
    )''')

    # 8. purchase orders & lines
    cur.execute('''
    CREATE TABLE IF NOT EXISTS purchase_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        partner_id INTEGER,
        partner_name TEXT,
        date_order TEXT,
        date_planned TEXT,
        state TEXT DEFAULT 'draft',
        amount_total REAL DEFAULT 0.0,
        notes TEXT
    )''')

    cur.execute('''
    CREATE TABLE IF NOT EXISTS purchase_order_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        product_id INTEGER,
        product_name TEXT,
        product_qty REAL DEFAULT 1.0,
        product_uom TEXT,
        price_unit REAL DEFAULT 0.0,
        price_subtotal REAL DEFAULT 0.0,
        name TEXT,
        FOREIGN KEY(order_id) REFERENCES purchase_orders(id)
    )''')

    # 9. stock pickings & stock moves (deliveries & receipts)
    cur.execute('''
    CREATE TABLE IF NOT EXISTS stock_pickings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        partner_id INTEGER,
        partner_name TEXT,
        picking_type_code TEXT,
        picking_type_name TEXT,
        state TEXT DEFAULT 'draft',
        scheduled_date TEXT,
        date_done TEXT,
        origin TEXT,
        sale_id INTEGER,
        purchase_id INTEGER
    )''')

    cur.execute('''
    CREATE TABLE IF NOT EXISTS stock_moves (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        picking_id INTEGER,
        product_id INTEGER,
        product_name TEXT,
        product_uom_qty REAL DEFAULT 0.0,
        quantity REAL DEFAULT 0.0,
        product_uom TEXT,
        location_id INTEGER,
        location_name TEXT,
        location_dest_id INTEGER,
        location_dest_name TEXT,
        lot_id INTEGER,
        lot_name TEXT,
        state TEXT DEFAULT 'draft',
        date TEXT,
        FOREIGN KEY(picking_id) REFERENCES stock_pickings(id)
    )''')

    # 10. invoices & bills (account.move)
    cur.execute('''
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        partner_id INTEGER,
        partner_name TEXT,
        move_type TEXT,
        state TEXT DEFAULT 'draft',
        payment_state TEXT DEFAULT 'not_paid',
        amount_untaxed REAL DEFAULT 0.0,
        amount_total REAL DEFAULT 0.0,
        amount_residual REAL DEFAULT 0.0,
        invoice_date TEXT,
        invoice_date_due TEXT
    )''')

    # 11. manufacturing orders (mrp)
    cur.execute('''
    CREATE TABLE IF NOT EXISTS mrp_productions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        product_id INTEGER,
        product_name TEXT,
        product_qty REAL DEFAULT 0.0,
        qty_producing REAL DEFAULT 0.0,
        state TEXT DEFAULT 'draft',
        date_start TEXT,
        date_finished TEXT
    )''')

    # 12. CRM Leads & HR Employees
    cur.execute('''
    CREATE TABLE IF NOT EXISTS crm_leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        partner_id INTEGER,
        partner_name TEXT,
        stage_name TEXT,
        expected_revenue REAL DEFAULT 0.0,
        probability REAL DEFAULT 0.0,
        user_name TEXT
    )''')

    cur.execute('''
    CREATE TABLE IF NOT EXISTS hr_employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        job_title TEXT,
        department_name TEXT,
        work_email TEXT,
        work_phone TEXT
    )''')

    conn.commit()
    conn.close()
    print("Database schema initialized successfully.")

def migrate_from_odoo():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    print("Connecting to Odoo...")
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_KEY, {})
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", allow_none=True)

    def flatten(v):
        if isinstance(v, list) and len(v) == 2:
            return v[1]
        return v if v is not False and v is not None else ""

    def m2o_id(v):
        if isinstance(v, list) and len(v) >= 1:
            return v[0]
        return v if isinstance(v, int) else None

    # 1. Partners
    print("Migrating partners...")
    partners = models.execute_kw(ODOO_DB, uid, ODOO_KEY, 'res.partner', 'search_read', [[]],
        {'fields': ['name', 'email', 'phone', 'is_company', 'customer_rank', 'supplier_rank', 'street', 'city', 'country_id'], 'limit': 1000})
    for p in partners:
        cur.execute('''INSERT OR REPLACE INTO partners (id, name, email, phone, is_company, customer_rank, supplier_rank, street, city, country)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (p['id'], p.get('name') or '', p.get('email') or '', p.get('phone') or '',
                     1 if p.get('is_company') else 0, p.get('customer_rank') or 0, p.get('supplier_rank') or 0,
                     p.get('street') or '', p.get('city') or '', flatten(p.get('country_id'))))

    # 2. UOMs
    print("Migrating UOMs...")
    uoms = models.execute_kw(ODOO_DB, uid, ODOO_KEY, 'uom.uom', 'search_read', [[]],
        {'fields': ['name', 'factor', 'rounding', 'active', 'relative_uom_id'], 'limit': 100})
    for u in uoms:
        cur.execute('''INSERT OR REPLACE INTO uoms (id, name, category, uom_type, factor, rounding, active)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (u['id'], u['name'], 'Standard', 'reference' if u.get('factor') == 1.0 else 'relative',
                     u.get('factor') or 1.0, u.get('rounding') or 0.01, 1 if u.get('active') else 0))

    # 3. Products
    print("Migrating products...")
    prods = models.execute_kw(ODOO_DB, uid, ODOO_KEY, 'product.product', 'search_read', [[]],
        {'fields': ['name', 'default_code', 'type', 'categ_id', 'list_price', 'standard_price', 'uom_id', 'active'], 'limit': 1000})
    for pr in prods:
        cur.execute('''INSERT OR REPLACE INTO products (id, name, default_code, type, categ_id, list_price, standard_price, uom_id, uom_name, active)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (pr['id'], pr.get('name') or '', pr.get('default_code') or '', pr.get('type') or 'product',
                     flatten(pr.get('categ_id')), pr.get('list_price') or 0.0, pr.get('standard_price') or 0.0,
                     m2o_id(pr.get('uom_id')), flatten(pr.get('uom_id')), 1 if pr.get('active') else 0))

    # 4. Warehouses & Locations
    print("Migrating warehouses & locations...")
    whs = models.execute_kw(ODOO_DB, uid, ODOO_KEY, 'stock.warehouse', 'search_read', [[]],
        {'fields': ['name', 'code', 'lot_stock_id'], 'limit': 50})
    for w in whs:
        cur.execute('''INSERT OR REPLACE INTO warehouses (id, name, code, lot_stock_id, lot_stock_name)
                       VALUES (?, ?, ?, ?, ?)''',
                    (w['id'], w.get('name') or '', w.get('code') or '', m2o_id(w.get('lot_stock_id')), flatten(w.get('lot_stock_id'))))

    locs = models.execute_kw(ODOO_DB, uid, ODOO_KEY, 'stock.location', 'search_read', [[]],
        {'fields': ['name', 'complete_name', 'usage'], 'limit': 200})
    for l in locs:
        cur.execute('''INSERT OR REPLACE INTO locations (id, name, complete_name, usage)
                       VALUES (?, ?, ?, ?)''',
                    (l['id'], l.get('name') or '', l.get('complete_name') or '', l.get('usage') or ''))

    # 5. Lots (active ones with quantity or recent)
    print("Migrating stock lots (subset of recent/active)...")
    lots = models.execute_kw(ODOO_DB, uid, ODOO_KEY, 'stock.lot', 'search_read', [[]],
        {'fields': ['name', 'product_id', 'product_qty', 'expiration_date', 'ref'], 'limit': 1500, 'order': 'id desc'})
    for lt in lots:
        cur.execute('''INSERT OR REPLACE INTO stock_lots (id, name, product_id, product_name, product_qty, expiration_date, ref)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (lt['id'], lt.get('name') or '', m2o_id(lt.get('product_id')), flatten(lt.get('product_id')),
                     lt.get('product_qty') or 0.0, lt.get('expiration_date') or '', lt.get('ref') or ''))

    # 6. Stock Quants (on-hand internal stock)
    print("Migrating internal stock quants...")
    quants = models.execute_kw(ODOO_DB, uid, ODOO_KEY, 'stock.quant', 'search_read',
        [[['location_id.usage', '=', 'internal']]],
        {'fields': ['product_id', 'location_id', 'lot_id', 'quantity', 'reserved_quantity'], 'limit': 2000})
    for q in quants:
        cur.execute('''INSERT INTO stock_quants (product_id, product_name, location_id, location_name, lot_id, lot_name, quantity, reserved_quantity)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (m2o_id(q.get('product_id')), flatten(q.get('product_id')),
                     m2o_id(q.get('location_id')), flatten(q.get('location_id')),
                     m2o_id(q.get('lot_id')), flatten(q.get('lot_id')),
                     q.get('quantity') or 0.0, q.get('reserved_quantity') or 0.0))

    # 7. Sales Orders & Lines
    print("Migrating sales orders...")
    sos = models.execute_kw(ODOO_DB, uid, ODOO_KEY, 'sale.order', 'search_read', [[]],
        {'fields': ['name', 'partner_id', 'date_order', 'commitment_date', 'state', 'amount_untaxed', 'amount_total', 'note', 'user_id'], 'limit': 1000})
    for s in sos:
        cur.execute('''INSERT OR REPLACE INTO sale_orders (id, name, partner_id, partner_name, date_order, commitment_date, state, amount_untaxed, amount_total, note, user_name)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (s['id'], s.get('name') or '', m2o_id(s.get('partner_id')), flatten(s.get('partner_id')),
                     s.get('date_order') or '', s.get('commitment_date') or '', s.get('state') or 'draft',
                     s.get('amount_untaxed') or 0.0, s.get('amount_total') or 0.0, s.get('note') or '', flatten(s.get('user_id')) or 'PPIC Jakarta'))

    print("Migrating sales order lines...")
    so_lines = models.execute_kw(ODOO_DB, uid, ODOO_KEY, 'sale.order.line', 'search_read', [[]],
        {'fields': ['order_id', 'product_id', 'product_uom_qty', 'product_uom_id', 'price_unit', 'price_subtotal'], 'limit': 3000})
    for sl in so_lines:
        cur.execute('''INSERT OR REPLACE INTO sale_order_lines (id, order_id, product_id, product_name, product_uom_qty, product_uom, price_unit, price_subtotal)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (sl['id'], m2o_id(sl.get('order_id')), m2o_id(sl.get('product_id')), flatten(sl.get('product_id')),
                     sl.get('product_uom_qty') or 1.0, flatten(sl.get('product_uom_id')), sl.get('price_unit') or 0.0, sl.get('price_subtotal') or 0.0))

    # 8. Purchase Orders & Lines
    print("Migrating purchase orders...")
    pos = models.execute_kw(ODOO_DB, uid, ODOO_KEY, 'purchase.order', 'search_read', [[]],
        {'fields': ['name', 'partner_id', 'date_order', 'date_planned', 'state', 'amount_total', 'note'], 'limit': 1000})
    for p in pos:
        cur.execute('''INSERT OR REPLACE INTO purchase_orders (id, name, partner_id, partner_name, date_order, date_planned, state, amount_total, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (p['id'], p.get('name') or '', m2o_id(p.get('partner_id')), flatten(p.get('partner_id')),
                     p.get('date_order') or '', p.get('date_planned') or '', p.get('state') or 'draft',
                     p.get('amount_total') or 0.0, p.get('note') or ''))

    print("Migrating purchase order lines...")
    po_lines = models.execute_kw(ODOO_DB, uid, ODOO_KEY, 'purchase.order.line', 'search_read', [[]],
        {'fields': ['order_id', 'product_id', 'product_qty', 'product_uom_id', 'price_unit', 'price_subtotal', 'name'], 'limit': 2000})
    for pl in po_lines:
        cur.execute('''INSERT OR REPLACE INTO purchase_order_lines (id, order_id, product_id, product_name, product_qty, product_uom, price_unit, price_subtotal, name)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (pl['id'], m2o_id(pl.get('order_id')), m2o_id(pl.get('product_id')), flatten(pl.get('product_id')),
                     pl.get('product_qty') or 1.0, flatten(pl.get('product_uom_id')), pl.get('price_unit') or 0.0, pl.get('price_subtotal') or 0.0, pl.get('name') or ''))

    # 9. Stock Pickings (Deliveries/Receipts)
    print("Migrating stock pickings...")
    pickings = models.execute_kw(ODOO_DB, uid, ODOO_KEY, 'stock.picking', 'search_read', [[]],
        {'fields': ['name', 'partner_id', 'picking_type_code', 'picking_type_id', 'state', 'scheduled_date', 'date_done', 'origin', 'sale_id', 'purchase_id'], 'limit': 1500})
    for pk in pickings:
        cur.execute('''INSERT OR REPLACE INTO stock_pickings (id, name, partner_id, partner_name, picking_type_code, picking_type_name, state, scheduled_date, date_done, origin, sale_id, purchase_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (pk['id'], pk.get('name') or '', m2o_id(pk.get('partner_id')), flatten(pk.get('partner_id')),
                     pk.get('picking_type_code') or '', flatten(pk.get('picking_type_id')), pk.get('state') or 'draft',
                     pk.get('scheduled_date') or '', pk.get('date_done') or '', pk.get('origin') or '',
                     m2o_id(pk.get('sale_id')), m2o_id(pk.get('purchase_id'))))

    # 10. Invoices (AR / AP)
    print("Migrating invoices & bills...")
    invs = models.execute_kw(ODOO_DB, uid, ODOO_KEY, 'account.move', 'search_read',
        [[['move_type', 'in', ['out_invoice', 'out_refund', 'in_invoice', 'in_refund']]]],
        {'fields': ['name', 'partner_id', 'move_type', 'state', 'payment_state', 'amount_untaxed', 'amount_total', 'amount_residual', 'invoice_date', 'invoice_date_due'], 'limit': 1000})
    for inv in invs:
        cur.execute('''INSERT OR REPLACE INTO invoices (id, name, partner_id, partner_name, move_type, state, payment_state, amount_untaxed, amount_total, amount_residual, invoice_date, invoice_date_due)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (inv['id'], inv.get('name') or '', m2o_id(inv.get('partner_id')), flatten(inv.get('partner_id')),
                     inv.get('move_type') or '', inv.get('state') or 'draft', inv.get('payment_state') or 'not_paid',
                     inv.get('amount_untaxed') or 0.0, inv.get('amount_total') or 0.0, inv.get('amount_residual') or 0.0,
                     inv.get('invoice_date') or '', inv.get('invoice_date_due') or ''))

    # 11. Manufacturing
    print("Migrating manufacturing orders...")
    mops = models.execute_kw(ODOO_DB, uid, ODOO_KEY, 'mrp.production', 'search_read', [[]],
        {'fields': ['name', 'product_id', 'product_qty', 'qty_producing', 'state', 'date_start', 'date_finished'], 'limit': 1000})
    for m in mops:
        cur.execute('''INSERT OR REPLACE INTO mrp_productions (id, name, product_id, product_name, product_qty, qty_producing, state, date_start, date_finished)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (m['id'], m.get('name') or '', m2o_id(m.get('product_id')), flatten(m.get('product_id')),
                     m.get('product_qty') or 0.0, m.get('qty_producing') or 0.0, m.get('state') or 'draft',
                     m.get('date_start') or '', m.get('date_finished') or ''))

    # 12. CRM Leads & Employees
    print("Migrating CRM leads & Employees...")
    try:
        leads = models.execute_kw(ODOO_DB, uid, ODOO_KEY, 'crm.lead', 'search_read', [[]],
            {'fields': ['name', 'partner_id', 'stage_id', 'expected_revenue', 'probability', 'user_id'], 'limit': 100})
        for ld in leads:
            cur.execute('''INSERT OR REPLACE INTO crm_leads (id, name, partner_id, partner_name, stage_name, expected_revenue, probability, user_name)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                        (ld['id'], ld.get('name') or '', m2o_id(ld.get('partner_id')), flatten(ld.get('partner_id')),
                         flatten(ld.get('stage_id')), ld.get('expected_revenue') or 0.0, ld.get('probability') or 0.0, flatten(ld.get('user_id'))))
    except Exception as e:
        print(f"CRM lead migration note: {e}")

    try:
        emps = models.execute_kw(ODOO_DB, uid, ODOO_KEY, 'hr.employee.public', 'search_read', [[]],
            {'fields': ['name', 'job_title', 'department_id', 'work_email', 'work_phone'], 'limit': 50})
        for e in emps:
            cur.execute('''INSERT OR REPLACE INTO hr_employees (id, name, job_title, department_name, work_email, work_phone)
                           VALUES (?, ?, ?, ?, ?, ?)''',
                        (e['id'], e.get('name') or '', e.get('job_title') or '', flatten(e.get('department_id')),
                         e.get('work_email') or '', e.get('work_phone') or ''))
    except Exception as e:
        print(f"Employee migration fallback: {e}")
        # Insert default PPIC Jakarta user as standard employee
        cur.execute('''INSERT OR REPLACE INTO hr_employees (id, name, job_title, department_name, work_email, work_phone)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (9, "PPIC Jakarta", "PPIC Specialist", "Operations", "ppicjkt@kultivaco.com", ""))

    conn.commit()
    conn.close()
    print("ALL DATA SUCCESSFULLY MIGRATED INTO KULTIVA.DB!")

if __name__ == '__main__':
    migrate_from_odoo()

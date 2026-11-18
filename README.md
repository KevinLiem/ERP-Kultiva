# Kultiva ERP 🌱

A real-time ERP dashboard for Kultiva, powered by Streamlit and connected live to Odoo 19 Enterprise.

## Features

| Module | Description |
|--------|-------------|
| 🏠 Dashboard | Live KPIs, revenue trends, top customers, recent orders |
| 📦 Sales | Full sales order management with filters and analytics |
| 🧾 Invoicing | Customer invoices + vendor bills, payment tracking |
| 🏭 Manufacturing | Manufacturing orders, production status |
| 📋 Inventory | Stock levels by location, product catalog, stock moves |
| 🛒 Purchasing | Purchase orders, vendor analysis |
| 👥 CRM / Accounts | Pipeline funnel, customers, vendors |
| 🚚 Deliveries | Outgoing/incoming deliveries, warehouse breakdown |
| 👨‍💼 HR | Employee directory, departments, time-off |
| 📊 Reports | Sales performance, invoice aging, top products/customers |

## Running Locally

```bash
pip install -r requirements.txt
streamlit run erp.py
```

## Deployment

Deployed via [Streamlit Community Cloud](https://share.streamlit.io).

> **Note:** Credentials are stored as Streamlit Secrets in production.

## Tech Stack
- **Frontend:** Streamlit 1.58
- **Charts:** Plotly
- **Data:** Odoo 19 Enterprise (XML-RPC API)
- **Language:** Python 3.14

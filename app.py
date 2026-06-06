import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# Set page configuration to wide layout
st.set_page_config(page_title="Customer Dues Review Portal", layout="wide")

EXCEL_FILE = "Customer Dues - Review File"
DB_FILE = "remarks_database.db"

# -------------------------------------------------------------------------
# DATABASE & DATA INITIALIZATION
# -------------------------------------------------------------------------
def init_db():
    """Create a database table to store sales team remarks if it doesn't exist."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS remarks (
            customer_id TEXT PRIMARY KEY,
            sales_remark TEXT,
            commitment_date TEXT,
            updated_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

@st.cache_data
def load_base_data():
    """Load core data from the Excel file starting from the correct row header."""
    # Row index 3 (4th row) contains the correct headers in your Excel sheet
    df = pd.read_excel(EXCEL_FILE, sheet_name="Review Data", header=3)
    # Filter out columns that are completely empty or unneeded
    df = df.dropna(subset=['Customer', 'Customer Name'])
    return df

def get_latest_remarks():
    """Fetch all saved remarks from the database."""
    conn = sqlite3.connect(DB_FILE)
    df_remarks = pd.read_sql_query("SELECT * FROM remarks", conn)
    conn.close()
    return df_remarks

def save_remark(cust_id, remark, date_str):
    """Save or update a remark and commitment date for a customer."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
        INSERT INTO remarks (customer_id, sales_remark, commitment_date, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(customer_id) DO UPDATE SET
            sales_remark=excluded.sales_remark,
            commitment_date=excluded.commitment_date,
            updated_at=excluded.updated_at
    ''', (cust_id, remark, date_str, now_str))
    conn.commit()
    conn.close()

# Initialize Database and Load Data
init_db()
df_base = load_base_data()
df_remarks = get_latest_remarks()

# Combine Excel Data with Live Database Remarks
df_merged = pd.merge(df_base, df_remarks, left_on='Customer', right_on='customer_id', how='left')

# -------------------------------------------------------------------------
# APPLICATION DASHBOARD & GRAPHS
# -------------------------------------------------------------------------
st.title("📊 Customer Dues Review Portal")
st.markdown("Welcome to the live review platform. Filter data, update remarks, and track commitments below.")

# High-Level Metrics Calculations
total_outstanding = df_merged['Total Outstanding'].sum()
total_due = df_merged['Due Amount'].sum()

# Identify Commitment Breaches
# Breach condition: Current Date > Commitment Date AND Due Amount > 0
today_str = datetime.today().strftime('%Y-%m-%d')
df_merged['commitment_date'] = pd.to_datetime(df_merged['commitment_date'], errors='coerce')
commitment_breaches = df_merged[
    (df_merged['commitment_date'].dt.strftime('%Y-%m-%d') < today_str) & 
    (df_merged['Due Amount'] > 0)
]

# Display Summary Cards
col1, col2, col3 = st.columns(3)
col1.metric("Total Outstanding Amt", f"₹ {total_outstanding:,.2f}")
col2.metric("Total Due Amt", f"₹ {total_due:,.2f}")
col3.metric("Commitment Breaches ⚠️", len(commitment_breaches))

# Chart Section
st.subheader("Regional Performance Analytics")
chart_data = df_merged.groupby('Region')[['Total Outstanding', 'Due Amount']].sum().reset_index()
st.bar_chart(chart_data, x='Region', y=['Total Outstanding', 'Due Amount'], color=["#2b5c8f", "#d9534f"])

# -------------------------------------------------------------------------
# LIVE SALES TEAM ENTRY INTERFACE
# -------------------------------------------------------------------------
st.divider()
st.subheader("✍️ Sales Team Feedback & Updates")

# Sidebar Filters
st.sidebar.header("Filter & Navigation")
all_regions = ["All Regions"] + list(df_merged['Region'].dropna().unique())
selected_region = st.sidebar.selectbox("Choose Your Region:", all_regions)

# Apply Region Filter
if selected_region != "All Regions":
    df_filtered = df_merged[df_merged['Region'] == selected_region]
else:
    df_filtered = df_merged

# Select Customer to update
customer_list = df_filtered.apply(lambda row: f"{row['Customer']} - {row['Customer Name']}", axis=1).tolist()

if customer_list:
    selected_cust_str = st.selectbox("Select Customer to Review/Update:", customer_list)
    selected_cust_id = selected_cust_str.split(" - ")[0]
    
    # Get the specific details for the selected customer
    cust_details = df_filtered[df_filtered['Customer'] == selected_cust_id].iloc[0]
    
    # Display Ageing Grid for the Customer
    st.markdown(f"### 🏢 Details for: **{cust_details['Customer Name']}**")
    
    ageing_col1, ageing_col2, ageing_col3, ageing_col4 = st.columns(4)
    ageing_col1.metric("0-15 Days Due", f"₹ {cust_details['0-15 Days']:,.2f}")
    ageing_col2.metric("16-30 Days Due", f"₹ {cust_details['16-30 Days']:,.2f}")
    ageing_col3.metric("31-90 Days Due", f"₹ {cust_details['31-90 Days']:,.2f}")
    ageing_col4.metric(">=90 Days Due", f"₹ {cust_details['>=90 Days']:,.2f}")

    # Entry Form for Remarks
    st.markdown("#### Submit New Update")
    existing_remark = cust_details['sales_remark'] if pd.notna(cust_details['sales_remark']) else ""
    existing_date = cust_details['commitment_date']
if pd.isna(existing_date) or isinstance(existing_date, str):
    existing_date = datetime.today()
    
    with st.form("remarks_form", clear_on_submit=False):
        new_remark = st.text_area("Review Remarks & Status Update:", value=existing_remark)
       new_date = st.date_input("New Commitment Date:", value=existing_date)
        submit_btn = st.form_submit_button("Save Update")
        
        if submit_btn:
            save_remark(selected_cust_id, new_remark, new_date.strftime('%Y-%m-%d'))
            st.success(f"Successfully updated record for {cust_details['Customer Name']}!")
            st.rerun()
else:
    st.info("No customers found matching this filter criteria.")

# -------------------------------------------------------------------------
# BREACH TRACKER DISPLAY TABLE
# -------------------------------------------------------------------------
st.divider()
st.subheader("⚠️ Live Commitment Breach Tracker")
if not commitment_breaches.empty:
    display_cols = ['Region', 'Customer', 'Customer Name', 'Due Amount', 'sales_remark', 'commitment_date']
    st.dataframe(
        commitment_breaches[display_cols].rename(columns={
            'sales_remark': 'Broken Remark',
            'commitment_date': 'Promised Date'
        }), 
        use_container_width=True
    )
else:
    st.success("Great job! No commitment breaches tracked today.")
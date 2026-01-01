# ========================================
# STOCK HEALTH MONITOR - With Add/Edit/Delete
# ========================================

import streamlit as st
import pandas as pd
from snowflake.snowpark.context import get_active_session
from datetime import date

# Get Snowflake session
session = get_active_session()

# ========================================
# PAGE CONFIGURATION
# ========================================
st.set_page_config(
    page_title="Stock Health Monitor",
    page_icon="🏥",
    layout="wide"
)

# ========================================
# SIDEBAR NAVIGATION
# ========================================
st.sidebar.title("📋 Menu")
page = st.sidebar.radio(
    "Choose Action:",
    ["📊 Dashboard", "➕ Add Entry", "✏️ Edit Entry", "🗑️ Delete Entry"],
    help="Select what you want to do"
)

st.sidebar.markdown("---")
st.sidebar.info("What would you like to do today'😊")

# ========================================
# PAGE 1: DASHBOARD (Original View)
# ========================================
if page == "📊 Dashboard":
    
    # HEADER
    st.title("🏥 Stock Health Monitor")
    st.markdown("### *AI-Powered Inventory Management for Healthcare*")
    st.markdown("---")
    
    # LOAD DATA
    @st.cache_data(ttl=600)
    def load_data():
        
        query = """
        SELECT 
            location, item, date, closing_stock, issued, avg_daily_usage,
            days_until_stockout, stock_status, suggested_reorder_qty,
            lead_time_days, reorder_level
        FROM stock_health_metrics
        WHERE date = (SELECT MAX(date) FROM stock_health_metrics)
        """
        return session.sql(query).to_pandas()
    
    with st.spinner("📊 Loading stock data..."):
        df = load_data()
        # ===============================
# FIX STOCK STATUS CALCULATION
# ===============================

# Prevent division by zero
    df["AVG_DAILY_USAGE"] = df["AVG_DAILY_USAGE"].replace(0, 0.01)

# Calculate days until stockout
    df["DAYS_UNTIL_STOCKOUT"] = (df["CLOSING_STOCK"] / df["AVG_DAILY_USAGE"]).round(1)

# Assign stock status correctly
    def classify_stock(row):
        if row["DAYS_UNTIL_STOCKOUT"] <= 2:
            return "CRITICAL"
        elif row["DAYS_UNTIL_STOCKOUT"] <= 5:
            return "WARNING"
        elif row["DAYS_UNTIL_STOCKOUT"] <= 10:
            return "HEALTHY"
        else:
            return "OVERSTOCK"

    df["STOCK_STATUS"] = df.apply(classify_stock, axis=1)

    
    if df.empty:
        st.error("⚠️ No data found! Make sure stock_health_metrics table exists.")
        st.stop()
    
    st.success(f"✅ Data loaded: {len(df)} items across {df['LOCATION'].nunique()} locations")
    
    # TOP METRICS
    st.markdown("## 📈 Key Metrics")
    col1, col2, col3, col4 = st.columns(4)
    
    critical_count = len(df[df['STOCK_STATUS'] == 'CRITICAL'])
    warning_count = len(df[df['STOCK_STATUS'] == 'WARNING'])
    healthy_count = len(df[df['STOCK_STATUS'] == 'HEALTHY'])
    overstock_count = len(df[df['STOCK_STATUS'] == 'OVERSTOCK'])
    
    col1.metric("🚨 Critical Items", critical_count, delta=f"{critical_count} urgent", delta_color="inverse")
    col2.metric("⚠️ Warning Items", warning_count)
    col3.metric("✅ Healthy Items", healthy_count)
    col4.metric("📦 Overstock Items", overstock_count)
    
    st.markdown("---")
    
    # HEATMAP
    st.markdown("## 🗺️ Stock Status Heatmap")
    st.markdown("*Days until stockout by location and item*")
    
    heatmap_data = df.pivot_table(
        index='ITEM', columns='LOCATION', values='DAYS_UNTIL_STOCKOUT', aggfunc='mean'
    )
    
    def color_days(val):
        if pd.isna(val):
            return ''
        elif val <= 2:
            return 'background-color: #ff6b6b; color: white; font-weight: bold'
        elif val <= 5:
            return 'background-color: #feca57; color: black; font-weight: bold'
        elif val <= 10:
            return 'background-color: #48dbfb; color: black'
        else:
            return 'background-color: #1dd1a1; color: white'
    
    styled_heatmap = heatmap_data.style.applymap(color_days).format("{:.1f}")
    st.dataframe(styled_heatmap, use_container_width=True, height=400)
    
    st.markdown("""
    **Color Legend:**
    - 🔴 **Red (0-2 days)**: Critical - Immediate action needed
    - 🟡 **Yellow (3-5 days)**: Warning - Order soon
    - 🔵 **Blue (6-10 days)**: Adequate - Monitor
    - 🟢 **Green (11+ days)**: Healthy stock levels
    """)
    
    st.markdown("---")
    
    # CRITICAL ALERTS
    st.markdown("## 🚨 Critical & Warning Alerts")
    
    alerts_df = df[df['STOCK_STATUS'].isin(['CRITICAL', 'WARNING'])].copy()
    alerts_df = alerts_df.sort_values('DAYS_UNTIL_STOCKOUT')
    
    if len(alerts_df) > 0:
        def highlight_status(row):
            if row['STOCK_STATUS'] == 'CRITICAL':
                return ['background-color: #ffcdd2'] * len(row)
            elif row['STOCK_STATUS'] == 'WARNING':
                return ['background-color: #fff9c4'] * len(row)
            return [''] * len(row)
        
        display_cols = ['LOCATION', 'ITEM', 'CLOSING_STOCK', 'AVG_DAILY_USAGE',
                       'DAYS_UNTIL_STOCKOUT', 'STOCK_STATUS', 'SUGGESTED_REORDER_QTY']
        
        styled_alerts = alerts_df[display_cols].style.apply(highlight_status, axis=1)
        st.dataframe(styled_alerts, use_container_width=True, height=400)
        
        st.markdown("### 📢 Top Priority Actions:")
        top_critical = alerts_df[alerts_df['STOCK_STATUS'] == 'CRITICAL'].head(3)
        
        if len(top_critical) > 0:
            for idx, row in top_critical.iterrows():
                st.error(f"""
                **🚨 {row['ITEM']}** at **{row['LOCATION']}**
                - ⏱️ Only **{row['DAYS_UNTIL_STOCKOUT']:.1f} days** remaining
                - 📦 Current stock: **{int(row['CLOSING_STOCK'])} units**
                - 📊 Daily usage: **{row['AVG_DAILY_USAGE']:.0f} units/day**
                - 🛒 **Suggested order: {int(row['SUGGESTED_REORDER_QTY'])} units**
                """)
    else:
        st.success("✅ No critical or warning items! All stock levels are healthy.")
    
    st.markdown("---")
    
    # REORDER LIST
    st.markdown("## 📋 Reorder Priority List")
    reorder_df = df[df['SUGGESTED_REORDER_QTY'] > 0].copy()
    reorder_df = reorder_df.sort_values('DAYS_UNTIL_STOCKOUT')
    
    if len(reorder_df) > 0:
        reorder_cols = ['LOCATION', 'ITEM', 'CLOSING_STOCK', 'LEAD_TIME_DAYS',
                       'DAYS_UNTIL_STOCKOUT', 'SUGGESTED_REORDER_QTY', 'STOCK_STATUS']
        
        st.dataframe(reorder_df[reorder_cols], use_container_width=True, height=300)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("📦 Items to Reorder", len(reorder_df))
        col2.metric("🔢 Total Units", f"{int(reorder_df['SUGGESTED_REORDER_QTY'].sum()):,}")
        col3.metric("🚨 Critical", len(reorder_df[reorder_df['STOCK_STATUS'] == 'CRITICAL']))
        
        csv = reorder_df[reorder_cols].to_csv(index=False)
        st.download_button(
            label="⬇️ Download Priority List as CSV",
            data=csv,
            file_name=f"reorder_list_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("✅ No reorders needed!")

# ========================================
# PAGE 2: ADD NEW ENTRY
# ========================================
elif page == "➕ Add Entry":
    
    st.title("➕ Add New Stock Entry")
    st.markdown("*Add a new daily stock record to the database*")
    st.markdown("---")
    
    with st.form("add_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            entry_date = st.date_input("📅 Date", value=date.today())
            location = st.text_input("📍 Location", placeholder="Hospital_Mumbai")
            item = st.text_input("💊 Item Name", placeholder="Insulin_Vials")
            opening_stock = st.number_input("📦 Opening Stock", min_value=0, value=0)
            received = st.number_input("📥 Received Today", min_value=0, value=0)
        
        with col2:
            issued = st.number_input("📤 Issued Today", min_value=0, value=0)
            closing_stock = opening_stock + received - issued
            st.metric("🔢 Closing Stock (Calculated)", closing_stock)
            lead_time = st.number_input("⏱️ Lead Time (Days)", min_value=1, value=7)
            reorder_level = st.number_input("🔄 Reorder Level", min_value=0, value=100)
        
        submitted = st.form_submit_button("✅ Add Entry", use_container_width=True)
        
        if submitted:
            if not location or not item:
                st.error("❌ Location and Item are required!")
            else:
                try:
                    insert_query = f"""
                    INSERT INTO daily_stock 
                    (DATE, LOCATION, ITEM, OPENING_STOCK, RECEIVED, ISSUED, 
                     CLOSING_STOCK, LEAD_TIME_DAYS, REORDER_LEVEL)
                    VALUES 
                    ('{entry_date}', '{location}', '{item}', {opening_stock}, 
                     {received}, {issued}, {closing_stock}, {lead_time}, {reorder_level})
                    """
                    session.sql(insert_query).collect()
                    
                    st.success(f"""
                    ✅ **Entry Added Successfully!**
                    - Date: {entry_date}
                    - Location: {location}
                    - Item: {item}
                    - Closing Stock: {closing_stock}
                    
                    💡 Dynamic Table will update within 1 min.
                    """)
                    st.balloons()
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

# ========================================
# PAGE 3: EDIT ENTRY
# ========================================
elif page == "✏️ Edit Entry":
    
    st.title("✏️ Edit Existing Entry")
    st.markdown("*Update stock quantities for an existing record*")
    st.markdown("---")
    
    # Load recent entries (using * to get all columns regardless of names)
    try:
        recent_query = "SELECT * FROM daily_stock ORDER BY date DESC LIMIT 50"
        recent_df = session.sql(recent_query).to_pandas()
        
        # Get actual column names
        col_names = list(recent_df.columns)
        st.info(f"📋 Columns found: {', '.join(col_names)}")
        
    except Exception as e:
        st.error(f"❌ Error loading data: {str(e)}")
        st.stop()
    
    if not recent_df.empty:
        # DEBUG: Show actual columns
        st.info(f"🔍 **Columns in daily_stock table:** {', '.join(recent_df.columns)}")
        
        # Get actual column names (case-insensitive mapping)
        cols = {col.upper(): col for col in recent_df.columns}
        
        # Map to expected columns with safe fallback
        date_col = cols.get('DATE', list(recent_df.columns)[0] if len(recent_df.columns) > 0 else 'DATE')
        location_col = cols.get('LOCATION', list(recent_df.columns)[1] if len(recent_df.columns) > 1 else 'LOCATION')
        item_col = cols.get('ITEM', list(recent_df.columns)[2] if len(recent_df.columns) > 2 else 'ITEM')
        opening_col = cols.get('OPENING_STOCK', list(recent_df.columns)[3] if len(recent_df.columns) > 3 else 'OPENING_STOCK')
        received_col = cols.get('RECEIVED', list(recent_df.columns)[4] if len(recent_df.columns) > 4 else 'RECEIVED')
        issued_col = cols.get('ISSUED', list(recent_df.columns)[5] if len(recent_df.columns) > 5 else 'ISSUED')
        closing_col = cols.get('CLOSING_STOCK', list(recent_df.columns)[6] if len(recent_df.columns) > 6 else 'CLOSING_STOCK')
        lead_col = cols.get('LEAD_TIME_DAYS', list(recent_df.columns)[7] if len(recent_df.columns) > 7 else 'LEAD_TIME_DAYS')
        reorder_col = cols.get('REORDER_LEVEL', list(recent_df.columns)[8] if len(recent_df.columns) > 8 else 'REORDER_LEVEL')
        
        st.success(f"✅ **Using columns:** Date={date_col}, Location={location_col}, Item={item_col}, Received={received_col}")
        
        st.subheader("Step 1: Select Entry to Edit")
        
        recent_df['display'] = (
            recent_df[date_col].astype(str) + " | " + 
            recent_df[location_col] + " | " + 
            recent_df[item_col]
        )
        
        selected = st.selectbox("Choose entry:", recent_df['display'].tolist())
        selected_row = recent_df[recent_df['display'] == selected].iloc[0]
        
        st.markdown("---")
        st.subheader("Step 2: Update Values")
        
        with st.form("edit_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"**📅 Date:** {selected_row[date_col]}")
                st.markdown(f"**📍 Location:** {selected_row[location_col]}")
                st.markdown(f"**💊 Item:** {selected_row[item_col]}")
                
                new_opening = st.number_input("Opening Stock", 
                    value=int(selected_row[opening_col]), min_value=0)
                new_received = st.number_input("Received", 
                    value=int(selected_row[received_col]), min_value=0)
            
            with col2:
                new_issued = st.number_input("Issued", 
                    value=int(selected_row[issued_col]), min_value=0)
                new_closing = new_opening + new_received - new_issued
                st.metric("New Closing Stock", new_closing)
                new_lead = st.number_input("Lead Time", 
                    value=int(selected_row[lead_col]), min_value=1)
                new_reorder = st.number_input("Reorder Level", 
                    value=int(selected_row[reorder_col]), min_value=0)
            
            update_btn = st.form_submit_button("💾 Update Entry", use_container_width=True)
            
            if update_btn:
                try:
                    # Use actual column names from the table
                    update_query = f"""
                    UPDATE daily_stock
                    SET {opening_col} = {new_opening},
                        {received_col} = {new_received},
                        {issued_col} = {new_issued},
                        {closing_col} = {new_closing},
                        {lead_col} = {new_lead},
                        {reorder_col} = {new_reorder}
                    WHERE {date_col} = '{selected_row[date_col]}'
                      AND {location_col} = '{selected_row[location_col]}'
                      AND {item_col} = '{selected_row[item_col]}'
                    """
                    session.sql(update_query).collect()
                    
                    st.success("✅ Entry updated! Dynamic Table will refresh within 1 min.")
                    st.balloons()
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
    else:
        st.warning("No entries found!")

# ========================================
# PAGE 4: DELETE ENTRY
# ========================================
elif page == "🗑️ Delete Entry":
    
    st.title("🗑️ Delete Entry")
    st.markdown("*Remove a stock record from the database*")
    st.warning("⚠️ **Warning:** Deletion is permanent!")
    st.markdown("---")
    
    delete_query = """
    SELECT DATE, LOCATION, ITEM, CLOSING_STOCK
    FROM daily_stock
    ORDER BY DATE DESC, LOCATION, ITEM
    LIMIT 50
    """
    delete_df = session.sql(delete_query).to_pandas()
    
    if not delete_df.empty:
        # Get actual column names
        cols = {col.upper(): col for col in delete_df.columns}
        date_col = cols.get('DATE', 'DATE')
        location_col = cols.get('LOCATION', 'LOCATION')
        item_col = cols.get('ITEM', 'ITEM')
        closing_col = cols.get('CLOSING_STOCK', 'CLOSING_STOCK')
        
        delete_df['display'] = (
            delete_df[date_col].astype(str) + " | " +
            delete_df[location_col] + " | " +
            delete_df[item_col] + " | Stock: " +
            delete_df[closing_col].astype(str)
        )
        
        selected_delete = st.selectbox("Select entry to delete:", delete_df['display'].tolist())
        delete_row = delete_df[delete_df['display'] == selected_delete].iloc[0]
        
        st.markdown("### Entry to be deleted:")
        col1, col2, col3, col4 = st.columns(4)
        col1.markdown(f"**Date:** {delete_row[date_col]}")
        col2.markdown(f"**Location:** {delete_row[location_col]}")
        col3.markdown(f"**Item:** {delete_row[item_col]}")
        col4.markdown(f"**Stock:** {delete_row[closing_col]}")
        
        st.markdown("---")
        
        confirm = st.checkbox("⚠️ I understand this cannot be undone")
        
        if st.button("🗑️ Delete Entry", type="primary", disabled=not confirm):
            try:
                delete_sql = f"""
                DELETE FROM daily_stock
                WHERE {date_col} = '{delete_row[date_col]}'
                  AND {location_col} = '{delete_row[location_col]}'
                  AND {item_col} = '{delete_row[item_col]}'
                """
                session.sql(delete_sql).collect()
                
                st.success("✅ Entry deleted! Dynamic Table will update within 1 min.")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    else:
        st.warning("No entries found!")

# ========================================
# FOOTER (All Pages)
# ========================================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 1rem;'>
    <p><b>🏥 Stock Health Monitor</b> - AI for Good Hackathon 2025</p>
    <p><i>Built with Snowflake & Streamlit</i></p>
    <p>Build With ❤️ By-<b>NEEL SAXENA</b><p>
</div>
""", unsafe_allow_html=True)

# ========================================
# CUSTOM UI STYLING
# ========================================
st.markdown("""
<style>

/* ---- MAIN APP BACKGROUND ---- */
.stApp {
    background-color: #f6f8fb;
    color: #1f2933;
}

/* ---- SIDEBAR ---- */
[data-testid="stSidebar"] {
    background-color: #1e293b;
    color: white;
}

[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label {
    color: #ffffff !important;
}

/* ---- HEADINGS ---- */
h1 {
    color: #1e3a8a;
    font-weight: 700;
}
h2 {
    color: #1d4ed8;
}
h3 {
    color: #2563eb;
}

/* ---- METRIC CARDS ---- */
[data-testid="stMetric"] {
    background-color: #ffffff;
    padding: 12px;
    border-radius: 10px;
    box-shadow: 0px 2px 6px rgba(0,0,0,0.08);
}

/* ---- DATAFRAMES ---- */
.stDataFrame {
    background-color: white;
    border-radius: 8px;
}

/* ---- BUTTONS ---- */
.stButton>button {
    background-color: #2563eb;
    color: white;
    border-radius: 8px;
    padding: 0.6rem 1.2rem;
    font-weight: 600;
    border: none;
}

.stButton>button:hover {
    background-color: #1d4ed8;
}

/* ---- SUCCESS / ERROR BOXES ---- */
.stAlert {
    border-radius: 8px;
}

</style>
""", unsafe_allow_html=True)
